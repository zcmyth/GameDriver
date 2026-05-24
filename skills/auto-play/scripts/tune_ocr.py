#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml
from PIL import Image


@dataclass(frozen=True)
class Button:
    label: str
    x: float
    y: float
    confidence: float
    clickability: float
    source: str
    score: float = 0.0
    reason: str = ''
    template_path: str = ''


@dataclass(frozen=True)
class MatchResult:
    captured: bool
    reason: str
    matched_button: Button | None
    label_similarity: float
    coordinate_distance: float | None


@dataclass(frozen=True)
class TurnScore:
    turn: str
    screenshot: Path
    target: Button
    ocr_buttons: list[Button]
    match: MatchResult
    decision_status: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def local_root() -> Path:
    return skill_root()


def games_root() -> Path:
    return local_root() / 'games'


def ensure_script_imports() -> None:
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def slugify(value: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', value.strip().lower()).strip('-')
    return slug or 'default-game'


def game_root_for(game: str) -> Path:
    return games_root() / slugify(game)


def template_images_dir_for(game: str) -> Path:
    return game_root_for(game) / 'images'


def normalize_label(value: str) -> str:
    value = str(value or '').lower()
    value = re.sub(r'[^a-z0-9\u4e00-\u9fff]+', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def label_similarity(left: str, right: str) -> float:
    left_norm = normalize_label(left)
    right_norm = normalize_label(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    base = SequenceMatcher(None, left_norm, right_norm).ratio()
    if len(left_norm) >= 3 and len(right_norm) >= 3:
        if left_norm in right_norm or right_norm in left_norm:
            return max(base, 0.86)
    return base


def button_from_data(data: dict[str, Any], *, fallback_source: str) -> Button | None:
    label = str(data.get('label') or data.get('text') or '').strip()
    if not label:
        return None
    try:
        x = float(data.get('x'))
        y = float(data.get('y'))
    except (TypeError, ValueError):
        return None
    return Button(
        label=label,
        x=max(0.0, min(1.0, x)),
        y=max(0.0, min(1.0, y)),
        confidence=float(data.get('confidence', 0.0) or 0.0),
        clickability=float(data.get('clickability', 0.0) or 0.0),
        source=str(data.get('source') or fallback_source),
        score=float(data.get('score', 0.0) or 0.0),
        reason=str(data.get('reason') or ''),
        template_path=str(data.get('template_path') or ''),
    )


def button_to_data(button: Button) -> dict[str, Any]:
    data = {
        'label': button.label,
        'x': round(button.x, 6),
        'y': round(button.y, 6),
        'confidence': round(button.confidence, 6),
        'clickability': round(button.clickability, 6),
        'source': button.source,
        'score': round(button.score, 6),
    }
    if button.reason:
        data['reason'] = button.reason
    if button.template_path:
        data['template_path'] = button.template_path
    return data


def coordinate_distance(left: Button, right: Button) -> float:
    return math.dist((left.x, left.y), (right.x, right.y))


def match_target(
    target: Button,
    candidates: list[Button],
    *,
    label_threshold: float,
    coord_tolerance: float,
) -> MatchResult:
    best_button = None
    best_label = 0.0
    best_distance = None
    for candidate in candidates:
        similarity = label_similarity(target.label, candidate.label)
        distance = coordinate_distance(target, candidate)
        better = False
        if best_button is None:
            better = True
        elif similarity > best_label:
            better = True
        elif similarity == best_label and (
            best_distance is None or distance < best_distance
        ):
            better = True
        if better:
            best_button = candidate
            best_label = similarity
            best_distance = distance

    if best_button is None:
        return MatchResult(
            captured=False,
            reason='no_ocr_buttons',
            matched_button=None,
            label_similarity=0.0,
            coordinate_distance=None,
        )

    label_hit = best_label >= label_threshold
    coordinate_hit = best_distance is not None and best_distance <= coord_tolerance
    if label_hit and coordinate_hit:
        reason = 'label_and_coordinate'
    elif label_hit:
        reason = 'label'
    elif coordinate_hit:
        reason = 'coordinate'
    else:
        reason = 'miss'

    return MatchResult(
        captured=label_hit or coordinate_hit,
        reason=reason,
        matched_button=best_button,
        label_similarity=best_label,
        coordinate_distance=best_distance,
    )


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text()) or {}


def target_for_turn(
    ocr_payload: dict[str, Any],
    metadata_payload: dict[str, Any],
    *,
    statuses: set[str],
) -> Button | None:
    decision = ocr_payload.get('decision') or {}
    status = str(decision.get('status') or 'unknown')
    if status not in statuses:
        return None

    action = ((metadata_payload.get('worklog') or {}).get('action_taken')) or None
    if action:
        return button_from_data(action, fallback_source='action')

    recommended = decision.get('recommended')
    if isinstance(recommended, dict):
        return button_from_data(recommended, fallback_source='recommended')

    return None


def buttons_from_saved_ocr(payload: dict[str, Any]) -> list[Button]:
    buttons = []
    for item in payload.get('ocr_buttons') or []:
        if button := button_from_data(item, fallback_source='ocr'):
            buttons.append(button)
    for item in payload.get('template_buttons') or []:
        if button := button_from_data(item, fallback_source='template'):
            buttons.append(button)
    return buttons


def create_analyzer(args: argparse.Namespace):
    ensure_script_imports()

    from image_analyzer import create_analyzer as create

    template_dirs = []
    if not args.disable_template_matching:
        template_dirs.append(template_images_dir_for(args.game))
    return create(
        template_dirs=template_dirs,
        template_match_threshold=args.template_match_threshold,
    )


def regenerate_ocr_buttons(
    analyzer: Any,
    screenshot: Path,
    *,
    confidence: float,
) -> list[Button]:
    image = Image.open(screenshot).convert('RGB')
    raw_locations = analyzer.extract_text_locations(
        image,
        confidence_threshold=confidence,
    )
    buttons = []
    for item in raw_locations:
        label = str(item.get('text') or '').strip()
        if not label:
            continue
        buttons.append(
            Button(
                label=label,
                x=float(item.get('x', 0.0) or 0.0),
                y=float(item.get('y', 0.0) or 0.0),
                confidence=float(item.get('confidence', 0.0) or 0.0),
                clickability=float(item.get('clickability', 0.0) or 0.0),
                source=str(item.get('source') or 'ocr'),
                template_path=str(item.get('template_path') or ''),
            )
        )
    return buttons


def write_generated_turn_yaml(
    path: Path,
    *,
    turn_score: TurnScore,
    original_payload: dict[str, Any],
) -> None:
    match = turn_score.match
    payload = {
        'turn': turn_score.turn,
        'game': original_payload.get('game'),
        'screenshot': str(turn_score.screenshot),
        'target_action': button_to_data(turn_score.target),
        'ocr_buttons': [button_to_data(button) for button in turn_score.ocr_buttons],
        'capture': {
            'captured': match.captured,
            'reason': match.reason,
            'label_similarity': round(match.label_similarity, 6),
            'coordinate_distance': (
                round(match.coordinate_distance, 6)
                if match.coordinate_distance is not None
                else None
            ),
            'matched_button': (
                button_to_data(match.matched_button) if match.matched_button else None
            ),
        },
        'original_decision': {
            'status': turn_score.decision_status,
            'recommended': original_payload.get('decision', {}).get('recommended'),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    )


def discover_turns(turns_dir: Path, game: str | None) -> list[Path]:
    if not turns_dir.exists():
        return []
    turn_dirs = sorted(path for path in turns_dir.iterdir() if path.is_dir())
    if not game:
        return turn_dirs
    suffix = f'-{slugify(game)}'
    return [path for path in turn_dirs if path.name.endswith(suffix)]


def score_turns(args: argparse.Namespace, run_dir: Path) -> list[TurnScore]:
    statuses = {'ready'}
    if args.include_needs_user_choice:
        statuses.add('needs_user_choice')

    analyzer = create_analyzer(args) if args.mode == 'regenerate' else None
    turn_scores: list[TurnScore] = []

    for index, turn_dir in enumerate(discover_turns(args.turns_dir, args.game)):
        if args.max_turns and index >= args.max_turns:
            break

        ocr_path = turn_dir / 'ocr.yaml'
        metadata_path = turn_dir / 'metadata.yaml'
        screenshot = turn_dir / 'screenshot.png'
        if (
            not ocr_path.exists()
            or not metadata_path.exists()
            or not screenshot.exists()
        ):
            continue

        ocr_payload = read_yaml(ocr_path)
        metadata_payload = read_yaml(metadata_path)
        target = target_for_turn(
            ocr_payload,
            metadata_payload,
            statuses=statuses,
        )
        if target is None:
            continue

        if analyzer is None:
            ocr_buttons = buttons_from_saved_ocr(ocr_payload)
        else:
            ocr_buttons = regenerate_ocr_buttons(
                analyzer,
                screenshot,
                confidence=args.confidence,
            )

        match = match_target(
            target,
            ocr_buttons,
            label_threshold=args.label_threshold,
            coord_tolerance=args.coord_tolerance,
        )
        turn_score = TurnScore(
            turn=turn_dir.name,
            screenshot=screenshot,
            target=target,
            ocr_buttons=ocr_buttons,
            match=match,
            decision_status=str((ocr_payload.get('decision') or {}).get('status')),
        )
        turn_scores.append(turn_score)
        write_generated_turn_yaml(
            run_dir / 'turns' / turn_dir.name / 'ocr.yaml',
            turn_score=turn_score,
            original_payload=ocr_payload,
        )

    return turn_scores


def classify_missing(turn_score: TurnScore, coord_tolerance: float) -> str:
    if not turn_score.ocr_buttons:
        return 'no OCR text survived filtering'
    nearest = min(
        turn_score.ocr_buttons,
        key=lambda button: coordinate_distance(turn_score.target, button),
    )
    distance = coordinate_distance(turn_score.target, nearest)
    if distance <= coord_tolerance * 2:
        return f'near action but wrong text: {nearest.label}'
    return 'no OCR text near target action'


def build_report(
    *,
    args: argparse.Namespace,
    run_dir: Path,
    turn_scores: list[TurnScore],
) -> tuple[dict[str, Any], str]:
    captured = [score for score in turn_scores if score.match.captured]
    missing = [score for score in turn_scores if not score.match.captured]
    ready_count = len(turn_scores)
    capture_rate = (len(captured) / ready_count) if ready_count else 0.0

    missing_by_label = Counter(score.target.label for score in missing)
    missing_by_symptom = Counter(
        classify_missing(score, args.coord_tolerance) for score in missing
    )
    captured_by_reason = Counter(score.match.reason for score in captured)
    source_counts = Counter(score.target.source for score in turn_scores)

    examples_by_label: dict[str, list[TurnScore]] = defaultdict(list)
    for score in missing:
        examples_by_label[score.target.label].append(score)

    top_missing = []
    for label, count in missing_by_label.most_common(args.example_labels):
        examples = examples_by_label[label][: args.examples_per_label]
        top_missing.append(
            {
                'label': label,
                'missing_count': count,
                'examples': [
                    {
                        'turn': example.turn,
                        'screenshot': str(example.screenshot),
                        'target': button_to_data(example.target),
                        'best_match': (
                            button_to_data(example.match.matched_button)
                            if example.match.matched_button
                            else None
                        ),
                        'match_reason': example.match.reason,
                        'ocr_labels': [button.label for button in example.ocr_buttons],
                    }
                    for example in examples
                ],
            }
        )

    report = {
        'run_dir': str(run_dir),
        'mode': args.mode,
        'game': args.game,
        'turns_dir': str(args.turns_dir),
        'template_images_dir': str(template_images_dir_for(args.game)),
        'template_matching_enabled': not args.disable_template_matching,
        'template_match_threshold': args.template_match_threshold,
        'template_image_count': len(
            list(template_images_dir_for(args.game).glob('*.png'))
        )
        if template_images_dir_for(args.game).exists()
        else 0,
        'confidence': args.confidence,
        'label_threshold': args.label_threshold,
        'coord_tolerance': args.coord_tolerance,
        'ready_actions': ready_count,
        'ready_actions_captured_by_ocr': len(captured),
        'ready_actions_missing_from_ocr': len(missing),
        'capture_rate': capture_rate,
        'target_source_counts': dict(source_counts),
        'captured_by_reason': dict(captured_by_reason),
        'missing_by_label': dict(missing_by_label),
        'missing_by_symptom': dict(missing_by_symptom),
        'top_missing': top_missing,
    }
    add_baseline_comparison(report, args=args)

    markdown = render_markdown_summary(report, args=args, run_dir=run_dir)
    return report, markdown


def add_baseline_comparison(
    report: dict[str, Any],
    *,
    args: argparse.Namespace,
) -> None:
    if args.baseline_report is None:
        return

    baseline = read_yaml(args.baseline_report)
    baseline_ready = int(baseline.get('ready_actions', 0) or 0)
    baseline_captured = int(baseline.get('ready_actions_captured_by_ocr', 0) or 0)
    baseline_rate = float(baseline.get('capture_rate', 0.0) or 0.0)
    current_ready = int(report.get('ready_actions', 0) or 0)
    current_captured = int(report.get('ready_actions_captured_by_ocr', 0) or 0)
    current_rate = float(report.get('capture_rate', 0.0) or 0.0)

    captured_delta = current_captured - baseline_captured
    ready_delta = current_ready - baseline_ready
    rate_delta = current_rate - baseline_rate

    if ready_delta == 0:
        improved = captured_delta >= args.minimum_captured_delta
        regressed = captured_delta < 0
    else:
        improved = rate_delta > 0 and captured_delta >= args.minimum_captured_delta
        regressed = rate_delta < 0 or captured_delta < 0

    if improved:
        verdict = 'improved'
    elif regressed:
        verdict = 'regressed'
    else:
        verdict = 'unchanged'

    report['comparison'] = {
        'baseline_report': str(args.baseline_report),
        'baseline_ready_actions': baseline_ready,
        'baseline_ready_actions_captured_by_ocr': baseline_captured,
        'baseline_capture_rate': baseline_rate,
        'current_ready_actions': current_ready,
        'current_ready_actions_captured_by_ocr': current_captured,
        'current_capture_rate': current_rate,
        'ready_actions_delta': ready_delta,
        'captured_delta': captured_delta,
        'capture_rate_delta': rate_delta,
        'minimum_captured_delta': args.minimum_captured_delta,
        'verdict': verdict,
    }


def render_markdown_summary(
    report: dict[str, Any],
    *,
    args: argparse.Namespace,
    run_dir: Path,
) -> str:
    ready = report['ready_actions']
    captured = report['ready_actions_captured_by_ocr']
    missing = report['ready_actions_missing_from_ocr']
    capture_rate = report['capture_rate'] * 100

    lines = [
        '# OCR Tuning Report',
        '',
        f'- Game: `{args.game or "all"}`',
        f'- Mode: `{args.mode}`',
        f'- Ready actions captured from OCR: `{captured} / {ready}` '
        f'(`{capture_rate:.1f}%`)',
        f'- Missing ready actions: `{missing}`',
        f'- Template images: `{report["template_image_count"]}` in '
        f'`{report["template_images_dir"]}`',
        f'- Generated per-turn OCR YAML: `{run_dir / "turns"}`',
        '',
    ]
    if comparison := report.get('comparison'):
        baseline_captured = comparison['baseline_ready_actions_captured_by_ocr']
        baseline_ready = comparison['baseline_ready_actions']
        baseline_rate = comparison['baseline_capture_rate'] * 100
        rate_delta = comparison['capture_rate_delta'] * 100
        lines.extend(
            [
                '## Comparison',
                '',
                f'- Baseline: `{baseline_captured} / {baseline_ready}` '
                f'(`{baseline_rate:.1f}%`)',
                f'- Captured delta: `{comparison["captured_delta"]}`',
                f'- Capture-rate delta: `{rate_delta:.1f}%`',
                f'- Verdict: `{comparison["verdict"]}`',
                '',
            ]
        )

    lines.extend(['## Missing Summary', ''])
    if report['missing_by_label']:
        for label, count in list(report['missing_by_label'].items())[
            : args.example_labels
        ]:
            lines.append(f'- `{label}`: {count}')
    else:
        lines.append('- No missing actionable labels in this run.')

    lines.extend(['', '## Symptoms', ''])
    if report['missing_by_symptom']:
        for symptom, count in report['missing_by_symptom'].items():
            lines.append(f'- {symptom}: {count}')
    else:
        lines.append('- No missing symptoms.')

    lines.extend(['', '## Examples', ''])
    for group in report['top_missing']:
        lines.append(f'### {group["label"]} ({group["missing_count"]})')
        for example in group['examples']:
            target = example['target']
            lines.append(
                f'- `{example["turn"]}` target `{target["label"]}` at '
                f'`{target["x"]:.3f}, {target["y"]:.3f}`'
            )
            lines.append(f'  screenshot: `{example["screenshot"]}`')
            if example['best_match']:
                best = example['best_match']
                lines.append(
                    f'  best OCR: `{best["label"]}` at '
                    f'`{best["x"]:.3f}, {best["y"]:.3f}` '
                    f'({example["match_reason"]})'
                )
            else:
                lines.append('  best OCR: none')
            labels = ', '.join(example['ocr_labels'][:8]) or 'none'
            lines.append(f'  OCR labels: {labels}')
        lines.append('')

    prompt = build_llm_code_change_prompt(report, args=args, run_dir=run_dir)
    lines.extend(['## LLM Code Change Prompt', '', '```text', prompt, '```', ''])
    return '\n'.join(lines)


def build_llm_code_change_prompt(
    report: dict[str, Any],
    *,
    args: argparse.Namespace,
    run_dir: Path,
) -> str:
    command = (
        'uv --directory skills/auto-play run python scripts/tune_ocr.py '
        f'--game {args.game} --mode regenerate'
    )
    if args.confidence != 0.8:
        command += f' --confidence {args.confidence}'
    if args.template_match_threshold != 0.82:
        command += f' --template-match-threshold {args.template_match_threshold}'
    if args.disable_template_matching:
        command += ' --disable-template-matching'
    if args.baseline_report is not None:
        command += f' --baseline-report {args.baseline_report}'
        command += ' --fail-unless-improved'

    missing_lines = []
    for group in report['top_missing']:
        examples = '; '.join(
            (
                f'{example["turn"]} target={example["target"]["label"]} '
                f'at {example["target"]["x"]:.3f},{example["target"]["y"]:.3f}'
            )
            for example in group['examples']
        )
        missing_lines.append(
            f'- {group["label"]}: {group["missing_count"]} missing. {examples}'
        )
    if not missing_lines:
        missing_lines.append('- No missing actionable examples in this report.')

    symptoms = [
        f'- {symptom}: {count}'
        for symptom, count in report['missing_by_symptom'].items()
    ]
    if not symptoms:
        symptoms = ['- No missing symptoms.']

    comparison = report.get('comparison')
    if comparison:
        verdict = comparison['verdict']
        comparison_lines = [
            f'Baseline report: {comparison["baseline_report"]}',
            (
                f'Baseline score: '
                f'{comparison["baseline_ready_actions_captured_by_ocr"]} / '
                f'{comparison["baseline_ready_actions"]} '
                f'({comparison["baseline_capture_rate"] * 100:.1f}%).'
            ),
            f'Captured delta: {comparison["captured_delta"]}.',
            f'Verdict: {verdict}.',
        ]
        if verdict == 'improved':
            next_step = (
                'Score increased. Commit only the OCR code change on a '
                'codex/ branch; do not commit generated artifacts.'
            )
        else:
            next_step = (
                'Score did not increase. Drop only the dirty OCR files changed '
                'for this attempt, summarize what was learned, and try a '
                'different code change.'
            )
    else:
        comparison_lines = [
            'No baseline report was supplied. Create a baseline first, then rerun '
            'with `--baseline-report <path>` after a code change.'
        ]
        next_step = 'Make one small OCR code change, then rerun with a baseline.'

    score_line = (
        f'{report["ready_actions_captured_by_ocr"]} / '
        f'{report["ready_actions"]} ({report["capture_rate"] * 100:.1f}%)'
    )
    summary_path = run_dir / 'summary.md'
    generated_turns_dir = run_dir / 'turns'

    return f"""Goal: improve OCR capture for ready auto-play actions.

Current score: {score_line}.
Report directory: {run_dir}

Comparison:
{chr(10).join(comparison_lines)}

Missing action clusters:
{chr(10).join(missing_lines)}

Symptoms:
{chr(10).join(symptoms)}

Please inspect the screenshots listed in `{summary_path}` and make a small code
change that improves OCR action capture.

Constraints:
- Prefer changing `skills/auto-play/scripts/image_analyzer.py`.
- If OCR missed an LLM-captured action with a bbox, prefer learning a cropped
  template image under `skills/auto-play/games/<game>/images/` and then
  matching that template before asking the LLM again.
- Do not edit saved turn ground truth, strategy memory, or LLM YAML to improve
  the score.
- Keep the output format of `extract_text_locations` compatible with existing callers.
- Preserve or improve filtering of obviously non-actionable noise.
- After the change, run:
  `{command}`
- Success means the regenerated OCR YAML under `{generated_turns_dir}` contains
  more needed action buttons and the score increases.
- Next step for this run: {next_step}
"""


def create_run_dir(args: argparse.Namespace) -> Path:
    base = args.output_dir
    base.mkdir(parents=True, exist_ok=True)
    run_name = args.run_name
    if not run_name:
        timestamp = datetime.now().astimezone().strftime('%Y%m%dT%H%M%S%z')
        run_name = f'{timestamp}-{slugify(args.game or "all")}-{args.mode}'
    run_dir = base / run_name
    suffix = 2
    while run_dir.exists():
        run_dir = base / f'{run_name}-{suffix:02d}'
        suffix += 1
    run_dir.mkdir(parents=True)
    return run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Score and iterate on OCR capture of actionable saved turns.'
    )
    parser.add_argument('--game', default='tower', help='Game slug to evaluate.')
    parser.add_argument(
        '--mode',
        choices=['saved', 'regenerate'],
        default='regenerate',
        help='Use saved OCR buttons or regenerate OCR with current code.',
    )
    parser.add_argument(
        '--turns-dir',
        type=Path,
        help='Saved auto-play turns directory. Defaults to the game turns folder.',
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        help='Directory for tuning reports. Defaults to the game OCR tuning folder.',
    )
    parser.add_argument('--run-name', help='Optional output run folder name.')
    parser.add_argument(
        '--baseline-report',
        type=Path,
        help='Optional prior report.yaml to compare this run against.',
    )
    parser.add_argument(
        '--minimum-captured-delta',
        type=int,
        default=1,
        help='Captured-action increase required for an improved verdict.',
    )
    parser.add_argument(
        '--fail-unless-improved',
        action='store_true',
        help='Exit non-zero when --baseline-report verdict is not improved.',
    )
    parser.add_argument(
        '--confidence',
        type=float,
        default=0.8,
        help='OCR confidence threshold used when regenerating.',
    )
    parser.add_argument(
        '--template-match-threshold',
        type=float,
        default=0.82,
        help='Minimum confidence for learned image-template action matches.',
    )
    parser.add_argument(
        '--disable-template-matching',
        action='store_true',
        help='Regenerate using direct OCR only, ignoring per-game template images.',
    )
    parser.add_argument(
        '--label-threshold',
        type=float,
        default=0.68,
        help='Minimum normalized label similarity counted as captured.',
    )
    parser.add_argument(
        '--coord-tolerance',
        type=float,
        default=0.06,
        help='Normalized coordinate distance counted as captured.',
    )
    parser.add_argument(
        '--include-needs-user-choice',
        action='store_true',
        help='Also evaluate needs_user_choice turns with a chosen recommendation.',
    )
    parser.add_argument(
        '--max-turns',
        type=int,
        default=0,
        help='Limit evaluated turn directories for smoke tests. 0 means all.',
    )
    parser.add_argument(
        '--example-labels',
        type=int,
        default=8,
        help='Number of missing label groups to include in the prompt.',
    )
    parser.add_argument(
        '--examples-per-label',
        type=int,
        default=3,
        help='Number of turn examples to include for each missing label.',
    )
    args = parser.parse_args()
    if not 0.0 <= args.confidence <= 1.0:
        parser.error('--confidence must be between 0.0 and 1.0')
    if not 0.0 <= args.template_match_threshold <= 1.0:
        parser.error('--template-match-threshold must be between 0.0 and 1.0')
    if not 0.0 <= args.label_threshold <= 1.0:
        parser.error('--label-threshold must be between 0.0 and 1.0')
    if args.coord_tolerance < 0.0:
        parser.error('--coord-tolerance must be non-negative')
    if args.max_turns < 0:
        parser.error('--max-turns must be non-negative')
    if args.minimum_captured_delta < 1:
        parser.error('--minimum-captured-delta must be at least 1')
    if args.baseline_report is not None and not args.baseline_report.exists():
        parser.error(f'--baseline-report does not exist: {args.baseline_report}')
    if args.fail_unless_improved and args.baseline_report is None:
        parser.error('--fail-unless-improved requires --baseline-report')
    if args.turns_dir is None:
        args.turns_dir = game_root_for(args.game) / 'turns'
    if args.output_dir is None:
        args.output_dir = game_root_for(args.game) / 'ocr-tuning'
    return args


def main() -> int:
    args = parse_args()
    run_dir = create_run_dir(args)
    turn_scores = score_turns(args, run_dir)
    report, markdown = build_report(args=args, run_dir=run_dir, turn_scores=turn_scores)

    (run_dir / 'report.yaml').write_text(
        yaml.safe_dump(
            report,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    )
    (run_dir / 'summary.md').write_text(markdown)

    print(markdown)
    comparison = report.get('comparison')
    if (
        args.fail_unless_improved
        and comparison is not None
        and comparison.get('verdict') != 'improved'
    ):
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

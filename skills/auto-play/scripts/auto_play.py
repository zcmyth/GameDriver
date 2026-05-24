#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import io
import json
import re
import selectors
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from shutil import rmtree
from typing import Any

import yaml
from PIL import Image, ImageChops, ImageStat

DEFAULT_PREFERRED = [
    'Start',
    'Play',
    'Continue',
    'Next',
    'OK',
    'Claim',
    'Collect',
    'Battle',
    'Fight',
    'Resume',
    'Confirm',
    'Accept',
]
DEFAULT_AVOID = [
    'Exit',
    'Cancel',
    'Back',
    'Store',
    'Shop',
    'Buy',
    'Purchase',
    'Ad',
    'Ads',
]
NOISE_LABEL_PATTERNS = [
    re.compile(r'^\d{1,2}:\d{2}(:\d{2})?$'),
    re.compile(r'^[+\-]?\d+([./:]\d+)+[kmb%]?$', re.I),
    re.compile(r'^\d+[./:]?\d*[kmb%]?$', re.I),
]


@dataclass(frozen=True)
class ButtonCandidate:
    label: str
    x: float
    y: float
    confidence: float
    clickability: float
    source: str = 'ocr'
    reason: str = ''
    score: float = 0.0
    bbox: tuple[float, float, float, float] | None = None
    template_path: str = ''


@dataclass(frozen=True)
class Decision:
    status: str
    reason: str
    recommended: ButtonCandidate | None
    choices: list[ButtonCandidate]


@dataclass(frozen=True)
class StateVerification:
    status: str
    reason: str
    attempts: int
    threshold: float
    similarities: list[float]
    strategy_updated: bool = False
    last_screenshot: str | None = None


@dataclass(frozen=True)
class TurnResult:
    decision: Decision
    verification: StateVerification | None


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


def template_stem_for_label(value: str) -> str:
    stem = re.sub(r'[^\w\u4e00-\u9fff]+', '-', value.strip().lower()).strip('-_')
    return stem or 'action'


def normalize_label(value: str) -> str:
    return re.sub(r'\s+', ' ', value.strip().lower())


def looks_like_noise_label(value: str) -> bool:
    normalized = normalize_label(value)
    if len(normalized) <= 1:
        return True
    return any(pattern.search(normalized) for pattern in NOISE_LABEL_PATTERNS)


def memory_path_for(game: str) -> Path:
    return game_root_for(game) / 'strategy.md'


def game_root_for(game: str) -> Path:
    path = games_root() / slugify(game)
    path.mkdir(parents=True, exist_ok=True)
    return path


def template_images_dir_for(game: str) -> Path:
    path = game_root_for(game) / 'images'
    path.mkdir(parents=True, exist_ok=True)
    return path


def turns_root(args: argparse.Namespace) -> Path:
    return args.turns_dir or args.fixed_dir or (game_root_for(args.game) / 'turns')


def prune_turn_folders(root: Path, keep: int) -> None:
    if keep <= 0 or not root.exists():
        return

    turn_dirs = sorted(
        [path for path in root.iterdir() if path.is_dir()],
        key=lambda path: (path.stat().st_mtime, path.name),
    )
    for old_turn in turn_dirs[:-keep]:
        rmtree(old_turn)


def create_turn_artifacts(args: argparse.Namespace) -> tuple[dict[str, Path], datetime]:
    root = turns_root(args)
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone()
    turn_name = f'{timestamp.strftime("%Y%m%dT%H%M%S%z")}-{slugify(args.game)}'
    turn_dir = root / turn_name
    suffix = 2
    while turn_dir.exists():
        turn_dir = root / f'{turn_name}-{suffix:02d}'
        suffix += 1
    turn_dir.mkdir(parents=True)

    prune_turn_folders(root, args.turn_history_limit)

    return {
        'turn_dir': turn_dir,
        'screen': turn_dir / 'screenshot.png',
        'ocr': turn_dir / 'ocr.yaml',
        'llm': turn_dir / 'llm.yaml',
        'metadata': turn_dir / 'metadata.yaml',
        'last_screen': turn_dir / 'last_screenshot.png',
    }, timestamp


def default_strategy_markdown(game: str) -> str:
    return f"""# Auto Play Strategy: {game}

## Objective
- Describe the long-term goal for this game here.

## Preferred Buttons
- Start
- Play
- Continue
- Next
- OK
- Claim
- Collect
- Battle
- Fight
- Resume
- Confirm
- Accept

## Avoid Buttons
- Exit
- Cancel
- Back
- Store
- Shop
- Buy
- Purchase
- Ad
- Ads

## Ineffective Buttons
None yet.

## Decision Rules
- Prefer progression actions over shop, ad, or exit actions.
- Do not click unless the user explicitly asks for an action.

## Learned Choices
- Add user choices here as durable strategy. Include the reason.

## Notes
- Add durable strategy notes here. Do not record transient screen state.
"""


def extract_section(text: str, heading: str) -> str:
    marker = f'## {heading}'
    start = text.find(marker)
    if start < 0:
        return ''
    body_start = text.find('\n', start)
    if body_start < 0:
        return ''
    next_heading = text.find('\n## ', body_start + 1)
    if next_heading < 0:
        return text[body_start + 1 :].strip()
    return text[body_start + 1 : next_heading].strip()


def extract_list_section(text: str, heading: str, fallback: list[str]) -> list[str]:
    items = []
    for line in extract_section(text, heading).splitlines():
        stripped = line.strip()
        if stripped.startswith('- '):
            item = stripped[2:].strip()
            if item:
                items.append(item)
    return items or list(fallback)


def load_memory(game: str) -> dict[str, Any]:
    path = memory_path_for(game)
    memory: dict[str, Any] = {
        'game': game,
        'preferred': list(DEFAULT_PREFERRED),
        'avoid': list(DEFAULT_AVOID),
        'ineffective': [],
        'strategy_path': path,
    }
    if not path.exists():
        return memory

    text = path.read_text()
    memory['preferred'] = extract_list_section(
        text, 'Preferred Buttons', DEFAULT_PREFERRED
    )
    memory['avoid'] = extract_list_section(text, 'Avoid Buttons', DEFAULT_AVOID)
    memory['ineffective'] = extract_list_section(text, 'Ineffective Buttons', [])
    return memory


def load_strategy_text(game: str) -> str:
    path = ensure_strategy_memory(game)
    return path.read_text()


def markdown_escape(value: str) -> str:
    return value.replace('|', '\\|').replace('\n', ' ')


def ensure_strategy_memory(game: str) -> Path:
    path = memory_path_for(game)
    if not path.exists():
        path.write_text(default_strategy_markdown(game))
    return path


def append_to_strategy_section(
    path: Path,
    heading: str,
    line: str,
    *,
    insert_before: str = '## Notes',
) -> None:
    text = path.read_text()
    marker = f'## {heading}'
    if not line.endswith('\n'):
        line += '\n'

    if marker not in text:
        insert_at = text.find(f'\n{insert_before}')
        section = f'\n\n{marker}\n{line}'
        if insert_at < 0:
            text = text.rstrip() + section
        else:
            text = text[:insert_at].rstrip() + section + text[insert_at:]
    else:
        next_heading = text.find('\n## ', text.find(marker) + len(marker))
        if next_heading < 0:
            text = text.rstrip() + '\n' + line
        else:
            text = text[:next_heading].rstrip() + '\n' + line + text[next_heading:]

    path.write_text(text)


def append_learned_choice(game: str, label: str, reason: str) -> Path:
    path = ensure_strategy_memory(game)
    line = f'- Choose **{label}** when appropriate because {reason.strip()}.\n'
    append_to_strategy_section(path, 'Learned Choices', line)
    return path


def append_no_change_learning(
    game: str,
    button: ButtonCandidate,
    verification: StateVerification,
) -> Path:
    path = ensure_strategy_memory(game)
    text = path.read_text()
    ineffective = {
        normalize_label(item)
        for item in extract_list_section(text, 'Ineffective Buttons', [])
    }
    if normalize_label(button.label) not in ineffective:
        if not ineffective:
            text = re.sub(
                r'(## Ineffective Buttons\n)None yet\.\n?',
                r'\1',
                text,
            )
            path.write_text(text)
        append_to_strategy_section(
            path,
            'Ineffective Buttons',
            f'- {button.label}',
            insert_before='## Decision Rules',
        )

    text = path.read_text()
    improvements = extract_section(text, 'Strategy Improvements Needed')
    if normalize_label(button.label) not in normalize_label(improvements):
        append_to_strategy_section(
            path,
            'Strategy Improvements Needed',
            (
                f'- Treat **{button.label}** as ineffective unless another cue '
                f'confirms it advances play; after {verification.attempts} repeated '
                'attempts, prefer a different progression action or ask for '
                'vision/user input.'
            ),
        )
    return path


class McpClient:
    def __init__(self, command: list[str], timeout: float = 20.0):
        self.command = command
        self.timeout = timeout
        self.process: subprocess.Popen[str] | None = None
        self.selector: selectors.BaseSelector | None = None
        self.request_id = 0

    def __enter__(self) -> McpClient:
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.request(
            'initialize',
            {
                'protocolVersion': '2024-11-05',
                'capabilities': {},
                'clientInfo': {'name': 'auto-play-skill', 'version': '0.1.0'},
            },
        )
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.selector is not None:
            self.selector.close()
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.process is None or self.process.stdin is None:
            raise RuntimeError('MCP process is not running')
        self.request_id += 1
        request_id = self.request_id
        payload = {
            'jsonrpc': '2.0',
            'id': request_id,
            'method': method,
            'params': params,
        }
        self.process.stdin.write(json.dumps(payload, separators=(',', ':')) + '\n')
        self.process.stdin.flush()
        return self._read_response(request_id)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = self.request(
            'tools/call',
            {
                'name': name,
                'arguments': arguments,
            },
        )
        return response['result']

    def _read_response(self, request_id: int) -> dict[str, Any]:
        assert self.process is not None
        assert self.selector is not None
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            events = self.selector.select(timeout=remaining)
            if not events:
                break
            line = self.process.stdout.readline()
            if not line:
                break
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                continue
            if response.get('id') != request_id:
                continue
            if 'error' in response:
                raise RuntimeError(response['error'].get('message', response['error']))
            return response

        stderr = ''
        if self.process.poll() is not None and self.process.stderr is not None:
            stderr = self.process.stderr.read()
        raise TimeoutError(f'MCP request {request_id} timed out. {stderr}'.strip())


def default_mcp_command() -> list[str]:
    mcp_dir = repo_root() / 'projects' / 'android_access_mcp'
    return ['uv', '--directory', str(mcp_dir), 'run', 'android-access-mcp']


def decode_mcp_screen(result: dict[str, Any]) -> tuple[Image.Image, dict[str, Any]]:
    metadata: dict[str, Any] = {}
    image_data = None
    for item in result.get('content', []):
        if item.get('type') == 'text' and not metadata:
            metadata = json.loads(item.get('text') or '{}')
        if item.get('type') == 'image':
            image_data = item.get('data')
    if not image_data:
        raise RuntimeError('current_screen did not return image content')
    image = Image.open(io.BytesIO(base64.b64decode(image_data))).convert('RGB')
    return image, metadata


def load_image(args: argparse.Namespace) -> tuple[Image.Image, dict[str, Any]]:
    if args.image:
        image = Image.open(args.image).convert('RGB')
        if args.width and args.height:
            image = image.resize((args.width, args.height), Image.Resampling.LANCZOS)
        return image, {
            'width': image.width,
            'height': image.height,
            'source': str(args.image),
        }

    command = (
        shlex.split(args.mcp_command) if args.mcp_command else default_mcp_command()
    )
    tool_args: dict[str, Any] = {}
    if args.width:
        tool_args['width'] = args.width
    if args.height:
        tool_args['height'] = args.height
    with McpClient(command, timeout=args.timeout) as client:
        result = client.call_tool('current_screen', tool_args)
    return decode_mcp_screen(result)


def analyze_buttons(
    image: Image.Image,
    *,
    confidence: float,
    game: str,
    template_match_threshold: float,
) -> list[ButtonCandidate]:
    ensure_script_imports()

    from image_analyzer import create_analyzer

    analyzer = create_analyzer(
        template_dirs=[template_images_dir_for(game)],
        template_match_threshold=template_match_threshold,
    )
    locations = analyzer.extract_text_locations(image, confidence_threshold=confidence)
    buttons = []
    for item in locations:
        label = str(item.get('text', '')).strip()
        if not label or looks_like_noise_label(label):
            continue
        buttons.append(
            ButtonCandidate(
                label=label,
                x=float(item.get('x', 0.0)),
                y=float(item.get('y', 0.0)),
                confidence=float(item.get('confidence', 0.0)),
                clickability=float(item.get('clickability', 0.0)),
                source=str(item.get('source') or 'ocr'),
                template_path=str(item.get('template_path') or ''),
                bbox=parse_normalized_bbox(item),
            )
        )
    return buttons


def parse_normalized_bbox(
    item: dict[str, Any],
) -> tuple[float, float, float, float] | None:
    bbox = item.get('bbox') or item.get('bounding_box') or item.get('box')
    values: tuple[Any, Any, Any, Any] | None = None
    if isinstance(bbox, dict):
        if all(key in bbox for key in ('x1', 'y1', 'x2', 'y2')):
            values = (bbox['x1'], bbox['y1'], bbox['x2'], bbox['y2'])
        elif all(key in bbox for key in ('left', 'top', 'right', 'bottom')):
            values = (bbox['left'], bbox['top'], bbox['right'], bbox['bottom'])
        elif all(key in bbox for key in ('x', 'y', 'width', 'height')):
            x = float(bbox['x'])
            y = float(bbox['y'])
            values = (x, y, x + float(bbox['width']), y + float(bbox['height']))
    elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        values = (bbox[0], bbox[1], bbox[2], bbox[3])

    if values is None:
        return None

    try:
        x1, y1, x2, y2 = (float(value) for value in values)
    except (TypeError, ValueError):
        return None

    x1, x2 = sorted((max(0.0, min(1.0, x1)), max(0.0, min(1.0, x2))))
    y1, y2 = sorted((max(0.0, min(1.0, y1)), max(0.0, min(1.0, y2))))
    if x2 - x1 < 0.01 or y2 - y1 < 0.01:
        return None
    return x1, y1, x2, y2


def load_llm_buttons(path: Path | None) -> list[ButtonCandidate]:
    if path is None or not path.exists():
        return []

    payload = yaml.safe_load(path.read_text()) or {}
    buttons = []
    for item in payload.get('buttons', []):
        label = str(item.get('label') or item.get('text') or '').strip()
        if not label or looks_like_noise_label(label):
            continue
        try:
            x = float(item['x'])
            y = float(item['y'])
        except (KeyError, TypeError, ValueError):
            continue
        confidence = float(item.get('confidence', 0.7))
        buttons.append(
            ButtonCandidate(
                label=label,
                x=max(0.0, min(1.0, x)),
                y=max(0.0, min(1.0, y)),
                confidence=max(0.0, min(1.0, confidence)),
                clickability=float(item.get('clickability', 0.8)),
                source='llm',
                reason=str(item.get('reason', '')).strip(),
                bbox=parse_normalized_bbox(item),
            )
        )
    return buttons


def stage_llm_result(source: Path | None, target: Path) -> Path | None:
    if source is None:
        return None
    if not source.exists():
        return source
    if source.resolve() != target.resolve():
        target.write_text(source.read_text())
    return target


def candidate_captured_by_non_llm(
    candidate: ButtonCandidate,
    buttons: list[ButtonCandidate],
    *,
    coord_tolerance: float = 0.06,
) -> bool:
    candidate_label = normalize_label(candidate.label)
    for button in buttons:
        if button.source == 'llm':
            continue
        label_match = normalize_label(button.label) == candidate_label
        coord_match = (
            ((button.x - candidate.x) ** 2 + (button.y - candidate.y) ** 2) ** 0.5
        ) <= coord_tolerance
        if label_match or coord_match:
            return True
    return False


def crop_from_bbox(
    image: Image.Image,
    bbox: tuple[float, float, float, float],
    *,
    padding: float = 0.01,
) -> Image.Image | None:
    x1, y1, x2, y2 = bbox
    x1 = max(0.0, x1 - padding)
    y1 = max(0.0, y1 - padding)
    x2 = min(1.0, x2 + padding)
    y2 = min(1.0, y2 + padding)
    left = int(x1 * image.width)
    top = int(y1 * image.height)
    right = int(x2 * image.width)
    bottom = int(y2 * image.height)
    if right - left < 4 or bottom - top < 4:
        return None
    return image.crop((left, top, right, bottom))


def unique_template_path(directory: Path, label: str, turn_name: str) -> Path:
    stem = f'{template_stem_for_label(label)}--{turn_name}'
    path = directory / f'{stem}.png'
    suffix = 2
    while path.exists():
        path = directory / f'{stem}-{suffix:02d}.png'
        suffix += 1
    return path


def learn_templates_from_llm(
    *,
    game: str,
    image: Image.Image,
    llm_buttons: list[ButtonCandidate],
    non_llm_buttons: list[ButtonCandidate],
    turn_name: str,
) -> list[dict[str, Any]]:
    learned = []
    images_dir = template_images_dir_for(game)
    for button in llm_buttons:
        if candidate_captured_by_non_llm(button, non_llm_buttons):
            continue
        if button.bbox is None:
            learned.append(
                {
                    'label': button.label,
                    'status': 'skipped',
                    'reason': 'LLM button did not include bbox.',
                }
            )
            continue
        crop = crop_from_bbox(image, button.bbox)
        if crop is None:
            learned.append(
                {
                    'label': button.label,
                    'status': 'skipped',
                    'reason': 'bbox was too small after normalization.',
                    'bbox': button_to_data(button).get('bbox'),
                }
            )
            continue
        path = unique_template_path(images_dir, button.label, turn_name)
        crop.save(path)
        learned.append(
            {
                'label': button.label,
                'status': 'saved',
                'path': str(path),
                'bbox': button_to_data(button).get('bbox'),
            }
        )
    return learned


def merge_buttons(buttons: list[ButtonCandidate]) -> list[ButtonCandidate]:
    merged: dict[tuple[str, int, int], ButtonCandidate] = {}
    for button in buttons:
        key = (normalize_label(button.label), round(button.x, 2), round(button.y, 2))
        existing = merged.get(key)
        if existing is None or button.confidence > existing.confidence:
            merged[key] = button
    return list(merged.values())


def button_to_data(button: ButtonCandidate) -> dict[str, Any]:
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
    if button.bbox:
        x1, y1, x2, y2 = button.bbox
        data['bbox'] = {
            'x1': round(x1, 6),
            'y1': round(y1, 6),
            'x2': round(x2, 6),
            'y2': round(y2, 6),
        }
    if button.template_path:
        data['template_path'] = button.template_path
    return data


def verification_to_data(verification: StateVerification) -> dict[str, Any]:
    data = {
        'status': verification.status,
        'reason': verification.reason,
        'attempts': verification.attempts,
        'similarity_threshold': round(verification.threshold, 6),
        'similarities': [
            round(similarity, 6) for similarity in verification.similarities
        ],
        'strategy_updated': verification.strategy_updated,
    }
    if verification.last_screenshot:
        data['last_screenshot'] = verification.last_screenshot
    return data


def write_ocr_yaml(
    path: Path,
    *,
    game: str,
    image: Image.Image,
    metadata: dict[str, Any],
    strategy_path: Path,
    ocr_buttons: list[ButtonCandidate],
    template_buttons: list[ButtonCandidate],
    llm_buttons: list[ButtonCandidate],
    learned_templates: list[dict[str, Any]],
    buttons: list[ButtonCandidate],
    decision: Decision,
    verification: StateVerification | None = None,
) -> None:
    payload = {
        'game': game,
        'screen': {
            'width': image.width,
            'height': image.height,
            'original_width': metadata.get('original_width'),
            'original_height': metadata.get('original_height'),
            'device_serial': metadata.get('serial'),
            'screenshot': 'screenshot.png',
        },
        'strategy': {
            'path': str(strategy_path),
        },
        'ocr_buttons': [button_to_data(button) for button in ocr_buttons],
        'template_buttons': [button_to_data(button) for button in template_buttons],
        'llm_buttons': [button_to_data(button) for button in llm_buttons],
        'learned_templates': learned_templates,
        'ranked_buttons': [button_to_data(button) for button in buttons],
        'decision': {
            'status': decision.status,
            'reason': decision.reason,
            'recommended': (
                button_to_data(decision.recommended) if decision.recommended else None
            ),
            'choices': [button_to_data(button) for button in decision.choices],
        },
    }
    if verification is not None:
        payload['state_verification'] = verification_to_data(verification)
    path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    )


def strategy_change_recommendation(
    clicked: ButtonCandidate | None,
    verification: StateVerification | None,
) -> str | None:
    if clicked is None or verification is None:
        return None
    if not verification.strategy_updated:
        return None
    return (
        f'Treat {clicked.label} as ineffective unless another cue confirms it '
        'advances play; prefer a different progression action or ask for '
        'vision/user input.'
    )


def write_metadata_yaml(
    path: Path,
    *,
    game: str,
    timestamp: datetime,
    image: Image.Image,
    screen_metadata: dict[str, Any],
    strategy_path: Path,
    artifact_paths: dict[str, Path],
    decision: Decision,
    clicked: ButtonCandidate | None,
    verification: StateVerification | None,
    llm_used: bool,
    learned_templates: list[dict[str, Any]],
) -> None:
    last_screenshot = (
        artifact_paths['last_screen'].name
        if artifact_paths['last_screen'].exists()
        else None
    )
    payload = {
        'timestamp': timestamp.isoformat(),
        'game': game,
        'turn_dir': str(artifact_paths['turn_dir']),
        'screen': {
            'width': image.width,
            'height': image.height,
            'original_width': screen_metadata.get('original_width'),
            'original_height': screen_metadata.get('original_height'),
            'device_serial': screen_metadata.get('serial'),
        },
        'artifacts': {
            'screenshot': artifact_paths['screen'].name,
            'ocr': artifact_paths['ocr'].name,
            'llm': artifact_paths['llm'].name
            if artifact_paths['llm'].exists()
            else None,
            'last_screenshot_after_action': last_screenshot,
            'template_images_dir': str(template_images_dir_for(game)),
        },
        'strategy': {
            'path': str(strategy_path),
        },
        'worklog': {
            'llm_used': llm_used,
            'llm_requested': decision.status == 'needs_llm',
            'action_taken': button_to_data(clicked) if clicked else None,
            'decision_status': decision.status,
            'decision_reason': decision.reason,
            'state_verification': (
                verification_to_data(verification) if verification else None
            ),
            'strategy_change_recommendation': strategy_change_recommendation(
                clicked, verification
            ),
            'templates_learned': learned_templates,
            'last_screenshot_after_action': last_screenshot,
        },
    }
    path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    )


def score_buttons(
    buttons: list[ButtonCandidate],
    memory: dict[str, Any],
) -> list[ButtonCandidate]:
    preferred = {normalize_label(item) for item in memory['preferred']}
    avoid = {normalize_label(item) for item in memory['avoid']}
    ineffective = {normalize_label(item) for item in memory['ineffective']}
    scored = []
    for button in buttons:
        key = normalize_label(button.label)
        score = button.confidence + (0.4 * button.clickability)
        if key in preferred:
            score += 1.0
        if key in avoid:
            score -= 1.25
        if key in ineffective:
            score -= 1.75
        scored.append(
            ButtonCandidate(
                label=button.label,
                x=button.x,
                y=button.y,
                confidence=button.confidence,
                clickability=button.clickability,
                source=button.source,
                reason=button.reason,
                score=score,
                bbox=button.bbox,
                template_path=button.template_path,
            )
        )
    return sorted(scored, key=lambda item: item.score, reverse=True)


def decide_next_move(
    buttons: list[ButtonCandidate],
    *,
    min_action_score: float,
    ambiguity_margin: float,
    ask_on_ambiguous: bool,
) -> Decision:
    if not buttons:
        return Decision(
            status='needs_llm',
            reason='OCR and strategy did not find any actionable button text.',
            recommended=None,
            choices=[],
        )

    top = buttons[0]
    if top.score < min_action_score:
        return Decision(
            status='needs_llm',
            reason=(
                f'Top candidate score {top.score:.3f} is below {min_action_score:.3f}.'
            ),
            recommended=top,
            choices=buttons[:3],
        )

    close = [
        button for button in buttons[:4] if top.score - button.score <= ambiguity_margin
    ]
    if len(close) > 1:
        if not ask_on_ambiguous:
            return Decision(
                status='ready',
                reason=(
                    'Multiple top choices are close after applying the strategy. '
                    'Auto-trying the highest-scored option; if it does not change '
                    'state, it will be learned as ineffective so a later turn can '
                    'try another choice.'
                ),
                recommended=top,
                choices=close,
            )
        return Decision(
            status='needs_user_choice',
            reason=(
                'Multiple top choices are close after applying the strategy. '
                'Ask the user to choose and explain why.'
            ),
            recommended=None,
            choices=close,
        )

    return Decision(
        status='ready',
        reason='One candidate is clearly preferred by the current strategy.',
        recommended=top,
        choices=[top],
    )


def click_button(args: argparse.Namespace, button: ButtonCandidate) -> None:
    command = (
        shlex.split(args.mcp_command) if args.mcp_command else default_mcp_command()
    )
    with McpClient(command, timeout=args.timeout) as client:
        client.call_tool('click', {'x': button.x, 'y': button.y})


def image_similarity(
    before: Image.Image,
    after: Image.Image,
    *,
    sample_size: tuple[int, int] = (128, 128),
) -> float:
    before_sample = before.convert('RGB').resize(sample_size, Image.Resampling.LANCZOS)
    after_sample = after.convert('RGB').resize(sample_size, Image.Resampling.LANCZOS)
    diff = ImageChops.difference(before_sample, after_sample)
    mean_delta = sum(ImageStat.Stat(diff).mean) / 3.0
    return max(0.0, min(1.0, 1.0 - (mean_delta / 255.0)))


def verify_state_changed_after_click(
    args: argparse.Namespace,
    *,
    before_image: Image.Image,
    button: ButtonCandidate,
    last_screenshot_path: Path,
) -> StateVerification:
    threshold = args.state_similarity_threshold
    if args.image:
        return StateVerification(
            status='skipped',
            reason='Using --image, so there is no live Android state to verify.',
            attempts=0,
            threshold=threshold,
            similarities=[],
        )

    similarities: list[float] = []
    for attempt in range(1, args.state_change_retries + 1):
        time.sleep(args.state_change_interval)
        after_image, _metadata = load_image(args)
        after_image.save(last_screenshot_path)
        similarity = image_similarity(before_image, after_image)
        similarities.append(similarity)
        if similarity < threshold:
            return StateVerification(
                status='changed',
                reason=(
                    f'Screen changed after attempt {attempt}; similarity '
                    f'{similarity:.4f} is below threshold {threshold:.4f}.'
                ),
                attempts=attempt,
                threshold=threshold,
                similarities=similarities,
                last_screenshot=last_screenshot_path.name,
            )
        if attempt < args.state_change_retries:
            click_button(args, button)

    verification = StateVerification(
        status='unchanged',
        reason=(
            f'Screen stayed above similarity threshold {threshold:.4f} after '
            f'{args.state_change_retries} click attempts.'
        ),
        attempts=args.state_change_retries,
        threshold=threshold,
        similarities=similarities,
        strategy_updated=True,
        last_screenshot=last_screenshot_path.name,
    )
    append_no_change_learning(args.game, button, verification)
    return verification


def save_overlay(
    image: Image.Image, buttons: list[ButtonCandidate], path: Path
) -> None:
    ensure_script_imports()

    from image_analyzer import draw_text_locations

    locations = [
        {
            'text': button.label,
            'x': button.x,
            'y': button.y,
            'confidence': button.confidence,
        }
        for button in buttons
    ]
    overlay = draw_text_locations(image, locations)
    path.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(path)


def build_llm_prompt(
    *,
    game: str,
    image_path: Path,
    strategy_text: str,
    buttons: list[ButtonCandidate],
    decision: Decision,
) -> str:
    ocr_table = '\n'.join(
        (
            f'- {button.label}: x={button.x:.4f}, y={button.y:.4f}, '
            f'confidence={button.confidence:.3f}, score={button.score:.3f}, '
            f'source={button.source}'
        )
        for button in buttons
    )
    if not ocr_table:
        ocr_table = '- No OCR buttons detected.'

    return f"""Inspect the Android game screenshot at:

`{image_path}`

Use the strategy below and the OCR candidates to identify objects and clickable buttons.
Return YAML only, with normalized center coordinates from 0.0 to 1.0:

summary: brief screen description
objects:
  - label: object name
    description: what it is
    x: 0.5
    y: 0.5
buttons:
  - label: button/action label
    x: 0.5
    y: 0.5
    bbox:
      x1: 0.42
      y1: 0.46
      x2: 0.58
      y2: 0.54
    confidence: 0.8
    reason: why this is clickable and what it likely does

Do not include Markdown in the response YAML.
For each button, include a tight normalized bbox around the actionable visual
area or button. Include enough border for image-template matching later.

## Why LLM Vision Is Needed
{decision.reason}

## Strategy
{strategy_text.strip()}

## OCR Candidates
{ocr_table}
"""


def render_report(
    args: argparse.Namespace,
    image: Image.Image,
    metadata: dict[str, Any],
    buttons: list[ButtonCandidate],
    memory_path: Path,
    artifact_paths: dict[str, Path],
    decision: Decision,
    clicked: ButtonCandidate | None,
    verification: StateVerification | None,
    llm_prompt: str | None,
    learned_templates: list[dict[str, Any]],
) -> str:
    lines = ['# Auto Play Observation', '']
    lines.append(f'- Game: {args.game}')
    lines.append(f'- Screen: {image.width} x {image.height}')
    if metadata.get('original_width') and metadata.get('original_height'):
        lines.append(
            f'- Original screen: {metadata["original_width"]} x '
            f'{metadata["original_height"]}'
        )
    if metadata.get('serial'):
        lines.append(f'- Device serial: {metadata["serial"]}')
    lines.append(f'- Turn folder: {artifact_paths["turn_dir"]}')
    lines.append(f'- Screenshot: {artifact_paths["screen"]}')
    lines.append(f'- OCR YAML: {artifact_paths["ocr"]}')
    lines.append(f'- LLM YAML: {artifact_paths["llm"]} (optional)')
    lines.append(f'- Metadata YAML: {artifact_paths["metadata"]}')
    lines.append(f'- Strategy memory: {memory_path}')
    lines.append(f'- Template images: {template_images_dir_for(args.game)}')
    lines.append(f'- Decision status: `{decision.status}`')
    lines.append(f'- Decision reason: {decision.reason}')
    lines.append('')

    lines.extend(['## Recommended Button', ''])
    if decision.recommended:
        top = decision.recommended
        lines.append(
            f'- **{top.label}** at `{top.x:.4f}, {top.y:.4f}` '
            f'(score `{top.score:.3f}`, source `{top.source}`)'
        )
    elif decision.status == 'needs_user_choice':
        lines.append('- Multiple plausible choices. Ask the user to pick one.')
    else:
        lines.append('- No confident button choice yet.')
    lines.append('')

    lines.extend(['## Buttons', ''])
    lines.append('| # | Label | X | Y | Confidence | Clickability | Source | Score |')
    lines.append('| ---: | --- | ---: | ---: | ---: | ---: | --- | ---: |')
    for index, button in enumerate(buttons, start=1):
        lines.append(
            '| '
            + ' | '.join(
                [
                    str(index),
                    markdown_escape(button.label),
                    f'{button.x:.4f}',
                    f'{button.y:.4f}',
                    f'{button.confidence:.3f}',
                    f'{button.clickability:.3f}',
                    markdown_escape(button.source),
                    f'{button.score:.3f}',
                ]
            )
            + ' |'
        )
    if not buttons:
        lines.append('|  | No buttons detected |  |  |  |  |  |  |')
    lines.append('')

    if clicked:
        lines.extend(['## Action', ''])
        lines.append(
            f'- Clicked **{clicked.label}** at `{clicked.x:.4f}, {clicked.y:.4f}`.'
        )
        if verification is not None:
            lines.append(f'- State verification: `{verification.status}`.')
            lines.append(f'- Verification reason: {verification.reason}')
            if verification.similarities:
                similarities = ', '.join(
                    f'{similarity:.4f}' for similarity in verification.similarities
                )
                lines.append(f'- Similarities: `{similarities}`.')
            if verification.last_screenshot:
                lines.append(
                    f'- Last screenshot after action: '
                    f'`{artifact_paths["last_screen"]}`.'
                )
            if verification.strategy_updated:
                lines.append(
                    '- Strategy memory was updated; restart the turn with the '
                    'new strategy.'
                )
        lines.append('')
    if learned_templates:
        lines.extend(['## Learned Templates', ''])
        for item in learned_templates:
            label = markdown_escape(str(item.get('label') or 'unknown'))
            status = markdown_escape(str(item.get('status') or 'unknown'))
            path = item.get('path')
            if path:
                lines.append(f'- **{label}**: `{status}` at `{path}`')
            else:
                reason = markdown_escape(str(item.get('reason') or ''))
                lines.append(f'- **{label}**: `{status}` {reason}')
        lines.append('')
    if not clicked:
        if decision.status == 'needs_llm':
            lines.extend(['## Next Step', ''])
            lines.append(f'- Send `{artifact_paths["screen"]}` to the LLM.')
            lines.append(f'- Save the returned YAML to `{artifact_paths["llm"]}`.')
            lines.append(f'- Rerun with `--llm-result {artifact_paths["llm"]}`.')
            if llm_prompt:
                lines.extend(['', '## LLM Prompt', '', '```text', llm_prompt, '```'])
            lines.append('')
        elif decision.status == 'needs_user_choice':
            lines.extend(['## Next Step', ''])
            lines.append(
                '- Ask the user to choose one of these options and explain why:'
            )
            for button in decision.choices:
                lines.append(
                    f'  - **{button.label}** at `{button.x:.4f}, {button.y:.4f}` '
                    f'(source `{button.source}`, score `{button.score:.3f}`)'
                )
            lines.append(
                '- Remember the answer with `--remember-choice <label> '
                '--choice-reason <reason>` so it becomes strategy.'
            )
            lines.append('')
        else:
            lines.extend(['## Action', ''])
            lines.append('- Inspect-only. No click was performed.')
            lines.append('')
    return '\n'.join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=('Run one Android auto-play turn through MCP and strategy memory.')
    )
    parser.add_argument('--game', default='default-game', help='Game memory name.')
    parser.add_argument('--width', type=int, default=360, help='Analysis image width.')
    parser.add_argument(
        '--height', type=int, default=800, help='Analysis image height.'
    )
    parser.add_argument(
        '--confidence',
        type=float,
        default=0.8,
        help='OCR confidence threshold for button text.',
    )
    parser.add_argument(
        '--template-match-threshold',
        type=float,
        default=0.82,
        help='Minimum confidence for per-game image-template action matches.',
    )
    parser.add_argument(
        '--click-recommended',
        action='store_true',
        help='Click the top-ranked button after analysis.',
    )
    parser.add_argument('--save-screen', type=Path, help='Optional screenshot path.')
    parser.add_argument(
        '--save-overlay', type=Path, help='Optional annotated image path.'
    )
    parser.add_argument(
        '--image',
        type=Path,
        help='Analyze a saved image instead of requesting a live MCP screenshot.',
    )
    parser.add_argument(
        '--mcp-command',
        help='Override MCP server command. Defaults to the repo Android MCP project.',
    )
    parser.add_argument(
        '--timeout', type=float, default=30.0, help='MCP timeout seconds.'
    )
    parser.add_argument(
        '--fixed-dir',
        type=Path,
        help='Compatibility alias for --turns-dir.',
    )
    parser.add_argument(
        '--turns-dir',
        type=Path,
        help='Directory that stores rolling per-turn folders.',
    )
    parser.add_argument(
        '--turn-history-limit',
        type=int,
        default=100,
        help='Number of per-turn folders to keep under --turns-dir.',
    )
    parser.add_argument(
        '--llm-result',
        type=Path,
        help='Optional YAML returned by LLM vision for a turn screenshot.',
    )
    parser.add_argument(
        '--min-action-score',
        type=float,
        default=0.95,
        help='Minimum score required before a button can be auto-clicked.',
    )
    parser.add_argument(
        '--ambiguity-margin',
        type=float,
        default=0.20,
        help='Score margin used to identify close alternatives.',
    )
    parser.add_argument(
        '--ask-on-ambiguous',
        action='store_true',
        help='Stop and ask the user when multiple choices are close.',
    )
    parser.add_argument(
        '--state-similarity-threshold',
        type=float,
        default=0.995,
        help='Post-click similarity at or above this value counts as unchanged.',
    )
    parser.add_argument(
        '--state-change-retries',
        type=int,
        default=3,
        help='Post-click screenshot checks before treating the action as ineffective.',
    )
    parser.add_argument(
        '--state-change-interval',
        type=float,
        default=1.0,
        help='Seconds to sleep between post-click screenshot checks.',
    )
    parser.add_argument(
        '--remember-choice',
        help='Persist a user-chosen durable strategy choice by label.',
    )
    parser.add_argument(
        '--choice-reason',
        help='Reason to store with --remember-choice.',
    )
    parser.add_argument(
        '--loop',
        action='store_true',
        help='Repeat ready turns, sleeping between turns; stops on LLM/user need.',
    )
    parser.add_argument(
        '--max-turns',
        type=int,
        default=1,
        help='Maximum turns to run. Use 0 for unlimited with --loop.',
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=1.0,
        help='Seconds to sleep between loop turns.',
    )
    parser.add_argument(
        '--max-unchanged-restarts',
        type=int,
        default=1,
        help='Extra non-loop turns to run after strategy updates from no change.',
    )
    args = parser.parse_args()
    if not 0.0 <= args.state_similarity_threshold <= 1.0:
        parser.error('--state-similarity-threshold must be between 0.0 and 1.0')
    if not 0.0 <= args.template_match_threshold <= 1.0:
        parser.error('--template-match-threshold must be between 0.0 and 1.0')
    if args.state_change_retries < 1:
        parser.error('--state-change-retries must be at least 1')
    if args.state_change_interval < 0.0:
        parser.error('--state-change-interval must be non-negative')
    if args.max_unchanged_restarts < 0:
        parser.error('--max-unchanged-restarts must be non-negative')
    if args.turn_history_limit < 1:
        parser.error('--turn-history-limit must be at least 1')
    return args


def run_turn(args: argparse.Namespace) -> TurnResult:
    artifact_paths, timestamp = create_turn_artifacts(args)

    image, metadata = load_image(args)

    artifact_paths['screen'].parent.mkdir(parents=True, exist_ok=True)
    image.save(artifact_paths['screen'])
    image = Image.open(artifact_paths['screen']).convert('RGB')
    if args.save_screen:
        args.save_screen.parent.mkdir(parents=True, exist_ok=True)
        image.save(args.save_screen)

    memory_path = ensure_strategy_memory(args.game)
    memory = load_memory(args.game)
    strategy_text = load_strategy_text(args.game)
    llm_result_path = stage_llm_result(args.llm_result, artifact_paths['llm'])
    detected_buttons = analyze_buttons(
        image,
        confidence=args.confidence,
        game=args.game,
        template_match_threshold=args.template_match_threshold,
    )
    ocr_buttons = [button for button in detected_buttons if button.source != 'template']
    template_buttons = [
        button for button in detected_buttons if button.source == 'template'
    ]
    llm_buttons = load_llm_buttons(llm_result_path)
    learned_templates = learn_templates_from_llm(
        game=args.game,
        image=image,
        llm_buttons=llm_buttons,
        non_llm_buttons=[*ocr_buttons, *template_buttons],
        turn_name=artifact_paths['turn_dir'].name,
    )
    if any(item.get('status') == 'saved' for item in learned_templates):
        detected_buttons = analyze_buttons(
            image,
            confidence=args.confidence,
            game=args.game,
            template_match_threshold=args.template_match_threshold,
        )
        ocr_buttons = [
            button for button in detected_buttons if button.source != 'template'
        ]
        template_buttons = [
            button for button in detected_buttons if button.source == 'template'
        ]
    buttons = score_buttons(
        merge_buttons([*ocr_buttons, *template_buttons, *llm_buttons]), memory
    )
    decision = decide_next_move(
        buttons,
        min_action_score=args.min_action_score,
        ambiguity_margin=args.ambiguity_margin,
        ask_on_ambiguous=args.ask_on_ambiguous,
    )

    if args.save_overlay:
        args.save_overlay.parent.mkdir(parents=True, exist_ok=True)
        save_overlay(image, buttons, args.save_overlay)

    llm_prompt = None
    if decision.status == 'needs_llm':
        llm_prompt = build_llm_prompt(
            game=args.game,
            image_path=artifact_paths['screen'],
            strategy_text=strategy_text,
            buttons=buttons,
            decision=decision,
        )

    clicked = None
    verification = None
    if args.click_recommended and decision.status == 'ready' and decision.recommended:
        clicked = decision.recommended
        click_button(args, clicked)
        verification = verify_state_changed_after_click(
            args,
            before_image=image,
            button=clicked,
            last_screenshot_path=artifact_paths['last_screen'],
        )

    write_ocr_yaml(
        artifact_paths['ocr'],
        game=args.game,
        image=image,
        metadata=metadata,
        strategy_path=memory_path,
        ocr_buttons=ocr_buttons,
        template_buttons=template_buttons,
        llm_buttons=llm_buttons,
        learned_templates=learned_templates,
        buttons=buttons,
        decision=decision,
        verification=verification,
    )
    write_metadata_yaml(
        artifact_paths['metadata'],
        game=args.game,
        timestamp=timestamp,
        image=image,
        screen_metadata=metadata,
        strategy_path=memory_path,
        artifact_paths=artifact_paths,
        decision=decision,
        clicked=clicked,
        verification=verification,
        llm_used=bool(llm_buttons),
        learned_templates=learned_templates,
    )

    report = render_report(
        args,
        image,
        metadata,
        buttons,
        memory_path,
        artifact_paths,
        decision,
        clicked,
        verification,
        llm_prompt,
        learned_templates,
    )
    print(report)
    return TurnResult(decision=decision, verification=verification)


def main() -> int:
    args = parse_args()
    if args.remember_choice:
        if not args.choice_reason:
            raise SystemExit('--choice-reason is required with --remember-choice')
        append_learned_choice(args.game, args.remember_choice, args.choice_reason)

    turn = 0
    unchanged_restarts = 0
    while True:
        turn += 1
        result = run_turn(args)
        no_change = (
            result.verification is not None
            and result.verification.status == 'unchanged'
        )
        if no_change and not args.loop:
            if unchanged_restarts < args.max_unchanged_restarts:
                unchanged_restarts += 1
                time.sleep(args.interval)
                continue
            break

        if not args.loop or result.decision.status != 'ready':
            break
        if args.max_turns and turn >= args.max_turns:
            break
        time.sleep(args.interval)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

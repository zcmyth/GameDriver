#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml
from PIL import Image


@dataclass(frozen=True)
class TemplateInfo:
    path: Path
    label: str
    width: int
    height: int
    quality: float
    hash_bits: np.ndarray
    active_bbox: tuple[int, int, int, int]
    suspicious_reasons: tuple[str, ...]


@dataclass(frozen=True)
class DuplicateDecision:
    keep: TemplateInfo
    remove: TemplateInfo
    similarity: float
    reason: str


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def games_root() -> Path:
    return skill_root() / 'games'


def slugify(value: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', value.strip().lower()).strip('-')
    return slug or 'default-game'


def images_dir_for(game: str) -> Path:
    return games_root() / slugify(game) / 'images'


def template_label(path: Path) -> str:
    return path.stem.split('--', 1)[0]


def active_pixels(image: Image.Image) -> np.ndarray:
    pixels = np.asarray(image.convert('RGB'), dtype=np.float32)
    red = pixels[..., 0]
    green = pixels[..., 1]
    blue = pixels[..., 2]
    gray = 0.299 * red + 0.587 * green + 0.114 * blue
    chroma = np.maximum(np.maximum(red, green), blue) - np.minimum(
        np.minimum(red, green),
        blue,
    )
    return (gray >= 42.0) | (chroma >= 24.0)


def active_bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        height, width = mask.shape
        return 0, 0, width, height
    return int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)


def content_image(image: Image.Image) -> Image.Image:
    mask = active_pixels(image)
    left, top, right, bottom = active_bbox(mask)
    if right - left < 4 or bottom - top < 4:
        return image.convert('RGB')
    return image.crop((left, top, right, bottom)).convert('RGB')


def square_thumbnail(image: Image.Image, size: int = 96) -> np.ndarray:
    content = content_image(image)
    content.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new('L', (size, size), color=0)
    left = (size - content.width) // 2
    top = (size - content.height) // 2
    canvas.paste(content.convert('L'), (left, top))
    return np.asarray(canvas, dtype=np.float32)


def average_hash(image: Image.Image, size: int = 16) -> np.ndarray:
    sample = (
        content_image(image).convert('L').resize((size, size), Image.Resampling.LANCZOS)
    )
    pixels = np.asarray(sample, dtype=np.float32)
    return pixels > float(pixels.mean())


def hash_similarity(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape:
        return 0.0
    return 1.0 - float(np.mean(left != right))


def pixel_similarity(left: Image.Image, right: Image.Image) -> float:
    left_pixels = square_thumbnail(left)
    right_pixels = square_thumbnail(right)
    delta = float(np.mean(np.abs(left_pixels - right_pixels)) / 255.0)
    return max(0.0, min(1.0, 1.0 - delta))


def template_similarity(left: TemplateInfo, right: TemplateInfo) -> float:
    left_image = Image.open(left.path).convert('RGB')
    right_image = Image.open(right.path).convert('RGB')
    return (0.65 * pixel_similarity(left_image, right_image)) + (
        0.35 * hash_similarity(left.hash_bits, right.hash_bits)
    )


def prominent_row_gaps(mask: np.ndarray) -> int:
    if mask.size == 0:
        return 0
    row_active = mask.mean(axis=1)
    threshold = max(0.04, float(row_active.max()) * 0.12)
    active = row_active >= threshold
    gaps = []
    start = None
    for index, value in enumerate(active):
        if not value and start is None:
            start = index
        elif value and start is not None:
            gaps.append((start, index))
            start = None
    if start is not None:
        gaps.append((start, len(active)))

    count = 0
    for start, end in gaps:
        if end - start < 8:
            continue
        if active[:start].sum() >= 18 and active[end:].sum() >= 18:
            count += 1
    return count


def quality_score(image: Image.Image, mask: np.ndarray) -> float:
    rgb = np.asarray(image.convert('RGB'), dtype=np.float32)
    gray = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    contrast = min(1.0, float(gray.std()) / 72.0)
    sharpness = min(1.0, float(cv2.Laplacian(gray, cv2.CV_64F).var()) / 900.0)
    coverage = float(mask.mean())
    left, top, right, bottom = active_bbox(mask)
    active_area = max(1, (right - left) * (bottom - top))
    total_area = max(1, image.width * image.height)
    border_penalty = 1.0 - (active_area / total_area)
    oversize_penalty = max(0.0, (total_area - 18000.0) / 36000.0)
    tall_penalty = max(0.0, (image.height / max(1, image.width) - 1.45) / 1.2)
    gap_penalty = min(1.0, prominent_row_gaps(mask) * 0.25)
    return (
        (0.35 * contrast)
        + (0.35 * sharpness)
        + (0.2 * min(1.0, coverage * 2.0))
        + 0.1
        - (0.25 * border_penalty)
        - (0.2 * oversize_penalty)
        - (0.25 * tall_penalty)
        - (0.35 * gap_penalty)
    )


def suspicious_reasons(image: Image.Image, mask: np.ndarray) -> tuple[str, ...]:
    reasons = []
    aspect = image.height / max(1, image.width)
    gaps = prominent_row_gaps(mask)
    left, top, right, bottom = active_bbox(mask)
    active_area = max(1, (right - left) * (bottom - top))
    total_area = max(1, image.width * image.height)
    active_ratio = active_area / total_area
    if (
        image.height >= 145
        and aspect >= 1.45
        and (aspect >= 1.85 or gaps or active_ratio < 0.62)
    ):
        reasons.append(
            f'tall crop may include stacked UI (size {image.width}x{image.height})'
        )
    if gaps:
        reasons.append(f'{gaps} prominent horizontal inactive gap(s)')
    if total_area >= 4000 and active_ratio < 0.55:
        reasons.append('large inactive border or empty panel area')
    return tuple(reasons)


def inspect_template(path: Path) -> TemplateInfo:
    image = Image.open(path).convert('RGB')
    mask = active_pixels(image)
    return TemplateInfo(
        path=path,
        label=template_label(path),
        width=image.width,
        height=image.height,
        quality=quality_score(image, mask),
        hash_bits=average_hash(image),
        active_bbox=active_bbox(mask),
        suspicious_reasons=suspicious_reasons(image, mask),
    )


def group_by_label(templates: list[TemplateInfo]) -> dict[str, list[TemplateInfo]]:
    grouped: dict[str, list[TemplateInfo]] = {}
    for template in templates:
        grouped.setdefault(template.label, []).append(template)
    return grouped


def duplicate_decisions(
    templates: list[TemplateInfo],
    *,
    same_label_threshold: float,
    cross_label_threshold: float,
    dedupe_cross_label: bool,
) -> tuple[list[DuplicateDecision], list[DuplicateDecision]]:
    applied: list[DuplicateDecision] = []
    review_only: list[DuplicateDecision] = []

    for label, group in group_by_label(templates).items():
        if len(group) < 2:
            continue
        sorted_group = sorted(group, key=lambda item: item.quality, reverse=True)
        keep = sorted_group[0]
        for candidate in sorted_group[1:]:
            similarity = template_similarity(keep, candidate)
            if similarity >= same_label_threshold:
                applied.append(
                    DuplicateDecision(
                        keep=keep,
                        remove=candidate,
                        similarity=similarity,
                        reason=f'same label `{label}`',
                    )
                )

    for index, left in enumerate(templates):
        for right in templates[index + 1 :]:
            if left.label == right.label:
                continue
            similarity = template_similarity(left, right)
            if similarity < cross_label_threshold:
                continue
            keep, remove = sorted(
                (left, right), key=lambda item: item.quality, reverse=True
            )
            decision = DuplicateDecision(
                keep=keep,
                remove=remove,
                similarity=similarity,
                reason='cross-label visual match',
            )
            if dedupe_cross_label:
                applied.append(decision)
            else:
                review_only.append(decision)

    deduped: dict[Path, DuplicateDecision] = {}
    for decision in applied:
        existing = deduped.get(decision.remove.path)
        if existing is None or decision.keep.quality > existing.keep.quality:
            deduped[decision.remove.path] = decision
    return list(deduped.values()), review_only


def resolve_template_path(value: str, images_dir: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == 'games':
        return skill_root() / path
    return images_dir / path


def normalized_bbox_from_item(
    item: dict[str, Any],
) -> tuple[float, float, float, float]:
    bbox = item.get('template_bbox') or item.get('crop_bbox') or item.get('bbox')
    if not isinstance(bbox, dict):
        raise ValueError('crop item must include bbox/template_bbox/crop_bbox mapping')
    x1 = float(bbox['x1'])
    y1 = float(bbox['y1'])
    x2 = float(bbox['x2'])
    y2 = float(bbox['y2'])
    x1, x2 = sorted((max(0.0, min(1.0, x1)), max(0.0, min(1.0, x2))))
    y1, y2 = sorted((max(0.0, min(1.0, y1)), max(0.0, min(1.0, y2))))
    if x2 - x1 < 0.01 or y2 - y1 < 0.01:
        raise ValueError('crop bbox is too small')
    return x1, y1, x2, y2


def apply_llm_crops(
    llm_crops_path: Path | None,
    *,
    images_dir: Path,
    apply: bool,
) -> list[str]:
    if llm_crops_path is None:
        return []
    payload = yaml.safe_load(llm_crops_path.read_text()) or {}
    crop_items = payload.get('crops') or payload.get('images') or []
    applied = []
    for item in crop_items:
        path_value = item.get('path') or item.get('image') or item.get('file')
        if not path_value:
            continue
        path = resolve_template_path(str(path_value), images_dir)
        bbox = normalized_bbox_from_item(item)
        image = Image.open(path).convert('RGB')
        left = int(bbox[0] * image.width)
        top = int(bbox[1] * image.height)
        right = int(math.ceil(bbox[2] * image.width))
        bottom = int(math.ceil(bbox[3] * image.height))
        applied.append(f'{path}: crop ({left}, {top}, {right}, {bottom})')
        if apply:
            image.crop((left, top, right, bottom)).save(path)
    return applied


def llm_crop_request(template: TemplateInfo) -> dict[str, Any]:
    return {
        'path': str(template.path),
        'width': template.width,
        'height': template.height,
        'reasons': list(template.suspicious_reasons),
        'prompt': (
            'Inspect this template PNG and return YAML with one normalized '
            'template_bbox that contains exactly one clickable button/card/icon. '
            'Exclude neighboring cards, adjacent buttons, unrelated labels, '
            'empty panel area, and duplicated UI. Return: '
            f'crops: [{{path: "{template.path}", template_bbox: '
            '{x1: 0.0, y1: 0.0, x2: 1.0, y2: 1.0}, reason: "..."}]}'
        ),
    }


def render_report(
    *,
    templates: list[TemplateInfo],
    duplicate_removals: list[DuplicateDecision],
    review_duplicates: list[DuplicateDecision],
    llm_crop_actions: list[str],
) -> str:
    suspicious = [template for template in templates if template.suspicious_reasons]
    lines = [
        '# Template Audit',
        '',
        f'- Templates inspected: {len(templates)}',
        f'- Duplicate removals: {len(duplicate_removals)}',
        f'- Cross-label duplicate candidates for review: {len(review_duplicates)}',
        f'- Suspect crops needing LLM bbox review: {len(suspicious)}',
        f'- LLM crop actions: {len(llm_crop_actions)}',
        '',
        '## Duplicate Removals',
    ]
    if duplicate_removals:
        for decision in duplicate_removals:
            lines.append(
                '- Remove '
                f'`{decision.remove.path.name}` '
                f'(quality {decision.remove.quality:.3f}) keeping '
                f'`{decision.keep.path.name}` '
                f'(quality {decision.keep.quality:.3f}); '
                f'similarity {decision.similarity:.3f}; {decision.reason}.'
            )
    else:
        lines.append('- None.')

    lines.extend(['', '## Review Duplicates'])
    if review_duplicates:
        for decision in review_duplicates:
            lines.append(
                '- Possible duplicate '
                f'`{decision.remove.path.name}` vs `{decision.keep.path.name}`; '
                f'similarity {decision.similarity:.3f}.'
            )
    else:
        lines.append('- None.')

    lines.extend(['', '## Suspect Crops'])
    if suspicious:
        for template in suspicious:
            reasons = '; '.join(template.suspicious_reasons)
            lines.append(
                f'- `{template.path.name}` ({template.width}x{template.height}, '
                f'quality {template.quality:.3f}): {reasons}'
            )
    else:
        lines.append('- None.')

    lines.extend(['', '## LLM Crop Actions'])
    if llm_crop_actions:
        lines.extend(f'- {action}' for action in llm_crop_actions)
    else:
        lines.append('- None.')

    lines.extend(['', '## LLM Crop Requests', '```yaml'])
    lines.append(
        yaml.safe_dump(
            {'crops': [llm_crop_request(template) for template in suspicious]},
            sort_keys=False,
            allow_unicode=True,
        ).strip()
    )
    lines.append('```')
    return '\n'.join(lines) + '\n'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Audit per-game template images and dedupe similar crops.'
    )
    parser.add_argument('--game', default='tower')
    parser.add_argument('--images-dir', type=Path)
    parser.add_argument(
        '--report',
        type=Path,
        help='Markdown report path. Defaults to games/<game>/template_audit.md.',
    )
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--llm-crops', type=Path)
    parser.add_argument('--dedupe-cross-label', action='store_true')
    parser.add_argument('--same-label-threshold', type=float, default=0.88)
    parser.add_argument('--cross-label-threshold', type=float, default=0.965)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    images_dir = args.images_dir or images_dir_for(args.game)
    report_path = args.report or (images_dir.parent / 'template_audit.md')

    llm_crop_actions = apply_llm_crops(
        args.llm_crops,
        images_dir=images_dir,
        apply=args.apply,
    )
    templates = [
        inspect_template(path)
        for path in sorted(images_dir.glob('*.png'))
        if path.is_file()
    ]
    duplicate_removals, review_duplicates = duplicate_decisions(
        templates,
        same_label_threshold=args.same_label_threshold,
        cross_label_threshold=args.cross_label_threshold,
        dedupe_cross_label=args.dedupe_cross_label,
    )

    report = render_report(
        templates=templates,
        duplicate_removals=duplicate_removals,
        review_duplicates=review_duplicates,
        llm_crop_actions=llm_crop_actions,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report)

    if args.apply:
        for decision in duplicate_removals:
            if decision.remove.path.exists():
                decision.remove.path.unlink()

    print(report)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

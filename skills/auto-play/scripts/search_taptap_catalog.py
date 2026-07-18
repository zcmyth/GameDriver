#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

DEFAULT_TOWER_GUIDE_ROOT = Path('/Users/chunzhang/games/skills/game-tower/guide')


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def game_root(game: str) -> Path:
    slug = re.sub(r'[^0-9A-Za-z._-]+', '-', game.strip().lower()).strip('-')
    return repo_root() / 'skills' / 'auto-play' / 'games' / (slug or 'tower')


def default_index_path(game: str) -> Path:
    if re.sub(r'[^0-9A-Za-z._-]+', '-', game.strip().lower()).strip('-') == 'tower':
        guide = Path(os.environ.get('TOWER_GUIDE_ROOT', str(DEFAULT_TOWER_GUIDE_ROOT)))
        return guide / 'taptap_search_index.json'
    return game_root(game) / 'guide' / 'taptap_search_index.json'


def load_entries(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        entries = payload.get('entries')
        if isinstance(entries, list):
            return entries
    return []


def normalized(value: str) -> str:
    return value.casefold()


def term_variants(term: str) -> list[str]:
    variants = [term]
    if term == '超越卡牌':
        variants.append('超越牌')
    if term == '超越牌':
        variants.append('超越卡牌')
    return variants


def entry_matches(
    entry: dict[str, Any],
    terms: list[str],
    *,
    catalog: str,
    group: str,
    exclude_group: str,
    field: str,
) -> bool:
    if catalog and entry.get('catalog') != catalog:
        return False
    if group and entry.get('group') != group:
        return False
    if exclude_group and entry.get('group') == exclude_group:
        return False
    if field == 'all':
        fields = (
            'name',
            'catalog',
            'group',
            'type',
            'cost',
            'effect',
            'source',
            'search_text',
        )
    else:
        fields = (field,)
    search_text = normalized('\n'.join(str(entry.get(key) or '') for key in fields))
    return all(
        any(normalized(variant) in search_text for variant in term_variants(term))
        for term in terms
    )


def render_entry(entry: dict[str, Any]) -> str:
    image = entry.get('icon_path') or ''
    detail_images = entry.get('detail_image_paths') or []
    detail_image = detail_images[0] if detail_images else ''
    parts = [
        (
            f'- {entry.get("name", "")} '
            f'[{entry.get("catalog", "")} / {entry.get("group", "")}]'
        ),
        f'  Type: {entry.get("type") or "unknown"}',
        f'  Cost: {entry.get("cost") or "unknown"}',
        f'  Effect: {entry.get("effect") or "unknown"}',
        f'  Source: {entry.get("source") or "unknown"}',
        f'  URL: {entry.get("url") or ""}',
    ]
    if image:
        parts.append(f'  Icon: {image}')
    if detail_image:
        parts.append(f'  Detail image: {detail_image}')
    return '\n'.join(parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Search the local TapTap catalog.')
    parser.add_argument('terms', nargs='+', help='Substring terms to search for.')
    parser.add_argument('--game', default='tower')
    parser.add_argument('--catalog', default='')
    parser.add_argument('--group', default='')
    parser.add_argument('--exclude-group', default='')
    parser.add_argument(
        '--field',
        default='all',
        choices=[
            'all',
            'name',
            'catalog',
            'group',
            'type',
            'cost',
            'effect',
            'source',
        ],
    )
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--index', type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = args.index or default_index_path(args.game)
    entries = load_entries(path)
    matches = [
        entry
        for entry in entries
        if entry_matches(
            entry,
            args.terms,
            catalog=args.catalog,
            group=args.group,
            exclude_group=args.exclude_group,
            field=args.field,
        )
    ]
    print(f'{len(matches)} matches in {path}')
    for entry in matches[: args.limit]:
        print(render_entry(entry))
    if len(matches) > args.limit:
        print(f'... {len(matches) - args.limit} more matches omitted')
    return 0 if matches else 1


if __name__ == '__main__':
    raise SystemExit(main())

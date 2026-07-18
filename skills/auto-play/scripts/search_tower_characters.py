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
        return guide / 'taptap_character_index.json'
    return game_root(game) / 'guide' / 'taptap_character_index.json'


def load_characters(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get('entries'), list):
        return [item for item in payload['entries'] if isinstance(item, dict)]
    return []


def render_entry(entry: dict[str, Any]) -> str:
    lines = [f'- {entry.get("name", "")}']
    terms = entry.get('related_terms') or []
    if terms:
        lines.append(f'  Mechanics: {", ".join(terms)}')
    for label, key in (
        ('Ability', 'abilities'),
        ('Exclusive card', 'exclusive_cards'),
        ('Derived card', 'derived_cards'),
        ('Related card', 'related_cards'),
    ):
        for item in entry.get(key) or []:
            lines.append(
                f'  {label}: {item.get("name", "")} - {item.get("effect") or "unknown"}'
            )
    return '\n'.join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Search the derived Tower character, ability, and card index.'
    )
    parser.add_argument('terms', nargs='+', help='Terms that must all match.')
    parser.add_argument('--game', default='tower')
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--index', type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = args.index or default_index_path(args.game)
    characters = load_characters(path)
    terms = [term.casefold() for term in args.terms]
    matches = [
        item
        for item in characters
        if all(term in str(item.get('search_text') or '').casefold() for term in terms)
    ]
    print(f'{len(matches)} matches in {path}')
    for item in matches[: args.limit]:
        print(render_entry(item))
    if len(matches) > args.limit:
        print(f'... {len(matches) - args.limit} more matches omitted')
    return 0 if matches else 1


if __name__ == '__main__':
    raise SystemExit(main())

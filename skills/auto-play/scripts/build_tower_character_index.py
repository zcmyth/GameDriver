#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

MECHANIC_TERMS = (
    '超越牌',
    '瞬发',
    '宝石牌',
    '物攻牌',
    '法术牌',
    '技能牌',
    '防御牌',
    '愿望牌',
    '扑克牌',
    '抽牌',
    '法力',
    '金币',
    '水晶',
    '生命上限',
    '生命减少',
    '护盾',
    '专注',
    '中毒',
    '灼烧',
    '寒冷',
    '石化',
    '失控',
    '龙骨',
    '幻身',
)
DEFAULT_TOWER_GUIDE_ROOT = Path('/Users/chunzhang/games/skills/game-tower/guide')
CATALOG_SUPPLEMENTS_FILENAME = 'taptap_catalog_supplements.json'


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def slugify(value: str) -> str:
    slug = re.sub(r'[^0-9A-Za-z._-]+', '-', value.strip().lower()).strip('-')
    return slug or 'tower'


def guide_root(game: str) -> Path:
    if slugify(game) == 'tower':
        return Path(os.environ.get('TOWER_GUIDE_ROOT', str(DEFAULT_TOWER_GUIDE_ROOT)))
    return repo_root() / 'skills' / 'auto-play' / 'games' / slugify(game) / 'guide'


def load_catalog(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    if isinstance(payload, dict) and isinstance(payload.get('entries'), list):
        return [entry for entry in payload['entries'] if isinstance(entry, dict)]
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    return []


def merge_catalog_entries(
    primary: list[dict[str, Any]], supplements: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged = list(primary)
    positions = {
        (str(entry.get('catalog') or ''), str(entry.get('name') or '')): index
        for index, entry in enumerate(primary)
    }
    for entry in supplements:
        key = (str(entry.get('catalog') or ''), str(entry.get('name') or ''))
        if not key[1]:
            continue
        if key in positions:
            if entry.get('override') is True:
                merged[positions[key]] = entry
            continue
        positions[key] = len(merged)
        merged.append(entry)
    return merged


def clean_character_name(value: str) -> str:
    name = value.strip(' “”、，,。；;:：')
    name = re.sub(r'^(?:种族|来自|活动)', '', name)
    name = re.sub(r'(?:的)?(?:专属卡牌|专属|种族天赋|天赋衍生临时牌|衍生).*$', '', name)
    name = name.strip(' “”、，,。；;:：')
    if name == '普通':
        return '普通奇莫'
    return name


def character_names_from_source(source: str) -> list[str]:
    source = source.strip()
    names: list[str] = []

    if '普通种族天赋' in source:
        names.append('普通奇莫')

    for match in re.finditer(
        r'(?:^|种族|来自|[、，,])["“”]?(?P<name>[^、，,。；;：“”"\s的]*?奇莫)',
        source,
    ):
        name = clean_character_name(match.group('name'))
        if name.endswith('奇莫'):
            names.append(name)

    for match in re.finditer(r'(?P<name>[^、，,。；;：“”"\s]+)种族卡牌衍生', source):
        name = clean_character_name(match.group('name'))
        if name and not name.endswith('奇莫'):
            name = f'{name}奇莫'
        if name.endswith('奇莫'):
            names.append(name)

    deduped: list[str] = []
    seen = set()
    for name in names:
        if name and name not in seen:
            deduped.append(name)
            seen.add(name)
    return deduped


def bracket_terms(text: str) -> list[str]:
    terms = re.findall(r'[［\[]([^［\]\[\]]+)[\]］]', text)
    deduped: list[str] = []
    seen = set()
    for term in terms:
        term = term.strip()
        if term and term not in seen:
            deduped.append(term)
            seen.add(term)
    return deduped


def mechanic_terms(text: str) -> list[str]:
    normalized = text.replace('超越卡牌', '超越牌')
    return [term for term in MECHANIC_TERMS if term in normalized]


def entry_ref(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        'name': entry.get('name') or '',
        'catalog': entry.get('catalog') or '',
        'group': entry.get('group') or '',
        'type': entry.get('type') or '',
        'cost': entry.get('cost') or '',
        'effect': entry.get('effect') or '',
        'source': entry.get('source') or '',
        'url': entry.get('url') or '',
        'icon_path': entry.get('icon_path') or '',
        'detail_image_paths': entry.get('detail_image_paths') or [],
    }


def add_unique(items: list[dict[str, Any]], entry: dict[str, Any]) -> None:
    name = str(entry.get('name') or '')
    if not name:
        return
    if any(item.get('name') == name for item in items):
        return
    items.append(entry_ref(entry))


def classify_card_link(source: str) -> str:
    if '衍生' in source:
        return 'derived_cards'
    if '专属' in source or '种族' in source:
        return 'exclusive_cards'
    return 'related_cards'


def build_character_index(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}

    def character(name: str) -> dict[str, Any]:
        item = by_name.setdefault(
            name,
            {
                'name': name,
                'aliases': [name.removesuffix('奇莫')] if name.endswith('奇莫') else [],
                'abilities': [],
                'exclusive_cards': [],
                'derived_cards': [],
                'related_cards': [],
                'related_terms': [],
                'search_text': '',
            },
        )
        return item

    for entry in entries:
        source = str(entry.get('source') or '')
        names = character_names_from_source(source)
        if not names:
            continue

        for name in names:
            item = character(name)
            if entry.get('catalog') == '天赋图鉴' and entry.get('group') == '种族天赋':
                add_unique(item['abilities'], entry)
            elif entry.get('catalog') == '卡牌图鉴':
                add_unique(item[classify_card_link(source)], entry)
            else:
                add_unique(item['related_cards'], entry)

            entry_text = '\n'.join(
                str(entry.get(key) or '')
                for key in ('name', 'type', 'effect', 'source', 'group')
            )
            terms = bracket_terms(entry_text) + mechanic_terms(entry_text)
            for term in terms:
                if term not in item['related_terms']:
                    item['related_terms'].append(term)

    characters = sorted(by_name.values(), key=lambda item: item['name'])
    for item in characters:
        parts = [
            item['name'],
            ' '.join(item.get('aliases') or []),
            ' '.join(item.get('related_terms') or []),
        ]
        for section in (
            'abilities',
            'exclusive_cards',
            'derived_cards',
            'related_cards',
        ):
            for entry in item[section]:
                parts.extend(
                    [
                        str(entry.get('name') or ''),
                        str(entry.get('type') or ''),
                        str(entry.get('effect') or ''),
                        str(entry.get('source') or ''),
                    ]
                )
        item['search_text'] = '\n'.join(part for part in parts if part)
    return characters


def markdown_escape(value: Any) -> str:
    text = str(value or '')
    return text.replace('|', r'\|').replace('\n', '<br>')


def render_markdown(characters: list[dict[str, Any]]) -> str:
    lines = [
        '# Tower Character Index',
        '',
        'Derived from TapTap 卡牌图鉴 and 天赋图鉴 source fields. The public '
        'TapTap 角色图鉴 landing block is currently empty, so this index links '
        'characters to race talents, exclusive cards, and derived cards found '
        'in the fetched catalog.',
        '',
        f'- Characters: {len(characters)}',
        '',
        '| Character | Ability | Exclusive / Derived Cards | Related Terms |',
        '|---|---|---|---|',
    ]
    for item in characters:
        abilities = '<br>'.join(
            f'[{markdown_escape(entry["name"])}]({entry["url"]})'
            f': {markdown_escape(entry["effect"])}'
            for entry in item.get('abilities') or []
        )
        cards = []
        for section in ('exclusive_cards', 'derived_cards', 'related_cards'):
            for entry in item.get(section) or []:
                cards.append(
                    f'[{markdown_escape(entry["name"])}]({entry["url"]})'
                    f': {markdown_escape(entry["effect"])}'
                )
        lines.append(
            '| '
            + ' | '.join(
                [
                    markdown_escape(item.get('name')),
                    abilities or '',
                    '<br>'.join(cards),
                    ', '.join(
                        markdown_escape(term)
                        for term in item.get('related_terms') or []
                    ),
                ]
            )
            + ' |'
        )
    lines.append('')
    return '\n'.join(lines)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Build a derived Tower character index from TapTap catalog data.'
    )
    parser.add_argument('--game', default='tower')
    parser.add_argument('--catalog', type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = guide_root(args.game)
    catalog_path = args.catalog or (root / 'taptap_catalog.json')
    entries = load_catalog(catalog_path)
    supplement_path = root / CATALOG_SUPPLEMENTS_FILENAME
    supplements = load_catalog(supplement_path) if supplement_path.exists() else []
    entries = merge_catalog_entries(entries, supplements)
    characters = build_character_index(entries)
    payload = {
        'source_catalog': str(catalog_path),
        'source_supplements': str(supplement_path) if supplements else '',
        'character_count': len(characters),
        'characters': characters,
    }
    write_json(root / 'taptap_characters.json', payload)
    write_json(root / 'taptap_character_index.json', {'entries': characters})
    (root / 'taptap_characters.md').write_text(render_markdown(characters))
    print(f'Wrote {len(characters)} characters to {root}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

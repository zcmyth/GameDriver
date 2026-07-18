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

POSITIVE_RULES = (
    (25, 'permanent growth', r'永久|冒险中|生命上限|战斗胜利时|未满级卡牌升级'),
    (16, 'repeatable trigger', r'每使用|使用.+时|每抽|每装备|每拥有|每获得|每减少'),
    (14, 'turn or battle engine', r'回合开始时|回合结束时|战斗开始时|敌方回合'),
    (
        12,
        'multiplier or recursion',
        r'翻倍|复制|回到手牌|再次使用|费用减少|法力消耗减少',
    ),
    (9, 'draw or mana economy', r'抽.{0,4}张牌|获得.{0,5}法力|法力上限'),
    (8, 'resource economy', r'获得.{0,5}(金币|水晶)|金币获得|水晶获得'),
    (7, 'reliable starting value', r'\[固有\]|\[旅行用品\]'),
    (5, 'flexible action', r'\[瞬发\]'),
    (4, 'scaling combat stat', r'物攻|法术伤害|穿透|护盾|专注|易伤|暴击'),
)

NEGATIVE_RULES = (
    (
        -18,
        'spends long-term health or all resources',
        r'减少自身|减少当前生命|消耗所有|献祭所有|舍命',
    ),
    (-10, 'self-sacrifice cost', r'献祭|生命消耗|扣除.{0,4}生命|失去.{0,4}生命'),
    (-7, 'one-use value', r'\[消耗品\]|\[移除\]|\[弃置\]'),
    (-4, 'temporary value', r'临时'),
)

SELF_DAMAGE_PAYOFFS = ('生命减少时', '每减少1点生命', '龙骨', '幻身', '再生')
DEFAULT_TOWER_GUIDE_ROOT = Path('/Users/chunzhang/games/skills/game-tower/guide')


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def game_root(game: str) -> Path:
    slug = re.sub(r'[^0-9A-Za-z._-]+', '-', game.strip().lower()).strip('-')
    return repo_root() / 'skills' / 'auto-play' / 'games' / (slug or 'tower')


def load_entries(path: Path, key: str = 'entries') -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    if isinstance(payload, dict) and isinstance(payload.get(key), list):
        return [entry for entry in payload[key] if isinstance(entry, dict)]
    return []


def compact(value: str) -> str:
    return re.sub(r'[\s·•,，。:：;；、"“”\'‘’()（）\[\]［］]+', '', value).casefold()


def entry_text(entry: dict[str, Any]) -> str:
    return '\n'.join(
        str(entry.get(field) or '')
        for field in ('name', 'catalog', 'group', 'type', 'effect', 'source')
    ).replace('超越卡牌', '超越牌')


def find_entry(choice: str, entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    wanted = compact(choice)
    exact = [
        entry for entry in entries if compact(str(entry.get('name') or '')) == wanted
    ]
    if exact:
        return exact[0]
    partial = [
        entry
        for entry in entries
        if wanted and wanted in compact(str(entry.get('name') or ''))
    ]
    return partial[0] if len(partial) == 1 else None


def find_character(
    name: str, characters: list[dict[str, Any]]
) -> dict[str, Any] | None:
    if not name:
        return None
    wanted = compact(name)
    for character in characters:
        names = [character.get('name') or '', *(character.get('aliases') or [])]
        if wanted in {compact(str(candidate)) for candidate in names}:
            return character
    return None


def expand_setup(
    setup: str,
    character: dict[str, Any] | None,
    entries: list[dict[str, Any]],
) -> str:
    parts = [setup.replace('超越卡牌', '超越牌')]
    setup_compact = compact(setup)
    for entry in entries:
        name = str(entry.get('name') or '')
        if len(name) >= 2 and compact(name) in setup_compact:
            parts.append(entry_text(entry))
    if character:
        parts.append(str(character.get('search_text') or ''))
    return '\n'.join(parts)


def is_character_card(entry: dict[str, Any], character: dict[str, Any] | None) -> bool:
    if not character:
        return False
    name = str(entry.get('name') or '')
    for key in ('exclusive_cards', 'derived_cards'):
        if any(
            str(item.get('name') or '') == name for item in character.get(key) or []
        ):
            return True
    return False


def score_entry(
    entry: dict[str, Any],
    setup_context: str,
    character: dict[str, Any] | None,
) -> tuple[int, list[str]]:
    text = entry_text(entry)
    score = 0
    reasons: list[str] = []

    for points, label, pattern in POSITIVE_RULES:
        if re.search(pattern, text):
            score += points
            reasons.append(f'+{points} {label}')

    setup_has_self_damage_payoff = any(
        payoff in setup_context for payoff in SELF_DAMAGE_PAYOFFS
    )
    for points, label, pattern in NEGATIVE_RULES:
        if re.search(pattern, text):
            adjusted = points
            if setup_has_self_damage_payoff and label in {
                'spends long-term health or all resources',
                'self-sacrifice cost',
            }:
                adjusted = int(points / 3)
                label = f'{label}, mitigated by setup payoff'
            score += adjusted
            reasons.append(f'{adjusted:+d} {label}')

    setup_terms = [term for term in MECHANIC_TERMS if term in setup_context]
    shared_terms = [term for term in setup_terms if term in text]
    if shared_terms:
        synergy = min(30, 10 * len(shared_terms))
        score += synergy
        reasons.append(f'+{synergy} setup synergy: {", ".join(shared_terms)}')

    if is_character_card(entry, character):
        score += 16
        reasons.append('+16 character-exclusive card')

    if not reasons:
        reasons.append('+0 no detected long-term engine')
    return score, reasons


def rank_choices(
    choices: list[str],
    setup: str,
    character_name: str,
    entries: list[dict[str, Any]],
    characters: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    character = find_character(character_name, characters)
    setup_context = expand_setup(setup, character, entries)
    ranked = []
    for position, choice in enumerate(choices):
        entry = find_entry(choice, entries)
        if entry is None:
            ranked.append(
                {
                    'choice': choice,
                    'score': -100,
                    'reasons': ['catalog entry not found; inspect manually'],
                    'entry': None,
                    '_position': position,
                }
            )
            continue
        score, reasons = score_entry(entry, setup_context, character)
        ranked.append(
            {
                'choice': choice,
                'score': score,
                'reasons': reasons,
                'entry': entry,
                '_position': position,
            }
        )
    ranked.sort(key=lambda item: (-item['score'], item['_position']))
    for item in ranked:
        item.pop('_position', None)
    return ranked, character


def render_result(position: int, item: dict[str, Any]) -> str:
    entry = item.get('entry') or {}
    lines = [f'{position}. {item["choice"]} - score {item["score"]}']
    if entry:
        lines.extend(
            [
                f'   Catalog: {entry.get("catalog", "")} / {entry.get("group", "")}',
                f'   Type: {entry.get("type") or "unknown"}',
                f'   Cost: {entry.get("cost") or "unknown"}',
                f'   Effect: {entry.get("effect") or "unknown"}',
            ]
        )
    lines.append(f'   Why: {"; ".join(item["reasons"])}')
    return '\n'.join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Rank offered Tower choices for long-term build value.'
    )
    parser.add_argument(
        'choices', nargs='+', help='Offered card, treasure, or talent names.'
    )
    parser.add_argument('--game', default='tower')
    parser.add_argument(
        '--setup', default='', help='Current cards, treasures, and mechanics.'
    )
    parser.add_argument('--character', default='', help='Current character name.')
    parser.add_argument('--json', action='store_true', dest='as_json')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if (
        re.sub(r'[^0-9A-Za-z._-]+', '-', args.game.strip().lower()).strip('-')
        == 'tower'
    ):
        guide = Path(os.environ.get('TOWER_GUIDE_ROOT', str(DEFAULT_TOWER_GUIDE_ROOT)))
    else:
        guide = game_root(args.game) / 'guide'
    entries = load_entries(guide / 'taptap_search_index.json')
    characters = load_entries(guide / 'taptap_character_index.json')
    ranked, character = rank_choices(
        args.choices,
        args.setup,
        args.character,
        entries,
        characters,
    )
    result = {
        'character': character.get('name') if character else args.character or None,
        'setup': args.setup,
        'ranking': ranked,
    }
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if args.character and not character:
            print(f'Warning: character not found: {args.character}')
        if ranked:
            print(f'Best long-term choice: {ranked[0]["choice"]}')
        for position, item in enumerate(ranked, start=1):
            print(render_result(position, item))
    return 0 if all(item.get('entry') for item in ranked) else 1


if __name__ == '__main__':
    raise SystemExit(main())

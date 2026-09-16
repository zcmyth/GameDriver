#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import faulthandler
import io
import json
import os
import re
import selectors
import shlex
import signal
import subprocess
import sys
import time
from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from shutil import rmtree
from typing import Any

import cv2
import main_challenge_rules
import numpy as np
import yaml
from automation_types import (
    AutomationCandidateSpec,
    AutomationRepeatedActionSwipeSpec,
    AutomationRowCandidateSpec,
    ButtonCandidate,
    Decision,
    GameAutomationConfig,
    GameInfoEntry,
    ItemInspection,
    ItemPreferenceRule,
    StateVerification,
    TurnResult,
    UnblockAssessment,
)
from PIL import Image, ImageChops, ImageStat

if hasattr(signal, 'SIGUSR1'):
    faulthandler.register(signal.SIGUSR1, file=sys.stderr, all_threads=True)


def debug_progress(message: str) -> None:
    if os.getenv('AUTOPLAY_DEBUG_PROGRESS'):
        print(f'[auto-play] {message}', file=sys.stderr, flush=True)


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
CHALLENGE_DETAIL_ACTION_KEYS = {
    'steamroll',
    'start',
    'battle',
    'fight',
    'speed-up',
    'speed up',
    'battle speed-up',
    'quick battle',
}
CHALLENGE_DETAIL_FAST_ACTION_KEYS = {
    'steamroll',
    'speed-up',
    'speed up',
    'battle speed-up',
    'quick battle',
}
DEFAULT_AVOID = [
    'Abandon',
    'Abandon Adventure',
    '放弃',
    '放弃冒险',
]
HARD_AVOID_LABELS = {
    'abandon',
    'abandon adventure',
    '放弃',
    '放弃冒险',
}
AD_REVIVE_HINTS = (
    'ad revive',
    'revive ad',
    'watch an ad to revive',
    'watch ad to revive',
    '看广告复活',
    '广告复活',
)
DEFEAT_CONTEXT_HINTS = (
    'defeat',
    'defeated',
    'game over',
    'game failed',
    'failed',
    '游戏失败',
)
LIVE_RUN_CONTINUE_LABELS = {
    'continue adventure',
    'resume adventure',
    '继续冒险',
    '恢复冒险',
}
CANCEL_LABELS = {
    'cancel',
    '取消',
}
PLAIN_BACK_LABELS = {
    'back',
    'return',
    '返回',
}
WATCH_AD_LABELS = {
    'watch',
    'watch ad',
    'watch ads',
    'view ad',
    'view ads',
    '观看',
    '看广告',
    '看广告复活',
}
DEFEAT_RECOVERY_LABELS: set[str] = set()
RECRUIT_LABELS: set[str] = set()
NEVER_SELL_LABEL_KEYWORDS = (
    'sell',
    '出售',
    '卖出',
    '卖掉',
)
REAL_MONEY_PURCHASE_KEYWORDS = (
    '充值',
    '人民币',
    'rmb',
    '月卡',
    '礼包',
    '通行证',
    '购买金币',
    '购买水晶',
    '￥',
    '¥',
)
TOWER_PURCHASABLE_SHOP_LABELS = {
    '金币商店',
    '钱袋商店',
    '水晶商店',
    '神秘商店',
    '神桃商店',
}
TOWER_SHOP_SPARKLE_LABEL = '领取商店闪光奖励'
DEFAULT_TURN_HISTORY_LIMIT = 500
DEFAULT_PERIODIC_OCR_TUNE_EVERY_TURNS = 50
DEFAULT_PERIODIC_OCR_TUNE_ITERATIONS = 10
DEFAULT_PERIODIC_OCR_TUNE_RECENT_TURNS = 50
DEFAULT_STUCK_OCR_TUNE_ITERATIONS = 10
DEFAULT_STUCK_OCR_TUNE_RECENT_TURNS = 10
DEFAULT_OCR_TUNE_TIMEOUT_SECONDS = 60.0
EXPECTED_ANDROID_PACKAGES = {
    'tower': 'cn.thearky.projectrl',
}
CONFIRM_LABELS = {
    'confirm',
    'ok',
    'accept',
    'select',
    'choose',
    '确定',
    '确认',
    '选择',
}
COMMAND_LABELS = {
    'adventure',
    'enter adventure',
    'fight',
    'battle',
    'challenge',
    'start',
    'play',
    'continue',
    'resume',
    'retry',
    'again',
    'next',
    'end',
    'claim',
    'collect',
    'pick up',
    'dismiss reward',
    'close reward',
    'drag down',
    'swipe down',
}
COMBAT_CARD_DOUBLE_TAP_LABELS: set[str] = set()
DIRECT_ATTACK_COMBAT_CARD_LABELS = {
    'normal attack',
    'normal sword',
    'ordinary wooden sword',
    'blind blade',
    'swift attack',
    'weakness strike',
    'shield bash',
    'clown stab',
    'flash strike',
    'visible attack-number card',
    '普通攻击',
    '普通小剑',
    '普通木剑',
    '归一',
    '重影',
    '撞击',
    '盲击',
    '登龙斩',
    '推击',
    '盲刃',
    '迅捷攻击',
    '盾牌猛击',
    '弱点打击',
    '小丑飞刺',
    '闪耀挥击',
}
DIRECT_ATTACK_COMBAT_CARD_KEYWORDS = (
    'attack',
    'strike',
    'sword',
    'blade',
    'stab',
    'slash',
    'damage',
    '攻击',
    '打击',
    '木剑',
    '小剑',
    '剑',
    '刃',
    '刺',
    '挥击',
    '闪电',
    '归一',
    '重影',
    '撞击',
    '盲击',
    '登龙斩',
    '推击',
)
SELF_DAMAGE_COMBAT_CARD_KEYWORDS = (
    'life sacrifice',
    'sacrifice',
    'self-damage',
    'spend health',
    '舍命',
)
DEFENSIVE_OR_SETUP_COMBAT_CARD_LABELS = {
    'shield',
    'focus gem',
    'battle focus',
    'swift',
    'quick thinking',
    'weak',
    'turn preparation',
    '举盾',
    '专注宝石',
    '战斗专注',
    '迅捷',
    '快速思考',
    '虚弱',
    '转身准备',
    '绿舌头',
}
DEFENSIVE_OR_SETUP_COMBAT_CARD_KEYWORDS = (
    'shield',
    'block',
    'defend',
    'defense',
    'focus',
    'prepare',
    'preparation',
    'quick thinking',
    'weak',
    '盾',
    '防守',
    '防御',
    '专注',
    '准备',
    '虚弱',
)
SKILL_KIND_PATTERNS = (
    'skill',
    'card',
    'scroll',
    'spell',
    'ability',
    'talent',
    'focus',
    '技能',
    '卡',
    '卡牌',
    '卷轴',
    '法术',
    '能力',
    '天赋',
    '专注',
)
GAME_INFO_OCR_KEYWORDS = (
    'attack',
    'atk',
    'damage',
    'defense',
    'defence',
    'health',
    'speed',
    'range',
    'cooldown',
    'cd',
    'crit',
    'treasure',
    'skill',
    'card',
    'weapon',
    '攻击',
    '伤害',
    '防御',
    '生命',
    '血量',
    '暴击',
    '宝物',
    '技能',
    '卡牌',
    '武器',
)
GAME_INFO_ENTITY_HINTS = (
    'item',
    'skill',
    'card',
    'scroll',
    'spell',
    'treasure',
    'weapon',
    'reward',
    'buff',
    'debuff',
    '印记',
    '宝物',
    '技能',
    '卡',
    '卡牌',
    '卷轴',
    '法术',
    '武器',
    '奖励',
)
GAME_INFO_EFFECT_HINTS = (
    'attack',
    'atk',
    'damage',
    'defense',
    'defence',
    'health',
    'crit',
    'focus',
    'gain',
    'increase',
    'cost',
    'consume',
    'physical',
    'magic',
    '物攻',
    '法攻',
    '物理',
    '法术',
    '伤害',
    '攻击',
    '防御',
    '生命',
    '血量',
    '暴击',
    '专注',
    '获得',
    '增加',
    '减少',
    '消耗',
    '每层',
    '属性',
)
GAME_INFO_EFFECT_ACTION_HINTS = (
    '+',
    'gain',
    'gives',
    'increase',
    'cost',
    'consume',
    'physical attack',
    'physical damage',
    'magic damage',
    '获得',
    '增加',
    '减少',
    '消耗',
    '每层',
    '每1点',
    '生命减少',
    '物理伤害',
    '法术伤害',
)
GENERIC_GAME_INFO_LABELS = {
    'treasure detail',
    'activate prompt',
    'close hint',
    'close instruction',
    'adventurer avatar',
    'adventurer detail panel',
    'bottom navigation',
    'branch choices',
    'branch map',
    'character',
    'cleared room map',
    'connector arrow',
    'dungeon map',
    'hero',
    'highlighted unactivated treasure',
    'left route arrow',
    'minimap',
    'recruitment board',
    'remaining choices',
    'resume prompt',
    'reward description',
    'right path',
    'room counter',
    'selected stage',
    'stage title',
    'table room',
    'tavern keeper',
    'treasure event',
    'treasure tab',
    'tutorial prompt',
}
NOISE_LABEL_PATTERNS = [
    re.compile(r'^@\s*\d{2,}$'),
    re.compile(r'^\d{1,2}\s*-\s*\d{1,2}$'),
    re.compile(r'^[±+\-]?\s*\d+([.,]\d+)?[kmb]{1,3}$', re.I),
    re.compile(
        r'^\d+([.,]\d+)?[kmb]{1,3}\s*[-–]\s*[+\-]?\d+([.,]\d+)?[a-z0-9.]*$',
        re.I,
    ),
    re.compile(r'^[a-z]\s*[-–]\s*\d+([.,]\d+)?[kmb]{1,3}$', re.I),
    re.compile(r'^\d+([.,]\d+)?\s*[-–]\s*\d+([.,]\d+)?[kmb]$', re.I),
    re.compile(r'^\d+([.,]\d+)?\s*[-–]\s*\d+([.,]\d+)?[kmb][a-z]*$', re.I),
    re.compile(r'^\.\d+([.,]\d+)?[kmb]{1,3}$', re.I),
    re.compile(r'^\d+([.,]\d+)?[kmb]{1,3}$', re.I),
    re.compile(r'^\d+([.,]\d+)?[kmb]\d+([.,]\d+)?$', re.I),
    re.compile(r'^\d+([.,]\d+)?[kmb]\d+([.,]\d+)?[kmb]\d*$', re.I),
    re.compile(r'^[±+\-]\s*\d+([.]\d+)?%?[;；]?$'),
    re.compile(r'^q{2,}\d*$', re.I),
    re.compile(r'^[x×]{2,}\d*$', re.I),
    re.compile(r'^\d{1,2}:\d{2}(:\d{2})?$'),
    re.compile(r'^[+\-]?\d+([./:]\d+)+[kmb%]?$', re.I),
    re.compile(r'^\d+\s*>{1,2}\s*\d+$'),
    re.compile(r'^\d+\)$'),
    re.compile(r'^[\[(]?\s*\d+\s*/\s*\d+\s*[\])]?$'),
    re.compile(r'^[\[(]\s*\d+\s*[\])]?$'),
    re.compile(
        r'^(?!1[- ]?tap$)(?=[a-z0-9()\[\]{},.:;!?+\-*/\\|_~<>]+$)'
        r'(?=.*\d)(?=.*[()\[\]{},.:;!?+\-*/\\|_~<>]).{2,}$',
        re.I,
    ),
    re.compile(r'^[a-z]{1,2}\d{3,}[a-z0-9]*$', re.I),
    re.compile(r'^\d+[a-z]{1,3}\d+$', re.I),
    re.compile(r'^[•·●]\s*\d+[a-z0-9]*$', re.I),
    re.compile(r'^\d+[./:]?\d*[kmb%]?$', re.I),
    re.compile(r'^lv[.\s]*\d+$', re.I),
    re.compile(r'^v[.\s]*\d+$', re.I),
    re.compile(r'^[x×]\s*\d+$', re.I),
    re.compile(r'^[x×][x*×]\s*\d+$', re.I),
    re.compile(r'^[a-z]\s*\d+$', re.I),
    re.compile(r'^[()\[\]{}%.,:;!?+\-*/\\|_~<>•·]+$'),
]
NAVIGATION_ARROW_LABELS = {
    'down arrow',
    'up arrow',
    'left arrow',
    'right arrow',
    'move left',
    'move right',
    'left path',
    'right path',
    'next room',
}
NAVIGATION_ARROW_KEYWORDS = (
    ' arrow',
    ' path',
    ' route',
    ' road',
)
NAVIGATION_ARROW_GLYPHS = ('↑', '↓', '←', '→')
CURRENT_ROOM_ICON_LABELS: set[str] = set()
TOP_PLAYFIELD_PATH_COORDS = {
    'left': (0.08, 0.30),
    'right': (0.92, 0.30),
    'up': (0.50, 0.13),
    'down': (0.50, 0.41),
}


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


def looks_like_noise_label(
    value: str,
    automation_config: GameAutomationConfig | None = None,
) -> bool:
    raw = value.strip()
    normalized = normalize_label(value)
    if len(normalized) <= 1:
        return True
    if re.fullmatch(r'[A-Z]{2,3}', raw) and normalized not in (
        COMMAND_LABELS | CONFIRM_LABELS
    ):
        return True
    patterns = [
        *NOISE_LABEL_PATTERNS,
        *((automation_config.noise_patterns if automation_config else ()) or ()),
    ]
    return any(pattern.search(normalized) for pattern in patterns)


def is_navigation_arrow_label(
    value: str,
    automation_config: GameAutomationConfig | None = None,
) -> bool:
    normalized = normalize_label(value)
    labels = set(NAVIGATION_ARROW_LABELS)
    keywords = tuple(NAVIGATION_ARROW_KEYWORDS)
    glyphs = tuple(NAVIGATION_ARROW_GLYPHS)
    if automation_config is not None:
        labels |= set(automation_config.navigation_labels)
        keywords = (*keywords, *automation_config.navigation_keywords)
        glyphs = (*glyphs, *automation_config.navigation_glyphs)
    if normalized in labels:
        return True
    if any(glyph in normalized for glyph in glyphs):
        return True
    return any(keyword in normalized for keyword in keywords)


def navigation_direction(value: str) -> str | None:
    normalized = normalize_label(value)
    if any(token in normalized for token in ('left', '左', '←')):
        return 'left'
    if any(token in normalized for token in ('right', '右', '→')):
        return 'right'
    if any(token in normalized for token in ('up', '上', '↑')):
        return 'up'
    if any(token in normalized for token in ('down', '下', '↓')):
        return 'down'
    return None


def is_end_turn_label(value: str) -> bool:
    key = normalize_label(value)
    if key in {'end', '结束回合', '回合结束'}:
        return True
    return '结束第' in key and '回合' in key


def is_combat_card_label(value: str) -> bool:
    return normalize_label(value) in COMBAT_CARD_DOUBLE_TAP_LABELS


def is_configured_combat_card_label(
    value: str,
    automation_config: GameAutomationConfig | None = None,
) -> bool:
    key = normalize_label(value)
    if key.startswith('visible playable card'):
        return True
    if key in COMBAT_CARD_DOUBLE_TAP_LABELS:
        return True
    if automation_config is None:
        return False
    card_key = re.sub(r'[!！?？.,，。:：;；\[\]【】()（）]+$', '', key)
    if card_key in automation_config.combat_card_double_tap_labels:
        return True
    return any(
        card_key.startswith(known_card)
        and len(card_key) == len(known_card) + 1
        for known_card in automation_config.combat_card_double_tap_labels
    )


def is_direct_attack_combat_card_label(value: str) -> bool:
    key = normalize_label(value)
    if '攻击宝石' in key or any(
        keyword in key for keyword in SELF_DAMAGE_COMBAT_CARD_KEYWORDS
    ):
        return False
    if key in DIRECT_ATTACK_COMBAT_CARD_LABELS:
        return True
    return any(keyword in key for keyword in DIRECT_ATTACK_COMBAT_CARD_KEYWORDS)


def is_defensive_or_setup_combat_card_label(value: str) -> bool:
    key = normalize_label(value)
    if key in DEFENSIVE_OR_SETUP_COMBAT_CARD_LABELS:
        return True
    return any(keyword in key for keyword in DEFENSIVE_OR_SETUP_COMBAT_CARD_KEYWORDS)


def is_tower_timing_sensitive_finisher_label(value: str) -> bool:
    key = normalize_label(value)
    return any(
        name in key
        for name in {
            '慈悲',
            '烈性毒药',
            '安乐毒药',
            '救赎',
            '正念',
            '重整旗鼓',
            '逃生',
            '绿舌头',
        }
    )


def tower_combat_sequence_bonus(game: str, label: str) -> float:
    key = normalize_label(label)
    if '幸运币' in key or '运币' in key:
        return 25.0
    if '巨人协议' in key:
        return 15.0
    if '制造核心' in key:
        return -12.0
    profession = tower_run_profession(game)
    state = load_tower_run_state(game)
    predecessor = normalize_label(str(state.get('predecessor_treasure') or ''))
    battle = state.get('battle')
    cold_applied = bool(
        isinstance(battle, dict) and battle.get('cold_applied')
    )
    if '电解冰' in key and not cold_applied:
        return -6.0
    if profession == '旅行者':
        if tower_traveler_uses_prayer_build(game):
            priorities = (
                ('无限宝石', 12.0),
                ('黑神话', 11.0),
                ('回忆', 10.0),
                ('献祭', 10.0),
                ('未来汽水', 10.0),
                ('天使', 5.0),
                ('救赎', -3.0),
                ('奉献', -4.0),
                ('慈悲', -6.0),
                ('灵魂燃烧', -8.0),
            )
        else:
            priorities = (
                ('无限宝石', 12.0),
                ('回忆', 11.0),
                ('献祭', 11.0),
                ('未来汽水', 11.0),
                ('剧毒晶石', 10.0),
                ('毒龙钻石', 9.0),
                ('黑神话', 9.0),
                ('毒药攻击', 4.0),
                ('涂毒小刀', 4.0),
                ('烈性毒药', 2.0),
                ('毒死', 0.0),
                ('慈悲', -1.0),
                ('安乐毒药', -4.0),
                ('救赎', -5.0),
            )
    elif profession == '猎人':
        priorities = (
            ('宝石手套', 6.0),
            ('瞄准', 5.0),
            ('捕猎陷阱', 4.0),
            ('大力射击', 2.0),
            ('猎人嗅觉', -1.0),
        )
    elif profession == '法师':
        if '火焰草莓' in predecessor:
            priorities = (
                ('燃烧晶石', 7.0),
                ('太阳盾', 6.0),
                ('火焰打击', -3.0),
            )
        else:
            priorities = (
                ('快速思考', 12.0),
                ('寒冷晶石', 8.0),
                ('寒冷宝石', 8.0),
                ('冷风', 6.5),
                ('寒流', 6.5),
                ('寒冰盾', 6.0),
                ('过度解冻', 4.0),
                ('电解冰', 3.0),
                ('小雷虫', 2.5),
                ('雷龙', 1.0),
                ('火焰打击', -2.0),
            )
    elif profession == '战士':
        if '巨人之拳' in predecessor:
            equipment_text = ' '.join(
                normalize_label(str(item))
                for item in (
                    *(state.get('key_treasures') or []),
                    *(state.get('shop_purchases') or []),
                )
            )
            battle_state = state.get('battle') or {}
            floor = int(state.get('floor') or 0)
            guard_bonus = (
                13.0
                if bool(battle_state.get('player_hp_critical'))
                else 10.0 if floor > 0 and floor % 10 == 0 else 7.0
            )
            priorities = (
                ('愤怒宝石', 12.0),
                ('攻击宝石', 11.0),
                ('迅捷', 10.0 if '魔法熊手' in equipment_text else 1.0),
                ('守势', guard_bonus),
                (
                    '启动防守',
                    12.0 if bool(battle_state.get('player_hp_critical')) else 8.0,
                ),
                ('撞击', 6.0),
                ('神圣斩击', 4.0),
                ('换血', 2.0),
            )
        else:
            battle = state.get('battle') or {}
            floor = int(state.get('floor') or 0)
            weakness_applied = bool(battle.get('weakness_applied'))
            guard_bonus = (
                11.0
                if bool(battle.get('player_hp_critical'))
                or (floor > 0 and floor % 10 == 0)
                else 7.0
            )
            priorities = (
                ('愤怒宝石', 14.0),
                ('攻击宝石', 13.0),
                ('发现弱点', 12.0),
                ('守势', guard_bonus),
                ('迅捷攻击', 9.0),
                ('迅捷', 8.0),
                ('换血', 6.0),
                ('弱点加倍', 3.0),
                ('幽灵剑', 2.0),
                ('弱点打击', 4.0 if weakness_applied else -2.0),
            )
    else:
        priorities = ()
    for pattern, bonus in priorities:
        if normalize_label(pattern) in key:
            return bonus
    return 0.0


def tower_run_has_discard_all_finisher(game: str) -> bool:
    if normalize_label(game) != 'tower':
        return False
    state = load_tower_run_state(game)
    core_text = ' '.join(
        normalize_label(str(card)) for card in state.get('core_cards') or []
    )
    return any(name in core_text for name in {'正念', '重整旗鼓', '逃生'})


def is_configured_command_label(
    value: str,
    automation_config: GameAutomationConfig | None = None,
) -> bool:
    key = normalize_label(value)
    if key in COMMAND_LABELS:
        return True
    if automation_config is None:
        return False
    return key in automation_config.command_labels


def is_swipe_candidate(button: ButtonCandidate) -> bool:
    return button.source == 'swipe'


def is_back_candidate(button: ButtonCandidate) -> bool:
    return button.source == 'back'


def swipe_arguments_for_button(button: ButtonCandidate) -> dict[str, float | int]:
    if button.bbox is not None:
        start_x, start_y, end_x, end_y = button.bbox
    else:
        start_x, start_y, end_x, end_y = (button.x, button.y, button.x, button.y)
    return {
        'start_x': start_x,
        'start_y': start_y,
        'end_x': end_x,
        'end_y': end_y,
        'duration_ms': 800,
    }


def configured_claimed_visible(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    return main_challenge_rules.configured_claimed_visible(automation_config, buttons)


def configured_claimed_label_matches(
    automation_config: GameAutomationConfig,
    value: str,
) -> bool:
    return main_challenge_rules.configured_claimed_label_matches(
        automation_config,
        value,
    )


def configured_reward_overlay_visible(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    return main_challenge_rules.configured_reward_overlay_visible(
        automation_config,
        buttons,
    )


def configured_reward_close_visible(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    return main_challenge_rules.configured_reward_close_visible(
        automation_config,
        buttons,
    )


def configured_reward_close_label_match(
    label: str,
    automation_config: GameAutomationConfig | None,
) -> bool:
    return main_challenge_rules.configured_reward_close_label_match(
        label,
        automation_config,
    )


def configured_assist_pack_popup_visible(buttons: list[ButtonCandidate]) -> bool:
    labels = {
        normalize_label(button.label)
        for button in buttons
        if button.source != 'template'
    }
    text = ' '.join(sorted(labels))
    return 'view' in labels and 'assist pack' in text and 'unlocked in shop' in text


def label_group_visible(
    group: tuple[str, ...],
    *,
    labels: set[str],
    text: str,
) -> bool:
    return all(token in labels or token in text for token in group)


def configured_waiting_screen_visible(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    if (
        not automation_config.waiting_required_groups
        or not automation_config.waiting_hint_groups
    ):
        return False
    labels = {
        normalize_label(button.label)
        for button in buttons
        if button.source != 'template'
    }
    text = ' '.join(sorted(labels))
    required_visible = any(
        label_group_visible(group, labels=labels, text=text)
        for group in automation_config.waiting_required_groups
    )
    hint_visible = any(
        label_group_visible(group, labels=labels, text=text)
        for group in automation_config.waiting_hint_groups
    )
    return required_visible and hint_visible


def configured_shop_screen_visible(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    if not automation_config.shop_screen_required_groups:
        return False
    labels = {
        normalize_label(button.label)
        for button in buttons
        if button.source != 'template'
    }
    text = ' '.join(sorted(labels))
    return any(
        label_group_visible(group, labels=labels, text=text)
        for group in automation_config.shop_screen_required_groups
    )


def ad_or_watch_ad_visible(buttons: list[ButtonCandidate]) -> bool:
    if is_ad_revive_context(buttons):
        return True
    labels = [
        normalize_label(f'{button.label} {button.reason}')
        for button in buttons
        if button.source != 'template'
    ]
    text = ' '.join(labels)
    if any(is_watch_ad_button(button) for button in buttons):
        return True
    return bool(
        re.search(r'\bads?\b|\badvertisements?\b|\bwatch\b|\bfree with ad\b', text)
        or '广告' in text
        or '观看' in text
    )


def configured_safe_confirm_visible(
    automation_config: GameAutomationConfig | None,
    buttons: list[ButtonCandidate],
) -> bool:
    if automation_config is None or not automation_config.safe_confirm_required_groups:
        return False
    if ad_or_watch_ad_visible(buttons):
        return False
    labels = {
        normalize_label(button.label)
        for button in buttons
        if button.source != 'template'
    }
    if not any(label in CONFIRM_LABELS for label in labels):
        return False
    text = ' '.join(sorted(labels))
    return any(
        label_group_visible(group, labels=labels, text=text)
        for group in automation_config.safe_confirm_required_groups
    )


def configured_level_row_label(
    automation_config: GameAutomationConfig,
    label: str,
) -> bool:
    return main_challenge_rules.configured_level_row_label(automation_config, label)


def configured_level_grid_visible(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    return main_challenge_rules.configured_level_grid_visible(
        automation_config,
        buttons,
    )


def configured_level_rows(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    return main_challenge_rules.configured_level_rows(automation_config, buttons)


def configured_visible_level_numbers(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[int]:
    return main_challenge_rules.configured_visible_level_numbers(
        automation_config,
        buttons,
    )


def configured_level_number(button: ButtonCandidate) -> int | None:
    return main_challenge_rules.configured_level_number(button)


def visible_chapter_number(buttons: list[ButtonCandidate]) -> int | None:
    return main_challenge_rules.visible_chapter_number(buttons)


def main_challenge_next_level(
    automation_config: GameAutomationConfig,
) -> int | None:
    progress = load_main_challenge_progress(automation_config.game)
    return main_challenge_rules.main_challenge_next_level(
        automation_config,
        progress,
    )


def button_for_level_row(
    spec: AutomationRowCandidateSpec,
    row: ButtonCandidate,
    *,
    level: int | None,
) -> ButtonCandidate:
    return main_challenge_rules.button_for_level_row(
        spec,
        row,
        level=level,
    )


def candidate_level_number(button: ButtonCandidate) -> int | None:
    return main_challenge_rules.candidate_level_number(button)


def normalized_progress_levels(value: Any) -> list[int]:
    return main_challenge_rules.normalized_progress_levels(value)


def advance_main_challenge_next_level(
    progress: dict[str, Any],
    *,
    target_level: int | None,
) -> None:
    main_challenge_rules.advance_main_challenge_next_level(
        progress,
        target_level=target_level,
    )


def mark_main_challenge_level_cleared(
    progress: dict[str, Any],
    level: int | None,
    *,
    target_level: int | None,
) -> None:
    main_challenge_rules.mark_main_challenge_level_cleared(
        progress,
        level,
        target_level=target_level,
    )


def victory_result_visible(buttons: list[ButtonCandidate]) -> bool:
    return main_challenge_rules.victory_result_visible(buttons)


def update_main_challenge_progress_after_action(
    game: str,
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
    clicked: ButtonCandidate | None,
) -> None:
    progress = load_main_challenge_progress(game)
    updated = main_challenge_rules.update_main_challenge_progress_after_action(
        progress,
        automation_config,
        buttons,
        clicked,
    )
    if updated:
        write_main_challenge_progress(game, progress)


def configured_fallback_level_title_rows(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
    *,
    claimed_buttons: list[ButtonCandidate],
    existing_rows: list[ButtonCandidate],
    max_safe_click_y: float,
) -> list[ButtonCandidate]:
    return main_challenge_rules.configured_fallback_level_title_rows(
        automation_config,
        buttons,
        claimed_buttons=claimed_buttons,
        existing_rows=existing_rows,
        max_safe_click_y=max_safe_click_y,
    )


def configured_inferred_missing_level_row(
    rows: list[ButtonCandidate],
    *,
    next_level: int,
    max_safe_click_y: float,
) -> ButtonCandidate | None:
    return main_challenge_rules.configured_inferred_missing_level_row(
        rows,
        next_level=next_level,
        max_safe_click_y=max_safe_click_y,
    )


def configured_higher_levels_scroll_candidate(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
    recent_actions: list[str] | None = None,
) -> ButtonCandidate | None:
    _ = recent_actions
    progress = load_main_challenge_progress(automation_config.game)
    next_level = main_challenge_rules.main_challenge_next_level(
        automation_config,
        progress,
    )
    return main_challenge_rules.configured_higher_levels_scroll_candidate(
        automation_config,
        buttons,
        next_level,
    )


def configured_result_progress_visible(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    if not automation_config.result_progress_labels:
        return False
    return any(
        normalize_label(button.label) in automation_config.result_progress_labels
        for button in buttons
        if button.source != 'template'
    )


def configured_energy_empty_visible(
    automation_config: GameAutomationConfig | None,
    buttons: list[ButtonCandidate],
) -> bool:
    if automation_config is None or not automation_config.energy_empty_labels:
        return False
    labels = {
        normalize_label(button.label)
        for button in buttons
        if button.source != 'template'
    }
    return any(label in labels for label in automation_config.energy_empty_labels)


def configured_energy_empty_action_exemption_visible(
    automation_config: GameAutomationConfig | None,
    buttons: list[ButtonCandidate],
) -> bool:
    if (
        automation_config is None
        or not automation_config.energy_empty_action_exemption_labels
    ):
        return False
    labels = [
        normalize_label(button.label)
        for button in buttons
        if button.source != 'template'
    ]
    return any(
        exemption in label
        for label in labels
        for exemption in automation_config.energy_empty_action_exemption_labels
    )


def configured_loadout_start_visible(
    automation_config: GameAutomationConfig | None,
    buttons: list[ButtonCandidate],
) -> bool:
    if (
        automation_config is None
        or automation_config.loadout_select_candidate is None
        or not automation_config.loadout_start_labels
    ):
        return False
    labels = {normalize_label(button.label) for button in buttons}
    return any(label in labels for label in automation_config.loadout_start_labels)


def configured_challenge_detail_visible(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    return main_challenge_rules.configured_challenge_detail_visible(
        automation_config,
        buttons,
    )


def configured_claimed_y_positions(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[float]:
    return main_challenge_rules.configured_claimed_y_positions(
        automation_config,
        buttons,
    )


def configured_claimed_buttons(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    return main_challenge_rules.configured_claimed_buttons(
        automation_config,
        buttons,
    )


def configured_recently_reentered(
    automation_config: GameAutomationConfig,
    recent_actions: list[str] | None,
) -> bool:
    return main_challenge_rules.configured_recently_reentered(
        automation_config,
        recent_actions,
    )


def configured_reentry_loop_visible(
    automation_config: GameAutomationConfig,
    recent_actions: list[str] | None,
) -> bool:
    return main_challenge_rules.configured_reentry_loop_visible(
        automation_config,
        recent_actions,
    )


def configured_third_column_unclaimed_row_candidate(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
    recent_actions: list[str] | None = None,
) -> ButtonCandidate | None:
    _ = recent_actions
    progress = load_main_challenge_progress(automation_config.game)
    next_level = main_challenge_rules.main_challenge_next_level(
        automation_config,
        progress,
    )
    return main_challenge_rules.configured_third_column_unclaimed_row_candidate(
        automation_config,
        buttons,
        next_level,
    )


def configured_level_grid_complete_reason(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
    recent_actions: list[str] | None = None,
) -> str | None:
    progress = load_main_challenge_progress(automation_config.game)
    next_level = main_challenge_rules.main_challenge_next_level(
        automation_config,
        progress,
    )
    _ = recent_actions
    return main_challenge_rules.configured_level_grid_complete_reason(
        automation_config,
        buttons,
        progress,
        next_level,
    )


def assist_pack_dismiss_candidate() -> ButtonCandidate:
    return ButtonCandidate(
        label='Dismiss assist pack popup',
        x=0.5,
        y=0.34,
        confidence=1.0,
        clickability=3.0,
        source='vision',
        reason='Assist-pack shop popup is blocking the chapter action; tap outside it.',
    )


def wait_for_loading_candidate() -> ButtonCandidate:
    return ButtonCandidate(
        label='Wait for loading screen',
        x=0.5,
        y=0.5,
        confidence=1.0,
        clickability=3.0,
        source='wait',
        reason='Screen is blank/loading; wait before choosing an action.',
    )


def android_launch_candidate(package: str, reason: str) -> ButtonCandidate:
    return ButtonCandidate(
        label=f'Launch Android package: {package}',
        x=0.5,
        y=0.5,
        confidence=1.0,
        clickability=3.0,
        source='launch_app',
        reason=reason,
    )


def android_back_candidate(reason: str) -> ButtonCandidate:
    return ButtonCandidate(
        label='Android Back',
        x=0.05,
        y=0.95,
        confidence=1.0,
        clickability=3.0,
        source='back',
        reason=reason,
    )


def foreground_android_component(
    metadata: dict[str, Any],
) -> tuple[str, str] | None:
    serial = str(metadata.get('serial') or metadata.get('device_serial') or '').strip()
    command = ['adb']
    if serial:
        command.extend(['-s', serial])
    command.extend(['shell', 'dumpsys', 'window'])
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=5.0,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    match = re.search(
        r'mCurrentFocus=.*?\s([A-Za-z0-9._]+)/(\.?[A-Za-z0-9._$]+)',
        completed.stdout,
    )
    if match is None:
        return None
    return match.group(1), match.group(2)


def external_android_recovery_candidate(
    game: str,
    metadata: dict[str, Any],
) -> ButtonCandidate | None:
    expected_package = EXPECTED_ANDROID_PACKAGES.get(normalize_label(game))
    if not expected_package:
        return None
    component = foreground_android_component(metadata)
    if component is None:
        return None
    package, activity = component
    metadata['foreground_package'] = package
    metadata['foreground_activity'] = activity
    if package == expected_package:
        return None
    if package == 'com.taptap' and 'loginactivity' in activity.lower():
        return wait_for_loading_candidate()
    if package.endswith('launcher'):
        return android_launch_candidate(
            expected_package,
            'The ad or external app returned to the Android launcher; reopen the game.',
        )
    return android_back_candidate(
        f'Foreground package {package} is outside the expected game package '
        f'{expected_package}; press Android Back without clicking external content.'
    )


def wait_for_android_unlock_candidate() -> ButtonCandidate:
    return ButtonCandidate(
        label='Wait for Android unlock',
        x=0.5,
        y=0.5,
        confidence=1.0,
        clickability=3.0,
        source='wait',
        reason='Android lockscreen/notification shade is visible; wait for unlock.',
    )


def android_system_screen_visible(buttons: list[ButtonCandidate]) -> bool:
    labels = [
        normalize_label(button.label)
        for button in buttons
        if button.source in {'ocr', 'vision', 'llm'}
    ]
    if not labels:
        return False
    text = ' '.join(labels)
    date_visible = bool(
        re.search(r'\b(mon|tue|wed|thu|fri|sat|sun),?\b', text)
        and re.search(
            r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b',
            text,
        )
    )
    system_markers = (
        'no sim',
        'emergency',
        'charging',
        'battery',
        'notification',
        'done charging',
        'protect',
        '°f',
        '°c',
    )
    marker_count = sum(1 for marker in system_markers if marker in text)
    return marker_count >= 2 or (date_visible and marker_count >= 1)


def google_play_purchase_sheet_visible(buttons: list[ButtonCandidate]) -> bool:
    labels = [
        normalize_label(button.label)
        for button in buttons
        if button.source in {'ocr', 'vision', 'llm'}
    ]
    text = ' '.join(labels)
    if 'google play' not in text:
        return False
    purchase_markers = (
        '1-tap buy',
        'payment method',
        'purchase',
        'purchases are subject',
        'family payment',
    )
    return any(marker in text for marker in purchase_markers)


def weekly_goodies_popup_visible(buttons: list[ButtonCandidate]) -> bool:
    return any(normalize_label(button.label) == 'weekly goodies' for button in buttons)


def configured_repeated_action_swipe_candidate(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
    recent_actions: list[str] | None = None,
) -> ButtonCandidate | None:
    spec = automation_config.repeated_action_swipe_candidate
    if spec is None or not recent_actions:
        return None
    if len(recent_actions) < spec.min_count:
        return None
    if configured_skill_choice_visible(automation_config, buttons):
        return None
    if (
        configured_waiting_screen_visible(automation_config, buttons)
        or configured_shop_screen_visible(automation_config, buttons)
        or configured_reward_overlay_visible(automation_config, buttons)
        or configured_challenge_detail_visible(automation_config, buttons)
        or configured_result_progress_visible(automation_config, buttons)
        or configured_claimed_visible(automation_config, buttons)
        or configured_energy_empty_visible(automation_config, buttons)
    ):
        return None
    if buttons:
        active_labels = automation_config.main_screen_verification_labels or (
            normalize_label(spec.trigger_label),
        )
        labels = {normalize_label(button.label) for button in buttons}
        if labels.isdisjoint(active_labels):
            return None
        if any(label not in active_labels for label in labels):
            return None

    trigger = normalize_label(spec.trigger_label)
    recent = [normalize_label(label) for label in recent_actions[-spec.min_count :]]
    if recent and all(label == trigger for label in recent):
        return spec.to_button()
    return None


def tower_shop_empty_ocr_exit_candidate(
    automation_config: GameAutomationConfig,
    image: Image.Image | None,
    recent_actions: list[str] | None = None,
) -> ButtonCandidate | None:
    if normalize_label(automation_config.game) != 'tower' or image is None:
        return None

    state = load_tower_run_state(automation_config.game)
    active_shop = normalize_label(
        str(state.get('active_shop') or state.get('last_room_action') or '')
    )
    if active_shop not in (TOWER_PURCHASABLE_SHOP_LABELS | {'魔术商店'}):
        return None
    context_actions = {
        normalize_label(str(state.get('last_action') or '')),
        *(normalize_label(label) for label in (recent_actions or [])[-4:]),
    }
    if context_actions.isdisjoint({'变化', '确定', '点击空白处关闭'}):
        return None

    rgb = np.asarray(image.convert('RGB'))
    height, width = rgb.shape[:2]
    left = rgb[
        int(height * 0.84) : int(height * 0.925),
        int(width * 0.04) : int(width * 0.45),
    ]
    right = rgb[
        int(height * 0.84) : int(height * 0.925),
        int(width * 0.55) : int(width * 0.96),
    ]
    if left.size == 0 or right.size == 0:
        return None
    left_hsv = cv2.cvtColor(left, cv2.COLOR_RGB2HSV)
    right_hsv = cv2.cvtColor(right, cv2.COLOR_RGB2HSV)
    cyan_ratio = np.mean(
        (left_hsv[:, :, 0] >= 75)
        & (left_hsv[:, :, 0] <= 110)
        & (left_hsv[:, :, 1] >= 45)
        & (left_hsv[:, :, 2] >= 60)
    )
    yellow_ratio = np.mean(
        (right_hsv[:, :, 0] >= 12)
        & (right_hsv[:, :, 0] <= 45)
        & (right_hsv[:, :, 1] >= 50)
        & (right_hsv[:, :, 2] >= 70)
    )
    if cyan_ratio < 0.18 or yellow_ratio < 0.18:
        return None

    refresh_count = int(state.get('shop_refresh_count') or 0)
    refresh_limit = max(
        2,
        int((state.get('policy') or {}).get('shop_refresh_limit') or 0),
    )
    recent_keys = {
        normalize_label(label) for label in (recent_actions or [])[-2:]
    }
    if (
        active_shop in TOWER_PURCHASABLE_SHOP_LABELS
        and refresh_count < refresh_limit
        and '刷新商店' not in recent_keys
    ):
        return ButtonCandidate(
            label='刷新商店',
            x=0.14,
            y=0.303,
            confidence=0.97,
            clickability=22.0,
            source='vision',
            reason=(
                'Tower shop shelves are empty after a purchase; use one of the '
                'two allowed in-run currency refreshes.'
            ),
        )
    return ButtonCandidate(
        label='返回',
        x=0.27,
        y=0.883,
        confidence=0.99,
        clickability=20.0,
        source='vision',
        reason='Tower shop refresh failed or reached its limit; return to the map.',
    )


def tower_shop_sparkle_candidate(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
    image: Image.Image | None,
) -> ButtonCandidate | None:
    if normalize_label(automation_config.game) != 'tower' or image is None:
        return None

    labels = {normalize_label(button.label) for button in buttons}
    shop_labels = TOWER_PURCHASABLE_SHOP_LABELS | {'魔术商店'}
    visible_shop = next((label for label in shop_labels if label in labels), '')
    if not visible_shop:
        return None

    state = load_tower_run_state(automation_config.game)
    shop_key = tower_shop_refresh_key(state, visible_shop) or (
        f'{int(state.get("floor") or 0)}:{visible_shop}'
    )
    claimed_keys = {
        str(value) for value in state.get('claimed_shop_sparkle_keys') or []
    }
    if shop_key and shop_key in claimed_keys:
        return None

    rgb = np.asarray(image.convert('RGB').resize((360, 800)))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    hue, saturation, value = cv2.split(hsv)
    yy, xx = np.indices(value.shape)
    upper_right = (
        (xx >= 225)
        & (xx <= 355)
        & (yy >= 90)
        & (yy <= 275)
    )
    yellow_glow = (
        (hue >= 10)
        & (hue <= 45)
        & (saturation >= 75)
        & (value >= 155)
    )
    white_glint = (saturation <= 100) & (value >= 205)
    sparkle_pixels = upper_right & (yellow_glow | white_glint)
    if int(sparkle_pixels.sum()) < 90:
        return None

    heat = cv2.GaussianBlur(
        sparkle_pixels.astype(np.float32),
        (41, 41),
        0,
    )
    peak_y, peak_x = np.unravel_index(int(np.argmax(heat)), heat.shape)
    peak_strength = float(heat[peak_y, peak_x])
    if peak_strength < 0.08:
        return None

    return ButtonCandidate(
        label=TOWER_SHOP_SPARKLE_LABEL,
        x=float(peak_x) / 360.0,
        y=float(peak_y) / 800.0,
        confidence=min(0.99, 0.88 + peak_strength * 0.1),
        clickability=30.0,
        source='vision',
        reason=(
            '商店右上背景出现可领取的闪光点；先拿免费金币或水晶，'
            '再购买、刷新或离店。'
        ),
    )


def tower_task_reward_badge_candidate(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
    image: Image.Image | None,
) -> ButtonCandidate | None:
    if normalize_label(automation_config.game) != 'tower' or image is None:
        return None
    if load_tower_run_state(automation_config.game).get(
        'skip_unsafe_trainer_reward'
    ):
        return None
    labels = {normalize_label(button.label) for button in buttons}
    if labels & {'招募', '旅馆', '商城', '福利', '邮件', '庄园'}:
        return None
    if '结束回合' in labels:
        return None
    task_button = next(
        (
            button
            for button in buttons
            if normalize_label(button.label) == '任务'
            and button.source != 'template'
            and button.x <= 0.20
            and 0.48 <= button.y <= 0.60
        ),
        None,
    )
    if task_button is None:
        return None
    rgb = np.asarray(image.convert('RGB').resize((360, 800)))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    if task_button.bbox is not None:
        _, task_y1, task_x2, _ = task_button.bbox
        badge_x1 = max(0, int((task_x2 + 0.005) * 360))
        badge_x2 = min(360, int((task_x2 + 0.06) * 360))
        badge_y1 = max(0, int((task_y1 - 0.025) * 800))
        badge_y2 = min(800, int((task_y1 + 0.015) * 800))
        badge = hsv[badge_y1:badge_y2, badge_x1:badge_x2]
    else:
        badge = hsv[415:450, 53:78]
    if badge.size == 0:
        return None
    red_pixels = (
        ((badge[:, :, 0] <= 10) | (badge[:, :, 0] >= 170))
        & (badge[:, :, 1] >= 120)
        & (badge[:, :, 2] >= 100)
    )
    has_red_badge = (
        int(red_pixels.sum()) >= 25 and float(red_pixels.mean()) >= 0.02
    )
    state = load_tower_run_state(automation_config.game)
    battle_number = int(state.get('battle_number') or 0)
    if not has_red_badge and (
        battle_number <= 0 or state.get('trainer_task_checked_once')
    ):
        return None
    return ButtonCandidate(
        label='任务',
        x=task_button.x,
        y=task_button.y,
        confidence=max(task_button.confidence, 0.99),
        clickability=max(task_button.clickability, 25.0 if has_red_badge else 14.0),
        source='vision',
        reason=(
            'Tower trainer task reward badge is red; open 任务 now to activate '
            'the completed talent reward.'
            if has_red_badge
            else 'Tower trainer task post-battle check; inspect 任务 once after '
            'this battle so an unread talent reward cannot be missed.'
        ),
    )


def configured_extra_candidates(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
    recent_actions: list[str] | None = None,
    image: Image.Image | None = None,
    context_buttons: list[ButtonCandidate] | None = None,
) -> list[ButtonCandidate]:
    extras: list[ButtonCandidate] = []
    tower_revive = tower_ad_revive_candidate(automation_config, buttons)
    if tower_revive is not None:
        extras.append(tower_revive)
    tower_shop_sparkle = tower_shop_sparkle_candidate(
        automation_config,
        context_buttons if context_buttons is not None else buttons,
        image,
    )
    if tower_shop_sparkle is not None:
        extras.append(tower_shop_sparkle)
    tower_task_reward = tower_task_reward_badge_candidate(
        automation_config,
        context_buttons if context_buttons is not None else buttons,
        image,
    )
    if tower_task_reward is not None:
        extras.append(tower_task_reward)
    repeated_swipe = configured_repeated_action_swipe_candidate(
        automation_config,
        buttons,
        recent_actions,
    )
    if not any(button.source != 'template' for button in buttons):
        tower_shop_exit = tower_shop_empty_ocr_exit_candidate(
            automation_config,
            image,
            recent_actions,
        )
        if tower_shop_exit is not None:
            return [tower_shop_exit]
    if not buttons and automation_config.empty_screen_candidate is not None:
        if repeated_swipe is not None:
            return [
                repeated_swipe,
                automation_config.empty_screen_candidate.to_button(),
            ]
        return [automation_config.empty_screen_candidate.to_button()]
    if (
        configured_waiting_screen_visible(automation_config, buttons)
        and automation_config.waiting_candidate is not None
    ):
        extras.append(automation_config.waiting_candidate.to_button())
    if configured_assist_pack_popup_visible(buttons):
        return [*extras, assist_pack_dismiss_candidate()]
    if (
        configured_shop_screen_visible(automation_config, buttons)
        and automation_config.shop_escape_candidate is not None
    ):
        return [*extras, automation_config.shop_escape_candidate.to_button()]
    if configured_reward_overlay_visible(
        automation_config,
        buttons,
    ) and configured_reward_close_visible(automation_config, buttons):
        return extras
    if configured_challenge_detail_visible(automation_config, buttons):
        return extras
    if configured_result_progress_visible(automation_config, buttons):
        return extras
    if configured_loadout_start_visible(automation_config, buttons):
        extras.append(automation_config.loadout_select_candidate.to_button())
    third_column = configured_third_column_unclaimed_row_candidate(
        automation_config,
        buttons,
        recent_actions,
    )
    higher_levels_scroll = configured_higher_levels_scroll_candidate(
        automation_config,
        buttons,
        recent_actions,
    )
    claimed_visible = configured_claimed_visible(automation_config, buttons)
    if higher_levels_scroll is not None:
        extras.append(higher_levels_scroll)
    elif claimed_visible:
        if third_column and main_challenge_next_level(automation_config) is not None:
            extras.append(third_column)
        elif (
            configured_recently_reentered(automation_config, recent_actions)
            and third_column
        ):
            extras.append(third_column)
        elif automation_config.claimed_back_candidate is not None:
            extras.append(automation_config.claimed_back_candidate.to_button())
    elif third_column:
        extras.append(third_column)
    if repeated_swipe is not None:
        extras.append(repeated_swipe)
    return extras


def top_playfield_path_probe_candidates(
    buttons: list[ButtonCandidate],
    automation_config: GameAutomationConfig | None = None,
) -> list[ButtonCandidate]:
    probes = []
    seen_directions = set()
    for button in buttons:
        if not is_navigation_arrow_label(button.label, automation_config):
            continue
        direction = navigation_direction(button.label)
        if direction is None or direction in seen_directions:
            continue
        seen_directions.add(direction)
        x, y = TOP_PLAYFIELD_PATH_COORDS[direction]
        probes.append(
            ButtonCandidate(
                label=f'Top path {direction}',
                x=x,
                y=y,
                confidence=1.0,
                clickability=2.0,
                source='vision',
                reason=(
                    'Navigation arrows have been cycling; probe the upper '
                    'playfield path instead of the minimap arrow.'
                ),
            )
        )
    return probes


def escape_menu_probe_candidates() -> list[ButtonCandidate]:
    return [
        ButtonCandidate(
            label='Open settings',
            x=0.94,
            y=0.465,
            confidence=1.0,
            clickability=3.2,
            source='vision',
            reason=(
                'Navigation and top-path probes are cycling; open settings '
                'to look for a recovery or return action.'
            ),
        ),
        ButtonCandidate(
            label='Open run menu',
            x=0.55,
            y=0.105,
            confidence=0.75,
            clickability=1.2,
            source='vision',
            reason=(
                'Fallback only: this can open the share panel instead of a '
                'recovery menu.'
            ),
        ),
    ]


ESCAPE_MENU_PROBE_LABELS = {
    'open settings',
    'open run menu',
}
MIN_UNBLOCK_NON_MENU_SCORE = 0.65
TOWER_MAP_ROOM_SKIP_LABELS = {
    'end',
    'abandon',
    'back',
    '返回',
    'fight',
    'battle',
    'challenge',
    '战斗',
    '挑战',
    'enhance card',
    'forget card',
    '点击空白处关闭',
}
TOWER_MAP_ROOM_BOTTOM_ACTION_LABELS = {
    '强化',
    '融合',
    '捡起',
    '捡起木剑',
}


def should_detect_tower_map_rooms(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    if normalize_label(automation_config.game) != 'tower':
        return False
    if configured_loadout_start_visible(automation_config, buttons):
        return False
    if not buttons:
        return True
    navigation_buttons = [
        button
        for button in buttons
        if button.source != 'ocr'
        and is_navigation_arrow_label(button.label, automation_config)
    ]
    navigation_count = len(navigation_buttons)
    navigation_visible = navigation_count >= 2
    button_keys = {normalize_label(button.label) for button in buttons}
    tower_map_hud_visible = bool(
        button_keys
        & {
            '当前所在层数',
            '全服最高层数',
            '冒险者携带的未激活宝物',
        }
    )
    if any(
        normalize_label(button.label) in automation_config.loadout_start_labels
        for button in buttons
    ):
        return False
    navigation_present = bool(navigation_buttons)
    floor_visible = any(
        re.fullmatch(r'm?\d/6', normalize_label(button.label)) for button in buttons
    )
    if not navigation_visible and not (floor_visible and navigation_present):
        if not tower_map_hud_visible:
            return False
    for button in buttons:
        key = normalize_label(button.label)
        if key in CONFIRM_LABELS or key in CANCEL_LABELS:
            return False
        if key in TOWER_MAP_ROOM_SKIP_LABELS:
            return False
        if key in TOWER_MAP_ROOM_BOTTOM_ACTION_LABELS and button.y >= 0.70:
            return False
    return True


def should_detect_tower_current_room(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    if normalize_label(automation_config.game) != 'tower':
        return False
    if configured_loadout_start_visible(automation_config, buttons):
        return False
    navigation_present = any(
        button.source != 'ocr'
        and is_navigation_arrow_label(button.label, automation_config)
        for button in buttons
    )
    if not navigation_present:
        return False
    if any(
        button.source != 'ocr'
        and is_navigation_arrow_label(button.label, automation_config)
        and 0.35 <= button.x <= 0.65
        and 0.56 <= button.y <= 0.70
        for button in buttons
    ):
        return False
    for button in buttons:
        key = normalize_label(button.label)
        if key in CONFIRM_LABELS or key in CANCEL_LABELS:
            return False
        if key in TOWER_MAP_ROOM_SKIP_LABELS:
            return False
        if key in TOWER_MAP_ROOM_BOTTOM_ACTION_LABELS:
            return False
    return True


def tower_hp_looks_critical(image: Image.Image) -> bool:
    rgb = np.asarray(image.convert('RGB'))
    height, width = rgb.shape[:2]
    if width <= 0 or height <= 0:
        return False
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    y_index = np.arange(height)[:, None]
    x_index = np.arange(width)[None, :]
    status_region = (
        (x_index >= int(width * 0.13))
        & (x_index <= int(width * 0.42))
        & (y_index >= int(height * 0.42))
        & (y_index <= int(height * 0.49))
    )
    red_pixels = (
        ((hsv[:, :, 0] <= 8) | (hsv[:, :, 0] >= 170))
        & (hsv[:, :, 1] > 70)
        & (hsv[:, :, 2] > 80)
        & status_region
    )
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[red_pixels] = 255
    red_columns = np.where(mask.any(axis=0))[0]
    if red_columns.size == 0:
        return False
    red_span = int(red_columns.max() - red_columns.min() + 1)
    return red_span <= max(16, int(width * 0.06))


def tower_current_room_icon_candidates(
    image: Image.Image,
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    if not should_detect_tower_current_room(automation_config, buttons):
        return []

    rgb = np.asarray(image.convert('RGB'))
    height, width = rgb.shape[:2]
    if width <= 0 or height <= 0:
        return []

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    y_index = np.arange(height)[:, None]
    x_index = np.arange(width)[None, :]
    center_map_region = (
        (x_index >= int(width * 0.34))
        & (x_index <= int(width * 0.66))
        & (y_index >= int(height * 0.58))
        & (y_index <= int(height * 0.82))
    )
    saturated = (hsv[:, :, 1] > 55) & (hsv[:, :, 2] > 65) & center_map_region
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[saturated] = 255
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        np.ones((5, 5), dtype=np.uint8),
        iterations=2,
    )
    ys, xs = np.where(mask > 0)
    if xs.size < max(160, int(width * height * 0.0007)):
        return []

    x1 = int(xs.min())
    x2 = int(xs.max()) + 1
    y1 = int(ys.min())
    y2 = int(ys.max()) + 1
    box_width = x2 - x1
    box_height = y2 - y1
    norm_width = box_width / width
    norm_height = box_height / height
    if not (0.08 <= norm_width <= 0.30 and 0.05 <= norm_height <= 0.24):
        return []

    center_x = (x1 + (box_width / 2)) / width
    center_y = (y1 + (box_height / 2)) / height
    if not (0.38 <= center_x <= 0.62 and 0.60 <= center_y <= 0.80):
        return []

    return [
        ButtonCandidate(
            label='Visible current room icon',
            x=center_x,
            y=min(0.80, max(center_y, 0.72)),
            confidence=0.98,
            clickability=6.8,
            source='vision',
            reason=(
                'Detected the active room plaque in the center of the tower '
                'map; click it to start the current room.'
            ),
            bbox=(x1 / width, y1 / height, x2 / width, y2 / height),
        )
    ]


def tower_map_room_icon_candidates(
    image: Image.Image,
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    if not should_detect_tower_map_rooms(automation_config, buttons):
        return []

    rgb = np.asarray(image.convert('RGB'))
    height, width = rgb.shape[:2]
    if width <= 0 or height <= 0:
        return []

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    y_index = np.arange(height)[:, None]
    x_index = np.arange(width)[None, :]
    map_region = (
        (y_index >= int(height * 0.58))
        & (y_index <= int(height * 0.88))
        & (x_index >= int(width * 0.08))
        & (x_index <= int(width * 0.94))
    )
    saturated = (hsv[:, :, 1] > 45) & (hsv[:, :, 2] > 70) & map_region
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[saturated] = 255
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        np.ones((3, 3), dtype=np.uint8),
        iterations=2,
    )
    hp_critical = tower_hp_looks_critical(image)
    contours, _hierarchy = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    candidates: list[tuple[float, ButtonCandidate]] = []
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        area = float(cv2.contourArea(contour))
        if area < max(300.0, width * height * 0.001):
            continue
        norm_width = box_width / width
        norm_height = box_height / height
        center_x = (x + (box_width / 2)) / width
        center_y = (y + (box_height / 2)) / height
        if not (0.10 <= norm_width <= 0.36 and 0.05 <= norm_height <= 0.17):
            continue
        if not (0.14 <= center_x <= 0.90 and 0.60 <= center_y <= 0.86):
            continue

        crop_hsv = hsv[y : y + box_height, x : x + box_width]
        crop_mask = mask[y : y + box_height, x : x + box_width] > 0
        hues = crop_hsv[:, :, 0][crop_mask]
        if hues.size == 0:
            continue
        warm_ratio = float(np.mean(((hues >= 0) & (hues <= 85)) | (hues >= 170)))
        blue_ratio = float(np.mean((hues >= 86) & (hues <= 135)))
        pale_center_ratio = float(
            np.mean((crop_hsv[:, :, 1] < 55) & (crop_hsv[:, :, 2] > 100))
        )
        next_floor_text_visible = any(
            button.source != 'template'
            and '下一层' in normalize_label(button.label)
            and (x / width) <= button.x <= ((x + box_width) / width)
            and (y / height) <= button.y <= ((y + box_height) / height)
            for button in buttons
        )
        combat_like = warm_ratio >= 0.55 and blue_ratio <= 0.40
        rest_like = blue_ratio >= 0.50 and warm_ratio <= 0.45
        next_floor_like = (
            next_floor_text_visible
            and blue_ratio >= 0.60
            and pale_center_ratio >= 0.18
            and area >= width * height * 0.01
        )
        if next_floor_like:
            clickability = 9.0
            label = 'Visible next-floor stair room'
        elif hp_critical and rest_like:
            clickability = 8.5
            label = 'Visible rest room icon'
        elif combat_like:
            clickability = 6.0 if hp_critical else 7.0
            label = 'Visible combat room icon'
        else:
            clickability = 3.2
            label = 'Visible room icon'
        priority = 5.0 if next_floor_like else (2.0 if combat_like else 1.0)
        if hp_critical and rest_like and not next_floor_like:
            priority = 3.0
        candidates.append(
            (
                priority + (area / (width * height)),
                ButtonCandidate(
                    label=label,
                    x=center_x,
                    y=center_y,
                    confidence=0.98,
                    clickability=clickability,
                    source='vision',
                    reason=(
                        'Detected a saturated room plaque on the tower map; '
                        'prefer concrete rooms over connector arrows.'
                    ),
                    bbox=(
                        x / width,
                        y / height,
                        (x + box_width) / width,
                        (y + box_height) / height,
                    ),
                ),
            )
        )

    return [
        candidate
        for _priority, candidate in sorted(
            candidates,
            key=lambda item: item[0],
            reverse=True,
        )
    ][:4]


TOWER_COMBAT_CARD_SLOT_CENTERS = (
    (0.205, 0.635),
    (0.500, 0.635),
    (0.795, 0.635),
    (0.205, 0.815),
    (0.500, 0.815),
    (0.795, 0.815),
)


def tower_combat_hp_looks_critical(image: Image.Image) -> bool:
    """Use the unobscured left edge of the combat HP bar as a cheap guard."""
    rgb = np.asarray(image.convert('RGB').resize((360, 800)))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    guard = hsv[356:363, 86:91]
    if guard.size == 0:
        return False
    warm_fill = (
        (guard[:, :, 0] <= 15)
        & (guard[:, :, 1] > 100)
        & (guard[:, :, 2] > 100)
    )
    return float(np.mean(warm_fill)) < 0.25


def tower_enemy_hp_looks_sacred_finisher_ready(image: Image.Image) -> bool:
    """Detect roughly the last 10% of the enemy HP bar without OCR."""
    rgb = np.asarray(image.convert('RGB').resize((360, 800)))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    health_bar = hsv[56:64, 219:301]
    if health_bar.size == 0:
        return False
    orange_fill = (
        (health_bar[:, :, 0] >= 3)
        & (health_bar[:, :, 0] <= 25)
        & (health_bar[:, :, 1] > 80)
        & (health_bar[:, :, 2] > 70)
    )
    filled_columns = np.count_nonzero(orange_fill, axis=0) >= 3
    contiguous_fill = 0
    for filled in filled_columns:
        if not filled:
            break
        contiguous_fill += 1
    return contiguous_fill <= 8


def tower_combat_item_pouch_has_consumable(image: Image.Image) -> bool:
    """Distinguish the pouch's zero counter from a positive item count."""
    rgb = np.asarray(image.convert('RGB').resize((360, 800)))
    gray = cv2.cvtColor(rgb[738:752, 284:304], cv2.COLOR_RGB2GRAY)
    bright = np.uint8(gray > 210) * 255
    bright = cv2.resize(bright, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST)
    contours, hierarchy = cv2.findContours(
        bright,
        cv2.RETR_TREE,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if hierarchy is None or not contours:
        return False

    parents = [
        index
        for index, relation in enumerate(hierarchy[0])
        if relation[3] == -1 and cv2.contourArea(contours[index]) >= 100.0
    ]
    zero_holes = []
    for index, relation in enumerate(hierarchy[0]):
        parent_index = int(relation[3])
        if parent_index < 0 or parent_index not in parents:
            continue
        _x, _y, _width, child_height = cv2.boundingRect(contours[index])
        _px, _py, _pwidth, parent_height = cv2.boundingRect(
            contours[parent_index]
        )
        if parent_height > 0 and child_height / parent_height >= 0.65:
            zero_holes.append(index)
    return not (len(parents) == 1 and bool(zero_holes))


def tower_combat_emergency_item_candidates(
    image: Image.Image,
    automation_config: GameAutomationConfig,
) -> list[ButtonCandidate]:
    if normalize_label(automation_config.game) != 'tower':
        return []
    if not tower_combat_screen_visible(image):
        return []
    if not tower_combat_item_pouch_has_consumable(image):
        return []
    if not tower_combat_hp_looks_critical(image):
        return []
    return [
        ButtonCandidate(
            label='低血打开道具口袋',
            x=0.768,
            y=0.938,
            confidence=0.99,
            clickability=30.0,
            source='vision',
            reason=(
                '战斗生命低于约30%，且道具计数不为0；优先使用回血或循环'
                '消耗品，避免结束回合后死亡。'
            ),
        )
    ]


def tower_attack_number_card_candidates(
    image: Image.Image,
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    if normalize_label(automation_config.game) != 'tower':
        return []
    if not any(is_end_turn_label(button.label) for button in buttons):
        return []
    if any(
        normalize_label(button.label) in CONFIRM_LABELS | CANCEL_LABELS
        for button in buttons
    ):
        return []

    rgb = np.asarray(image.convert('RGB'))
    height, width = rgb.shape[:2]
    if width <= 0 or height <= 0:
        return []
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    slot_width = int(width * 0.25)
    slot_height = int(height * 0.16)
    candidates: list[tuple[float, ButtonCandidate]] = []

    for slot_index, (center_x, center_y) in enumerate(
        TOWER_COMBAT_CARD_SLOT_CENTERS,
        start=1,
    ):
        x1 = max(0, int((center_x * width) - (slot_width / 2)))
        x2 = min(width, int((center_x * width) + (slot_width / 2)))
        y1 = max(0, int((center_y * height) - (slot_height / 2)))
        y2 = min(height, int((center_y * height) + (slot_height / 2)))
        if x2 <= x1 or y2 <= y1:
            continue

        crop_hsv = hsv[y1:y2, x1:x2]
        crop_rgb = rgb[y1:y2, x1:x2]
        saturated = (crop_hsv[:, :, 1] > 55) & (crop_hsv[:, :, 2] > 70)
        if float(np.mean(saturated)) < 0.18:
            continue

        hues = crop_hsv[:, :, 0][saturated]
        if hues.size == 0:
            continue
        warm_ratio = float(np.mean(((hues >= 0) & (hues <= 35)) | (hues >= 170)))
        if warm_ratio < 0.28:
            continue

        crop_height, crop_width = crop_rgb.shape[:2]
        bottom = crop_rgb[
            int(crop_height * 0.66) : int(crop_height * 0.92),
            int(crop_width * 0.28) : int(crop_width * 0.76),
        ]
        if bottom.size == 0:
            continue
        whiteish = (
            (bottom[:, :, 0] > 160) & (bottom[:, :, 1] > 150) & (bottom[:, :, 2] > 135)
        )
        if int(np.count_nonzero(whiteish)) < 25:
            continue

        clickability = 8.2 + min(warm_ratio, 0.6)
        candidates.append(
            (
                clickability,
                ButtonCandidate(
                    label='Visible attack-number card',
                    x=center_x,
                    y=center_y,
                    confidence=0.94,
                    clickability=clickability,
                    source='vision',
                    reason=(
                        'Detected a warm combat card with a white attack-number '
                        f'mark in hand slot {slot_index}; prefer it over shield '
                        'or setup cards.'
                    ),
                    bbox=(x1 / width, y1 / height, x2 / width, y2 / height),
                ),
            )
        )

    return [
        candidate
        for _score, candidate in sorted(
            candidates,
            key=lambda item: item[0],
            reverse=True,
        )
    ]


def tower_combat_screen_visible(image: Image.Image) -> bool:
    """Detect a yellow End-turn control together with physical hand cards."""
    rgb = np.asarray(image.convert('RGB'))
    height, width = rgb.shape[:2]
    if width <= 0 or height <= 0:
        return False
    roi = rgb[
        int(height * 0.90) : int(height * 0.985),
        int(width * 0.27) : int(width * 0.73),
    ]
    if roi.size == 0:
        return False
    hsv = cv2.cvtColor(roi, cv2.COLOR_RGB2HSV)
    yellow = (
        (hsv[:, :, 0] >= 15)
        & (hsv[:, :, 0] <= 45)
        & (hsv[:, :, 1] >= 70)
        & (hsv[:, :, 2] >= 90)
    )
    if float(np.mean(yellow)) < 0.035:
        return False
    card_boxes = tower_card_outline_boxes(rgb)
    return any(
        (y + (box_height / 2)) / height < 0.75
        for _x, y, _box_width, box_height in card_boxes
    )


def tower_card_outline_boxes(rgb: np.ndarray) -> list[tuple[int, int, int, int]]:
    height, width = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 70, 150)
    edges[: int(height * 0.42)] = 0
    edges[int(height * 0.90) :] = 0
    edges = cv2.morphologyEx(
        edges,
        cv2.MORPH_CLOSE,
        np.ones((5, 5), dtype=np.uint8),
        iterations=2,
    )
    contours, _hierarchy = cv2.findContours(
        edges,
        cv2.RETR_LIST,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    boxes: list[tuple[int, int, int, int]] = []
    min_area = max(1200.0, width * height * 0.012)
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        if box_width * box_height < min_area:
            continue
        norm_width = box_width / width
        norm_height = box_height / height
        center_y = (y + (box_height / 2)) / height
        if not (0.15 <= norm_width <= 0.32):
            continue
        if not (0.12 <= norm_height <= 0.30):
            continue
        if not (0.48 <= center_y <= 0.88):
            continue
        boxes.append((x, y, box_width, box_height))

    deduped: list[tuple[int, int, int, int]] = []
    for box in sorted(boxes, key=lambda value: value[2] * value[3], reverse=True):
        x, y, box_width, box_height = box
        center_x = x + (box_width / 2)
        center_y = y + (box_height / 2)
        if any(
            abs(center_x - (other_x + (other_w / 2))) <= width * 0.04
            and abs(center_y - (other_y + (other_h / 2))) <= height * 0.035
            for other_x, other_y, other_w, other_h in deduped
        ):
            continue
        deduped.append(box)
    return deduped


def tower_card_name_from_ocr(
    buttons: list[ButtonCandidate],
    bbox: tuple[float, float, float, float],
) -> str:
    x1, y1, x2, y2 = bbox
    matches = []
    for button in buttons:
        if button.source != 'ocr':
            continue
        if not (x1 <= button.x <= x2 and y1 <= button.y <= y2):
            continue
        label = button.label.strip()
        if not label or re.fullmatch(r'[0-9+*/.\-]+', label):
            continue
        matches.append(button)
    if not matches:
        return ''
    matches.sort(key=lambda button: (button.y, -button.confidence))
    return matches[0].label


def tower_combat_card_looks_enabled(crop: np.ndarray) -> bool:
    hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    value = hsv[:, :, 2]
    bright_ratio = float(np.mean(value > 90))
    mean_value = float(np.mean(value))
    return mean_value >= 100.0 or bright_ratio >= 0.55


def tower_combat_card_candidates(
    image: Image.Image,
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    """Find every bright, affordable hand card from its physical outline."""
    if normalize_label(automation_config.game) != 'tower':
        return []
    if not tower_combat_screen_visible(image):
        return []
    if any(
        normalize_label(button.label) in CONFIRM_LABELS | CANCEL_LABELS
        for button in buttons
    ):
        return []

    rgb = np.asarray(image.convert('RGB'))
    height, width = rgb.shape[:2]
    deduped = tower_card_outline_boxes(rgb)

    candidates: list[ButtonCandidate] = []
    for x, y, box_width, box_height in sorted(
        deduped,
        key=lambda box: (box[1], box[0]),
    ):
        crop = rgb[y : y + box_height, x : x + box_width]
        if not tower_combat_card_looks_enabled(crop):
            continue

        bbox = (
            x / width,
            y / height,
            (x + box_width) / width,
            (y + box_height) / height,
        )
        card_name = tower_card_name_from_ocr(buttons, bbox)
        label = 'Visible playable card'
        if card_name:
            label = f'{label}: {card_name}'
        candidates.append(
            ButtonCandidate(
                label=label,
                x=(x + (box_width / 2)) / width,
                y=(y + (box_height * 0.10)) / height,
                confidence=0.96,
                clickability=7.4,
                source='vision',
                reason=(
                    'Detected a bright card-sized outline in the combat hand; '
                    'double tap it, then recapture because the hand reflows.'
                ),
                bbox=bbox,
            )
        )
    return candidates


def tower_navigation_template_position_is_valid(button: ButtonCandidate) -> bool:
    direction = navigation_direction(button.label)
    if direction == 'left':
        return button.x <= 0.20 and 0.55 <= button.y <= 0.86
    if direction == 'right':
        return button.x >= 0.80 and 0.55 <= button.y <= 0.86
    if direction == 'up':
        return 0.30 <= button.x <= 0.70 and 0.52 <= button.y <= 0.78
    if direction == 'down':
        return 0.30 <= button.x <= 0.70 and 0.72 <= button.y <= 0.92
    return True


def filter_tower_context_buttons(
    image: Image.Image,
    buttons: list[ButtonCandidate],
    automation_config: GameAutomationConfig,
) -> list[ButtonCandidate]:
    if normalize_label(automation_config.game) != 'tower':
        return buttons
    combat_visible = tower_combat_screen_visible(image)
    prebattle_visible = any(
        '即将发起战斗' in normalize_label(button.label) for button in buttons
    )
    filtered = []
    for button in buttons:
        if button.source != 'template':
            filtered.append(button)
            continue
        if is_navigation_arrow_label(button.label, automation_config):
            if combat_visible or not tower_navigation_template_position_is_valid(
                button
            ):
                continue
        if is_configured_combat_card_label(button.label, automation_config):
            if not combat_visible:
                continue
        if prebattle_visible and normalize_label(button.label) in {
            '雇佣',
            '招募',
            'hire',
            'recruit',
        }:
            continue
        filtered.append(button)
    return filtered


def tower_prebattle_start_candidates(
    automation_config: GameAutomationConfig,
    image: Image.Image,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    if normalize_label(automation_config.game) != 'tower':
        return []
    title_visible = any(
        '即将发起战斗' in normalize_label(button.label) for button in buttons
    )
    rgb = np.asarray(image.convert('RGB').resize((360, 800)), dtype=np.float32)
    versus = rgb[360:485, 110:250]
    left = rgb[740:790, 35:170]
    right = rgb[740:790, 195:330]
    pale_versus = np.mean(
        (versus.min(axis=2) > 105)
        & ((versus.max(axis=2) - versus.min(axis=2)) < 70)
    )
    cyan_left = np.mean(
        (left[:, :, 1] > left[:, :, 0] + 15)
        & (left[:, :, 2] > left[:, :, 0] + 20)
    )
    yellow_right = np.mean(
        (right[:, :, 0] > right[:, :, 1] + 20)
        & (right[:, :, 1] > right[:, :, 2] + 20)
    )
    visual_prebattle = (
        pale_versus > 0.05 and cyan_left > 0.25 and yellow_right > 0.25
    )
    if not title_visible and not visual_prebattle:
        return []
    return [
        ButtonCandidate(
            label='战斗',
            x=0.715,
            y=0.948,
            confidence=0.99,
            clickability=5.0,
            source='vision',
            reason=(
                'The prebattle title is visible; use the stable bottom-right '
                'battle control even when OCR misses its text.'
            ),
        )
    ]


def tower_map_exit_candidates(
    image: Image.Image,
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    if normalize_label(automation_config.game) != 'tower':
        return []
    labels = {normalize_label(button.label) for button in buttons}
    tower_map_hud_visible = bool(labels & {'当前所在层数', '全服最高层数'}) or any(
        label.startswith('当前层数') for label in labels
    )
    if not tower_map_hud_visible:
        return []
    if labels & (CONFIRM_LABELS | CANCEL_LABELS):
        return []
    rgb = np.asarray(image.convert('RGB'))
    height, width = rgb.shape[:2]
    regions = (
        ('上方道路', 0.39, 0.58, 0.61, 0.71, 0.025),
        ('下方道路', 0.42, 0.88, 0.58, 0.97, 0.05),
        ('左侧道路', 0.02, 0.62, 0.20, 0.82, 0.025),
        ('右侧道路', 0.80, 0.62, 0.98, 0.82, 0.025),
    )
    candidates = []
    for label, x1, y1, x2, y2, threshold in regions:
        top = int(height * y1)
        bottom = int(height * y2)
        left = int(width * x1)
        right = int(width * x2)
        roi = rgb[top:bottom, left:right]
        if roi.size == 0:
            continue
        cyan = (
            (roi[:, :, 1] > 100)
            & (roi[:, :, 2] > 110)
            & (roi[:, :, 2] > roi[:, :, 0] * 1.25)
            & (roi[:, :, 1] > roi[:, :, 0] * 1.15)
        )
        if float(np.mean(cyan)) < threshold:
            continue
        cyan_y, cyan_x = np.where(cyan)
        candidates.append(
            ButtonCandidate(
                label=label,
                x=(left + float(cyan_x.mean())) / width,
                y=(top + float(cyan_y.mean())) / height,
                confidence=0.99,
                clickability=7.0,
                source='vision',
                reason=f'本地视觉检测到高亮青色{label}。',
            )
        )
    return candidates


TOWER_PASSIVE_STATUS_PREFIXES = (
    '当前层数',
    '该层剩余冒险事件',
    '正在加载',
    '正在进入旅馆',
    '正在前往魔塔冒险',
    '服务器正在维护中',
    '是否查看更新详情',
)

TOWER_COMBAT_METADATA_LABELS = {
    '攻击牌',
    '防御牌',
    '法术牌',
    '技能牌',
    '宝石牌',
    '超越牌',
    '状态牌',
}
TOWER_PLAYABLE_CARD_CLICKABILITY = 1.55


def is_tower_combat_card_candidate(
    button: ButtonCandidate,
    automation_config: GameAutomationConfig | None,
) -> bool:
    if is_configured_combat_card_label(button.label, automation_config):
        return True
    return bool(
        automation_config is not None
        and normalize_label(automation_config.game) == 'tower'
        and button.source == 'ocr'
        and 0.55 <= button.y <= 0.84
        and not is_configured_command_label(button.label, automation_config)
        and normalize_label(button.label) not in TOWER_COMBAT_METADATA_LABELS
    )


def is_tower_playable_combat_card_candidate(
    button: ButtonCandidate,
    automation_config: GameAutomationConfig | None,
) -> bool:
    if not is_tower_combat_card_candidate(button, automation_config):
        return False
    if button.source != 'ocr':
        return True
    return (
        button.y >= 0.45
        and button.clickability >= TOWER_PLAYABLE_CARD_CLICKABILITY
        and normalize_label(button.label) not in TOWER_COMBAT_METADATA_LABELS
    )


def tower_playable_combat_card_slot_count(
    buttons: Iterable[ButtonCandidate],
    automation_config: GameAutomationConfig | None,
) -> int:
    slots: list[tuple[float, float]] = []
    for button in buttons:
        if not is_tower_playable_combat_card_candidate(button, automation_config):
            continue
        # OCR reads the title near the bottom of a card; vision marks its center.
        # Normalize both to the card center before merging duplicate detections.
        slot_y = button.y - 0.105 if button.source == 'ocr' else button.y
        if any(
            abs(button.x - slot_x) <= 0.08 and abs(slot_y - existing_y) <= 0.08
            for slot_x, existing_y in slots
        ):
            continue
        slots.append((button.x, slot_y))
    return len(slots)


def is_tower_passive_status_label(
    automation_config: GameAutomationConfig,
    label: str,
) -> bool:
    if normalize_label(automation_config.game) != 'tower':
        return False
    key = normalize_label(label)
    return any(key.startswith(prefix) for prefix in TOWER_PASSIVE_STATUS_PREFIXES)


def is_tower_map_floor_status_button(
    automation_config: GameAutomationConfig,
    button: ButtonCandidate,
) -> bool:
    if normalize_label(automation_config.game) != 'tower':
        return False
    return bool(
        button.source != 'template'
        and re.fullmatch(r'\d{1,3}', normalize_label(button.label))
        and 0.54 <= button.x <= 0.72
        and 0.50 <= button.y <= 0.57
    )


def tower_loading_wait_candidates(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    if normalize_label(automation_config.game) != 'tower':
        return []
    maintenance = next(
        (
            button
            for button in buttons
            if normalize_label(button.label).startswith(
                ('服务器正在维护中', '是否查看更新详情')
            )
        ),
        None,
    )
    if maintenance is not None:
        return [
            ButtonCandidate(
                label='等待服务器维护',
                x=0.5,
                y=0.5,
                confidence=0.99,
                clickability=30.0,
                source='wait',
                reason=(
                    f'检测到停服提示“{maintenance.label}”；保留当前存档并等待，'
                    '不点击更新详情或反复登录。'
                ),
            )
        ]
    loading = next(
        (
            button
            for button in buttons
            if normalize_label(button.label).startswith(
                ('正在加载', '正在进入旅馆', '正在前往魔塔冒险')
            )
        ),
        None,
    )
    if loading is None:
        return []
    return [
        ButtonCandidate(
            label='等待页面加载',
            x=0.5,
            y=0.5,
            confidence=0.99,
            clickability=9.0,
            source='wait',
            reason=f'检测到加载提示“{loading.label}”，等待而不点击文字。',
        )
    ]


def configured_image_candidates(
    automation_config: GameAutomationConfig,
    image: Image.Image,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    return [
        *tower_loading_wait_candidates(automation_config, buttons),
        *tower_card_fusion_candidates(automation_config, buttons),
        *tower_prebattle_start_candidates(automation_config, image, buttons),
        *tower_reward_overlay_close_candidates(automation_config, image),
        *tower_stair_choice_visual_candidates(automation_config, image, buttons),
        *tower_unreadable_card_reward_skip_candidates(
            automation_config,
            image,
            buttons,
        ),
        *tower_combat_emergency_item_candidates(image, automation_config),
        *tower_map_exit_candidates(image, automation_config, buttons),
        *tower_combat_card_candidates(image, automation_config, buttons),
        *tower_map_room_icon_candidates(image, automation_config, buttons),
    ]


def tower_card_fusion_candidates(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    if normalize_label(automation_config.game) != 'tower':
        return []
    labels = [normalize_label(button.label) for button in buttons]
    if not any('消耗2张相同的牌进行融合' in label for label in labels):
        return []
    if '返回' not in labels or '融合' not in labels:
        return []
    return [
        ButtonCandidate(
            label='融合',
            x=0.72,
            y=0.8375,
            confidence=0.99,
            clickability=20.0,
            source='vision',
            reason='两张同名卡的融合确认页；直接融合以升级核心牌且不增加牌数。',
            score=12.0,
        )
    ]


def tower_reward_overlay_close_candidates(
    automation_config: GameAutomationConfig,
    image: Image.Image,
) -> list[ButtonCandidate]:
    if normalize_label(automation_config.game) != 'tower':
        return []
    rgb = np.asarray(image.convert('RGB').resize((360, 800)))
    title = rgb[80:170, 70:290]
    card = rgb[250:450, 100:260]
    bottom = rgb[700:790, 60:300]
    yellow_title_fraction = np.mean(
        (title[:, :, 0] > 150)
        & (title[:, :, 1] > 100)
        & (title[:, :, 2] < 80)
    )
    bright_card_fraction = np.mean(card.max(axis=2) > 160)
    if not (
        yellow_title_fraction > 0.015
        and bright_card_fraction > 0.06
        and bottom.mean() < 20
    ):
        return []
    return [
        ButtonCandidate(
            label='点击空白处关闭',
            x=0.5,
            y=0.945,
            confidence=0.98,
            clickability=8.0,
            source='vision',
            reason='奖励详情页底部文字过暗；点击固定空白区域关闭。',
        )
    ]


def tower_stair_choice_visual_candidates(
    automation_config: GameAutomationConfig,
    image: Image.Image,
    _buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    """Recover the fixed stair modal when OCR misses its outlined text."""
    if normalize_label(automation_config.game) != 'tower':
        return []

    rgb = np.asarray(image.convert('RGB').resize((360, 800)))
    cancel = rgb[540:610, 40:160]
    confirm = rgb[540:610, 205:325]
    footer = rgb[610:790, 10:350]
    cyan_fraction = np.mean(
        (cancel[:, :, 1] > cancel[:, :, 0] + 10)
        & (cancel[:, :, 2] > cancel[:, :, 0] + 10)
        & (cancel[:, :, 1] > 70)
    )
    yellow_fraction = np.mean(
        (confirm[:, :, 0] > 130)
        & (confirm[:, :, 1] > 95)
        & (confirm[:, :, 2] < 100)
    )
    if not (
        cyan_fraction > 0.12
        and yellow_fraction > 0.035
        and footer.mean() < 35
    ):
        return []

    return [
        ButtonCandidate(
            label='选择一个楼梯',
            x=0.5,
            y=0.26,
            confidence=0.96,
            clickability=2.0,
            source='vision',
            reason='检测到深渊楼梯双路线弹窗。',
        ),
        ButtonCandidate(
            label='左侧楼梯',
            x=0.25,
            y=0.40,
            confidence=0.95,
            clickability=6.0,
            source='vision',
            reason='OCR 漏字时恢复左侧楼梯选择区域。',
            score=1.0,
        ),
        ButtonCandidate(
            label='右侧楼梯',
            x=0.75,
            y=0.40,
            confidence=0.96,
            clickability=6.0,
            source='vision',
            reason='OCR 漏字时默认选择右侧路线并交由确认步骤提交。',
            score=2.0,
        ),
        ButtonCandidate(
            label='确定',
            x=0.73,
            y=0.71,
            confidence=0.97,
            clickability=7.0,
            source='vision',
            reason='深渊楼梯弹窗的固定确认按钮。',
        ),
    ]


def tower_unreadable_card_reward_skip_candidates(
    automation_config: GameAutomationConfig,
    image: Image.Image,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    if normalize_label(automation_config.game) != 'tower':
        return []
    run_state = load_tower_run_state(automation_config.game)
    if normalize_label(str(run_state.get('phase') or '')) != 'card_reward':
        return []
    recognized = {
        normalize_label(button.label)
        for button in buttons
        if button.source != 'template'
    }
    if recognized & ({'放弃'} | CONFIRM_LABELS):
        return []
    rgb = np.asarray(image.convert('RGB').resize((360, 800)), dtype=np.float32)
    left = rgb[540:575, 45:165]
    right = rgb[540:575, 205:325]
    cyan_left = np.mean(
        (left[:, :, 1] > left[:, :, 0] + 15)
        & (left[:, :, 2] > left[:, :, 0] + 20)
    )
    yellow_right = np.mean(
        (right[:, :, 0] > right[:, :, 1] + 20)
        & (right[:, :, 1] > right[:, :, 2] + 20)
    )
    if cyan_left < 0.35 or yellow_right < 0.35:
        return []
    return [
        ButtonCandidate(
            label='放弃',
            x=0.29,
            y=0.697,
            confidence=0.97,
            clickability=9.0,
            source='vision',
            reason='卡牌三选一整屏 OCR 失败；放弃拿金币，避免盲选污染短牌组。',
        )
    ]


def tower_fast_combat_buttons(
    image: Image.Image,
    automation_config: GameAutomationConfig,
) -> list[ButtonCandidate]:
    if normalize_label(automation_config.game) != 'tower':
        return []
    if not tower_combat_screen_visible(image):
        return []
    emergency_items = tower_combat_emergency_item_candidates(
        image,
        automation_config,
    )
    if emergency_items:
        return emergency_items
    return [
        ButtonCandidate(
            label='结束回合',
            x=0.5,
            y=0.92,
            confidence=0.99,
            clickability=4.0,
            source='vision',
            reason='Tower combat fast path: stable local End-turn control.',
        )
    ]


def is_escape_menu_probe_button(button: ButtonCandidate) -> bool:
    return normalize_label(button.label) in ESCAPE_MENU_PROBE_LABELS


def memory_path_for(game: str) -> Path:
    return game_root_for(game) / 'strategy.md'


def game_info_path_for(game: str) -> Path:
    return game_root_for(game) / 'game_info.md'


def ocr_config_path_for(game: str) -> Path:
    return game_root_for(game) / 'ocr_config.yaml'


def tower_run_state_path_for(game: str) -> Path:
    return game_root_for(game) / 'active_run.yaml'


def tower_daily_state_path_for(game: str) -> Path:
    return game_root_for(game) / 'daily_run.yaml'


def tower_shop_refresh_key(
    state: dict[str, Any],
    shop_label: str | None = None,
    position: Iterable[float] | None = None,
) -> str:
    shop_key = normalize_label(
        str(shop_label or state.get('active_shop') or '').strip()
    )
    if shop_key not in TOWER_PURCHASABLE_SHOP_LABELS:
        return ''
    return f'{int(state.get("floor") or 0)}:{shop_key}'


def tower_visible_shop_refresh_count(labels: Iterable[str]) -> int | None:
    counts: list[int] = []
    for label in labels:
        key = normalize_label(str(label))
        match = re.search(r'(?:已|巳)?刷新\s*(\d+)\s*次', key)
        if match:
            counts.append(int(match.group(1)))
    return max(counts) if counts else None


def normalize_tower_shop_refresh_state(state: dict[str, Any]) -> None:
    history = dict(state.get('shop_refresh_history') or {})
    if not history:
        return

    canonical_counts: dict[str, int] = {}
    legacy_counts: dict[str, int] = {}
    for raw_key, raw_count in history.items():
        parts = str(raw_key).split(':')
        if len(parts) < 2:
            continue
        canonical_key = f'{parts[0]}:{parts[1]}'
        count = max(0, int(raw_count or 0))
        target = canonical_counts if len(parts) == 2 else legacy_counts
        target[canonical_key] = target.get(canonical_key, 0) + count

    normalized = {
        key: max(count, legacy_counts.get(key, 0))
        for key, count in canonical_counts.items()
    }
    for key, count in legacy_counts.items():
        normalized.setdefault(key, count)
    state['shop_refresh_history'] = normalized

    active_key = tower_shop_refresh_key(state)
    if active_key:
        state['active_shop_key'] = active_key
        state['shop_refresh_count'] = max(
            int(state.get('shop_refresh_count') or 0),
            normalized.get(active_key, 0),
        )


def load_tower_run_state(game: str) -> dict[str, Any]:
    path = tower_run_state_path_for(game)
    if not path.exists():
        return {}
    state = safe_load_yaml_mapping(path)
    normalize_tower_shop_refresh_state(state)
    return state


def load_tower_daily_state(game: str) -> dict[str, Any]:
    path = tower_daily_state_path_for(game)
    if not path.exists():
        return {}
    return safe_load_yaml_mapping(path)


def write_tower_daily_state(game: str, state: dict[str, Any]) -> None:
    path = tower_daily_state_path_for(game)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            state,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    )


def ensure_tower_daily_state(game: str) -> dict[str, Any]:
    if normalize_label(game) != 'tower':
        return {}
    today = datetime.now().astimezone().date().isoformat()
    state = load_tower_daily_state(game)
    if state.get('date') != today:
        state = {
            'version': 1,
            'date': today,
            'phase': 'abyss',
            'abyss_target_floor': 124,
            'never_sell': True,
            'recruit_if_available': True,
            'recruited_character_name': '',
            'recruited_character_power': None,
            'character_selected': False,
            'selection_swipes': 0,
            'predecessor_rerolls': 0,
            'notes': [],
        }
        write_tower_daily_state(game, state)
    return state


def configure_tower_daily_focus(game: str, focus: str) -> None:
    if normalize_label(game) != 'tower' or focus == 'workflow':
        return
    state = load_tower_daily_state(game)
    if not state:
        return
    state['focus'] = focus
    phase = normalize_label(str(state.get('phase') or ''))
    if focus == 'abyss' and phase not in {'abyss', 'abyss_retry'}:
        state['phase'] = 'abyss_retry'
    elif focus == 'spire' and phase not in {'go_to_spire', 'spire_running'}:
        state['phase'] = 'go_to_spire'
        state['character_selected'] = False
        state.pop('spire_victory', None)
    elif focus == 'recruit_spire' and phase not in {
        'recruit',
        'recruit_result',
        'go_to_spire',
        'spire_running',
    }:
        state['phase'] = 'recruit'
        state['recruited_character_name'] = ''
        state['recruited_character_power'] = None
        state['character_selected'] = False
        state['selection_swipes'] = 0
        state.pop('spire_victory', None)
        state.pop('spire_attempts_exhausted', None)
        state.pop('recruitment_blocked_by_capacity', None)
    write_tower_daily_state(game, state)


def tower_daily_completion_reason(state: dict[str, Any]) -> str:
    focus = normalize_label(str(state.get('focus') or ''))
    if focus == 'recruit_spire':
        if state.get('spire_victory'):
            return '招募一次并通关尖塔木屋，流程完成。'
        if state.get('recruitment_blocked_by_capacity'):
            return '见习冒险者容量已满；未解雇角色，招募尖塔流程停止。'
        if state.get('spire_attempts_exhausted'):
            return '已招募并挑战尖塔；今日次数已用完，未购买次数。'
        return '招募一次并挑战尖塔木屋，流程已结束。'
    if focus == 'spire':
        return '尖塔木屋已通关，尖塔专注流程完成。'
    return '今日深渊、招募和新角色尖塔木屋流程已完成。'


def tower_recruit_identity(
    buttons: list[ButtonCandidate],
) -> tuple[str, int | None]:
    ignored = {
        '招募',
        '招募中',
        '拒绝',
        '雇佣',
        '卡牌',
        '未激活宝物',
        '生命',
        '物攻',
        '法力',
    }
    names = [
        button
        for button in buttons
        if button.source != 'template'
        and 0.07 <= button.y <= 0.22
        and 0.25 <= button.x <= 0.75
        and normalize_label(button.label) not in ignored
        and not re.fullmatch(r'\d+', normalize_label(button.label))
        and 2 <= len(button.label.strip()) <= 16
    ]
    powers = [
        int(normalize_label(button.label))
        for button in buttons
        if button.source != 'template'
        and 0.05 <= button.y <= 0.18
        and re.fullmatch(r'\d{3,6}', normalize_label(button.label))
    ]
    name = max(names, key=lambda button: button.confidence).label if names else ''
    power = max(powers) if powers else None
    return name, power


def update_tower_daily_state(
    game: str,
    buttons: list[ButtonCandidate],
    *,
    clicked_label: str = '',
    action_succeeded: bool = True,
) -> None:
    if normalize_label(game) != 'tower':
        return
    state = load_tower_daily_state(game)
    if not state:
        return
    phase = normalize_label(str(state.get('phase') or ''))
    labels = [button.label.strip() for button in buttons if button.label.strip()]
    normalized = [normalize_label(label) for label in labels]
    action = normalize_label(clicked_label)
    now = datetime.now().astimezone().isoformat(timespec='seconds')

    free_recruits_remaining = tower_free_recruits_remaining(normalized)
    spire_floor_visible = any(
        re.search(r'当前层数\s*\d+\s*/\s*\d+', label)
        for label in normalized
    )
    if phase == 'go_to_spire' and spire_floor_visible:
        state['phase'] = 'spire_running'
        state['character_selected'] = True
        phase = 'spire_running'

    ordinary_recruits_exhausted = any(
        re.fullmatch(r'0\s*/\s*\d+', label) for label in normalized
    )
    recruits_exhausted = free_recruits_remaining == 0 or (
        free_recruits_remaining is None and ordinary_recruits_exhausted
    )
    if phase in {'recruit', 'recruit_all'} and recruits_exhausted:
        state['phase'] = 'complete' if phase == 'recruit_all' else 'go_to_spire'
        if phase == 'recruit_all':
            state['completed_at'] = now
        state.setdefault('notes', []).append('今日招募次数已用完。')
    joined_result = any('正式加入' in label for label in normalized)
    if phase in {'recruit_result', 'recruit_all_result'} and joined_result:
        name, power = tower_recruit_identity(buttons)
        if phase == 'recruit_result' and name:
            state['recruited_character_name'] = name
        if phase == 'recruit_result' and power is not None:
            state['recruited_character_power'] = power
        if phase == 'recruit_all_result' and name:
            recruits = list(state.get('recruited_characters') or [])
            recruit = {'name': name, 'power': power}
            if recruit not in recruits:
                recruits.append(recruit)
            state['recruited_characters'] = recruits

    if clicked_label and action_succeeded:
        state['last_action'] = clicked_label
        if (
            phase in {'go_to_spire', 'spire_running'}
            and action == '关闭尖塔次数提示'
        ):
            state['phase'] = 'complete'
            state['completed_at'] = now
            state['spire_attempts_exhausted'] = True
            state.setdefault('notes', []).append(
                '尖塔木屋今日次数已用完；返回冒险页并停止，未购买次数。'
            )
        elif phase in {'recruit', 'recruit_all'} and action == '取消招募容量弹窗':
            recruit_spire_focus = (
                normalize_label(str(state.get('focus') or '')) == 'recruit_spire'
            )
            state['phase'] = 'complete' if recruit_spire_focus else 'abyss_retry'
            if recruit_spire_focus:
                state['completed_at'] = now
            state['recruitment_blocked_by_capacity'] = True
            state.setdefault('notes', []).append(
                '见习冒险者容量已满；为遵守绝不解雇/出售，'
                '剩余招募无法继续。'
            )
        elif phase == 'abyss' and action in {'返回旅馆', 'return to inn'}:
            run_state = load_tower_run_state(game)
            abyss_focus = normalize_label(str(state.get('focus') or '')) == 'abyss'
            if run_state.get('reroll_predecessor') or abyss_focus:
                state['phase'] = 'abyss_retry'
                state.setdefault('notes', []).append(
                    '前辈职业宝物不匹配，返回旅馆后继续重开深渊。'
                    if run_state.get('reroll_predecessor')
                    else '深渊专注模式：本局结束后立即重开深渊。'
                )
            else:
                state['phase'] = 'recruit'
                state.setdefault('notes', []).append(
                    '深渊挑战已结束，转入旅馆招募。'
                )
        elif phase == 'abyss_retry' and action in {
            '返回旅馆',
            'return to inn',
        }:
            run_state = load_tower_run_state(game)
            abyss_focus = normalize_label(str(state.get('focus') or '')) == 'abyss'
            if run_state.get('reroll_predecessor') or abyss_focus:
                state.setdefault('notes', []).append(
                    '前辈职业宝物不匹配，返回旅馆后继续重开深渊。'
                    if run_state.get('reroll_predecessor')
                    else '深渊专注模式：本局结束后立即重开深渊。'
                )
            else:
                state['phase'] = 'recruit_all'
                state.setdefault('notes', []).append(
                    '追加深渊挑战已结束，使用今日剩余招募次数。'
                )
        elif phase == 'recruit' and action in {'雇佣', 'hire', 'hire adventurer'}:
            state['phase'] = 'recruit_result'
        elif phase == 'recruit_all' and action in {
            '雇佣',
            'hire',
            'hire adventurer',
        }:
            state['phase'] = 'recruit_all_result'
        elif phase == 'recruit_result' and action == '关闭招募结果':
            state['phase'] = 'go_to_spire'
        elif phase == 'recruit_all_result' and action == '关闭招募结果':
            state['phase'] = 'recruit_all'
        elif phase == 'go_to_spire' and action.startswith('选择新招募角色'):
            state['character_selected'] = True
        elif phase == 'go_to_spire' and action in {
            '向下查找新招募角色',
            '向上查找新招募角色',
        }:
            state['selection_swipes'] = int(state.get('selection_swipes') or 0) + 1
        elif phase == 'go_to_spire' and action in {'开始冒险', 'start adventure'}:
            state['phase'] = 'spire_running'
        elif phase == 'spire_running' and action in {
            '冒险胜利',
            '马上离开（冒险者转正）',
            '马上离开(冒险者转正)',
        }:
            state['spire_victory'] = True
        elif phase == 'spire_running' and action in {
            '返回旅馆',
            'return to inn',
        }:
            if normalize_label(str(state.get('focus') or '')) in {
                'spire',
                'recruit_spire',
            }:
                if state.get('spire_victory'):
                    state['phase'] = 'complete'
                    state['completed_at'] = now
                    state.setdefault('notes', []).append(
                        '尖塔木屋已通关，尖塔专注流程完成。'
                    )
                else:
                    state['phase'] = 'go_to_spire'
                    state['character_selected'] = False
                    state.setdefault('notes', []).append(
                        '尖塔木屋挑战未通关，按尖塔专注模式重试。'
                    )
            else:
                state['phase'] = 'abyss_retry'
                state.setdefault('notes', []).append(
                    '尖塔木屋已结束，优先再次挑战深渊楼梯。'
                )
    state['updated_at'] = now
    write_tower_daily_state(game, state)


def tower_daily_matching_button(
    buttons: list[ButtonCandidate],
    labels: set[str],
) -> ButtonCandidate | None:
    matches = [
        button for button in buttons if normalize_label(button.label) in labels
    ]
    if not matches:
        return None
    return max(
        matches,
        key=lambda button: (
            button.source != 'template',
            button.clickability,
            button.confidence,
            button.y,
        ),
    )


def tower_free_recruits_remaining(labels: Iterable[str]) -> int | None:
    for label in labels:
        key = normalize_label(label)
        match = re.search(r'免费\s*[（(]?\s*(\d+)\s*/\s*\d+\s*[）)]?', key)
        if match:
            return int(match.group(1))
    return None


def tower_paid_recruit_prompt_visible(labels: Iterable[str]) -> bool:
    text = ' '.join(normalize_label(label) for label in labels)
    return '消耗' in text and '萝卜' in text and '招募次数' in text


def tower_recruit_blocking_modal_candidates(
    game: str,
    image: Image.Image,
) -> list[ButtonCandidate]:
    phase = normalize_label(str(load_tower_daily_state(game).get('phase') or ''))
    if normalize_label(game) != 'tower' or phase not in {
        'recruit',
        'recruit_all',
    }:
        return []
    rgb = np.asarray(image.convert('RGB').resize((360, 800)), dtype=np.float32)

    def mean_rgb(left: float, top: float, right: float, bottom: float) -> np.ndarray:
        crop = rgb[
            int(top * 800) : int(bottom * 800),
            int(left * 360) : int(right * 360),
        ]
        return crop.mean(axis=(0, 1))

    left_button = mean_rgb(0.18, 0.58, 0.43, 0.63)
    right_button = mean_rgb(0.57, 0.58, 0.82, 0.63)
    dimmed_background = mean_rgb(0.07, 0.66, 0.93, 0.80)
    cyan_left = (
        left_button[1] > left_button[0] + 20
        and left_button[2] > left_button[0] + 25
    )
    yellow_right = (
        right_button[0] > right_button[1] + 15
        and right_button[1] > right_button[2] + 25
    )
    if not (cyan_left and yellow_right and dimmed_background.mean() < 30):
        return []
    return [
        ButtonCandidate(
            label='取消招募容量弹窗',
            x=0.30,
            y=0.60,
            confidence=0.98,
            clickability=20.0,
            source='vision',
            reason=(
                '招募界面出现双按钮阻断弹窗；选左侧取消，'
                '禁止前往解雇或付费。'
            ),
        )
    ]


def tower_daily_policy_candidates(
    game: str,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate] | None:
    state = load_tower_daily_state(game)
    if normalize_label(game) != 'tower' or not state:
        return None
    phase = normalize_label(str(state.get('phase') or ''))
    labels = {normalize_label(button.label) for button in buttons}
    waiting = next((button for button in buttons if button.source == 'wait'), None)
    if waiting is not None:
        return [waiting]
    if phase == 'complete':
        return []

    run_state = load_tower_run_state(game)
    shop_sparkle = next(
        (
            button
            for button in buttons
            if normalize_label(button.label)
            == normalize_label(TOWER_SHOP_SPARKLE_LABEL)
        ),
        None,
    )
    if shop_sparkle is not None:
        return [
            replace(
                shop_sparkle,
                clickability=max(shop_sparkle.clickability, 30.0),
                reason=(
                    '商店右上有免费闪光奖励；先领取金币或水晶，'
                    '再购买、刷新或离店。'
                ),
            )
        ]
    active_abyss_phases = {
        'initial_setup',
        'climbing_map',
        'route_choice',
        'prebattle',
        'combat',
        'card_reward',
    }
    visible_abyss_ui = bool(
        labels
        & {
            '选择一个楼梯',
            '左侧楼梯',
            '右侧楼梯',
            '进入下一层',
            '当前所在层数',
            '战斗',
            '结束回合',
            '选一张卡牌学习',
        }
    ) or any(
        label.startswith('visible playable card')
        or label.startswith('结束第')
        or label.startswith('当前层数')
        for label in labels
    ) or any(is_tower_room_vision_candidate(button) for button in buttons)
    stale_daily_phase_during_abyss = (
        phase not in {'abyss', 'abyss_retry', 'go_to_spire'}
        and normalize_label(str(run_state.get('stage') or '')) == '深渊楼梯'
        and normalize_label(str(run_state.get('phase') or ''))
        in active_abyss_phases
        and visible_abyss_ui
    )
    if stale_daily_phase_during_abyss and not any(
        run_state.get(flag)
        for flag in (
            'awaiting_route_after_reward',
            'post_revive_route_guard',
            'reroll_predecessor',
        )
    ):
        return None
    if stale_daily_phase_during_abyss:
        phase = 'abyss_retry'

    def choose(keys: set[str], reason: str) -> list[ButtonCandidate] | None:
        button = tower_daily_matching_button(buttons, keys)
        if button is None:
            return None
        return [
            replace(
                button,
                clickability=max(button.clickability, 20.0),
                reason=reason,
            )
        ]

    if phase in {'go_to_spire', 'spire_running'} and '今日次数已用完' in labels:
        return [
            ButtonCandidate(
                label='关闭尖塔次数提示',
                x=0.10,
                y=0.965,
                confidence=0.99,
                clickability=20.0,
                source='state',
                reason=(
                    '尖塔今日次数已用完；点击左下角返回冒险页并停止，'
                    '禁止点击刷新倒计时或购买次数。'
                ),
            )
        ]

    if phase in {'recruit', 'recruit_all'} and tower_paid_recruit_prompt_visible(
        labels
    ):
        remaining = tower_free_recruits_remaining(labels)
        free_buttons = [
            button
            for button in buttons
            if tower_free_recruits_remaining([button.label]) not in {None, 0}
        ]
        if remaining and free_buttons:
            button = max(free_buttons, key=lambda candidate: candidate.confidence)
            return [
                replace(
                    button,
                    clickability=max(button.clickability, 20.0),
                    reason=(
                        '招募普通次数已用完，只使用左侧免费广告次数；'
                        '禁止点击花费萝卜的确认按钮。'
                    ),
                )
            ]
        return []

    if phase in {'abyss', 'abyss_retry'}:
        talking_stairs_reward = next(
            (
                button
                for button in buttons
                if '拿走' in normalize_label(button.label)
                and any(
                    blood in normalize_label(button.label)
                    for blood in ('深澜龙血', '深渊龙血')
                )
            ),
            None,
        )
        if '说话的楼梯' in labels and talking_stairs_reward is not None:
            return [
                replace(
                    talking_stairs_reward,
                    clickability=max(talking_stairs_reward.clickability, 25.0),
                    reason=(
                        '说话的楼梯固定提供深澜龙血；优先拿走保命消耗品，'
                        '并压过透过弹窗误识别的旧房间模板。'
                    ),
                )
            ]
        talking_stairs_room = next(
            (
                button
                for button in buttons
                if normalize_label(button.label) == '说话的楼梯'
                and button.y >= 0.55
            ),
            None,
        )
        map_hud_visible = bool(
            labels
            & {
                '当前所在层数',
                '全服最高层数',
                '冒险者携带的未激活宝物',
            }
        )
        if talking_stairs_room is not None and map_hud_visible:
            return [
                replace(
                    talking_stairs_room,
                    clickability=max(talking_stairs_room.clickability, 25.0),
                    reason=(
                        '地图上的说话的楼梯是未完成房间；进入后领取'
                        '深澜龙血并继续爬层。'
                    ),
                )
            ]
        trainer_reward_claim = next(
            (
                button
                for button in buttons
                if normalize_label(button.label) == '领取'
            ),
            None,
        )
        trainer_reward_panel_visible = (
            '训练师任务' in labels
            and any('还可以领取' in label for label in labels)
        )
        unsafe_trainer_reward = bool(
            run_state.get('skip_unsafe_trainer_reward')
        ) or any('敌方物攻增加100点' in label for label in labels)
        if trainer_reward_panel_visible and unsafe_trainer_reward:
            trainer_panel_exit = next(
                (
                    button
                    for button in buttons
                    if normalize_label(button.label) == '返回'
                    and button.source != 'template'
                ),
                None,
            )
            if trainer_panel_exit is not None:
                return [
                    replace(
                        trainer_panel_exit,
                        clickability=max(trainer_panel_exit.clickability, 25.0),
                        reason=(
                            '已检查训练师红点，但奖励天赋会使敌方物攻增加100点；'
                            '为保证深渊后手生存，跳过领取并返回。'
                        ),
                    )
                ]
        if trainer_reward_claim is not None and trainer_reward_panel_visible:
            return [
                replace(
                    trainer_reward_claim,
                    clickability=max(trainer_reward_claim.clickability, 25.0),
                    reason='训练师任务已经完成；领取并激活对应天赋。',
                )
            ]
        if trainer_reward_panel_visible:
            trainer_panel_close = next(
                (
                    button
                    for button in buttons
                    if normalize_label(button.label) == '点击空白处关闭'
                    and button.source != 'template'
                ),
                None,
            )
            if trainer_panel_close is not None:
                return [
                    replace(
                        trainer_panel_close,
                        clickability=max(trainer_panel_close.clickability, 25.0),
                        reason=(
                            '训练师任务面板没有可领取奖励；关闭遮罩后继续爬塔，'
                            '不要点击透过遮罩误识别出的道路模板。'
                        ),
                    )
                ]
        trainer_task_reward = next(
            (
                button
                for button in buttons
                if any(
                    marker in normalize_label(button.reason)
                    for marker in (
                        'tower trainer task reward badge',
                        'tower trainer task post-battle check',
                    )
                )
            ),
            None,
        )
        if trainer_task_reward is not None:
            return [
                replace(
                    trainer_task_reward,
                    clickability=max(trainer_task_reward.clickability, 25.0),
                    reason='训练师任务已完成；立即打开任务面板，领取并激活天赋奖励。',
                )
            ]
        card_fusion = next(
            (
                button
                for button in buttons
                if normalize_label(button.label) == '融合'
                and button.source != 'template'
                and button.y >= 0.78
            ),
            None,
        )
        fusion_detail_visible = any(
            '相同的牌进行融合' in normalize_label(button.label)
            for button in buttons
        )
        if card_fusion is not None and fusion_detail_visible:
            return [
                replace(
                    card_fusion,
                    clickability=max(card_fusion.clickability, 24.0),
                    reason='同名牌融合确认页；完成无增牌数升级后继续深渊。',
                )
            ]
        last_room_key = normalize_label(
            str(
                run_state.get('active_shop')
                or run_state.get('last_room_action')
                or ''
            )
        )
        magic_shop_change_complete = bool(
            run_state.get('magic_shop_change_complete')
        )
        if (
            last_room_key == '魔术商店'
            and magic_shop_change_complete
            and '卡牌变化' in labels
        ):
            selected = choose(
                {'放弃'},
                '本魔术商店已经完成一次换牌；放弃重复变化，避免继续花费。',
            )
            if selected is not None:
                return selected
        if (
            last_room_key == '魔术商店'
            and {'魔术商店', '变化法阵'} <= labels
        ):
            if magic_shop_change_complete:
                selected = choose(
                    {'返回'},
                    '本魔术商店已换过一张废牌；立即返回深渊地图。',
                )
                if selected is not None:
                    return selected
            return None
        if (
            last_room_key in TOWER_PURCHASABLE_SHOP_LABELS
            and last_room_key in labels
            and '返回' in labels
        ):
            if tower_real_money_purchase_prompt_visible(labels):
                selected = choose(
                    {'取消', '返回'},
                    '仅允许使用局内金币或水晶；退出真钱充值或礼包购买界面。',
                )
                return selected or []
            pending_purchase = str(run_state.get('last_action') or '').strip()
            if (
                tower_shop_purchase_bonus(game, pending_purchase) > 0
                and bool(labels & CONFIRM_LABELS)
            ):
                selected = choose(
                    CONFIRM_LABELS,
                    (
                        f'已选中高价值商品“{pending_purchase}”；先确认购买，'
                        '禁止刷新覆盖当前选择。'
                    ),
                )
                if selected is not None:
                    return selected
            if any(
                tower_shop_purchase_bonus(game, button.label) > 0
                for button in buttons
            ):
                return None
            refresh_count = int(run_state.get('shop_refresh_count') or 0)
            refresh_limit = max(
                2,
                int((run_state.get('policy') or {}).get('shop_refresh_limit') or 0),
            )
            refresh_buttons = [
                button
                for button in buttons
                if normalize_label(button.label).startswith('刷新')
                or (
                    normalize_label(button.label).startswith('免费')
                    and '次' in normalize_label(button.label)
                )
            ]
            failed_refresh = normalize_label(
                str(run_state.get('last_failed_action') or '')
            )
            refresh_buttons = [
                button
                for button in refresh_buttons
                if normalize_label(button.label) != failed_refresh
            ]
            if refresh_count < refresh_limit and refresh_buttons:
                refresh = max(
                    refresh_buttons,
                    key=lambda button: (
                        normalize_label(button.label).startswith('免费'),
                        button.confidence,
                    ),
                )
                return [
                    replace(
                        refresh,
                        x=0.14,
                        y=0.303,
                        clickability=max(refresh.clickability, 22.0),
                        reason=(
                            f'本店尚无赚钱、加血或循环核心；使用第'
                            f'{refresh_count + 1}/{refresh_limit}次刷新继续寻找。'
                        ),
                    )
                ]
            selected = choose(
                {'返回'},
                '已刷新两次仍无赚钱、加血或循环核心；保留资源并返回。',
            )
            if selected is not None:
                return selected
        magic_shop_exit = next(
            (
                button
                for button in buttons
                if normalize_label(button.label) == '返回'
                and button.source == 'vision'
                and 'shop footer' in button.reason
            ),
            None,
        )
        if magic_shop_exit is not None:
            return [
                replace(
                    magic_shop_exit,
                    clickability=max(magic_shop_exit.clickability, 20.0),
                    reason='魔术商店换牌已经完成；返回深渊地图继续爬层。',
                )
            ]
        if '冒险结束' in labels:
            selected = choose(
                {'返回旅馆', 'return to inn'},
                '深渊本局已经结算；返回旅馆后重新开始深渊挑战。',
            )
            if selected is not None:
                return selected
        run_phase = normalize_label(str(run_state.get('phase') or ''))
        if run_state.get('post_revive_route_guard') and run_phase != 'complete':
            map_hud_visible = bool(
                labels
                & {
                    '当前所在层数',
                    '全服最高层数',
                    '冒险者携带的未激活宝物',
                }
            ) or any(
                is_tower_room_vision_candidate(button) for button in buttons
            )
            if run_phase == 'prebattle':
                selected = choose(
                    {'战斗', 'fight', 'battle'},
                    '广告复活后游戏强制返回原战斗；继续复活后的战斗。',
                )
                if selected is not None:
                    return selected
            if run_phase == 'combat' and not map_hud_visible:
                return None
            rest_rooms = [
                button
                for button in buttons
                if normalize_label(button.label)
                in {'休息点', 'visible rest room icon'}
            ]
            if rest_rooms:
                button = max(
                    rest_rooms,
                    key=lambda candidate: (
                        normalize_label(candidate.label) == '休息点',
                        candidate.confidence,
                    ),
                )
                return [
                    replace(
                        button,
                        clickability=max(button.clickability, 24.0),
                        reason='广告复活后优先进入休息点回血，禁止重撞刚才的险房。',
                    )
                ]
            for keys, reason in (
                (
                    {'进入下一层', '下一层', '进人下', '进入下'},
                    '广告复活后先进入下一层，脱离刚才导致阵亡的房间。',
                ),
                (
                    {'左侧道路', '右侧道路', '上方道路', '下方道路'},
                    '广告复活后沿道路离开当前险房，禁止立即重战。',
                ),
            ):
                selected = choose(keys, reason)
                if selected is not None:
                    return selected
            current_room = (
                max(
                    (
                        button
                        for button in buttons
                        if (
                            is_tower_room_vision_candidate(button)
                            or button.source == 'ocr'
                        )
                        and 0.15 <= button.x <= 0.85
                        and 0.64 <= button.y <= 0.74
                        and normalize_label(button.label)
                        not in {
                            '当前所在层数',
                            '全服最高层数',
                            '获得的战利品',
                            '冒险者携带的未激活宝物',
                        }
                    ),
                    key=lambda button: (button.confidence, button.clickability),
                    default=None,
                )
                if map_hud_visible
                else None
            )
            if current_room is not None:
                return [
                    replace(
                        current_room,
                        label='Visible current room icon',
                        y=max(0.64, current_room.y - 0.02),
                        confidence=max(current_room.confidence, 0.96),
                        clickability=max(current_room.clickability, 20.0),
                        source='vision',
                        reason=(
                            '广告复活后地图没有退路；点击当前怪物房间，'
                            '恢复尚未结束的战斗。'
                        ),
                    )
                ]
            return []
        if run_state.get('reroll_predecessor') and {
            '返回旅馆',
            '继续冒险',
        } <= labels:
            selected = choose(
                {'返回旅馆', 'return to inn'},
                '前辈宝物不匹配；从设置面板返回旅馆后彻底放弃旧冒险。',
            )
            if selected is not None:
                return selected
        if run_state.get('reroll_predecessor'):
            if any('确认放弃战斗' in label for label in labels):
                selected = choose(
                    {'好的', '确定', 'ok', 'confirm'},
                    '确认结束未成型的战斗，立即重开深渊。',
                )
                if selected is not None:
                    return selected
            selected = choose(
                {'放弃战斗', 'abandon battle'},
                '设置面板已打开；结束未成型局并重开深渊。',
            )
            if selected is not None:
                return selected
        if run_state.get('reroll_predecessor') and run_phase in {
            'climbing_map',
            'prebattle',
            'combat',
        }:
            selected = choose(
                {'设置', 'settings'},
                '前辈宝物不匹配；奖励关闭后打开设置直接结束'
                '本局并重刷，不多走房间。',
            )
            if selected is not None:
                return selected
        if run_state.get('awaiting_route_after_reward') and not run_state.get(
            'reroll_predecessor'
        ):
            run_phase = normalize_label(str(run_state.get('phase') or ''))
            if run_phase == 'prebattle':
                selected = choose(
                    {'战斗', 'fight', 'battle'},
                    '已经进入下一间战斗预览；清除上一房间的领奖导航限制并开战。',
                )
                if selected is not None:
                    return selected
            card_reward_visible = run_phase == 'card_reward' and (
                '放弃' in labels
                or bool(labels & CONFIRM_LABELS)
                or any('选一张卡牌' in label for label in labels)
            )
            reward_detail_visible = run_phase == 'reward_detail' and (
                '点击空白处关闭' in labels or '恭喜获得' in labels
            )
            if card_reward_visible or reward_detail_visible:
                return None
            if '角色升级' in labels:
                selected = choose(
                    {'好的', '确定', 'ok', 'confirm'},
                    '先关闭角色升级弹窗，再离开已完成房间。',
                )
                if selected is not None:
                    return selected
            for keys, reason in (
                (
                    {'进入下一层', '下一层', '进人下', '进入下'},
                    '奖励已经结算；先进入下一层，禁止重新点击已完成房间。',
                ),
                (
                    {'左侧道路', '右侧道路', '上方道路', '下方道路'},
                    '奖励已经结算；强制沿可见道路离开已完成房间。',
                ),
            ):
                selected = choose(keys, reason)
                if selected is not None:
                    return selected
            last_room_position = run_state.get('last_room_position') or []
            new_rooms = [
                button
                for button in buttons
                if is_tower_room_vision_candidate(button)
                and 0.58 <= button.y <= 0.87
                and (
                    len(last_room_position) != 2
                    or (
                        abs(button.x - float(last_room_position[0]))
                        + abs(button.y - float(last_room_position[1]))
                    )
                    >= 0.10
                )
            ]
            if new_rooms:
                button = max(
                    new_rooms,
                    key=lambda candidate: (
                        (
                            abs(candidate.x - float(last_room_position[0]))
                            + abs(candidate.y - float(last_room_position[1]))
                            if len(last_room_position) == 2
                            else abs(candidate.x - 0.5)
                        ),
                        candidate.confidence,
                    ),
                )
                return [
                    replace(
                        button,
                        clickability=max(button.clickability, 20.0),
                        reason=(
                            '奖励已经结算且没有道路按钮；离开中央已完成房间，'
                            '进入侧边的新房间。'
                        ),
                    )
                ]
            return []
        if run_state.get('reroll_predecessor'):
            run_phase = normalize_label(str(run_state.get('phase') or ''))
            if '角色升级' in labels:
                selected = choose(
                    {'好的', '确定', 'ok', 'confirm'},
                    '先关闭角色升级弹窗，再结束弱开局并重刷前辈宝物。',
                )
                if selected is not None:
                    return selected
            if '胜利' in labels:
                selected = choose(
                    {'好的', '确定', 'ok', 'confirm'},
                    '先关闭当前战斗胜利弹窗，再结束弱开局并重刷前辈宝物。',
                )
                if selected is not None:
                    return selected
            if run_phase in {'route_choice', 'card_reward', 'reward_detail'}:
                return None
            if any('确认放弃冒险' in label for label in labels):
                selected = choose(
                    {'好的', '确定', 'ok', 'confirm'},
                    '确认结束旧冒险，确保下一局重新随机前辈宝物。',
                )
                if selected is not None:
                    return selected
            selected = choose(
                {'放弃冒险', 'abandon adventure'},
                '旧冒险仍可恢复；彻底放弃后再开始，刷新前辈宝物。',
            )
            if selected is not None:
                return selected
            if any('确认放弃战斗' in label for label in labels):
                selected = choose(
                    {'好的', '确定', 'ok', 'confirm'},
                    '前辈职业宝物不匹配速刷流派，确认放弃并重刷。',
                )
                if selected is not None:
                    return selected
            selected = choose(
                {'放弃战斗', 'abandon battle'},
                '前辈职业宝物不匹配速刷流派，放弃本局重刷。',
            )
            if selected is not None:
                return selected
            selected = choose(
                {'返回旅馆', 'return to inn'},
                '错误宝物局已结束，返回后重新进入深渊。',
            )
            if selected is not None:
                return selected
            if run_phase in {'combat', 'climbing_map', 'prebattle'}:
                selected = choose(
                    {'设置', 'settings'},
                    '前辈宝物不匹配，打开设置直接结束本局并重刷。',
                )
                if selected is not None:
                    return selected
            for keys, reason in (
                (
                    {'进入下一层', '下一层', '进人下', '进入下'},
                    '进入下一层寻找最近战斗，再放弃错误宝物局。',
                ),
                (
                    {'左侧道路', '右侧道路', '上方道路', '下方道路'},
                    '沿当前可见道路前往最近房间，再进入战斗放弃错误宝物局。',
                ),
                ({'战斗', 'fight', 'battle'}, '进入最近的战斗以便放弃并重刷职业宝物。'),
                (
                    {'visible combat room icon'},
                    '前辈宝物不合格，优先进入普通战斗后放弃重刷。',
                ),
            ):
                selected = choose(keys, reason)
                if selected is not None:
                    return selected
        for keys, reason in (
            ({'开始冒险', 'start adventure'}, '深渊挑战：开始已选定的冒险。'),
            ({'进入冒险', 'enter adventure'}, '深渊挑战：进入深渊楼梯。'),
            ({'深渊楼梯'}, '深渊挑战：选择深渊楼梯。'),
            ({'冒险', 'adventure'}, '深渊挑战：从主界面打开冒险。'),
        ):
            selected = choose(keys, reason)
            if selected is not None:
                return selected
        return None

    if phase == 'recruit':
        for keys, reason in (
            ({'雇佣', 'hire', 'hire adventurer'}, '每日招募：雇佣当前报名者。'),
            ({'招募', '招募中', 'recruit'}, '每日招募：打开下一位报名者。'),
            ({'旅馆', 'tavern'}, '每日招募：进入旅馆。'),
            ({'返回', 'back'}, '每日招募：先离开深渊关卡页。'),
        ):
            selected = choose(keys, reason)
            if selected is not None:
                return selected
        return None

    if phase == 'recruit_result':
        if any('正式加入' in label for label in labels):
            return [
                ButtonCandidate(
                    label='关闭招募结果',
                    x=0.5,
                    y=0.75,
                    confidence=0.99,
                    clickability=20.0,
                    source='vision',
                    reason='招募成功，关闭结果页后前往尖塔木屋。',
                )
            ]
        return None

    if phase in {'recruit_all', 'recruit_all_result'}:
        selected = choose(
            {'取消招募容量弹窗'},
            '角色容量已满；取消招募并转回深渊，绝不解雇或出售角色。',
        )
        if selected is not None:
            return selected
        if phase == 'recruit_all_result' and any(
            '正式加入' in label for label in labels
        ):
            return [
                ButtonCandidate(
                    label='关闭招募结果',
                    x=0.5,
                    y=0.75,
                    confidence=0.99,
                    clickability=20.0,
                    source='vision',
                    reason='招募成功，关闭结果页后继续使用剩余招募次数。',
                )
            ]
        for keys, reason in (
            ({'雇佣', 'hire', 'hire adventurer'}, '连续招募：雇佣当前报名者。'),
            ({'招募', '招募中', 'recruit'}, '连续招募：打开下一位报名者。'),
            ({'旅馆', 'tavern'}, '连续招募：进入旅馆。'),
            ({'返回', 'back'}, '连续招募：返回旅馆招募入口。'),
        ):
            selected = choose(keys, reason)
            if selected is not None:
                return selected
        return None

    if phase == 'go_to_spire':
        run_stage = normalize_label(str(run_state.get('stage') or ''))
        run_phase = normalize_label(str(run_state.get('phase') or ''))
        wrong_deep_visible = run_stage == '深渊楼梯' or any(
            '深渊楼梯' in label
            or ('每日无尽' in label and '楼梯' in label)
            for label in labels
        )
        if wrong_deep_visible:
            selected = choose(
                {'我再想想'},
                '目标已切换为尖塔；先关闭当前深渊房间的奖励提示。',
            )
            if selected is not None:
                return selected
            if any('确认放弃冒险' in label for label in labels) or any(
                '确认放弃战斗' in label for label in labels
            ):
                selected = choose(
                    {'好的', '确定', 'ok', 'confirm'},
                    '目标已切换为尖塔；确认结束误入的深渊冒险。',
                )
                if selected is not None:
                    return selected
            for keys, reason in (
                (
                    {'放弃冒险', 'abandon adventure'},
                    '目标已切换为尖塔；彻底放弃可恢复的深渊冒险。',
                ),
                (
                    {'放弃战斗', 'abandon battle'},
                    '目标已切换为尖塔；结束误入的深渊战斗。',
                ),
                (
                    {'返回旅馆', 'return to inn'},
                    '目标已切换为尖塔；从深渊设置返回旅馆。',
                ),
            ):
                selected = choose(keys, reason)
                if selected is not None:
                    return selected
            if run_phase not in {'', 'complete', 'defeated'}:
                selected = choose(
                    {'设置', 'settings'},
                    '目标已切换为尖塔；打开设置退出当前深渊。',
                )
                if selected is not None:
                    return selected
                if run_phase in {'combat', 'climbing_map', 'prebattle'}:
                    return [
                        ButtonCandidate(
                            label='设置',
                            x=0.94,
                            y=0.475,
                            confidence=0.99,
                            clickability=20.0,
                            source='state',
                            reason=(
                                '目标已切换为尖塔；使用已知的右上角设置'
                                '位置退出当前深渊。'
                            ),
                        )
                    ]
        target_name = normalize_label(str(state.get('recruited_character_name') or ''))
        target_power = state.get('recruited_character_power')
        selected_character = bool(state.get('character_selected'))
        if '尖塔木屋' in labels and labels & {'开始冒险', 'start adventure'}:
            if not selected_character:
                target = next(
                    (
                        button
                        for button in buttons
                        if (
                            target_name
                            and normalize_label(button.label) == target_name
                        )
                        or (
                            target_power is not None
                            and normalize_label(button.label) == str(target_power)
                        )
                    ),
                    None,
                )
                if target is not None:
                    target_display = (
                        state.get('recruited_character_name') or target.label
                    )
                    return [
                        ButtonCandidate(
                            label=f'选择新招募角色：{target_display}',
                            x=target.x,
                            y=target.y,
                            confidence=target.confidence,
                            clickability=20.0,
                            source='state',
                            reason='按招募时记录的姓名或战力精确选中新角色。',
                        )
                    ]
                swipe_count = int(state.get('selection_swipes') or 0)
                searching_up = swipe_count >= 12 and (swipe_count // 12) % 2 == 1
                return [
                    ButtonCandidate(
                        label=(
                            '向上查找新招募角色'
                            if searching_up
                            else '向下查找新招募角色'
                        ),
                        x=0.55,
                        y=0.82 if searching_up else 0.52,
                        confidence=0.99,
                        clickability=20.0,
                        source='swipe',
                        reason='按战力排序滚动，直到匹配招募结果页记录的角色。',
                        bbox=(
                            (0.55, 0.52, 0.55, 0.82)
                            if searching_up
                            else (0.55, 0.82, 0.55, 0.52)
                        ),
                    )
                ]
            selected = choose(
                {'开始冒险', 'start adventure'},
                '已选中新招募角色，开始尖塔木屋。',
            )
            if selected is not None:
                return selected
        for keys, reason in (
            ({'尖塔木屋'}, '每日尖塔：选择尖塔木屋。'),
            ({'冒险', 'adventure'}, '每日尖塔：从旅馆前往冒险地图。'),
        ):
            selected = choose(keys, reason)
            if selected is not None:
                return selected
        return None

    if phase == 'spire_running':
        for keys, reason in (
            (
                {'返回旅馆', 'return to inn'},
                '每日尖塔：胜利或失败结算后返回旅馆并结束今日流程。',
            ),
            (
                {'马上离开（冒险者转正）', '马上离开(冒险者转正)'},
                '每日尖塔：BOSS已击败，立即离开并让新角色转正。',
            ),
            ({'冒险胜利'}, '每日尖塔：进入胜利出口，不再清理可选房间。'),
        ):
            selected = choose(keys, reason)
            if selected is not None:
                return selected
        return None
    return None


def tower_daily_result_requires_ocr(game: str, enabled: bool) -> bool:
    if not enabled or normalize_label(game) != 'tower':
        return False
    state = load_tower_daily_state(game)
    return normalize_label(str(state.get('last_action') or '')) in {
        '马上离开（冒险者转正）',
        '马上离开(冒险者转正)',
    }


def tower_observation_phase(
    image: Image.Image,
    buttons: list[ButtonCandidate],
) -> str:
    labels = {normalize_label(button.label) for button in buttons}
    if tower_combat_screen_visible(image):
        return 'combat'
    if '选一张卡牌学习' in labels:
        return 'card_reward'
    if '选择一个楼梯' in labels:
        return 'route_choice'
    if any('即将发起战斗' in label for label in labels):
        return 'prebattle'
    if labels & {'开始冒险', 'start adventure'}:
        return 'initial_setup'
    if '恭喜获得' in labels:
        return 'reward_detail'
    if '当前所在层数' in labels:
        return 'climbing_map'
    if any(re.search(r'当前层数\s*\d+\s*/\s*\d+', label) for label in labels):
        return 'climbing_map'
    if labels & {'返回旅馆', 'return to inn'}:
        return 'defeated'
    return 'unknown'


TOWER_PROFESSION_CARD_HINTS = {
    '战士': (
        '幽灵剑',
        '换血',
        '盾牌猛击',
        '盾击',
        '发现弱点',
        '弱点加倍',
        '弱点打击',
        '守势',
    ),
    '法师': (
        '寒流',
        '冷风',
        '电解冰',
        '快速思考',
        '小雷虫',
        '雷龙',
        '雷电飞弹',
        '能量飞弹',
        '火焰打击',
        '燃烧晶石',
        '闪电晶石',
        '百火',
    ),
    '猎人': (
        '捕猎陷阱',
        '大力射击',
        '猎人嗅觉',
        '会心射击',
        '近身准备',
        '防守烟雾',
        '瞄准',
    ),
    '旅行者': (
        '涂毒小刀',
        '毒药攻击',
        '虔诚',
        '慈悲',
        '特殊信念',
        '祈愿灯',
        '投掷',
        '烈性毒药',
        '安乐毒药',
        '救赎',
    ),
}

TOWER_PROFESSION_TREASURE_HINTS = {
    '战士': (
        '胜利短剑',
        '骑士之誓',
        '骑士手套',
        '骑士专注',
        '燃烧辣椒',
        '巨人之拳',
        '曜蓝水晶',
        '骑士之翼',
        '矮人手套',
        '骑士狼牙棒',
    ),
    '猎人': (
        '迷彩外套',
        '弹药背包',
        '诅咒魔法石',
        '螺丝刀',
        '骑士之刃',
        '猎人赏金',
        '瞄准镜',
        '子弹勋章',
        '贵族手刀',
        '远古魔法手套',
    ),
    '旅行者': (
        '贵族拖鞋',
        '花喇叭',
        '花叭喇',
        '旅行者手册',
        '能量棒',
        '削皮刀',
        '贵族眼睛',
        '巨人之花',
        '安全出口',
        '毒龙匕首',
        '炸弹Tiger机',
        '炸弹老虎机',
    ),
    '法师': (
        '魔法龙蛋',
        '草龙蛋',
        '海马铃铛',
        '电虫药水',
        '火焰草莓',
        '能量苹果',
        '能量火腿',
        '能量手套',
        '过期卷轴',
        '法术绒帽',
    ),
}

TOWER_PREDECESSOR_TREASURE_TARGETS = {
    '战士': ('巨人之拳', '骑士狼牙棒', '曜蓝水晶'),
    '法师': ('电虫药水', '火焰草莓'),
    '猎人': ('远古魔法手套', '贵族手刀'),
    '旅行者': ('毒龙匕首',),
}

TOWER_PREDECESSOR_TREASURE_FALLBACKS = {
    '旅行者': ('花喇叭',),
}

TOWER_TREASURE_OCR_CORRECTIONS = {
    '花叭喇': '花喇叭',
    '骑土手套': '骑士手套',
    '骑土狼牙棒': '骑士狼牙棒',
    '荆赫花环': '荆棘花环',
    '荆赫花环！': '荆棘花环',
}

TOWER_PREDECESSOR_REROLL_LIMIT = 20


def tower_profession_from_text(values: Iterable[str]) -> str | None:
    text = ' '.join(normalize_label(str(value)) for value in values)
    scores = {
        profession: sum(
            1
            for hint in (
                *hints,
                *TOWER_PROFESSION_TREASURE_HINTS.get(profession, ()),
            )
            if normalize_label(hint) in text
        )
        for profession, hints in TOWER_PROFESSION_CARD_HINTS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None


def tower_run_profession(game: str) -> str | None:
    state = load_tower_run_state(game)
    profession = str(state.get('profession') or '').strip()
    if profession:
        return profession
    inferred = tower_profession_from_text(
        [
            *(state.get('initial_setup') or []),
            *(state.get('core_cards') or []),
        ]
    )
    if inferred:
        return inferred
    daily = load_tower_daily_state(game)
    profession = str(daily.get('abyss_profession') or '').strip()
    if profession:
        return profession
    preferred = str(daily.get('preferred_abyss_profession') or '').strip()
    return preferred or None


def tower_predecessor_treasure_from_reward(
    buttons: list[ButtonCandidate],
) -> str | None:
    ignored = {
        '恭喜获得',
        '点击空白处关闭',
        '任务',
        '设置',
    }
    titles = [
        button
        for button in buttons
        if button.source != 'template'
        and 0.25 <= button.x <= 0.75
        and 0.46 <= button.y <= 0.57
        and normalize_label(button.label) not in ignored
        and len(button.label.strip()) <= 18
    ]
    if not titles:
        return None
    title = max(titles, key=lambda button: button.confidence).label.strip()
    return TOWER_TREASURE_OCR_CORRECTIONS.get(normalize_label(title), title)


def tower_predecessor_treasure_is_target(
    profession: str | None,
    treasure: str,
    *,
    reroll_count: int = 0,
) -> bool:
    profession_key = str(profession or '')
    targets = TOWER_PREDECESSOR_TREASURE_TARGETS.get(profession_key)
    if not targets:
        return True
    key = normalize_label(treasure)
    if any(normalize_label(target) in key for target in targets):
        return True
    if reroll_count < TOWER_PREDECESSOR_REROLL_LIMIT:
        return False
    fallbacks = TOWER_PREDECESSOR_TREASURE_FALLBACKS.get(profession_key, ())
    if fallbacks:
        return any(normalize_label(fallback) in key for fallback in fallbacks)
    return True


def tower_predecessor_treasure_targets(
    game: str,
    profession: str | None,
) -> tuple[str, ...]:
    profession_key = str(profession or '')
    targets = TOWER_PREDECESSOR_TREASURE_TARGETS.get(profession_key, ())
    daily_state = load_tower_daily_state(game)
    reroll_count = int(daily_state.get('predecessor_rerolls') or 0)
    if reroll_count >= TOWER_PREDECESSOR_REROLL_LIMIT:
        return TOWER_PREDECESSOR_TREASURE_FALLBACKS.get(profession_key, ())
    return targets


def tower_deep_map_room_bonus(label: str) -> float:
    key = normalize_label(label)
    if '不想遇到' in key and '训练师' in key:
        return -20.0
    if '咒宝库' in key:
        return -10.0
    if '遗忘' in key or '通忘' in key:
        return 8.0
    if key.startswith('前') and '宝物' in key:
        return 6.0
    bonuses = {
        '前辈的宝物': 6.0,
        '拿走前辈的宝物': 8.0,
        'BOSS宝库': 3.0,
        '超越牌包': 3.0,
        '宝物宝库': 2.0,
        '任务': 7.0,
        '训练师': 7.0,
        '卡牌遗忘': 8.0,
        '遗忘法阵': 8.0,
        '休息点': 5.0,
        '金币哥布': 5.5,
        '水晶哥布': 5.5,
        '宝石牌包': 6.0,
        '职业牌包': 5.0,
        '金币商店': 5.5,
        '魔术商店': 5.5,
        '水晶商店': 5.5,
        '神秘商店': 0.5,
        '神桃商店': 0.5,
    }
    if key in bonuses:
        return bonuses[key]
    return max(
        (bonus for pattern, bonus in bonuses.items() if pattern in key),
        default=0.0,
    )


def tower_traveler_state_uses_prayer_build(state: dict[str, Any]) -> bool:
    treasure_text = ' '.join(
        normalize_label(str(value))
        for value in (
            state.get('predecessor_treasure') or '',
            *(state.get('key_treasures') or []),
        )
    )
    return any(
        normalize_label(treasure) in treasure_text
        for treasure in ('花喇叭', '花叭喇', '旅行者手册')
    )


def tower_traveler_uses_prayer_build(game: str) -> bool:
    return tower_traveler_state_uses_prayer_build(load_tower_run_state(game))


def tower_prayer_build_should_stop(state: dict[str, Any]) -> bool:
    if normalize_label(str(state.get('stage') or '')) != '深渊楼梯':
        return False
    if normalize_label(str(state.get('profession') or '')) != '旅行者':
        return False
    if not tower_traveler_state_uses_prayer_build(state):
        return False
    if int(state.get('floor') or 0) < 6:
        return False
    battle = state.get('battle') or {}
    known_cards = ' '.join(
        normalize_label(str(card))
        for card in (
            *(state.get('initial_setup') or []),
            *(state.get('core_cards') or []),
            *(battle.get('initial_hand') or []),
        )
    )
    return not any(
        normalize_label(card) in known_cards
        for card in ('天使', '救赎', '无限宝石')
    )


def tower_real_money_purchase_prompt_visible(labels: Iterable[str]) -> bool:
    text = ' '.join(normalize_label(label) for label in labels)
    return any(keyword in text for keyword in REAL_MONEY_PURCHASE_KEYWORDS)


def tower_visible_purchasable_shop(
    buttons: Iterable[ButtonCandidate],
) -> str:
    visible = [button for button in buttons if button.source != 'template']
    if not any(
        normalize_label(button.label) in PLAIN_BACK_LABELS for button in visible
    ):
        return ''
    shops = [
        button
        for button in visible
        if normalize_label(button.label) in TOWER_PURCHASABLE_SHOP_LABELS
    ]
    if not shops:
        return ''
    return normalize_label(max(shops, key=lambda button: button.confidence).label)


def tower_shop_purchase_profile(game: str, label: str) -> tuple[float, str]:
    state = load_tower_run_state(game)
    if normalize_label(str(state.get('stage') or '')) != '深渊楼梯':
        return 0.0, ''
    key = normalize_label(label)
    if any(keyword in key for keyword in REAL_MONEY_PURCHASE_KEYWORDS):
        return 0.0, ''
    purchased = {
        normalize_label(str(item)) for item in state.get('shop_purchases') or []
    }
    if key in purchased:
        return 0.0, ''

    profession = tower_run_profession(game)
    build_text = ' '.join(
        normalize_label(str(value))
        for value in (
            state.get('predecessor_treasure') or '',
            *(state.get('core_cards') or []),
            *(state.get('key_treasures') or []),
        )
    )
    treasure_priorities = [
        ('金丹砂', 45.0),
        ('聚宝盆', 38.0),
        ('矮人招财猫', 37.0),
        ('实验眼睛', 36.0),
        ('实验眼镜', 36.0),
        ('贵族咖啡', 35.0),
        ('机械龙蛋', 34.0),
        ('巨人之眼', 33.0),
        ('魔法熊手', 32.0),
        ('女鹅套娃', 31.0),
        ('时之沙漏', 30.0),
        ('魔塔石像', 29.0),
        ('魔法笔记', 28.0),
        ('拐棍糖', 27.0),
        ('贵族匕首', 26.0),
        ('巨人泡泡糖', 24.0),
        ('巨人布袋', 23.0),
        ('巨人胡须', 22.0),
        ('蝙蝠牙齿', 21.0),
        ('矮人王宝石', 20.0),
        ('超级金币', 19.0),
        ('巨人手指', 18.0),
        ('诅咒饭团', 17.0),
    ]
    if profession == '战士' and '巨人之拳' in build_text:
        treasure_priorities = [
            ('矮人王宝石', 42.0),
            ('巨人面罩', 35.0),
            ('巨人之眼', 34.0),
            *treasure_priorities,
        ]
    if any(
        marker in build_text
        for marker in ('超越牌', '代号肉鸽', '海是那个味', '魔法面具', '宇宙面具')
    ):
        treasure_priorities.insert(0, ('幻龙蛋', 40.0))
    for pattern, bonus in treasure_priorities:
        if normalize_label(pattern) in key:
            return bonus, 'treasure'

    if '幸运币' in key or '运币' in key:
        return 43.0, 'consumable'

    if '药水' in key:
        consumable_priorities = [
            ('恢复药水', 40.0),
            ('生命药水', 40.0),
            ('迅捷药水', 34.0),
            ('巨人药水', 22.0),
        ]
        if profession == '旅行者':
            consumable_priorities.extend(
                (
                    ('唤回药水', 26.0),
                    ('宝石药水', 23.0),
                    ('过期药水', 21.0),
                )
            )
        for pattern, bonus in consumable_priorities:
            if normalize_label(pattern) in key:
                return bonus, 'consumable'
        return 0.0, ''

    for pattern, priority in tower_card_reward_priority_rules(game, profession):
        if priority >= 20.0 and normalize_label(pattern) in key:
            return priority, 'card'
    return 0.0, ''


def tower_shop_purchase_bonus(game: str, label: str) -> float:
    return tower_shop_purchase_profile(game, label)[0]


def tower_card_cull_bonus(
    game: str,
    label: str,
    *,
    visible_labels: Iterable[str] = (),
) -> float:
    state = load_tower_run_state(game)
    if normalize_label(str(state.get('stage') or '')) != '深渊楼梯':
        return 0.0
    key = normalize_label(label)
    if tower_traveler_uses_prayer_build(game):
        common_priorities = (
            ('灵魂燃烧', 20.0),
            ('慈悲', 19.0),
            ('毒药攻击', 18.0),
            ('涂毒小刀', 18.0),
            ('绿舌头', 17.0),
            ('盾牌石块', 14.0),
            ('投掷', 13.0),
            ('投挪', 13.0),
            ('虔诚', 12.0),
            ('杂念', 11.0),
            ('杂物', 10.0),
        )
    else:
        common_priorities = (
            ('慈悲', 18.0),
            ('救赎', 17.0),
            ('虔诚', 16.0),
            ('灵魂燃烧', 15.0),
            ('盾牌石块', 14.0),
            ('投掷', 13.0),
            ('投挪', 13.0),
            ('绿舌头', 12.0),
            ('杂念', 11.0),
            ('杂物', 10.0),
        )
    profession = tower_run_profession(game)
    if (
        profession == '战士'
        and '举盾' in key
        and any(
            '防具加固' in normalize_label(visible_label)
            for visible_label in visible_labels
        )
    ):
        return 0.0
    profession_protected = {
        '战士': (
            '弱点打击',
            '发现弱点',
            '弱点加倍',
            '迅捷',
            '未来汽水',
            '愤怒宝石',
            '攻击宝石',
            '神圣斩击',
            '巨人协议',
            '撞击',
        ),
        '法师': (
            '快速思考',
            '小雷虫',
            '寒冷晶石',
            '寒冷宝石',
            '闪电晶石',
            '电解冰',
            '冷风',
            '寒流',
            '雷龙',
            '恢复宝石',
            '路人甲',
            '能量盾',
        ),
    }
    if any(
        normalize_label(pattern) in key
        for pattern in profession_protected.get(str(profession or ''), ())
    ):
        return 0.0
    profession_priorities = {
        '战士': (
            ('举盾', 24.0),
            ('普通攻击', 23.0),
            ('劈砍', 22.0),
            ('全力一击', 21.0),
            ('全劲一击', 21.0),
            ('胜势', 20.0),
        ),
        '旅行者': (
            ('许愿', 20.0),
            ('代号肉鸽', 9.0),
            ('海是那个味', 8.0),
            ('毒死', 7.0),
        ),
        '法师': (
            ('虚弱', 20.0),
            ('能量飞弹', 18.0),
            ('雷电飞弹', 17.0),
        ),
    }
    for pattern, bonus in (
        *common_priorities,
        *profession_priorities.get(str(profession or ''), ()),
    ):
        if normalize_label(pattern) in key:
            return bonus
    return 0.0


def is_tower_status_fraction_label(label: str) -> bool:
    key = normalize_label(label)
    return len(key) <= 12 and bool(re.search(r'\d+\s*/\s*\d+', key))


def is_tower_next_floor_action(label: str) -> bool:
    key = normalize_label(label)
    return '下一层' in key or key in {'进人下', '进入下'}


def tower_action_advances_floor(label: str, phase: str) -> bool:
    key = normalize_label(label)
    return is_tower_next_floor_action(label) or (
        normalize_label(phase) == 'route_choice' and key in CONFIRM_LABELS
    )


def update_tower_run_state(
    game: str,
    image: Image.Image,
    buttons: list[ButtonCandidate],
    *,
    clicked_label: str = '',
    action_succeeded: bool = True,
) -> None:
    if normalize_label(game) != 'tower':
        return
    path = tower_run_state_path_for(game)
    state = load_tower_run_state(game)
    now = datetime.now().astimezone().isoformat(timespec='seconds')
    labels = [button.label.strip() for button in buttons if button.label.strip()]
    previous_action = normalize_label(str(state.get('last_action') or ''))
    start_labels = {
        '开始冒险',
        'start adventure',
        '进入冒险',
        'enter adventure',
    }
    clicked_key = normalize_label(clicked_label)
    battle_launch_labels = {
        normalize_label(label) for label in labels
    }
    active_tower_run = bool(state.get('run_id')) and normalize_label(
        str(state.get('stage') or '')
    ) in {'深渊楼梯', '尖塔木屋'}
    stage_page_visible = bool(
        battle_launch_labels & {'深渊楼梯', '尖塔木屋'}
    )
    stage_battle_launch = (
        clicked_key == '战斗'
        and (not active_tower_run or stage_page_visible)
        and not battle_launch_labels & {
            '撤退',
            '即将发起战斗',
            '卡组',
            '宝物',
        }
    )
    starting_new_run = clicked_key in start_labels or stage_battle_launch
    previous_stage = str(state.get('stage') or '').strip()
    if not state or starting_new_run:
        state = {
            'version': 1,
            'run_id': datetime.now().astimezone().strftime('%Y%m%dT%H%M%S%z'),
            'started_at': now,
            'stage': (
                previous_stage
                if normalize_label(previous_stage) in {'深渊楼梯', '尖塔木屋'}
                else 'unknown'
            ),
            'character': 'unknown',
            'phase': 'initial_setup' if starting_new_run else 'unknown',
            'floor': 1 if starting_new_run else 0,
            'initial_setup': [],
            'core_cards': [],
            'key_treasures': [],
            'policy': {
                'never_sell': True,
                'immortal_priority': True,
                'always_take_immediate_fusion': True,
                'shop_refresh_limit': 2,
            },
        }

    visible_stages = [
        label
        for label in labels
        if normalize_label(label) in {'深渊楼梯', '尖塔木屋'}
    ]
    clicked_stage = next(
        (
            label
            for label in visible_stages
            if normalize_label(label) == normalize_label(clicked_label)
        ),
        None,
    )
    if clicked_stage:
        state['stage'] = clicked_stage
    elif len(visible_stages) == 1:
        state['stage'] = visible_stages[0]

    for label in labels:
        key = normalize_label(label)
        spire_floor = re.search(r'当前层数\s*(\d+)\s*/\s*(\d+)', key)
        if spire_floor:
            if (
                normalize_label(previous_stage) != '尖塔木屋'
                or state.get('floor_goal') is None
            ):
                for stale_key in (
                    'last_room_action',
                    'last_room_position',
                    'awaiting_route_after_reward',
                    'post_revive_route_guard',
                    'reroll_predecessor',
                    'awaiting_predecessor_treasure',
                    'predecessor_treasure',
                    'stop_loss_reason',
                ):
                    state.pop(stale_key, None)
                state['run_id'] = datetime.now().astimezone().strftime(
                    '%Y%m%dT%H%M%S%z'
                )
                state['started_at'] = now
                state['core_cards'] = []
                state['key_treasures'] = []
            state['stage'] = '尖塔木屋'
            state['floor'] = int(spire_floor.group(1))
            state['floor_goal'] = int(spire_floor.group(2))
        if any(name in key for name in ('铁面奇莫', '女巫', '小黑龙', '黑八戒')):
            state['character'] = label
    if {'当前所在层数', '全服最高层数'} <= {
        normalize_label(label) for label in labels
    }:
        visible_abyss_floors = [
            int(normalize_label(button.label))
            for button in buttons
            if button.source != 'template'
            and re.fullmatch(r'\d{1,3}', normalize_label(button.label))
            and 0.54 <= button.x <= 0.72
            and 0.52 <= button.y <= 0.56
        ]
        if visible_abyss_floors:
            state['stage'] = '深渊楼梯'
            state['floor'] = visible_abyss_floors[0]
    daily_state = load_tower_daily_state(game)
    if starting_new_run and normalize_label(
        str(daily_state.get('phase') or '')
    ) in {'abyss', 'abyss_retry'}:
        daily_state.pop('abyss_profession', None)
        daily_state.pop('accepted_predecessor_treasure', None)
        daily_state.pop('accepted_predecessor_run_id', None)
        daily_state['updated_at'] = now
        write_tower_daily_state(game, daily_state)
    if state.get('stage') == '尖塔木屋' and daily_state.get(
        'recruited_character_name'
    ):
        state['character'] = daily_state['recruited_character_name']

    phase = tower_observation_phase(image, buttons)
    if phase != 'unknown':
        state['phase'] = phase
    effective_phase = (
        phase
        if phase != 'unknown'
        else normalize_label(str(state.get('phase') or ''))
    )
    timing_sensitive_cards_seen = list(
        state.get('timing_sensitive_cards_seen') or []
    )
    for label in labels:
        key = normalize_label(label)
        if '制造核心' in key and not any(
            '制造核心' in normalize_label(str(card))
            for card in timing_sensitive_cards_seen
        ):
            timing_sensitive_cards_seen.append(label)
    if timing_sensitive_cards_seen:
        state['timing_sensitive_cards_seen'] = timing_sensitive_cards_seen
    visible_shop = tower_visible_purchasable_shop(buttons)
    if visible_shop:
        refresh_history = dict(state.get('shop_refresh_history') or {})
        active_refresh_key = tower_shop_refresh_key(state, visible_shop)
        state['last_room_action'] = visible_shop
        state['active_shop'] = visible_shop
        state['active_shop_key'] = active_refresh_key
        state['shop_refresh_count'] = int(
            refresh_history.get(active_refresh_key, 0)
        )
        refresh_history.setdefault(active_refresh_key, 0)
        state['shop_refresh_history'] = refresh_history
    visible_refresh_count = tower_visible_shop_refresh_count(labels)
    active_refresh_shop = normalize_label(
        str(visible_shop or state.get('active_shop') or '')
    )
    if (
        visible_refresh_count is not None
        and active_refresh_shop in TOWER_PURCHASABLE_SHOP_LABELS
    ):
        refresh_history = dict(state.get('shop_refresh_history') or {})
        active_refresh_key = tower_shop_refresh_key(state, active_refresh_shop)
        current_refresh_count = int(state.get('shop_refresh_count') or 0)
        observed_refresh_count = max(
            current_refresh_count,
            refresh_history.get(active_refresh_key, 0),
            visible_refresh_count,
        )
        state['active_shop'] = active_refresh_shop
        state['active_shop_key'] = active_refresh_key
        state['shop_refresh_count'] = observed_refresh_count
        if active_refresh_key:
            refresh_history[active_refresh_key] = observed_refresh_count
            state['shop_refresh_history'] = refresh_history
    if phase == 'combat':
        state['awaiting_route_after_reward'] = False
        battle = state.get('battle')
        if isinstance(battle, dict):
            battle['enemy_sacred_finisher_range'] = (
                tower_enemy_hp_looks_sacred_finisher_ready(image)
            )
            battle['player_hp_critical'] = tower_combat_hp_looks_critical(image)
    if phase == 'initial_setup':
        ignored = start_labels | CONFIRM_LABELS | CANCEL_LABELS
        state['initial_setup'] = list(
            dict.fromkeys(
                label for label in labels if normalize_label(label) not in ignored
            )
        )[:30]
    if (
        '训练师任务' in {normalize_label(label) for label in labels}
        and any(normalize_label(label) == '领取' for label in labels)
        and any('敌方物攻增加100点' in normalize_label(label) for label in labels)
    ):
        state['skip_unsafe_trainer_reward'] = True
    predecessor_profession = tower_profession_from_text(
        [str(state.get('predecessor_treasure') or '')]
    )
    profession = predecessor_profession or tower_profession_from_text(
        [
            *labels,
            *(state.get('initial_setup') or []),
            *(state.get('core_cards') or []),
        ]
    ) or str(state.get('profession') or '').strip()
    if profession:
        state['profession'] = profession
        if state.get('stage') == '深渊楼梯':
            daily_state['abyss_profession'] = profession
            daily_state['updated_at'] = now
            write_tower_daily_state(game, daily_state)
    awaiting_predecessor = bool(state.get('awaiting_predecessor_treasure'))
    current_floor = int(state.get('floor') or 0)
    if current_floor > 1:
        state['awaiting_predecessor_treasure'] = False
        awaiting_predecessor = False
    if (
        state.get('stage') == '深渊楼梯'
        and current_floor <= 1
        and not state.get('predecessor_treasure')
        and phase == 'reward_detail'
        and (awaiting_predecessor or '拿走前辈的宝物' in previous_action)
    ):
        treasure = tower_predecessor_treasure_from_reward(buttons)
        if treasure:
            state['predecessor_treasure'] = treasure
            treasures = list(state.get('key_treasures') or [])
            if treasure not in treasures:
                treasures.append(treasure)
            state['key_treasures'] = treasures
            reroll_count = int(daily_state.get('predecessor_rerolls') or 0)
            preferred_profession = str(
                daily_state.get('preferred_abyss_profession') or ''
            ).strip()
            resolved_profession = (
                profession
                or tower_run_profession(game)
                or preferred_profession
            )
            is_target = tower_predecessor_treasure_is_target(
                resolved_profession,
                treasure,
                reroll_count=reroll_count,
            )
            state['reroll_predecessor'] = not is_target
            if is_target:
                daily_state['accepted_predecessor_treasure'] = treasure
                daily_state['accepted_predecessor_run_id'] = state.get('run_id')
            else:
                daily_state['predecessor_rerolls'] = reroll_count + 1
                daily_state['last_rejected_predecessor_treasure'] = treasure
            daily_state['updated_at'] = now
            write_tower_daily_state(game, daily_state)
            state['awaiting_predecessor_treasure'] = False
    if clicked_label:
        policy = state.setdefault('policy', {})
        policy['shop_refresh_limit'] = max(
            2,
            int(policy.get('shop_refresh_limit') or 0),
        )
        state['last_action'] = clicked_label
        clicked_key = normalize_label(clicked_label)
        if action_succeeded:
            state.pop('last_failed_action', None)
        else:
            state['last_failed_action'] = clicked_label
        refresh_history = dict(state.get('shop_refresh_history') or {})
        active_refresh_key = str(state.get('active_shop_key') or '').strip()
        if not active_refresh_key:
            active_refresh_key = tower_shop_refresh_key(state)
            if active_refresh_key:
                state['active_shop_key'] = active_refresh_key
                refresh_history.setdefault(
                    active_refresh_key,
                    int(state.get('shop_refresh_count') or 0),
                )
                state['shop_refresh_history'] = refresh_history
        clicked_candidate = next(
            (
                button
                for button in buttons
                if normalize_label(button.label) == clicked_key
            ),
            None,
        )
        if action_succeeded and effective_phase == 'combat':
            battle = state.get('battle')
            if isinstance(battle, dict):
                shield_builders = ('举盾', '守势', '胜势', '启动防守')
                if any(builder in clicked_key for builder in shield_builders):
                    battle['shield_built_this_turn'] = True
                elif clicked_key and is_end_turn_label(clicked_key):
                    battle['shield_built_this_turn'] = False
                if clicked_key and is_end_turn_label(clicked_key) and battle.get(
                    'enemy_sacred_finisher_range'
                ):
                    battle['sacred_finisher_waits'] = int(
                        battle.get('sacred_finisher_waits') or 0
                    ) + 1
                cold_sources = (
                    '冷风',
                    '寒流',
                    '寒冰盾',
                    '冰霜飞弹',
                )
                if any(source in clicked_key for source in cold_sources):
                    battle['cold_applied'] = True
                elif '电解冰' in clicked_key and battle.get('cold_applied'):
                    battle['cold_applied'] = False
                if '发现弱点' in clicked_key:
                    battle['weakness_applied'] = True
                elif '弱点打击' in clicked_key:
                    battle['weakness_applied'] = False
        if action_succeeded and clicked_key == '任务':
            state['trainer_task_checked_once'] = True
            state['trainer_task_checked_battle'] = int(
                state.get('battle_number') or 0
            )
        if action_succeeded and (
            tower_deep_map_room_bonus(clicked_label) != 0
            or (
                clicked_candidate is not None
                and is_tower_room_vision_candidate(clicked_candidate)
            )
        ):
            state['last_room_action'] = clicked_label
            if clicked_key in TOWER_PURCHASABLE_SHOP_LABELS:
                state['active_shop'] = clicked_key
                room_position = (
                    [clicked_candidate.x, clicked_candidate.y]
                    if clicked_candidate is not None
                    else state.get('last_room_position') or []
                )
                active_refresh_key = tower_shop_refresh_key(
                    state,
                    clicked_key,
                    room_position,
                )
                state['active_shop_key'] = active_refresh_key
                state['shop_refresh_count'] = int(
                    refresh_history.get(active_refresh_key, 0)
                )
                refresh_history.setdefault(active_refresh_key, 0)
                state['shop_refresh_history'] = refresh_history
            else:
                state.pop('shop_refresh_count', None)
                state.pop('active_shop', None)
                state.pop('active_shop_key', None)
            if clicked_candidate is not None:
                state['last_room_position'] = [
                    round(clicked_candidate.x, 6),
                    round(clicked_candidate.y, 6),
                ]
        if (
            action_succeeded
            and clicked_key == normalize_label(TOWER_SHOP_SPARKLE_LABEL)
        ):
            sparkle_key = str(state.get('active_shop_key') or '').strip()
            if not sparkle_key:
                sparkle_key = tower_shop_refresh_key(state)
            if not sparkle_key:
                sparkle_shop = normalize_label(
                    str(
                        state.get('active_shop')
                        or state.get('last_room_action')
                        or ''
                    )
                )
                if sparkle_shop:
                    sparkle_key = (
                        f'{int(state.get("floor") or 0)}:{sparkle_shop}'
                    )
            claimed_sparkle_keys = list(
                state.get('claimed_shop_sparkle_keys') or []
            )
            if sparkle_key and sparkle_key not in claimed_sparkle_keys:
                claimed_sparkle_keys.append(sparkle_key)
            state['claimed_shop_sparkle_keys'] = claimed_sparkle_keys
        if (
            action_succeeded
            and normalize_label(
                str(
                    state.get('active_shop')
                    or state.get('last_room_action')
                    or ''
                )
            )
            in TOWER_PURCHASABLE_SHOP_LABELS
            and (
                clicked_key.startswith('刷新')
                or (clicked_key.startswith('免费') and '次' in clicked_key)
            )
        ):
            state['shop_refresh_count'] = int(
                state.get('shop_refresh_count') or 0
            ) + 1
            active_refresh_key = str(state.get('active_shop_key') or '').strip()
            if active_refresh_key:
                refresh_history[active_refresh_key] = state['shop_refresh_count']
                state['shop_refresh_history'] = refresh_history
        if (
            action_succeeded
            and clicked_key == '变化'
            and normalize_label(str(state.get('last_room_action') or ''))
            == '魔术商店'
        ):
            state['magic_shop_change_complete'] = True
        if (
            action_succeeded
            and clicked_key in PLAIN_BACK_LABELS
            and normalize_label(str(state.get('active_shop') or ''))
            in TOWER_PURCHASABLE_SHOP_LABELS
        ):
            completed_shop_keys = list(state.get('completed_shop_keys') or [])
            completed_key = tower_shop_refresh_key(state)
            if completed_key and completed_key not in completed_shop_keys:
                completed_shop_keys.append(completed_key)
            state['completed_shop_keys'] = completed_shop_keys
            state['last_room_action'] = state['active_shop']
            state.pop('shop_refresh_count', None)
            state.pop('active_shop', None)
            state.pop('active_shop_key', None)
        if (
            action_succeeded
            and clicked_key in CONFIRM_LABELS
            and normalize_label(
                str(
                    state.get('active_shop')
                    or state.get('last_room_action')
                    or ''
                )
            )
            in TOWER_PURCHASABLE_SHOP_LABELS
        ):
            purchase_bonus, purchase_kind = tower_shop_purchase_profile(
                game,
                previous_action,
            )
            if purchase_bonus > 0:
                purchases = list(state.get('shop_purchases') or [])
                if previous_action not in purchases:
                    purchases.append(previous_action)
                state['shop_purchases'] = purchases
                if purchase_kind == 'card':
                    cards = list(state.get('core_cards') or [])
                    if previous_action not in cards:
                        cards.append(previous_action)
                    state['core_cards'] = cards
                elif purchase_kind == 'treasure':
                    treasures = list(state.get('key_treasures') or [])
                    if previous_action not in treasures:
                        treasures.append(previous_action)
                    state['key_treasures'] = treasures
        if action_succeeded and clicked_key in {
            '复活（广告）',
            '看广告复活',
        }:
            state['post_revive_route_guard'] = True
        if action_succeeded and (
            (
                clicked_key in ({'放弃'} | CONFIRM_LABELS)
                and effective_phase == 'card_reward'
            )
            or (
                clicked_key == '点击空白处关闭'
                and effective_phase == 'reward_detail'
            )
            or (
                clicked_key in (CONFIRM_LABELS | {'好的'})
                and any('胜利' in normalize_label(label) for label in labels)
            )
        ):
            state['awaiting_route_after_reward'] = True
        if action_succeeded and (
            clicked_key
            in {'左侧道路', '右侧道路', '上方道路', '下方道路'}
            or clicked_key
            in {
                'visible next-floor stair room',
                'visible rest room icon',
                'visible combat room icon',
                'visible room icon',
            }
            or tower_action_advances_floor(clicked_label, phase)
        ):
            state['awaiting_route_after_reward'] = False
            state['post_revive_route_guard'] = False
        if (
            action_succeeded
            and state.get('post_revive_route_guard')
            and clicked_key in {'战斗', 'fight', 'battle'}
            and effective_phase == 'prebattle'
        ):
            state['post_revive_route_guard'] = False
        if (
            state.get('stage') == '深渊楼梯'
            and clicked_key == '拿走前辈的宝物'
            and int(state.get('floor') or 0) <= 1
            and not state.get('predecessor_treasure')
        ):
            state['awaiting_predecessor_treasure'] = True
        if int(state.get('floor') or 0) > 1:
            state['awaiting_predecessor_treasure'] = False
        if action_succeeded and normalize_label(clicked_label) in {
            '返回旅馆',
            'return to inn',
        }:
            state['phase'] = 'complete'
        if action_succeeded and tower_action_advances_floor(clicked_label, phase):
            state['floor'] = int(state.get('floor') or 0) + 1
            state.pop('last_room_action', None)
            state.pop('last_room_position', None)
            state.pop('magic_shop_change_complete', None)
    if tower_prayer_build_should_stop(state):
        state['reroll_predecessor'] = True
        state['stop_loss_reason'] = (
            '纯祈愿局到第6层仍无天使、救赎或无限宝石，'
            '按前期成型止损线重开。'
        )
    accepted_treasure = normalize_label(
        str(daily_state.get('accepted_predecessor_treasure') or '')
    )
    accepted_run_id = str(daily_state.get('accepted_predecessor_run_id') or '')
    current_treasure = normalize_label(str(state.get('predecessor_treasure') or ''))
    if (
        int(state.get('floor') or 0) <= 1
        and accepted_run_id
        and accepted_run_id == str(state.get('run_id') or '')
        and accepted_treasure
        and accepted_treasure == current_treasure
    ):
        state['reroll_predecessor'] = False
        state.pop('stop_loss_reason', None)
    state['updated_at'] = now
    path.write_text(
        yaml.safe_dump(
            state,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    )


def record_tower_run_choice(game: str, kind: str, label: str) -> None:
    if normalize_label(game) != 'tower':
        return
    state = load_tower_run_state(game)
    if not state:
        return
    key = 'core_cards' if kind == 'card' else 'key_treasures'
    values = list(state.get(key) or [])
    if label not in values:
        values.append(label)
    state[key] = values
    daily_state = load_tower_daily_state(game)
    if (
        kind == 'treasure'
        and int(state.get('floor') or 0) <= 1
        and normalize_label(str(daily_state.get('phase') or ''))
        in {'abyss', 'abyss_retry'}
    ):
        state['awaiting_predecessor_treasure'] = True
    state['updated_at'] = datetime.now().astimezone().isoformat(timespec='seconds')
    tower_run_state_path_for(game).write_text(
        yaml.safe_dump(
            state,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    )


def tower_battle_needs_initial_read(game: str, image: Image.Image) -> bool:
    if normalize_label(game) != 'tower' or not tower_combat_screen_visible(image):
        return False
    state = load_tower_run_state(game)
    return normalize_label(str(state.get('phase') or '')) != 'combat'


def tower_battle_requires_precise_read(game: str) -> bool:
    if normalize_label(game) != 'tower':
        return False
    state = load_tower_run_state(game)
    core_text = ' '.join(
        normalize_label(str(card))
        for card in (
            *(state.get('core_cards') or []),
            *(state.get('timing_sensitive_cards_seen') or []),
        )
    )
    battle = state.get('battle') or {}
    known_card_text = ' '.join(
        (
            core_text,
            *(
                normalize_label(str(card))
                for card in battle.get('initial_hand') or []
            ),
        )
    )
    floor = int(state.get('floor') or 0)
    return (
        is_tower_timing_sensitive_finisher_label(known_card_text)
        or '电解冰' in known_card_text
        or '快速思考' in known_card_text
        or '制造核心' in known_card_text
        or (floor > 0 and floor % 10 == 0)
        or (
            '神圣斩击' in known_card_text
            and bool(battle.get('enemy_sacred_finisher_range'))
        )
    )


def start_tower_battle_state(
    game: str,
    image: Image.Image,
    buttons: list[ButtonCandidate],
) -> None:
    state = load_tower_run_state(game)
    if not state:
        return
    rgb = np.asarray(image.convert('RGB'))
    hand = []
    boxes = sorted(
        tower_card_outline_boxes(rgb),
        key=lambda item: (item[1], item[0]),
    )
    for box in boxes:
        x, y, width, height = box
        bbox = (
            x / image.width,
            y / image.height,
            (x + width) / image.width,
            (y + height) / image.height,
        )
        name = tower_card_name_from_ocr(buttons, bbox)
        hand.append(name or '未识别手牌')
    battle_number = int(state.get('battle_number') or 0) + 1
    now = datetime.now().astimezone().isoformat(timespec='seconds')
    state['battle_number'] = battle_number
    state['battle'] = {
        'battle_id': f'{state.get("run_id", "run")}-b{battle_number:03d}',
        'started_at': now,
        'initial_hand': hand,
        'mode': (
            'per_action_ocr'
            if tower_battle_requires_precise_read(game)
            else 'initial_ocr_then_local_cv'
        ),
        'max_actions_per_read': (
            1 if tower_battle_requires_precise_read(game) else 2
        ),
    }
    state['phase'] = 'combat'
    state['awaiting_route_after_reward'] = False
    state['updated_at'] = now
    tower_run_state_path_for(game).write_text(
        yaml.safe_dump(
            state,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    )


def main_challenge_progress_path_for(game: str) -> Path:
    return game_root_for(game) / 'main_challenge_progress.yaml'


def load_main_challenge_progress(game: str) -> dict[str, Any]:
    path = main_challenge_progress_path_for(game)
    if not path.exists():
        return {}
    payload = safe_load_yaml_mapping(path)
    return payload if isinstance(payload, dict) else {}


def write_main_challenge_progress(game: str, progress: dict[str, Any]) -> None:
    path = main_challenge_progress_path_for(game)
    path.write_text(
        yaml.safe_dump(
            progress,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    )


def load_ocr_config(game: str) -> dict[str, Any]:
    path = ocr_config_path_for(game)
    if not path.exists():
        return {}
    payload = safe_load_yaml_mapping(path)
    return payload if isinstance(payload, dict) else {}


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
        rmtree(old_turn, ignore_errors=True)


def create_turn_artifacts(args: argparse.Namespace) -> tuple[dict[str, Path], datetime]:
    root = turns_root(args)
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone()
    turn_name = f'{timestamp.strftime("%Y%m%dT%H%M%S%z")}-{slugify(args.game)}'
    turn_dir = root / turn_name
    suffix = 2
    while True:
        try:
            turn_dir.mkdir(parents=True)
            break
        except FileExistsError:
            turn_dir = root / f'{turn_name}-{suffix:02d}'
            suffix += 1

    prune_turn_folders(root, args.turn_history_limit)

    return {
        'turn_dir': turn_dir,
        'screen': turn_dir / 'screenshot.png',
        'ocr_overlay': turn_dir / 'ocr_overlay.png',
        'llm_overlay': turn_dir / 'llm_overlay.png',
        'ocr': turn_dir / 'ocr.yaml',
        'llm': turn_dir / 'llm.yaml',
        'metadata': turn_dir / 'metadata.yaml',
        'last_screen': turn_dir / 'last_screenshot.png',
        'item_inspections': turn_dir / 'item_inspections.yaml',
        'item_inspection_dir': turn_dir / 'item_inspections',
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
- Abandon
- Abandon Adventure
- 放弃
- 放弃冒险

## Ineffective Buttons
None yet.

## Decision Rules
- Add avoid labels only for high-confidence run-ending or clearly harmful actions.
- Add ineffective labels only after repeated, high-confidence evidence that a
  concrete action does not progress in this game.
- Record uncertain or merely non-progressing actions under Strategy Improvements
  Needed instead.
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


def normalized_label_set(values: list[str] | tuple[str, ...]) -> frozenset[str]:
    return frozenset(normalize_label(value) for value in values if value.strip())


def compile_strategy_patterns(values: list[str]) -> tuple[re.Pattern[str], ...]:
    patterns: list[re.Pattern[str]] = []
    for value in values:
        try:
            patterns.append(re.compile(value, re.I))
        except re.error:
            continue
    return tuple(patterns)


def parse_candidate_spec(value: str) -> AutomationCandidateSpec | None:
    parts = [part.strip() for part in value.split('|')]
    if len(parts) < 4:
        return None
    try:
        return AutomationCandidateSpec(
            label=parts[0],
            x=float(parts[1]),
            y=float(parts[2]),
            clickability=float(parts[3]),
            reason=parts[4] if len(parts) > 4 else '',
        )
    except ValueError:
        return None


def parse_row_candidate_spec(value: str) -> AutomationRowCandidateSpec | None:
    parts = [part.strip() for part in value.split('|')]
    if len(parts) < 4:
        return None
    try:
        return AutomationRowCandidateSpec(
            label=parts[0],
            x=float(parts[1]),
            y_offset=float(parts[2]),
            clickability=float(parts[3]),
            reason=parts[4] if len(parts) > 4 else '',
        )
    except ValueError:
        return None


def parse_repeated_action_swipe_spec(
    value: str,
) -> AutomationRepeatedActionSwipeSpec | None:
    parts = [part.strip() for part in value.split('|')]
    if len(parts) < 8:
        return None
    try:
        return AutomationRepeatedActionSwipeSpec(
            trigger_label=parts[0],
            min_count=max(1, int(parts[1])),
            label=parts[2],
            start_x=float(parts[3]),
            start_y=float(parts[4]),
            end_x=float(parts[5]),
            end_y=float(parts[6]),
            clickability=float(parts[7]),
            reason=parts[8] if len(parts) > 8 else '',
        )
    except ValueError:
        return None


def parse_first_candidate_section(
    text: str,
    heading: str,
) -> AutomationCandidateSpec | None:
    for item in extract_list_section(text, heading, []):
        candidate = parse_candidate_spec(item)
        if candidate is not None:
            return candidate
    return None


def parse_first_row_candidate_section(
    text: str,
    heading: str,
) -> AutomationRowCandidateSpec | None:
    for item in extract_list_section(text, heading, []):
        candidate = parse_row_candidate_spec(item)
        if candidate is not None:
            return candidate
    return None


def parse_first_repeated_action_swipe_section(
    text: str,
    heading: str,
) -> AutomationRepeatedActionSwipeSpec | None:
    for item in extract_list_section(text, heading, []):
        candidate = parse_repeated_action_swipe_spec(item)
        if candidate is not None:
            return candidate
    return None


def parse_label_groups(values: list[str]) -> tuple[tuple[str, ...], ...]:
    groups = []
    for value in values:
        tokens = [
            normalize_label(part)
            for part in re.split(r'\s*\+\s*', value)
            if part.strip()
        ]
        if tokens:
            groups.append(tuple(tokens))
    return tuple(groups)


def parse_item_preference_rules(values: list[str]) -> tuple[ItemPreferenceRule, ...]:
    rules: list[ItemPreferenceRule] = []
    for value in values:
        parts = [part.strip() for part in value.split('|')]
        if len(parts) < 2:
            continue
        try:
            points = float(parts[1])
        except ValueError:
            continue
        pattern = normalize_label(parts[0])
        if not pattern:
            continue
        reason = parts[2] if len(parts) > 2 else f'configured preference: {parts[0]}'
        rules.append(ItemPreferenceRule(pattern=pattern, points=points, reason=reason))
    return tuple(rules)


def parse_passive_nameplate_region(
    text: str,
) -> tuple[float, float, float, float, float] | None:
    for item in extract_list_section(text, 'Automation Passive Nameplate Region', []):
        parts = [part.strip() for part in item.split('|')]
        if len(parts) < 5:
            continue
        try:
            return tuple(float(part) for part in parts[:5])  # type: ignore[return-value]
        except ValueError:
            continue
    return None


def first_list_item(text: str, heading: str) -> str:
    items = extract_list_section(text, heading, [])
    return items[0] if items else ''


def first_list_int(text: str, heading: str) -> int | None:
    item = first_list_item(text, heading)
    if not item:
        return None
    match = re.search(r'\d+', item)
    return int(match.group(0)) if match else None


def first_list_bool(text: str, heading: str) -> bool:
    value = normalize_label(first_list_item(text, heading))
    return value in {'1', 'true', 'yes', 'on', '是', '开启', '允许'}


def load_automation_config(game: str) -> GameAutomationConfig:
    text = load_strategy_text(game)
    navigation_labels = normalized_label_set(
        [
            *NAVIGATION_ARROW_LABELS,
            *extract_list_section(text, 'Automation Navigation Labels', []),
        ]
    )
    navigation_keywords = tuple(
        normalize_label(value)
        for value in [
            *NAVIGATION_ARROW_KEYWORDS,
            *extract_list_section(text, 'Automation Navigation Keywords', []),
        ]
        if value.strip()
    )
    navigation_glyphs = tuple(
        value.strip()
        for value in [
            *NAVIGATION_ARROW_GLYPHS,
            *extract_list_section(text, 'Automation Navigation Glyphs', []),
        ]
        if value.strip()
    )
    noise_pattern_text = tuple(
        extract_list_section(text, 'Automation Noise Patterns', [])
    )
    return GameAutomationConfig(
        game=game,
        noise_pattern_text=noise_pattern_text,
        noise_patterns=compile_strategy_patterns(list(noise_pattern_text)),
        navigation_labels=navigation_labels,
        navigation_keywords=navigation_keywords,
        navigation_glyphs=navigation_glyphs,
        command_labels=normalized_label_set(
            [
                *COMMAND_LABELS,
                *extract_list_section(text, 'Automation Command Labels', []),
            ]
        ),
        defeat_recovery_labels=normalized_label_set(
            [
                *DEFEAT_RECOVERY_LABELS,
                *extract_list_section(text, 'Automation Defeat Recovery Labels', []),
            ]
        ),
        recruit_labels=normalized_label_set(
            [
                *RECRUIT_LABELS,
                *extract_list_section(text, 'Automation Recruit Labels', []),
            ]
        ),
        combat_card_double_tap_labels=normalized_label_set(
            [
                *COMBAT_CARD_DOUBLE_TAP_LABELS,
                *extract_list_section(
                    text,
                    'Automation Combat Double Tap Labels',
                    [],
                ),
            ]
        ),
        current_room_icon_labels=normalized_label_set(
            [
                *CURRENT_ROOM_ICON_LABELS,
                *extract_list_section(text, 'Automation Current Room Labels', []),
            ]
        ),
        claimed_labels=normalized_label_set(
            extract_list_section(text, 'Automation Claimed Labels', [])
        ),
        reward_overlay_labels=normalized_label_set(
            extract_list_section(text, 'Automation Reward Overlay Labels', [])
        ),
        reward_close_labels=normalized_label_set(
            extract_list_section(text, 'Automation Reward Close Labels', [])
        ),
        passive_non_action_labels=normalized_label_set(
            extract_list_section(text, 'Automation Passive Non-Action Labels', [])
        ),
        result_progress_labels=normalized_label_set(
            extract_list_section(text, 'Automation Result Progress Labels', [])
        ),
        skill_choice_required_labels=tuple(
            normalize_label(value)
            for value in extract_list_section(
                text,
                'Automation Skill Choice Required Labels',
                [],
            )
        ),
        skill_choice_instruction_labels=tuple(
            normalize_label(value)
            for value in extract_list_section(
                text,
                'Automation Skill Choice Instruction Labels',
                [],
            )
        ),
        skill_choice_split_instruction_labels=parse_label_groups(
            extract_list_section(
                text,
                'Automation Skill Choice Split Instruction Labels',
                [],
            )
        ),
        skill_choice_ignored_labels=normalized_label_set(
            extract_list_section(text, 'Automation Skill Choice Ignored Labels', [])
        ),
        level_row_patterns=compile_strategy_patterns(
            extract_list_section(text, 'Automation Level Row Patterns', [])
        ),
        challenge_detail_action_labels=normalized_label_set(
            extract_list_section(
                text,
                'Automation Challenge Detail Action Labels',
                [],
            )
        ),
        challenge_detail_patterns=compile_strategy_patterns(
            extract_list_section(text, 'Automation Challenge Detail Patterns', [])
        ),
        recent_reentry_keywords=tuple(
            normalize_label(value)
            for value in extract_list_section(
                text,
                'Automation Recent Reentry Keywords',
                [],
            )
        ),
        waiting_required_groups=parse_label_groups(
            extract_list_section(text, 'Automation Waiting Required Text', [])
        ),
        waiting_hint_groups=parse_label_groups(
            extract_list_section(text, 'Automation Waiting Hint Text', [])
        ),
        shop_screen_required_groups=parse_label_groups(
            extract_list_section(text, 'Automation Shop Screen Required Text', [])
        ),
        safe_confirm_required_groups=parse_label_groups(
            extract_list_section(text, 'Automation Safe Confirm Required Text', [])
        ),
        energy_empty_labels=normalized_label_set(
            extract_list_section(text, 'Automation Energy Empty Labels', [])
        ),
        energy_empty_destination_labels=normalized_label_set(
            extract_list_section(
                text,
                'Automation Energy Empty Destination Labels',
                [],
            )
        ),
        energy_empty_action_exemption_labels=normalized_label_set(
            extract_list_section(
                text,
                'Automation Energy Empty Action Exemption Labels',
                [],
            )
        ),
        loadout_start_labels=normalized_label_set(
            extract_list_section(text, 'Automation Loadout Start Labels', [])
        ),
        energy_empty_candidate=parse_first_candidate_section(
            text,
            'Automation Energy Empty Candidate',
        ),
        loadout_select_candidate=parse_first_candidate_section(
            text,
            'Automation Loadout Select Candidate',
        ),
        shop_escape_candidate=parse_first_candidate_section(
            text,
            'Automation Shop Escape Candidate',
        ),
        empty_screen_candidate=parse_first_candidate_section(
            text,
            'Automation Empty Screen Candidate',
        ),
        waiting_candidate=parse_first_candidate_section(
            text,
            'Automation Waiting Candidate',
        ),
        claimed_back_candidate=parse_first_candidate_section(
            text,
            'Automation Claimed Back Candidate',
        ),
        third_column_unclaimed_row_candidate=parse_first_row_candidate_section(
            text,
            'Automation Third Column Unclaimed Row Candidate',
        ),
        repeated_action_swipe_candidate=parse_first_repeated_action_swipe_section(
            text,
            'Automation Repeated Action Swipe Candidate',
        ),
        disabled_visual_filters=frozenset(
            normalize_label(value)
            for value in extract_list_section(
                text,
                'Automation Disabled Visual Filters',
                [],
            )
        ),
        passive_nameplate_region=parse_passive_nameplate_region(text),
        main_screen_verification_labels=normalized_label_set(
            extract_list_section(
                text,
                'Automation Main Screen Verification Labels',
                [],
            )
        ),
        always_preferred_choice_terms=tuple(
            normalize_label(value)
            for value in extract_list_section(
                text,
                'Automation Always Preferred Choices',
                [],
            )
            if value.strip()
        ),
        item_preference_rules=parse_item_preference_rules(
            extract_list_section(text, 'Automation Item Preference Rules', [])
        ),
        ignored_game_info_types=normalized_label_set(
            extract_list_section(
                text,
                'Automation Ignored Game Info Types',
                [],
            )
        ),
        no_change_skill_choice_rule=first_list_item(
            text,
            'Automation No Change Skill Choice Rule',
        ),
        no_change_empty_screen_rule=first_list_item(
            text,
            'Automation No Change Empty Screen Rule',
        ),
        target_level=first_list_int(text, 'Automation Target Level'),
        prefer_watch_ads=first_list_bool(text, 'Automation Prefer Watch Ads'),
    )


def load_memory(game: str) -> dict[str, Any]:
    path = memory_path_for(game)
    memory: dict[str, Any] = {
        'game': game,
        'preferred': list(DEFAULT_PREFERRED),
        'fallback': [],
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
    memory['fallback'] = extract_list_section(text, 'Fallback Buttons', [])
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


def append_unique_decision_rule(path: Path, line: str) -> bool:
    if not line.startswith('- '):
        line = f'- {line}'
    rule_text = line[2:].strip()
    decision_rules = extract_section(path.read_text(), 'Decision Rules')
    if normalize_label(rule_text) in normalize_label(decision_rules):
        return False
    append_to_strategy_section(
        path,
        'Decision Rules',
        line,
        insert_before='## Learned Choices',
    )
    return True


def should_remember_ineffective_button(
    button: ButtonCandidate,
    verification: StateVerification,
    strategy_text: str,
    automation_config: GameAutomationConfig | None = None,
) -> bool:
    if button.source == 'wait':
        return False
    if is_end_turn_label(button.label):
        return False
    key = normalize_label(button.label)
    if (
        automation_config is not None
        and normalize_label(automation_config.game) == 'tower'
        and (
            tower_shop_purchase_bonus(automation_config.game, button.label) > 0
            or tower_deep_map_room_bonus(button.label) != 0
            or key.startswith('刷新')
            or (key.startswith('免费') and '次' in key)
        )
    ):
        return False
    preferred = {
        normalize_label(item)
        for item in extract_list_section(strategy_text, 'Preferred Buttons', [])
    }
    fallback = {
        normalize_label(item)
        for item in extract_list_section(strategy_text, 'Fallback Buttons', [])
    }
    avoid = {
        normalize_label(item)
        for item in extract_list_section(strategy_text, 'Avoid Buttons', [])
    }
    if verification.status != 'unchanged' or verification.attempts < 3:
        return False
    if button.source in {'back', 'launch_app', 'state', 'swipe', 'vision'}:
        return False
    if looks_like_noise_label(button.label, automation_config):
        return False
    if is_navigation_arrow_label(button.label, automation_config):
        return False
    if (
        is_configured_command_label(button.label, automation_config)
        or key in CONFIRM_LABELS
    ):
        return False
    if is_configured_combat_card_label(button.label, automation_config) or (
        key in HARD_AVOID_LABELS
    ):
        return False
    if key in preferred or key in fallback or key in avoid:
        return False
    if button.source != 'template' and button.confidence < 0.9:
        return False
    if button.source == 'ocr' and button.clickability < 0.5:
        return False
    return True


def append_no_change_learning(
    game: str,
    button: ButtonCandidate,
    verification: StateVerification,
) -> bool:
    path = ensure_strategy_memory(game)
    text = path.read_text()
    automation_config = load_automation_config(game)
    changed = False
    ineffective = {
        normalize_label(item)
        for item in extract_list_section(text, 'Ineffective Buttons', [])
    }
    if button.source == 'wait':
        return False
    if is_navigation_arrow_label(button.label, automation_config):
        return append_unique_decision_rule(
            path,
            (
                '- When a room arrow fails to change the screen after retries, '
                'pick the brighter route or a concrete room icon before '
                'retrying that arrow.'
            ),
        )

    if (
        automation_config.skill_choice_required_labels
        and 'skill choice' in normalize_label(button.reason)
    ):
        rule = automation_config.no_change_skill_choice_rule or (
            '- If a configured skill-choice banner click does not change state, '
            'try another visible choice or a configured fallback before marking '
            'the card ineffective.'
        )
        return append_unique_decision_rule(
            path,
            rule,
        )

    if automation_config.empty_screen_candidate is not None and normalize_label(
        button.label
    ) == normalize_label(automation_config.empty_screen_candidate.label):
        rule = automation_config.no_change_empty_screen_rule or (
            '- If a configured empty-screen fallback does not verify progress, '
            'keep treating it as a fallback while trying other visible choices '
            'before marking it ineffective.'
        )
        return append_unique_decision_rule(
            path,
            rule,
        )

    if normalize_label(
        button.label
    ) not in ineffective and should_remember_ineffective_button(
        button,
        verification,
        text,
        automation_config,
    ):
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
        changed = True

    return changed


def append_unblock_learning(game: str, assessment: UnblockAssessment) -> bool:
    path = ensure_strategy_memory(game)
    if assessment.status != 'stuck':
        return False

    return append_unique_decision_rule(
        path,
        (
            '- When the last few turn screenshots remain nearly identical, '
            'temporarily deprioritize repeated actions and try a different '
            'visible target, tutorial-highlighted control, close/detail/back '
            'control, or vision-identified clickable before retrying.'
        ),
    )


class McpClient:
    def __init__(self, command: list[str], timeout: float = 20.0):
        self.command = command
        self.timeout = timeout
        self.process: subprocess.Popen[str] | None = None
        self.selector: selectors.BaseSelector | None = None
        self.request_id = 0

    def __enter__(self) -> McpClient:
        debug_progress(f'start MCP: {shlex.join(self.command)}')
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
        debug_progress('initialize MCP')
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
        debug_progress(f'MCP request {request_id}: {method}')
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
            debug_progress(f'MCP response {request_id}')
            return response

        stderr = ''
        if self.process.poll() is not None and self.process.stderr is not None:
            stderr = self.process.stderr.read()
        raise TimeoutError(f'MCP request {request_id} timed out. {stderr}'.strip())


_ACTIVE_MCP_CLIENT: McpClient | None = None
_ACTIVE_MCP_CLIENT_KEY: tuple[tuple[str, ...], float] | None = None


def live_mcp_client(args: argparse.Namespace) -> McpClient:
    global _ACTIVE_MCP_CLIENT, _ACTIVE_MCP_CLIENT_KEY
    command = (
        shlex.split(args.mcp_command) if args.mcp_command else default_mcp_command()
    )
    key = (tuple(command), float(args.timeout))
    process = getattr(_ACTIVE_MCP_CLIENT, 'process', None)
    process_stopped = process is not None and process.poll() is not None
    if (
        _ACTIVE_MCP_CLIENT is None
        or _ACTIVE_MCP_CLIENT_KEY != key
        or process_stopped
    ):
        close_live_mcp_client()
        _ACTIVE_MCP_CLIENT = McpClient(command, timeout=args.timeout)
        _ACTIVE_MCP_CLIENT.__enter__()
        _ACTIVE_MCP_CLIENT_KEY = key
    return _ACTIVE_MCP_CLIENT


def close_live_mcp_client() -> None:
    global _ACTIVE_MCP_CLIENT, _ACTIVE_MCP_CLIENT_KEY
    if _ACTIVE_MCP_CLIENT is not None:
        _ACTIVE_MCP_CLIENT.__exit__(None, None, None)
    _ACTIVE_MCP_CLIENT = None
    _ACTIVE_MCP_CLIENT_KEY = None


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

    tool_args: dict[str, Any] = {}
    if args.width:
        tool_args['width'] = args.width
    if args.height:
        tool_args['height'] = args.height
    result = live_mcp_client(args).call_tool('current_screen', tool_args)
    return decode_mcp_screen(result)


_ANALYZER_CACHE: dict[tuple[Any, ...], Any] = {}


def analyzer_cache_key(game: str, template_match_threshold: float) -> tuple[Any, ...]:
    strategy_path = memory_path_for(game)
    config_path = ocr_config_path_for(game)
    image_dir = template_images_dir_for(game)

    def file_signature(path: Path) -> tuple[int, int]:
        if not path.exists():
            return (0, 0)
        stat = path.stat()
        return (stat.st_mtime_ns, stat.st_size)

    template_signature = (
        tuple(
            (path.name, *file_signature(path))
            for path in sorted(image_dir.glob('*.png'))
        )
        if image_dir.exists()
        else ()
    )
    return (
        slugify(game),
        float(template_match_threshold),
        file_signature(strategy_path),
        file_signature(config_path),
        template_signature,
    )


def analyze_buttons(
    image: Image.Image,
    *,
    confidence: float,
    game: str,
    template_match_threshold: float,
) -> list[ButtonCandidate]:
    ensure_script_imports()

    from image_analyzer import create_analyzer

    automation_config = load_automation_config(game)
    analyzer_key = analyzer_cache_key(game, template_match_threshold)
    analyzer = _ANALYZER_CACHE.get(analyzer_key)
    if analyzer is None:
        analyzer = create_analyzer(
            template_dirs=[template_images_dir_for(game)],
            template_match_threshold=template_match_threshold,
            template_configs=load_ocr_config(game),
            noise_text_patterns=list(automation_config.noise_pattern_text),
            navigation_template_labels=list(automation_config.navigation_labels),
            navigation_template_keywords=list(automation_config.navigation_keywords),
            navigation_template_glyphs=list(automation_config.navigation_glyphs),
        )
        _ANALYZER_CACHE.clear()
        _ANALYZER_CACHE[analyzer_key] = analyzer
    locations = analyzer.extract_text_locations(image, confidence_threshold=confidence)
    buttons = []
    for item in locations:
        label = str(item.get('text', '')).strip()
        x = float(item.get('x', 0.0))
        y = float(item.get('y', 0.0))
        tower_map_floor_digit = bool(
            normalize_label(game) == 'tower'
            and re.fullmatch(r'\d{1,3}', normalize_label(label))
            and 0.54 <= x <= 0.72
            and 0.52 <= y <= 0.56
        )
        if not label or (
            looks_like_noise_label(label, automation_config)
            and not tower_map_floor_digit
        ):
            continue
        buttons.append(
            ButtonCandidate(
                label=label,
                x=x,
                y=y,
                confidence=float(item.get('confidence', 0.0)),
                clickability=float(item.get('clickability', 0.0)),
                source=str(item.get('source') or 'ocr'),
                template_path=str(item.get('template_path') or ''),
                bbox=parse_normalized_bbox(item),
                score=float(item.get('score') or 0.0),
            )
        )
    buttons = filter_tower_context_buttons(image, buttons, automation_config)
    return filter_conflicting_template_buttons(buttons)


def button_distance(left: ButtonCandidate, right: ButtonCandidate) -> float:
    return ((left.x - right.x) ** 2 + (left.y - right.y) ** 2) ** 0.5


def filter_conflicting_template_buttons(
    buttons: list[ButtonCandidate],
    *,
    coord_tolerance: float = 0.08,
) -> list[ButtonCandidate]:
    avoid_labels = {normalize_label(item) for item in DEFAULT_AVOID}
    avoid_buttons = [
        button
        for button in buttons
        if button.source != 'template' and normalize_label(button.label) in avoid_labels
    ]
    if not avoid_buttons:
        return buttons

    filtered = []
    for button in buttons:
        if button.source != 'template':
            filtered.append(button)
            continue
        if any(
            button_distance(button, avoid) <= coord_tolerance for avoid in avoid_buttons
        ):
            continue
        filtered.append(button)
    return filtered


def parse_normalized_bbox(
    item: dict[str, Any],
) -> tuple[float, float, float, float] | None:
    bbox = (
        item.get('template_bbox')
        or item.get('crop_bbox')
        or item.get('tight_bbox')
        or item.get('clickable_bbox')
        or item.get('bbox')
        or item.get('bounding_box')
        or item.get('box')
    )
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


def first_text_value(item: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(item.get(key) or '').strip()
        if value:
            return value
    return ''


def llm_label_text(item: dict[str, Any]) -> str:
    return first_text_value(
        item,
        (
            'game_label',
            'game_name',
            'original_label',
            'original_name',
            'visible_label',
            'visible_name',
            'name',
            'label',
            'text',
        ),
    )


def llm_description_text(item: dict[str, Any]) -> str:
    return first_text_value(
        item,
        (
            'game_description',
            'original_description',
            'visible_description',
            'description',
        ),
    )


def has_original_description_text(item: dict[str, Any]) -> bool:
    return bool(
        first_text_value(
            item,
            (
                'game_description',
                'original_description',
                'visible_description',
            ),
        )
    )


def llm_game_info_name(item: dict[str, Any]) -> str:
    return first_text_value(
        item,
        (
            'game_label',
            'game_name',
            'original_label',
            'original_name',
            'visible_label',
            'visible_name',
            'name',
            'label',
            'text',
        ),
    )


def llm_game_info_kind(item: dict[str, Any], label: str, description: str) -> str:
    value = first_text_value(
        item,
        ('type', 'kind', 'category', 'entity_type', 'game_info_type'),
    )
    if value:
        return normalize_label(value)
    return classify_game_info_entry(label, description)


def load_llm_buttons(
    path: Path | None,
    automation_config: GameAutomationConfig | None = None,
) -> list[ButtonCandidate]:
    if path is None or not path.exists():
        return []

    payload = safe_load_yaml_mapping(path)
    buttons = []
    for item in payload.get('buttons', []):
        label = llm_label_text(item)
        if not label or looks_like_noise_label(label, automation_config):
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


def truthy_llm_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        return normalize_label(value) in {
            '1',
            'true',
            'yes',
            'y',
            'clickable',
            'actionable',
        }
    return False


def llm_object_is_clickable(item: dict[str, Any]) -> bool:
    if any(
        truthy_llm_flag(item.get(key))
        for key in ('clickable', 'actionable', 'can_click', 'is_button')
    ):
        return True
    try:
        return float(item.get('clickability', 0.0)) > 0.0
    except (TypeError, ValueError):
        return False


def normalized_xy_from_item(
    item: dict[str, Any],
    bbox: tuple[float, float, float, float] | None,
) -> tuple[float, float] | None:
    try:
        x = float(item['x'])
        y = float(item['y'])
    except (KeyError, TypeError, ValueError):
        if bbox is None:
            return None
        x = (bbox[0] + bbox[2]) / 2.0
        y = (bbox[1] + bbox[3]) / 2.0
    return max(0.0, min(1.0, x)), max(0.0, min(1.0, y))


def load_llm_icon_candidates(
    path: Path | None,
    automation_config: GameAutomationConfig | None = None,
) -> list[ButtonCandidate]:
    if path is None or not path.exists():
        return []

    payload = safe_load_yaml_mapping(path)
    icons: list[ButtonCandidate] = []
    for item in payload.get('objects', []):
        if not isinstance(item, dict) or not llm_object_is_clickable(item):
            continue
        label = first_text_value(
            item,
            (
                'game_label',
                'game_name',
                'original_label',
                'original_name',
                'visible_label',
                'visible_name',
                'name',
                'label',
                'action_label',
                'button_label',
                'text',
            ),
        )
        if not label or looks_like_noise_label(label, automation_config):
            continue
        bbox = parse_normalized_bbox(item)
        if bbox is None:
            continue
        xy = normalized_xy_from_item(item, bbox)
        if xy is None:
            continue
        try:
            confidence = float(item.get('confidence', 0.7))
        except (TypeError, ValueError):
            confidence = 0.7
        try:
            clickability = float(item.get('clickability', 0.8))
        except (TypeError, ValueError):
            clickability = 0.8
        icons.append(
            ButtonCandidate(
                label=label,
                x=xy[0],
                y=xy[1],
                confidence=max(0.0, min(1.0, confidence)),
                clickability=max(0.0, min(1.0, clickability)),
                source='llm_icon',
                reason=str(item.get('reason') or llm_description_text(item)).strip(),
                bbox=bbox,
            )
        )
    return icons


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
    focus: tuple[float, float] | None = None,
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
    crop = image.crop((left, top, right, bottom))
    if focus is None:
        return crop

    focus_x = (focus[0] * image.width) - left
    focus_y = (focus[1] * image.height) - top
    return trim_crop_to_focused_component(crop, focus=(focus_x, focus_y))


def trim_crop_to_focused_component(
    crop: Image.Image,
    *,
    focus: tuple[float, float],
) -> Image.Image:
    if crop.width < 8 or crop.height < 8:
        return crop

    active_pixels = active_template_pixels(crop)
    if not active_pixels.any():
        return crop

    row_bounds = focused_axis_bounds(
        active_pixels.mean(axis=1),
        focus=focus[1],
        length=crop.height,
    )
    col_bounds = focused_axis_bounds(
        active_pixels.mean(axis=0),
        focus=focus[0],
        length=crop.width,
    )
    left, right = col_bounds
    top, bottom = row_bounds
    if right - left < 4 or bottom - top < 4:
        return crop
    return crop.crop((left, top, right, bottom))


def active_template_pixels(crop: Image.Image) -> np.ndarray:
    pixels = np.asarray(crop.convert('RGB'), dtype=np.float32)
    red = pixels[..., 0]
    green = pixels[..., 1]
    blue = pixels[..., 2]
    gray = 0.299 * red + 0.587 * green + 0.114 * blue
    chroma = np.maximum(np.maximum(red, green), blue) - np.minimum(
        np.minimum(red, green),
        blue,
    )
    return (gray >= 42.0) | (chroma >= 24.0)


def focused_axis_bounds(
    activity: np.ndarray,
    *,
    focus: float,
    length: int,
    margin: int = 2,
) -> tuple[int, int]:
    if length <= 0:
        return 0, 0
    max_activity = float(activity.max()) if activity.size else 0.0
    if max_activity <= 0.0:
        return 0, length

    threshold = max(0.04, max_activity * 0.12)
    mask = smooth_axis_mask(activity >= threshold, max_gap=max(2, length // 80))
    runs = true_runs(mask)
    if not runs:
        return 0, length

    focus_index = int(max(0, min(length - 1, round(focus))))
    containing = [run for run in runs if run[0] <= focus_index < run[1]]
    if containing:
        start, end = max(containing, key=lambda run: run[1] - run[0])
    else:
        start, end = min(
            runs,
            key=lambda run: min(abs(focus_index - run[0]), abs(focus_index - run[1])),
        )

    start = max(0, start - margin)
    end = min(length, end + margin)
    return start, end


def smooth_axis_mask(mask: np.ndarray, *, max_gap: int) -> np.ndarray:
    smoothed = mask.astype(bool).copy()
    runs = true_runs(~smoothed)
    for start, end in runs:
        if start == 0 or end == len(smoothed):
            continue
        if end - start <= max_gap:
            smoothed[start:end] = True
    return smoothed


def true_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    runs = []
    start = None
    for index, value in enumerate(mask):
        if value and start is None:
            start = index
        elif not value and start is not None:
            runs.append((start, index))
            start = None
    if start is not None:
        runs.append((start, len(mask)))
    return runs


def unique_template_path(directory: Path, label: str, turn_name: str) -> Path:
    stem = template_stem_for_label(label)
    path = directory / f'{stem}.png'
    suffix = 2
    while path.exists():
        path = directory / f'{stem}--{suffix:02d}.png'
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
                    'source': button.source,
                    'reason': 'LLM candidate did not include bbox.',
                }
            )
            continue
        crop = crop_from_bbox(image, button.bbox, focus=(button.x, button.y))
        if crop is None:
            learned.append(
                {
                    'label': button.label,
                    'status': 'skipped',
                    'source': button.source,
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
                'source': button.source,
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


def item_inspection_to_data(inspection: ItemInspection) -> dict[str, Any]:
    data = {
        'candidate': button_to_data(inspection.candidate),
        'description': inspection.description,
        'item_score': round(inspection.score, 6),
        'reasons': inspection.reasons,
        'screenshot': inspection.screenshot,
        'ocr_labels': inspection.ocr_labels,
    }
    if inspection.kind:
        data['kind'] = inspection.kind
    return data


def is_confirm_button(button: ButtonCandidate) -> bool:
    return normalize_label(button.label) in CONFIRM_LABELS


NON_ITEM_CONFIRMATION_PROMPT_HINTS = ('replace old adventure',)


def is_non_item_confirmation_dialog(buttons: list[ButtonCandidate]) -> bool:
    labels = [
        normalize_label(button.label)
        for button in buttons
        if button.source != 'template'
    ]
    if not any(label in CONFIRM_LABELS for label in labels):
        return False
    if not any(label in CANCEL_LABELS for label in labels):
        return False
    return any(
        any(hint in label for hint in NON_ITEM_CONFIRMATION_PROMPT_HINTS)
        or label.endswith('?')
        or label.endswith('？')
        for label in labels
        if label not in CONFIRM_LABELS and label not in CANCEL_LABELS
    )


def tower_treasure_choice_candidate(
    automation_config: GameAutomationConfig | None,
    buttons: list[ButtonCandidate],
) -> ButtonCandidate | None:
    if automation_config is None or normalize_label(automation_config.game) != 'tower':
        return None
    labels = {normalize_label(button.label) for button in buttons}
    if not labels & CONFIRM_LABELS:
        return None
    if not labels & {'back', 'return', '返回', '放弃'}:
        return None
    if '宝物选择' not in labels:
        return None
    if 'abandon' in labels or 'end' in labels:
        return None
    if any(
        is_navigation_arrow_label(button.label, automation_config) for button in buttons
    ):
        return None
    columns = (
        (0.00, 0.34, 0.20),
        (0.34, 0.66, 0.50),
        (0.66, 1.00, 0.80),
    )
    common_priorities = (
        ('不灭', 100.0),
        ('实验眼镜', 32.0),
        ('实验眼睛', 32.0),
        ('机械龙蛋', 30.0),
        ('巨人天平', 28.0),
        ('诅咒饭团', 18.0),
        ('巨人泡泡糖', 18.0),
        ('诅咒火炬', 18.0),
        ('时之沙漏', 16.0),
        ('超越宝石', 15.0),
        ('愤怒宝石', 13.0),
        ('剧毒宝石', 12.0),
        ('巨人', 10.0),
        ('抽牌', 9.0),
        ('法力', 8.0),
        ('回复', 7.0),
        ('治疗', 7.0),
        ('宇宙十字架', -35.0),
        ('荆棘花环', -30.0),
        ('爱心三明治', -35.0),
        ('重骑头盔', -25.0),
    )
    run_state = load_tower_run_state(automation_config.game)
    profession = tower_run_profession(automation_config.game)
    daily_state = load_tower_daily_state(automation_config.game)
    predecessor_panel = bool(run_state.get('awaiting_predecessor_treasure')) or (
        int(run_state.get('floor') or 0) <= 1
        and normalize_label(str(daily_state.get('phase') or ''))
        in {'abyss', 'abyss_retry'}
    )
    preferred_profession = str(
        daily_state.get('preferred_abyss_profession') or ''
    ).strip()
    if predecessor_panel and preferred_profession and not profession:
        profession = preferred_profession
    predecessor_targets = (
        tower_predecessor_treasure_targets(
            automation_config.game,
            profession,
        )
        if predecessor_panel
        else ()
    )
    if predecessor_panel and not predecessor_targets:
        predecessor_targets = TOWER_PREDECESSOR_TREASURE_TARGETS.get(
            str(profession or ''),
            (),
        )
    predecessor_priorities = tuple(
        (target, 88.0 - (index * 4.0))
        for index, target in enumerate(predecessor_targets)
    )
    traveler_treasure_priorities = (
        (
            ('魔法面具', 44.0),
            ('巨人之花', 38.0),
            ('贵族匕首', 36.0),
            ('宝石龙蛋', 34.0),
        )
        if tower_traveler_uses_prayer_build(automation_config.game)
        else (
            ('魔法面具', 40.0),
            ('花喇叭', 34.0),
            ('毒龙匕首', 34.0),
        )
    )
    profession_priorities = {
        '旅行者': traveler_treasure_priorities,
        '猎人': (
            ('日不落火把', 38.0),
            ('魔法面具', 42.0),
            ('火龙蛋', 40.0),
            ('魔法熊手', 34.0),
        ),
        '法师': (
            ('日不落火把', -50.0),
            ('魔法面具', 42.0),
            ('海王鲨鱼', 34.0),
        ),
        '战士': (
            ('日不落火把', 42.0),
            ('魔法熊手', 40.0),
            ('女鹅套娃', 38.0),
            ('魔塔石像', 34.0),
            ('魔法笔记', 28.0),
        ),
    }
    priorities = (
        *predecessor_priorities,
        *profession_priorities.get(str(profession or ''), ()),
        *common_priorities,
    )
    ignored = {
        '宝物选择',
        '功能宝物',
        '诅咒宝物',
        '确定',
        '返回',
        '放弃',
        'back',
        'return',
    }
    candidates: list[tuple[float, ButtonCandidate]] = []
    for left, right, center in columns:
        titles = [
            button.label.strip()
            for button in buttons
            if button.source != 'template'
            and left <= button.x < right
            and 0.43 <= button.y <= 0.54
            and normalize_label(button.label) not in ignored
        ]
        title = ' '.join(titles)
        if not title:
            continue
        key = TOWER_TREASURE_OCR_CORRECTIONS.get(
            normalize_label(title),
            normalize_label(title),
        )
        priority = 1.0
        reasons = []
        for pattern, points in priorities:
            if normalize_label(pattern) in key:
                priority += points
                reasons.append(pattern)
        candidates.append(
            (
                priority,
                ButtonCandidate(
                    label=f'Tower treasure choice: {title}',
                    x=center,
                    y=0.37,
                    confidence=0.97,
                    clickability=7.0 + priority,
                    source='vision',
                    reason=(
                        'Choose the visible treasure title using the current '
                        'burst-and-cycle policy: '
                        f'{", ".join(reasons) or "known treasure title"}.'
                    ),
                    score=priority,
                ),
            )
        )
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def is_tower_stair_choice_label(value: str) -> bool:
    key = normalize_label(value)
    return key in {'左侧楼梯', '右侧楼梯', '选择一个楼梯'}


def tower_stair_choice_candidate(
    automation_config: GameAutomationConfig | None,
    buttons: list[ButtonCandidate],
) -> ButtonCandidate | None:
    if automation_config is None or normalize_label(automation_config.game) != 'tower':
        return None
    labels = {normalize_label(button.label) for button in buttons}
    if '选择一个楼梯' not in labels or not labels & CONFIRM_LABELS:
        return None
    routes = {
        normalize_label(button.label): button
        for button in buttons
        if normalize_label(button.label) in {'左侧楼梯', '右侧楼梯'}
    }
    if len(routes) != 2:
        return None

    left_text = ' '.join(
        normalize_label(button.label)
        for button in buttons
        if button.source != 'template' and button.x < 0.5
    )
    right_text = ' '.join(
        normalize_label(button.label)
        for button in buttons
        if button.source != 'template' and button.x >= 0.5
    )
    def route_value(text: str) -> float:
        value = tower_deep_map_room_bonus(text)
        if '精英怪' in text or '英怪' in text:
            value -= 3.0
        elif '普通怪' in text or '小怪' in text:
            value += 0.5
        return value

    left_value = route_value(left_text)
    right_value = route_value(right_text)
    if left_value > right_value:
        return routes['左侧楼梯']
    if right_value > left_value:
        return routes['右侧楼梯']
    return max(routes.values(), key=lambda button: (button.score, button.confidence))


def tower_card_reward_priority_rules(
    game: str,
    profession: str | None,
) -> tuple[tuple[str, float], ...]:
    state = load_tower_run_state(game)
    predecessor = normalize_label(str(state.get('predecessor_treasure') or ''))
    floor = int(state.get('floor') or 0)
    selected_cards = ' '.join(
        normalize_label(str(card)) for card in state.get('core_cards') or []
    )
    common = (
        ('马上融合', 10.0),
        ('未来汽水', 9.0),
        ('超时空宝石', 8.5),
        ('以物易物', 8.0),
        ('巨人协议', 8.0),
        ('瞬发宝石', 7.5),
        ('坚定宝石', 7.0),
        ('许愿', 7.0),
        ('恢复宝石', 6.5),
        ('祈愿灯', 6.5),
        ('抽1张牌', 6.0),
        ('智慧宝石', 6.0),
        ('闪避宝石', 6.0),
        ('奉献', 5.5),
        ('岩土宝石', 5.5),
        ('逃生', 5.0),
        ('法力', 5.0),
        ('均衡宝石', 4.5),
        ('回复', 4.0),
        ('治疗', 4.0),
        ('病变', 3.75),
        ('剧毒晶石', 3.5),
        ('毒龙弹', 3.0),
        ('虔诚', 3.0),
        ('风怒之岩', -5.0),
        ('杂念', -6.0),
        ('杂物', -6.0),
        ('烟歌', -8.0),
    )
    if profession == '旅行者':
        if tower_traveler_uses_prayer_build(game):
            focused = (
                ('无限宝石', 42.0),
                ('天使', 40.0),
                ('救赎', 39.0),
                ('奉献', 38.0),
                ('黑神话', 37.0),
                ('献祭', 36.0),
                ('回忆', 35.0),
                ('未来汽水', 34.0),
            )
        else:
            focused = (
                ('无限宝石', 38.0),
                ('烈性毒药', 36.0),
                ('致命毒药', 36.0),
                ('安乐毒药', 34.0),
                ('黑神话', 33.5),
                ('剧毒晶石', 33.0),
                ('毒龙钻石', 32.0),
                ('涂毒小刀', 31.0),
                ('献祭', 30.0),
                ('未来汽水', 29.0),
                ('毒药攻击', 26.0),
            )
    elif profession == '猎人':
        focused = (
            ('捕猎陷阱', 38.0),
            ('宝石手套', 34.0),
            ('猎人嗅觉', 32.0),
            ('大力射击', 28.0),
            ('代号肉鸽', 25.0),
            ('海是那个味', 24.0),
            ('瞄准', 22.0),
            ('照明弹', 20.0),
        )
    elif profession == '法师':
        early_bridge = ()
        if floor <= 6:
            bridge_priorities = (
                ('飞弹磁化', 30.0),
                ('飞弹冻结', 29.0),
                ('雷电连击', 28.0),
                ('法术压制', 27.0),
                ('法术手杖', 26.0),
                ('能量储备', 22.0),
                ('冰霜飞弹', 20.0),
            )
            early_bridge = tuple(
                (
                    pattern,
                    10.0 if normalize_label(pattern) in selected_cards else priority,
                )
                for pattern, priority in bridge_priorities
            )
        if '火焰草莓' in predecessor:
            focused = (
                ('燃烧晶石', 40.0),
                ('太阳盾', 39.0),
                ('火焰打击', 38.0),
            )
        elif '电虫药水' in predecessor:
            focused = (
                ('寒冷晶石', 39.0),
                ('寒冷宝石', 39.0),
                ('寒流', 38.5),
                ('冷风', 38.0),
                ('雷龙', 37.5),
                ('电解冰', 37.0),
                ('快速思考', 36.0),
                ('小雷虫', 35.0),
                ('能量飞电', 34.5),
                ('回忆', 33.0),
                ('寒冰盾', 32.5),
                ('闪电晶石', 31.0),
                ('过度解冻', 28.0),
                ('百火', 26.0),
                *early_bridge,
            )
        else:
            focused = (
                ('冷风', 38.0),
                ('寒冰盾', 37.5),
                ('寒流', 37.0),
                ('电解冰', 36.0),
                ('能量飞电', 35.5),
                ('快速思考', 35.0),
                ('火焰打击', 34.0),
                ('燃烧晶石', 33.0),
                ('闪电晶石', 32.0),
                ('小雷虫', 31.0),
                ('过度解冻', 30.0),
                *early_bridge,
            )
    elif profession == '战士':
        if '巨人之拳' in predecessor:
            focused = (
                ('愤怒宝石', 44.0),
                ('撞击', 42.0),
                ('未来汽水', 41.0),
                ('神圣斩击', 40.0),
                ('巨人协议', 38.0),
                ('守势', 36.0),
                ('启动防守', 34.0),
                ('迅捷', 30.0),
                ('回忆', 28.0),
                ('无限攻击', 24.0),
            )
        elif '曜蓝水晶' in predecessor:
            focused = (
                ('发现弱点', 38.0),
                ('弱点加倍', 36.0),
                ('弱点打击', 35.0),
                ('迅捷', 34.0),
                ('未来汽水', 33.0),
                ('神圣斩击', 30.0),
                ('巨人协议', 28.0),
                ('撞击', 27.0),
                ('代号肉鸽', 27.0),
                ('海是那个味', 26.0),
            )
        else:
            focused = (
                ('宝石手套', 40.0),
                ('超时空宝石', 39.0),
                ('迅捷', 38.0),
                ('发现弱点', 37.0),
                ('弱点打击', 36.0),
                ('未来汽水', 34.0),
                ('神圣斩击', 32.0),
                ('巨人协议', 31.0),
                ('撞击', 30.0),
                ('回忆', 30.0),
                ('献祭', 29.0),
            )
    else:
        focused = ()
    if profession == '旅行者':
        selected_cards = ' '.join(
            normalize_label(str(card)) for card in state.get('core_cards') or []
        )
        if tower_traveler_uses_prayer_build(game):
            capped_groups = (
                ('无限宝石',),
                ('天使',),
                ('救赎',),
                ('奉献',),
                ('黑神话',),
                ('未来汽水', '献祭'),
                ('回忆',),
            )
        else:
            capped_groups = (
                ('无限宝石',),
                ('剧毒晶石',),
                ('毒龙钻石',),
                ('烈性毒药',),
                ('安乐毒药',),
                ('黑神话',),
                ('涂毒小刀', '毒药攻击'),
                ('未来汽水', '献祭', '回忆'),
            )
        capped_patterns = {
            pattern
            for group in capped_groups
            if any(normalize_label(pattern) in selected_cards for pattern in group)
            for pattern in group
        }
        focused = tuple(
            (pattern, 10.0 if pattern in capped_patterns else priority)
            for pattern, priority in focused
        )
    if profession:
        return focused
    return common


def tower_card_reward_candidate(
    automation_config: GameAutomationConfig | None,
    buttons: list[ButtonCandidate],
) -> ButtonCandidate | None:
    if automation_config is None or normalize_label(automation_config.game) != 'tower':
        return None
    labels = {normalize_label(button.label) for button in buttons}
    if '选一张卡牌学习' not in labels or not labels & CONFIRM_LABELS:
        return None

    columns = (
        (0.00, 0.34, 0.17),
        (0.34, 0.66, 0.50),
        (0.66, 1.00, 0.83),
    )
    candidates: list[tuple[float, ButtonCandidate]] = []
    run_state = load_tower_run_state(automation_config.game)
    profession = (
        tower_run_profession(automation_config.game)
        if (
            normalize_label(str(run_state.get('phase') or '')) == 'card_reward'
            and normalize_label(str(run_state.get('stage') or '')) != '尖塔木屋'
        )
        else None
    )
    priorities = tower_card_reward_priority_rules(
        automation_config.game,
        profession,
    )
    if profession:
        priorities = (
            *priorities,
            ('无限宝石', 23.0),
            ('瞬发宝石', 22.0),
            ('超越宝石', 21.0),
            ('超时空宝石', 20.0),
            ('恢复宝石', 19.0),
        )
    ignored = {
        '选一张卡牌学习',
        '技能牌',
        '放弃',
        '确定',
        '消耗',
    }
    immediate_fusion_columns = {
        index
        for index, (left, right, _center) in enumerate(columns)
        if any(
            normalize_label(button.label) == '马上融合'
            and left <= button.x < right
            for button in buttons
        )
    }
    for column_index, (left, right, center) in enumerate(columns):
        texts = [
            button.label.strip()
            for button in buttons
            if button.source != 'template'
            and left <= button.x < right
            and 0.44 <= button.y <= 0.54
            and normalize_label(button.label) not in ignored
        ]
        text = ' '.join(texts)
        if not text and column_index not in immediate_fusion_columns:
            continue
        if not text:
            text = '马上融合'
        key = normalize_label(text)
        priority = 1.0
        reasons = []
        if column_index in immediate_fusion_columns:
            priority += 20.0
            reasons.append('马上融合')
        for pattern, points in priorities:
            if normalize_label(pattern) in key:
                priority += points
                reasons.append(pattern)
        candidates.append(
            (
                priority,
                ButtonCandidate(
                    label=f'Tower card choice: {text}',
                    x=center,
                    y=0.43,
                    confidence=0.96,
                    clickability=7.0 + priority,
                    source='vision',
                    reason=(
                        'Choose one card from its visible title and short-cycle '
                        f'synergy: {", ".join(reasons) or "known card title"}.'
                    ),
                    score=priority,
                ),
            )
        )
    abandon = next(
        (
            button
            for button in buttons
            if button.source != 'template'
            and normalize_label(button.label) == '放弃'
        ),
        None,
    )
    if abandon is None and profession:
        abandon = ButtonCandidate(
            label='放弃',
            x=0.286,
            y=0.696,
            confidence=0.96,
            clickability=21.0,
            source='vision',
            reason='牌包放弃按钮位置固定；OCR 漏字时使用本地视觉坐标。',
            score=14.0,
        )
    if abandon is not None and profession:
        candidates.append(
            (
                14.0,
                replace(
                    abandon,
                    clickability=21.0,
                    reason=(
                        f'{profession}速刷只收核心牌；本组三选一不够强，'
                        '放弃并获得10金币，避免牌库膨胀。'
                    ),
                    score=14.0,
                ),
            )
        )
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def tower_rest_choice_candidate(
    automation_config: GameAutomationConfig | None,
    buttons: list[ButtonCandidate],
) -> ButtonCandidate | None:
    if automation_config is None or normalize_label(automation_config.game) != 'tower':
        return None
    labels = {normalize_label(button.label) for button in buttons}
    if '破旧营地' not in labels or not labels & CONFIRM_LABELS:
        return None
    state = load_tower_run_state(automation_config.game)
    if normalize_label(str(state.get('stage') or '')) == '深渊楼梯':
        priorities = {
            '休息': 6,
            '锻炼': 5,
            '阅读': 4,
            '冥想': 3,
            '挖掘': 2,
        }
    else:
        priorities = {
            '锻炼': 5,
            '阅读': 4,
            '冥想': 3,
            '挖掘': 2,
            '休息': 1,
        }
    choices = [
        button
        for button in buttons
        if normalize_label(button.label) in priorities
    ]
    if not choices:
        return None
    return max(
        choices,
        key=lambda button: (
            priorities[normalize_label(button.label)],
            button.confidence,
        ),
    )


def is_inspectable_item_candidate(
    button: ButtonCandidate,
    *,
    fallback_labels: set[str],
    avoid_labels: set[str],
    ineffective_labels: set[str],
    automation_config: GameAutomationConfig | None = None,
) -> bool:
    if button.source not in {'ocr', 'llm', 'llm_icon', 'vision'}:
        return False
    key = normalize_label(button.label)
    if is_tower_stair_choice_label(button.label):
        return False
    if (
        key in CONFIRM_LABELS
        or key in CANCEL_LABELS
        or is_configured_command_label(
            button.label,
            automation_config,
        )
    ):
        return False
    if key in {'back', '返回', 'return'}:
        return False
    if key in HARD_AVOID_LABELS or is_navigation_arrow_label(
        button.label,
        automation_config,
    ):
        return False
    if key in fallback_labels or key in avoid_labels or key in ineffective_labels:
        return False
    return not looks_like_noise_label(button.label)


def item_description_labels(
    *,
    before_buttons: list[ButtonCandidate],
    after_buttons: list[ButtonCandidate],
    candidate: ButtonCandidate,
    automation_config: GameAutomationConfig | None = None,
) -> list[str]:
    before = {normalize_label(button.label) for button in before_buttons}
    command_labels = set(COMMAND_LABELS)
    if automation_config is not None:
        command_labels |= set(automation_config.command_labels)
    blocked = (
        before | command_labels | CONFIRM_LABELS | {normalize_label(candidate.label)}
    )
    labels: list[str] = []
    seen: set[str] = set()
    for button in after_buttons:
        if button.source == 'template':
            continue
        label = button.label.strip()
        key = normalize_label(label)
        if (
            not label
            or key in blocked
            or looks_like_noise_label(
                label,
                automation_config,
            )
        ):
            continue
        if key in seen:
            continue
        seen.add(key)
        labels.append(label)
    if labels:
        return labels

    for button in after_buttons:
        if button.source == 'template':
            continue
        label = button.label.strip()
        key = normalize_label(label)
        if (
            not label
            or key in seen
            or looks_like_noise_label(
                label,
                automation_config,
            )
        ):
            continue
        seen.add(key)
        labels.append(label)
    return labels


def configured_skill_choice_visible(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    if not automation_config.skill_choice_required_labels:
        return False
    labels = {normalize_label(button.label) for button in buttons}
    has_required = all(
        label in labels for label in automation_config.skill_choice_required_labels
    )
    has_instruction = any(
        label in labels for label in automation_config.skill_choice_instruction_labels
    ) or any(
        all(label in labels for label in group)
        for group in automation_config.skill_choice_split_instruction_labels
    )
    return has_required and has_instruction


def configured_skill_choice_detail_overlay_visible(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    if not configured_skill_choice_visible(automation_config, buttons):
        return False
    overlay_title = any(
        button.source != 'template'
        and 0.28 <= button.y <= 0.36
        and 0.34 <= button.x <= 0.66
        and normalize_label(button.label)
        not in automation_config.skill_choice_ignored_labels
        for button in buttons
    )
    if not overlay_title:
        return False
    overlay_detail = any(
        button.source != 'template'
        and 0.48 <= button.y <= 0.66
        and (
            ':' in button.label
            or 'can be evolved' in normalize_label(button.label)
            or 'guardian mode' in normalize_label(button.label)
            or 'evolved into' in normalize_label(button.label)
        )
        for button in buttons
    )
    return overlay_detail


def configured_skill_choice_detail_close_candidate() -> ButtonCandidate:
    return ButtonCandidate(
        label='Close skill detail',
        x=0.825,
        y=0.33,
        confidence=1.0,
        clickability=4.0,
        source='vision',
        reason=(
            'A skill description overlay is covering the cards; close it before '
            'choosing another yellow card banner.'
        ),
    )


def filter_configured_non_action_buttons(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    if configured_skill_choice_visible(automation_config, buttons):
        return buttons
    if not automation_config.passive_non_action_labels:
        return buttons
    filtered = [
        button
        for button in buttons
        if normalize_label(button.label)
        not in automation_config.passive_non_action_labels
        and not is_tower_passive_status_label(automation_config, button.label)
        and not is_tower_map_floor_status_button(automation_config, button)
        and not configured_top_left_battle_nameplate(automation_config, button)
    ]
    if filtered != buttons:
        return filtered
    return buttons


def configured_top_left_battle_nameplate(
    automation_config: GameAutomationConfig,
    button: ButtonCandidate,
) -> bool:
    region = automation_config.passive_nameplate_region
    if region is None:
        return False
    x_min, x_max, y_min, y_max, max_clickability = region
    return (
        button.source != 'template'
        and x_min <= button.x <= x_max
        and y_min <= button.y <= y_max
        and button.clickability <= max_clickability
    )


def expanded_button_visual_crop(
    image: Image.Image,
    button: ButtonCandidate,
) -> np.ndarray | None:
    if button.bbox is None:
        return None

    width, height = image.size
    x1, y1, x2, y2 = button.bbox
    left = max(0.0, min(1.0, x1)) * width
    top = max(0.0, min(1.0, y1)) * height
    right = max(0.0, min(1.0, x2)) * width
    bottom = max(0.0, min(1.0, y2)) * height
    if right <= left or bottom <= top:
        return None

    center_x = max(0.0, min(1.0, button.x)) * width
    center_y = max(0.0, min(1.0, button.y)) * height
    crop_width = max(right - left, width * 0.18)
    crop_height = max(bottom - top, height * 0.055)
    crop_left = max(0, int(round(center_x - (crop_width / 2.0))))
    crop_top = max(0, int(round(center_y - (crop_height / 2.0))))
    crop_right = min(width, int(round(center_x + (crop_width / 2.0))))
    crop_bottom = min(height, int(round(center_y + (crop_height / 2.0))))
    if crop_right <= crop_left or crop_bottom <= crop_top:
        return None
    return np.asarray(image.crop((crop_left, crop_top, crop_right, crop_bottom)))


def lower_toggle_visual_crop(
    image: Image.Image,
    button: ButtonCandidate,
) -> np.ndarray | None:
    width, height = image.size
    center_x = max(0.0, min(1.0, button.x)) * width
    center_y = max(0.0, min(1.0, button.y + 0.038)) * height
    crop_width = width * 0.09
    crop_height = height * 0.05
    crop_left = max(0, int(round(center_x - (crop_width / 2.0))))
    crop_top = max(0, int(round(center_y - (crop_height / 2.0))))
    crop_right = min(width, int(round(center_x + (crop_width / 2.0))))
    crop_bottom = min(height, int(round(center_y + (crop_height / 2.0))))
    if crop_right <= crop_left or crop_bottom <= crop_top:
        return None
    return np.asarray(image.crop((crop_left, crop_top, crop_right, crop_bottom)))


def is_low_chroma_gray_crop(crop: np.ndarray | None) -> bool:
    if crop is None or crop.size == 0:
        return False

    pixels = crop.astype(np.float32)
    if pixels.ndim == 2:
        gray = pixels
        saturation = np.zeros_like(gray)
    else:
        red = pixels[..., 0]
        green = pixels[..., 1]
        blue = pixels[..., 2]
        max_channel = np.maximum(np.maximum(red, green), blue)
        min_channel = np.minimum(np.minimum(red, green), blue)
        gray = 0.299 * red + 0.587 * green + 0.114 * blue
        saturation = (max_channel - min_channel) / np.maximum(max_channel, 1.0)

    mean_saturation = float(np.mean(saturation))
    high_saturation = float(np.percentile(saturation, 90))
    colored_pixel_ratio = float(np.mean(saturation >= 0.18))
    mean_brightness = float(np.mean(gray) / 255.0)
    highlight = float(np.percentile(gray, 90) / 255.0)
    contrast = float(np.std(gray) / 255.0)
    return (
        mean_saturation <= 0.12
        and high_saturation <= 0.20
        and colored_pixel_ratio <= 0.08
        and 0.18 <= mean_brightness <= 0.78
        and highlight <= 0.88
        and contrast <= 0.28
    )


def is_disabled_toggle_crop(crop: np.ndarray | None) -> bool:
    if crop is None or crop.size == 0:
        return False

    pixels = crop.astype(np.float32)
    if pixels.ndim == 2:
        gray = pixels
        saturation = np.zeros_like(gray)
    else:
        red = pixels[..., 0]
        green = pixels[..., 1]
        blue = pixels[..., 2]
        max_channel = np.maximum(np.maximum(red, green), blue)
        min_channel = np.minimum(np.minimum(red, green), blue)
        gray = 0.299 * red + 0.587 * green + 0.114 * blue
        saturation = (max_channel - min_channel) / np.maximum(max_channel, 1.0)

    mean_saturation = float(np.mean(saturation))
    high_saturation = float(np.percentile(saturation, 90))
    mean_brightness = float(np.mean(gray) / 255.0)
    highlight = float(np.percentile(gray, 90) / 255.0)
    contrast = float(np.std(gray) / 255.0)
    return (
        mean_saturation <= 0.30
        and high_saturation <= 0.45
        and 0.12 <= mean_brightness <= 0.70
        and highlight <= 0.78
        and contrast <= 0.30
    )


def is_configured_disabled_gray_button(
    automation_config: GameAutomationConfig,
    image: Image.Image,
    button: ButtonCandidate,
) -> bool:
    if 'gray-disabled-buttons' not in automation_config.disabled_visual_filters:
        return False
    if button.source == 'vision':
        return False
    if normalize_label(button.label) in CHALLENGE_DETAIL_FAST_ACTION_KEYS:
        return is_disabled_toggle_crop(lower_toggle_visual_crop(image, button))
    return is_low_chroma_gray_crop(expanded_button_visual_crop(image, button))


def filter_configured_disabled_gray_buttons(
    automation_config: GameAutomationConfig,
    image: Image.Image,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    if 'gray-disabled-buttons' not in automation_config.disabled_visual_filters:
        return buttons
    return [
        button
        for button in buttons
        if is_tower_room_vision_candidate(button)
        or not is_configured_disabled_gray_button(automation_config, image, button)
    ]


def configured_skill_choice_groups(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[tuple[float, list[ButtonCandidate], list[ButtonCandidate]]]:
    columns = [
        (0.00, 0.34, 0.17),
        (0.34, 0.66, 0.50),
        (0.66, 1.00, 0.83),
    ]
    groups: list[tuple[float, list[ButtonCandidate], list[ButtonCandidate]]] = []
    for left, right, center in columns:
        title_buttons: list[ButtonCandidate] = []
        description_buttons: list[ButtonCandidate] = []
        for button in buttons:
            if button.source == 'template' or not left <= button.x < right:
                continue
            label = button.label.strip()
            key = normalize_label(label)
            if (
                not label
                or key in automation_config.skill_choice_ignored_labels
                or key.startswith('refreshes left')
                or looks_like_noise_label(label, automation_config)
                or button.clickability < 1.25
            ):
                continue
            if 0.35 <= button.y <= 0.43:
                title_buttons.append(button)
            elif 0.48 <= button.y <= 0.56:
                description_buttons.append(button)
        if title_buttons:
            groups.append((center, title_buttons, description_buttons))
    return groups


def configured_skill_choice_inspections(
    *,
    automation_config: GameAutomationConfig,
    game: str,
    buttons: list[ButtonCandidate],
) -> list[ItemInspection]:
    if not configured_skill_choice_visible(automation_config, buttons):
        return []

    inspections: list[ItemInspection] = []
    for center, title_buttons, description_buttons in configured_skill_choice_groups(
        automation_config, buttons
    ):
        title = ' '.join(
            button.label.strip()
            for button in sorted(title_buttons, key=lambda item: (item.y, item.x))
        )
        title = strip_configured_skill_choice_badges(title, automation_config)
        description_labels = [
            button.label.strip()
            for button in sorted(description_buttons, key=lambda item: (item.y, item.x))
        ]
        description = '; '.join(description_labels)
        score, reasons = configured_item_preference_score(
            title,
            description,
            automation_config,
            game=game,
        )
        confidence = max(button.confidence for button in title_buttons)
        title_click_y = max(
            0.36,
            min(0.42, sum(button.y for button in title_buttons) / len(title_buttons)),
        )
        inspections.append(
            ItemInspection(
                candidate=ButtonCandidate(
                    label=title,
                    x=center,
                    y=title_click_y,
                    confidence=confidence,
                    clickability=2.4,
                    source='ocr',
                    reason='Configured skill choice yellow title banner.',
                    score=score,
                ),
                description=description,
                score=score,
                reasons=reasons,
                screenshot='screenshot.png',
                ocr_labels=[*description_labels],
                kind='skill',
            )
        )
    return inspections


def configured_skill_choice_fallback_candidates(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    if not configured_skill_choice_visible(automation_config, buttons):
        return []

    columns = [
        (0.00, 0.34, 0.17),
        (0.34, 0.66, 0.50),
        (0.66, 1.00, 0.83),
    ]
    titled_centers = {
        round(center, 2)
        for (
            center,
            _title_buttons,
            _description_buttons,
        ) in configured_skill_choice_groups(automation_config, buttons)
    }

    candidates: list[ButtonCandidate] = []
    for left, right, center in columns:
        if round(center, 2) in titled_centers:
            continue
        description_buttons: list[ButtonCandidate] = []
        for button in buttons:
            if button.source == 'template' or not left <= button.x < right:
                continue
            label = button.label.strip()
            key = normalize_label(label)
            if (
                not label
                or key in automation_config.skill_choice_ignored_labels
                or key.startswith('refreshes left')
                or looks_like_noise_label(label, automation_config)
            ):
                continue
            if 0.48 <= button.y <= 0.56:
                description_buttons.append(button)
        if not description_buttons:
            continue

        description = '; '.join(
            button.label.strip()
            for button in sorted(description_buttons, key=lambda item: (item.y, item.x))
        )
        item_score, reasons = configured_item_preference_score(
            '',
            description,
            automation_config,
        )
        candidates.append(
            ButtonCandidate(
                label='Skill card banner',
                x=center,
                y=0.395,
                confidence=max(button.confidence for button in description_buttons),
                clickability=2.4,
                source='vision',
                reason=(
                    'Configured skill-choice screen has card description text but '
                    'OCR missed the yellow title banner; click the inferred banner. '
                    f'Description: {description}'
                ),
                score=item_score,
            )
        )

    if candidates:
        return candidates

    return [
        ButtonCandidate(
            label='Skill card banner',
            x=0.5,
            y=0.395,
            confidence=0.5,
            clickability=2.4,
            source='vision',
            reason=(
                'Configured skill-choice screen is visible but OCR did not expose '
                'a usable card title; click the expected center yellow banner.'
            ),
        )
    ]


def inspect_configured_skill_choice(
    args: argparse.Namespace,
    *,
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
    artifact_paths: dict[str, Path],
) -> tuple[list[ItemInspection], Decision | None]:
    if configured_skill_choice_detail_overlay_visible(automation_config, buttons):
        close = configured_skill_choice_detail_close_candidate()
        return [], Decision(
            status='ready',
            reason=(
                'A skill detail overlay is open; close it before selecting the '
                'yellow banner for the next choice.'
            ),
            recommended=close,
            choices=[close],
        )

    inspections = configured_skill_choice_inspections(
        automation_config=automation_config,
        game=args.game,
        buttons=buttons,
    )
    if not inspections:
        fallback_candidates = configured_skill_choice_fallback_candidates(
            automation_config,
            buttons,
        )
        if not fallback_candidates:
            return [], None
        best = max(
            fallback_candidates,
            key=lambda item: (item.score, item.confidence, item.clickability),
        )
        return [], Decision(
            status='ready',
            reason=(
                'Skill-choice screen is visible, but OCR did not capture a usable '
                'card title. Clicking the inferred yellow card banner instead of '
                'instruction text or Refresh.'
            ),
            recommended=best,
            choices=fallback_candidates,
        )

    write_item_inspections_yaml(artifact_paths['item_inspections'], inspections)
    write_game_info_markdown(
        args.game,
        additional_inspection_path=artifact_paths['item_inspections'],
    )
    best = max(
        inspections,
        key=lambda item: (item.score, item.candidate.confidence),
    )
    return inspections, Decision(
        status='ready',
        reason=(
            f'Captured {len(inspections)} configured choices into game_info.md '
            f'and selected {best.candidate.label} because: '
            f'{", ".join(best.reasons) or "best current score"}.'
        ),
        recommended=best.candidate,
        choices=[
            replace(
                item.candidate,
                score=item.score,
                reason=(
                    f'{item.candidate.reason} Description: '
                    f'{item.description or "description not captured"}'
                ),
            )
            for item in sorted(
                inspections,
                key=lambda item: (item.score, item.candidate.confidence),
                reverse=True,
            )
        ],
    )


def normalize_badge_token(value: str) -> str:
    return normalize_label(
        re.sub(
            r'^[^\w\u4e00-\u9fff+\-]+|[^\w\u4e00-\u9fff+\-]+$',
            '',
            value,
        )
    )


def strip_configured_skill_choice_badges(
    label: str,
    automation_config: GameAutomationConfig | None,
) -> str:
    if automation_config is None:
        return label.strip()
    parts = label.strip().split()
    while (
        len(parts) > 1
        and normalize_badge_token(parts[0])
        in automation_config.skill_choice_ignored_labels
    ):
        parts.pop(0)
    return ' '.join(parts)


def item_preference_score(label: str, description: str) -> tuple[float, list[str]]:
    text = normalize_label(f'{label} {description}')
    score = 0.0
    reasons: list[str] = []

    permanent_patterns = ('permanent', 'forever', '永久', '永远')
    per_battle_patterns = (
        'per battle',
        'each battle',
        'every battle',
        'per fight',
        'each fight',
        '每场战斗',
        '每次战斗',
        '每场',
        '每次',
    )
    coin_patterns = ('coin', 'coins', 'gold', 'money', '金币', '金钱')
    currency_patterns = ('crystal', 'crystals', '水晶')
    cost_or_loss_patterns = (
        'lose',
        'spend',
        'cost',
        'consume',
        '失去',
        '消耗',
        '扣除',
    )
    sacrifice_patterns = (
        'sacrifice',
        'self damage',
        'spend hp',
        'cost hp',
        'lose hp',
        '舍命',
        '卖血',
        '扣血',
        '生命消耗',
    )
    stat_patterns = (
        'stat',
        'stats',
        'attack',
        'atk',
        'damage',
        'defense',
        'defence',
        'hp',
        'health',
        'speed',
        'movement',
        'range',
        'cooldown',
        'cd',
        'firing interval',
        'crit',
        'strength',
        '属性',
        '攻击',
        '伤害',
        '防御',
        '生命',
        '血量',
        '暴击',
    )

    def contains(patterns: tuple[str, ...]) -> bool:
        return any(pattern in text for pattern in patterns)

    def add_if(patterns: tuple[str, ...], points: float, reason: str) -> None:
        nonlocal score
        if contains(patterns):
            score += points
            reasons.append(reason)

    add_if(
        permanent_patterns,
        8.0,
        'permanent effect',
    )
    add_if(
        per_battle_patterns,
        7.0,
        'scales per battle',
    )
    add_if(
        coin_patterns,
        5.0,
        'coin gain',
    )
    add_if(
        stat_patterns,
        4.0,
        'stat increase',
    )
    permanent = contains(permanent_patterns)
    per_battle = contains(per_battle_patterns)
    coin = contains(coin_patterns)
    stat = contains(stat_patterns)
    currency = contains(currency_patterns)
    cost_or_loss = contains(cost_or_loss_patterns)
    if permanent and stat:
        score += 6.0
        reasons.append('permanent stat priority')
    if per_battle and (coin or stat):
        score += 5.0
        reasons.append('per-battle growth priority')
    add_if(
        (
            '+',
            'increase',
            'gain',
            'up',
            'more',
            'bigger',
            'doubled',
            'reduced',
            'shorter',
            '获得',
            '增加',
            '提升',
        ),
        2.0,
        'increase cue',
    )
    add_if(
        ('temporary', 'this battle', 'this fight', '本次', '临时', '当前战斗'),
        -5.0,
        'temporary-only effect',
    )
    if cost_or_loss and currency:
        reasons.append('currency cost ignored')
    elif cost_or_loss:
        score -= 4.0
        reasons.append('cost or loss')
    add_if(sacrifice_patterns, -8.0, 'self-sacrifice cue')
    return score, reasons


def compact_preference_text(value: str) -> str:
    normalized = normalize_label(value).replace('0', 'o')
    return re.sub(r'[^0-9a-z\u4e00-\u9fff]+', '', normalized)


def preferred_choice_term_matches(term: str, text: str) -> bool:
    term = normalize_label(term)
    if not term:
        return False
    if term in text:
        return True

    compact_term = compact_preference_text(term)
    compact_text = compact_preference_text(text)
    if compact_term and compact_term in compact_text:
        return True

    if len(compact_term) >= 5:
        for index in range(len(compact_term)):
            shortened = compact_term[:index] + compact_term[index + 1 :]
            if shortened and shortened in compact_text:
                return True
    return False


def configured_always_preferred_choice_match(
    label: str,
    description: str,
    automation_config: GameAutomationConfig | None = None,
) -> str:
    if automation_config is None:
        return ''
    text = normalize_label(f'{label} {description}')
    for term in automation_config.always_preferred_choice_terms:
        if preferred_choice_term_matches(term, text):
            return term
    return ''


def configured_item_preference_score(
    label: str,
    description: str,
    automation_config: GameAutomationConfig | None = None,
    game: str | None = None,
) -> tuple[float, list[str]]:
    score, reasons = item_preference_score(label, description)
    if automation_config is not None:
        text = normalize_label(f'{label} {description}')
        for rule in automation_config.item_preference_rules:
            if rule.pattern in text:
                score += rule.points
                reasons.append(rule.reason)
    match = configured_always_preferred_choice_match(
        label,
        description,
        automation_config,
    )
    if match:
        return score + 100.0, [
            f'always preferred by strategy: {match}',
            *reasons,
        ]
    return score, reasons


def write_item_inspections_yaml(path: Path, inspections: list[ItemInspection]) -> None:
    if not inspections:
        return
    payload = {'items': [item_inspection_to_data(item) for item in inspections]}
    path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    )


def classify_game_info_entry(label: str, description: str) -> str:
    text = normalize_label(f'{label} {description}')
    if any(pattern in text for pattern in SKILL_KIND_PATTERNS):
        return 'skill'
    return 'item'


def item_inspection_paths(
    game: str,
    additional_inspection_path: Path | None = None,
) -> list[Path]:
    paths: list[Path] = []
    turns_dir = game_root_for(game) / 'turns'
    if turns_dir.exists():
        paths.extend(sorted(turns_dir.glob('*/item_inspections.yaml')))
    if additional_inspection_path is not None and additional_inspection_path.exists():
        if additional_inspection_path not in paths:
            paths.append(additional_inspection_path)
    return paths


def game_turn_dirs(game: str) -> list[Path]:
    turns_dir = game_root_for(game) / 'turns'
    if not turns_dir.exists():
        return []
    return sorted(
        [path for path in turns_dir.iterdir() if path.is_dir()],
        key=lambda path: path.name,
    )


def reason_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def merge_reasons(*groups: list[str]) -> list[str]:
    merged = []
    seen = set()
    for group in groups:
        for reason in group:
            if reason in seen:
                continue
            merged.append(reason)
            seen.add(reason)
    return merged


def record_score_and_reasons(
    label: str,
    description: str,
    automation_config: GameAutomationConfig | None = None,
    game: str | None = None,
) -> tuple[float, list[str]]:
    score, reasons = configured_item_preference_score(
        label,
        description,
        automation_config,
        game=game,
    )
    return score, reasons or ['observed detail']


def record_screenshot_for(path: Path, screenshot: str | None = None) -> str:
    if screenshot:
        screenshot_path = Path(screenshot)
        if screenshot_path.is_absolute():
            return str(screenshot_path)
        return str(path.parent / screenshot_path)
    default_screenshot = path.parent / 'screenshot.png'
    return str(default_screenshot) if default_screenshot.exists() else ''


def safe_load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def inspection_records_from_yaml(
    path: Path,
    automation_config: GameAutomationConfig | None = None,
    game: str | None = None,
) -> list[dict[str, Any]]:
    payload = safe_load_yaml_mapping(path)
    records = []
    for item in payload.get('items', []):
        candidate = item.get('candidate') or {}
        label = str(candidate.get('label') or item.get('label') or '').strip()
        label = strip_configured_skill_choice_badges(label, automation_config)
        if not label:
            continue
        description = str(item.get('description') or '').strip()
        if (
            normalize_label(game or '') == 'tower'
            and (
                normalize_label(description) == '任务'
                or is_configured_command_label(label, automation_config)
                or normalize_label(label) == '胜利'
                or re.fullmatch(r'[（(]?\d+[）)]?', label.strip())
            )
        ):
            continue
        score, fallback_reasons = record_score_and_reasons(
            label,
            description,
            automation_config,
            game=game,
        )
        try:
            score = max(float(item.get('item_score') or item.get('score')), score)
        except (TypeError, ValueError):
            pass
        kind = str(item.get('kind') or '').strip() or classify_game_info_entry(
            label,
            description,
        )
        records.append(
            {
                'label': label,
                'kind': kind,
                'description': description,
                'score': score,
                'reasons': merge_reasons(
                    reason_list(item.get('reasons')),
                    fallback_reasons,
                ),
                'source': 'item inspection',
                'turn': path.parent.name,
                'screenshot': record_screenshot_for(
                    path,
                    str(item.get('screenshot') or '').strip(),
                ),
            }
        )
    return records


def yaml_scalar_from_line(value: str) -> str:
    return value.strip().strip('"').strip("'")


def loose_llm_object_records_from_yaml(
    path: Path,
    automation_config: GameAutomationConfig | None = None,
    game: str | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, str] | None = None
    in_objects = False
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped == 'objects:':
            in_objects = True
            continue
        if stripped == 'buttons:':
            break
        if not in_objects:
            continue
        if stripped.startswith('- label:'):
            if current is not None:
                records.extend(
                    llm_records_from_items(
                        [current],
                        path,
                        source='llm object',
                        require_durable=True,
                        automation_config=automation_config,
                        game=game,
                    )
                )
            current = {'label': yaml_scalar_from_line(stripped.split(':', 1)[1])}
            continue
        if current is None or ':' not in stripped:
            continue
        key, value = stripped.split(':', 1)
        if key.strip() in {
            'description',
            'game_description',
            'original_description',
            'visible_description',
            'game_label',
            'game_name',
            'original_label',
            'original_name',
            'visible_label',
            'visible_name',
            'type',
            'kind',
            'x',
            'y',
        }:
            current[key.strip()] = yaml_scalar_from_line(value)
    if current is not None:
        records.extend(
            llm_records_from_items(
                [current],
                path,
                source='llm object',
                require_durable=True,
                automation_config=automation_config,
                game=game,
            )
        )
    return records


def contains_any_text(value: str, patterns: tuple[str, ...]) -> bool:
    text = normalize_label(value)
    return any(pattern in text for pattern in patterns)


def is_generic_game_info_label(label: str) -> bool:
    key = normalize_label(label)
    if key in GENERIC_GAME_INFO_LABELS:
        return True
    generic_words = (
        'panel',
        'button',
        'prompt',
        'navigation',
        'map',
        'arrow',
        'route',
        'avatar',
        'screen',
        'tab',
        'hint',
        'instruction',
        'choices',
        'choice',
        'tile',
        'icon',
        'detail',
        'details',
        'event',
        'reward',
        'selected',
        'learnable',
        'fusion',
        'upgrade',
        'side',
        'loot',
    )
    return any(word in key for word in generic_words)


def infer_game_info_name_from_text(label: str, description: str, summary: str) -> str:
    if label and not is_generic_game_info_label(label):
        return label
    candidates = [description, summary]
    patterns = (
        (
            r'(?:screen for|detail screen for|for|labeled|labelled|titled)\s+'
            r'([^.;:,，。]+)'
        ),
        (
            r'^([^.;:,，。]+?)\s+(?:gives|treasure detail is open|card is|'
            r'cards are|is highlighted)'
        ),
        r'^([^.;:,，。]+?):\s+',
        r'(?:奖励|标题|名为|选择)\s*([^.;:,，。]+)',
    )
    for text in candidates:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I)
            if match:
                name = match.group(1).strip(' "\'')
                if name and not is_generic_game_info_label(name):
                    return name
    return label


def is_explicit_game_info_item(item: dict[str, Any]) -> bool:
    if truthy_llm_flag(item.get('game_info')) or truthy_llm_flag(item.get('durable')):
        return True
    kind = normalize_label(
        first_text_value(
            item,
            ('type', 'kind', 'category', 'entity_type', 'game_info_type'),
        )
    )
    return kind in {
        'item',
        'skill',
        'card',
        'treasure',
        'weapon',
        'reward',
        'buff',
        'debuff',
    }


def is_likely_durable_game_info(label: str, description: str) -> bool:
    if is_generic_game_info_label(label):
        return False
    if contains_any_text(description, GAME_INFO_EFFECT_HINTS) and contains_any_text(
        description, GAME_INFO_EFFECT_ACTION_HINTS
    ):
        return True
    return False


def llm_records_from_items(
    items: list[dict[str, Any]],
    path: Path,
    *,
    source: str = 'llm game_info',
    summary: str = '',
    require_durable: bool = False,
    automation_config: GameAutomationConfig | None = None,
    game: str | None = None,
) -> list[dict[str, Any]]:
    records = []
    for item in items:
        if not isinstance(item, dict):
            continue
        label = llm_game_info_name(item)
        description = llm_description_text(item)
        if not label or not description:
            continue
        label = infer_game_info_name_from_text(label, description, summary)
        explicit = is_explicit_game_info_item(item)
        if require_durable and not explicit:
            if not has_original_description_text(item):
                continue
            if not is_likely_durable_game_info(label, description):
                continue
        score, reasons = record_score_and_reasons(
            label,
            description,
            automation_config,
            game=game,
        )
        records.append(
            {
                'label': label,
                'kind': llm_game_info_kind(item, label, description),
                'description': description,
                'score': score,
                'reasons': reasons,
                'source': source,
                'turn': path.parent.name,
                'screenshot': record_screenshot_for(path),
            }
        )
    return records


def llm_records_from_yaml(
    path: Path,
    automation_config: GameAutomationConfig | None = None,
    game: str | None = None,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = safe_load_yaml_mapping(path)
    if not payload:
        return loose_llm_object_records_from_yaml(path, automation_config, game)
    summary = str(payload.get('summary') or '').strip()
    records = llm_records_from_items(
        payload.get('game_info', []),
        path,
        source='llm game_info',
        summary=summary,
        automation_config=automation_config,
        game=game,
    )
    records.extend(
        llm_records_from_items(
            payload.get('objects', []),
            path,
            source='llm object',
            summary=summary,
            require_durable=True,
            automation_config=automation_config,
            game=game,
        )
    )
    return records


def looks_like_stat_delta_label(value: str) -> bool:
    return bool(re.search(r'^[±+\-]\s*\d+([.]\d+)?%?[;；]?$', value.strip()))


def label_text_core(value: str) -> str:
    return re.sub(r'[^0-9A-Za-z\u4e00-\u9fff+\-]', '', value)


def has_cjk_text(value: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', value))


def is_game_info_signal_label(value: str) -> bool:
    key = normalize_label(value)
    if looks_like_stat_delta_label(value):
        return True
    if has_cjk_text(value):
        return True
    if any(pattern in key for pattern in GAME_INFO_OCR_KEYWORDS):
        return True
    return len(value.split()) >= 2 and len(label_text_core(value)) >= 4


def is_useful_detail_label(value: str) -> bool:
    label = value.strip()
    if not label:
        return False
    key = normalize_label(label)
    avoid_labels = {normalize_label(item) for item in DEFAULT_AVOID}
    if key in COMMAND_LABELS or key in CONFIRM_LABELS or key in avoid_labels:
        return False
    if key in {'close blank area', 'activate treasure', 'highlighted treasure'}:
        return False
    if looks_like_stat_delta_label(label):
        return True
    if looks_like_noise_label(label):
        return False
    if len(label_text_core(label)) <= 1:
        return False
    return is_game_info_signal_label(label)


def ocr_records_from_yaml(
    path: Path,
    automation_config: GameAutomationConfig | None = None,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = safe_load_yaml_mapping(path)
    labels: list[str] = []
    seen: set[str] = set()
    for item in payload.get('ocr_buttons', []):
        label = str(item.get('label') or '').strip()
        if not is_useful_detail_label(label):
            continue
        key = normalize_label(label)
        if key in seen:
            continue
        seen.add(key)
        labels.append(label)
    if not labels:
        return []

    label = labels[0] if len(labels) == 1 else f'OCR detail: {labels[0]}'
    description = '; '.join(labels)
    score, reasons = record_score_and_reasons(
        label,
        description,
        automation_config,
    )
    return [
        {
            'label': label,
            'kind': 'observation',
            'description': description,
            'score': score,
            'reasons': reasons,
            'source': 'ocr observation',
            'turn': path.parent.name,
            'screenshot': record_screenshot_for(path),
        }
    ]


def game_info_records(
    game: str,
    additional_inspection_path: Path | None = None,
    automation_config: GameAutomationConfig | None = None,
) -> list[dict[str, Any]]:
    automation_config = automation_config or load_automation_config(game)
    records: list[dict[str, Any]] = []
    for path in item_inspection_paths(game, additional_inspection_path):
        records.extend(inspection_records_from_yaml(path, automation_config, game))
    for turn_dir in game_turn_dirs(game):
        records.extend(
            llm_records_from_yaml(turn_dir / 'llm.yaml', automation_config, game)
        )
    return records


def filter_game_info_entries_for_config(
    entries: list[GameInfoEntry],
    automation_config: GameAutomationConfig,
) -> list[GameInfoEntry]:
    ignored_labels = (
        automation_config.command_labels
        | automation_config.navigation_labels
        | automation_config.passive_non_action_labels
        | automation_config.result_progress_labels
        | automation_config.reward_overlay_labels
        | automation_config.reward_close_labels
        | automation_config.skill_choice_ignored_labels
        | automation_config.energy_empty_labels
        | frozenset(automation_config.main_screen_verification_labels)
    )
    return [
        entry
        for entry in entries
        if normalize_label(entry.kind) not in automation_config.ignored_game_info_types
        and normalize_label(entry.label) not in ignored_labels
    ]


def game_info_entries_from_records(
    records: list[dict[str, Any]],
) -> list[GameInfoEntry]:
    entries: dict[str, dict[str, Any]] = {}
    for record in records:
        key = normalize_label(record['label'])
        existing = entries.get(key)
        reasons = set(record['reasons'])
        source = str(record.get('source') or 'observation')
        if existing is None:
            entries[key] = {
                **record,
                'reasons': reasons,
                'sources': {source},
                'seen_count': 1,
                'first_seen': record['turn'],
                'last_seen': record['turn'],
                'last_screenshot': record['screenshot'],
            }
            continue

        existing['seen_count'] += 1
        existing['last_seen'] = record['turn']
        existing['last_screenshot'] = record['screenshot']
        existing['reasons'].update(reasons)
        existing['sources'].add(source)
        if record['score'] > existing['score']:
            existing['label'] = record['label']
            existing['score'] = record['score']
            existing['kind'] = record['kind']
            existing['description'] = record['description']

    return merge_low_quality_duplicate_game_info_entries(
        [
            GameInfoEntry(
                label=str(item['label']),
                kind=str(item['kind']),
                description=str(item['description']),
                score=float(item['score']),
                reasons=sorted(item['reasons']),
                sources=sorted(item['sources']),
                seen_count=int(item['seen_count']),
                first_seen=str(item['first_seen']),
                last_seen=str(item['last_seen']),
                last_screenshot=str(item['last_screenshot']),
            )
            for item in entries.values()
        ]
    )


def content_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r'[0-9A-Za-z\u4e00-\u9fff]+', normalize_label(value))
        if len(token) >= 3 or has_cjk_text(token)
    }


def game_info_label_quality(entry: GameInfoEntry) -> int:
    label_tokens = content_tokens(entry.label)
    description_tokens = content_tokens(entry.description)
    words = normalize_label(entry.label).split()
    score = min(entry.seen_count, 5)
    if len(words) >= 2:
        score += 2
    if label_tokens & description_tokens:
        score += 3
    if looks_like_noise_label(entry.label):
        score -= 4
    if len(words) == 1 and entry.label.islower() and len(entry.label) <= 6:
        score -= 2
    return score


def should_merge_duplicate_game_info_entry(
    source: GameInfoEntry,
    target: GameInfoEntry,
) -> bool:
    if source.kind != target.kind:
        return False
    if not source.description or normalize_label(source.description) != normalize_label(
        target.description
    ):
        return False
    return game_info_label_quality(target) >= game_info_label_quality(source) + 2


def merge_game_info_entry(
    target: GameInfoEntry,
    source: GameInfoEntry,
) -> GameInfoEntry:
    return GameInfoEntry(
        label=target.label,
        kind=target.kind,
        description=target.description,
        score=max(target.score, source.score),
        reasons=merge_reasons(target.reasons, source.reasons),
        sources=merge_reasons(target.sources, source.sources),
        seen_count=target.seen_count + source.seen_count,
        first_seen=min(target.first_seen, source.first_seen),
        last_seen=max(target.last_seen, source.last_seen),
        last_screenshot=(
            source.last_screenshot
            if source.last_seen > target.last_seen
            else target.last_screenshot
        ),
    )


def merge_low_quality_duplicate_game_info_entries(
    entries: list[GameInfoEntry],
) -> list[GameInfoEntry]:
    merged: list[GameInfoEntry] = []
    for entry in sort_game_info_entries(entries):
        merged_into_existing = False
        for index, existing in enumerate(merged):
            if should_merge_duplicate_game_info_entry(entry, existing):
                merged[index] = merge_game_info_entry(existing, entry)
                merged_into_existing = True
                break
            if should_merge_duplicate_game_info_entry(existing, entry):
                merged[index] = merge_game_info_entry(entry, existing)
                merged_into_existing = True
                break
        if not merged_into_existing:
            merged.append(entry)
    return merged


def sort_game_info_entries(entries: list[GameInfoEntry]) -> list[GameInfoEntry]:
    return sorted(
        entries,
        key=lambda item: (-item.score, normalize_label(item.label)),
    )


def group_game_info_entries_by_type(
    entries: list[GameInfoEntry],
) -> dict[str, list[GameInfoEntry]]:
    grouped: dict[str, list[GameInfoEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.kind, []).append(entry)
    return {
        kind: sort_game_info_entries(group)
        for kind, group in sorted(grouped.items(), key=lambda item: item[0])
    }


def write_game_info_markdown(
    game: str,
    *,
    additional_inspection_path: Path | None = None,
) -> Path:
    path = game_info_path_for(game)
    manual_observations = ''
    if path.exists():
        existing_text = path.read_text()
        manual_match = re.search(
            r'(?ms)^## Manual Observations\n.*?(?=^## |\Z)',
            existing_text,
        )
        if manual_match:
            manual_observations = manual_match.group(0).rstrip()
    automation_config = load_automation_config(game)
    entries = filter_game_info_entries_for_config(
        sort_game_info_entries(
            game_info_entries_from_records(
                game_info_records(game, additional_inspection_path, automation_config)
            )
        ),
        automation_config,
    )
    grouped_entries = group_game_info_entries_by_type(entries)
    lines = [
        f'# Game Info: {game}',
        '',
        'This file stores durable descriptions captured from item inspections, '
        'explicit LLM game info, and durable LLM object captures. Ranking uses '
        'the same preference score as auto-play item selection when enough text '
        'is known. Entries are grouped by type and sorted by score descending '
        'within each type.',
        '',
    ]
    if manual_observations:
        lines.extend([manual_observations, '', '## Ranking', ''])
    else:
        lines.extend(['## Ranking', ''])
    if entries:
        for kind, group in grouped_entries.items():
            lines.extend([f'### {kind}', ''])
            lines.append(
                '| Rank | Name | Score | Seen | Sources | Cues | '
                'Description | Last Seen |'
            )
            lines.append('| ---: | --- | ---: | ---: | --- | --- | --- | --- |')
            for rank, entry in enumerate(group, start=1):
                cues = ', '.join(entry.reasons) if entry.reasons else 'no strong cue'
                sources = ', '.join(entry.sources)
                lines.append(
                    '| '
                    + ' | '.join(
                        [
                            str(rank),
                            markdown_escape(entry.label),
                            f'{entry.score:.2f}',
                            str(entry.seen_count),
                            markdown_escape(sources),
                            markdown_escape(cues),
                            markdown_escape(
                                entry.description or 'description not captured'
                            ),
                            markdown_escape(entry.last_seen),
                        ]
                    )
                    + ' |'
                )
            lines.append('')
    else:
        lines.append('No captured skill or item descriptions yet.')

    lines.extend(['', '## Captured Descriptions', ''])
    for kind, group in grouped_entries.items():
        lines.extend([f'### {kind}', ''])
        for rank, entry in enumerate(group, start=1):
            cues = ', '.join(entry.reasons) if entry.reasons else 'no strong cue'
            lines.extend(
                [
                    f'#### {rank}. {entry.label}',
                    f'- Type: {entry.kind}',
                    f'- Rank score: {entry.score:.2f}',
                    f'- Seen count: {entry.seen_count}',
                    f'- Sources: {", ".join(entry.sources)}',
                    f'- First seen: {entry.first_seen}',
                    f'- Last seen: {entry.last_seen}',
                    f'- Cues: {cues}',
                    f'- Description: {entry.description or "description not captured"}',
                ]
            )
            if entry.last_screenshot:
                lines.append(f'- Last screenshot: {entry.last_screenshot}')
            lines.append('')
    if not entries:
        lines.append('')

    path.write_text('\n'.join(lines).rstrip() + '\n')
    return path


def verification_to_data(verification: StateVerification) -> dict[str, Any]:
    data = {
        'status': verification.status,
        'reason': verification.reason,
        'attempts': verification.attempts,
        'similarity_threshold': round(verification.threshold, 6),
        'similarities': [
            round(similarity, 6) for similarity in verification.similarities
        ],
        'progress_similarity_threshold': round(
            verification.progress_threshold,
            6,
        ),
        'progress_region': verification.progress_region,
        'progress_similarities': [
            round(similarity, 6) for similarity in verification.progress_similarities
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
    item_inspections: list[ItemInspection] | None = None,
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
            'game_info_path': str(game_info_path_for(game)),
        },
        'ocr_buttons': [button_to_data(button) for button in ocr_buttons],
        'template_buttons': [button_to_data(button) for button in template_buttons],
        'llm_buttons': [button_to_data(button) for button in llm_buttons],
        'learned_templates': learned_templates,
        'item_inspections': [
            item_inspection_to_data(item) for item in item_inspections or []
        ],
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
    automation_config: GameAutomationConfig | None = None,
) -> str | None:
    if clicked is None or verification is None:
        return None
    if clicked.source == 'wait':
        return None
    if not verification.strategy_updated:
        return None
    if is_navigation_arrow_label(clicked.label, automation_config):
        return (
            'Updated route strategy from no-change evidence: prefer brighter '
            'routes or concrete room icons before retrying the same arrow.'
        )
    return (
        f'Updated strategy from repeated no-change evidence for {clicked.label}; '
        'prefer another visible progression action before retrying it.'
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
    item_inspections: list[ItemInspection],
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
            'ocr_overlay': artifact_paths['ocr_overlay'].name,
            'llm_overlay': artifact_paths['llm_overlay'].name
            if artifact_paths['llm_overlay'].exists()
            else None,
            'ocr': artifact_paths['ocr'].name,
            'llm': artifact_paths['llm'].name
            if artifact_paths['llm'].exists()
            else None,
            'last_screenshot_after_action': last_screenshot,
            'template_images_dir': str(template_images_dir_for(game)),
            'game_info': str(game_info_path_for(game)),
            'item_inspections': artifact_paths['item_inspections'].name
            if artifact_paths['item_inspections'].exists()
            else None,
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
                clicked,
                verification,
                load_automation_config(game),
            ),
            'templates_learned': learned_templates,
            'item_inspections': [
                item_inspection_to_data(item) for item in item_inspections
            ],
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
    automation_config: GameAutomationConfig | None = None,
    recent_actions: list[str] | None = None,
    recent_successful_actions: list[str] | None = None,
) -> list[ButtonCandidate]:
    preferred = {normalize_label(item) for item in memory['preferred']}
    avoid = {normalize_label(item) for item in memory['avoid']}
    ineffective = {normalize_label(item) for item in memory['ineffective']}
    non_end_buttons = [
        button for button in buttons if not is_end_turn_label(button.label)
    ]
    navigation_arrow_count = sum(
        1
        for button in buttons
        if button.source != 'ocr'
        and is_navigation_arrow_label(button.label, automation_config)
    )
    navigation_arrow_visible = navigation_arrow_count > 0
    recent_action_keys = {
        normalize_label(label) for label in (recent_actions or []) if label
    }
    latest_action_key = normalize_label((recent_actions or [''])[-1])
    successful_actions = (
        recent_successful_actions
        if recent_successful_actions is not None
        else recent_actions
    )
    latest_successful_action_key = normalize_label(
        (successful_actions or [''])[-1]
    )
    tower_last_named_room_key = ''
    tower_last_room_position: list[Any] = []
    tower_awaiting_route_after_reward = False
    tower_run_state: dict[str, Any] = {}
    tower_completed_shop_labels: set[str] = set()
    tower_shield_built_this_turn = False
    if (
        automation_config is not None
        and normalize_label(automation_config.game) == 'tower'
    ):
        tower_run_state = load_tower_run_state(automation_config.game)
        last_room_action = normalize_label(
            str(tower_run_state.get('last_room_action') or '')
        )
        if tower_deep_map_room_bonus(last_room_action) != 0:
            tower_last_named_room_key = last_room_action
        tower_last_room_position = tower_run_state.get('last_room_position') or []
        tower_awaiting_route_after_reward = bool(
            tower_run_state.get('awaiting_route_after_reward')
        )
        tower_battle = tower_run_state.get('battle')
        if isinstance(tower_battle, dict):
            tower_shield_built_this_turn = bool(
                tower_battle.get('shield_built_this_turn')
            )
        current_floor_prefix = f'{int(tower_run_state.get("floor") or 0)}:'
        tower_completed_shop_labels = {
            normalize_label(str(value).removeprefix(current_floor_prefix))
            for value in tower_run_state.get('completed_shop_keys') or []
            if str(value).startswith(current_floor_prefix)
        }
    selected_tower_shop_item_bonus = (
        tower_shop_purchase_bonus(automation_config.game, latest_action_key)
        if automation_config is not None
        and normalize_label(automation_config.game) == 'tower'
        else 0.0
    )
    tower_completed_room_visible = any(
        (
            normalize_label(button.label) in recent_action_keys
            or normalize_label(button.label) == tower_last_named_room_key
            or (
                len(tower_last_room_position) == 2
                and is_tower_room_vision_candidate(button)
                and normalize_label(button.label)
                != 'visible next-floor stair room'
                and (
                    abs(button.x - float(tower_last_room_position[0]))
                    + abs(button.y - float(tower_last_room_position[1]))
                )
                < 0.10
            )
        )
        and button.source != 'template'
        and not is_configured_command_label(button.label, automation_config)
        for button in buttons
    )
    tower_recent_room_visible = (
        automation_config is not None
        and normalize_label(automation_config.game) == 'tower'
        and (navigation_arrow_visible or tower_awaiting_route_after_reward)
        and tower_completed_room_visible
    )
    center_navigation_visible = any(
        button.source != 'ocr'
        and is_navigation_arrow_label(button.label, automation_config)
        and 0.35 <= button.x <= 0.65
        and 0.56 <= button.y <= 0.70
        for button in buttons
    )
    bottom_center_down_navigation_visible = not center_navigation_visible and any(
        button.source != 'ocr'
        and is_navigation_arrow_label(button.label, automation_config)
        and navigation_direction(button.label) == 'down'
        and 0.35 <= button.x <= 0.65
        and button.y >= 0.84
        for button in buttons
    )
    end_visible = any(is_end_turn_label(button.label) for button in buttons)
    combat_card_count = sum(
        1
        for button in non_end_buttons
        if is_tower_playable_combat_card_candidate(button, automation_config)
    )
    tower_playable_card_slot_count = tower_playable_combat_card_slot_count(
        non_end_buttons,
        automation_config,
    )
    tower_only_manufacture_core_cards_visible = bool(
        tower_playable_card_slot_count
        and not any(
            is_tower_playable_combat_card_candidate(button, automation_config)
            and '制造核心' not in normalize_label(button.label)
            for button in non_end_buttons
        )
    )
    tower_shield_builder_labels = ('举盾', '守势', '胜势', '启动防守')
    tower_basic_shield_visible = any(
        is_tower_playable_combat_card_candidate(button, automation_config)
        and any(
            label in normalize_label(button.label)
            for label in tower_shield_builder_labels
        )
        for button in non_end_buttons
    )
    tower_shield_multiplier_visible = any(
        is_tower_playable_combat_card_candidate(button, automation_config)
        and '防具加固' in normalize_label(button.label)
        for button in non_end_buttons
    )
    tower_recent_shield_builder = any(
        label in latest_successful_action_key
        for label in tower_shield_builder_labels
    )
    playable_combat_card_visible = combat_card_count > 0
    direct_attack_combat_card_visible = end_visible and any(
        is_tower_playable_combat_card_candidate(button, automation_config)
        and is_direct_attack_combat_card_label(button.label)
        for button in non_end_buttons
    )
    ad_revive_context = is_ad_revive_context(buttons)
    tower_button_keys = {normalize_label(button.label) for button in buttons}
    tower_visible_labels = tuple(
        button.label for button in buttons if button.source != 'template'
    )
    tower_battle_state = tower_run_state.get('battle') or {}
    tower_sacred_finisher_ready = bool(
        isinstance(tower_battle_state, dict)
        and tower_battle_state.get('enemy_sacred_finisher_range')
        and not tower_battle_state.get('player_hp_critical')
        and any(
            '神圣斩击' in normalize_label(str(card))
            for card in tower_run_state.get('core_cards') or []
        )
    )
    tower_sacred_finisher_can_wait = bool(
        tower_sacred_finisher_ready
        and int(tower_battle_state.get('sacred_finisher_waits') or 0) < 1
    )
    tower_playable_sacred_finisher_visible = any(
        button.source == 'vision'
        and normalize_label(button.label).startswith('visible playable card')
        and '神圣斩击' in normalize_label(button.label)
        for button in buttons
    )
    tower_predecessor_context_visible = bool(
        tower_run_state.get('awaiting_predecessor_treasure')
    ) or any(
        button.source != 'template'
        and '前辈' in normalize_label(button.label)
        and '宝物' in normalize_label(button.label)
        for button in buttons
    )
    tower_discard_finisher_may_be_unnamed = bool(
        automation_config is not None
        and tower_run_has_discard_all_finisher(automation_config.game)
        and not any(
            any(name in key for name in {'正念', '重整旗鼓', '逃生'})
            for key in tower_button_keys
        )
    )
    tower_prebattle_visible = any(
        '即将发起战斗' in key for key in tower_button_keys
    )
    tower_map_context_visible = not end_visible and not tower_prebattle_visible and (
        navigation_arrow_visible
        or bool(tower_button_keys & {'当前所在层数', '全服最高层数'})
        or any(key.startswith('当前层数') for key in tower_button_keys)
    )
    tower_completed_shop_buttons = [
        button
        for button in buttons
        if button.source != 'template'
        and normalize_label(button.label) in tower_completed_shop_labels
    ]
    tower_card_pickup_visible = (
        automation_config is not None
        and normalize_label(automation_config.game) == 'tower'
        and '拾取卡牌' in tower_button_keys
        and bool(tower_button_keys & CONFIRM_LABELS)
    )
    tower_shop_visible = (
        automation_config is not None
        and normalize_label(automation_config.game) == 'tower'
        and (
            '卡牌变化' in tower_button_keys
            or (
                bool(
                    tower_button_keys
                    & (TOWER_PURCHASABLE_SHOP_LABELS | {'变化法阵', '魔术商店'})
                )
                and any(
                    normalize_label(button.label) in PLAIN_BACK_LABELS
                    and button.source != 'template'
                    for button in buttons
                )
            )
        )
    )
    tower_failed_shop_items: set[str] = set()
    if tower_shop_visible and recent_actions:
        action_keys = [normalize_label(label) for label in recent_actions]
        shop_keys = TOWER_PURCHASABLE_SHOP_LABELS
        shop_start = max(
            (index for index, key in enumerate(action_keys) if key in shop_keys),
            default=-1,
        )
        shop_actions = action_keys[shop_start + 1 :]
        tower_failed_shop_items = {
            item
            for item, confirmation in zip(shop_actions, shop_actions[1:])
            if confirmation in CONFIRM_LABELS
            and tower_shop_purchase_bonus(automation_config.game, item) > 0
        }
    tower_card_change_visible = '卡牌变化' in tower_button_keys
    tower_recent_cull_selected = bool(
        automation_config is not None
        and normalize_label(automation_config.game) == 'tower'
        and any(
            tower_card_cull_bonus(automation_config.game, label) > 0
            for label in (recent_actions or [])[-2:]
        )
    )
    tower_card_forgetting_visible = (
        bool(tower_button_keys & {'卡牌遗忘', '遗忘法阵', '遗忘卡牌'})
        and bool(tower_button_keys & PLAIN_BACK_LABELS)
    ) or (
        '遗忘' in tower_button_keys
        and tower_recent_cull_selected
        and bool(tower_button_keys & PLAIN_BACK_LABELS)
    )
    tower_magic_shop_visible = (
        '魔术商店' in tower_button_keys and '变化法阵' in tower_button_keys
    )
    tower_free_magic_array_selected = (
        tower_magic_shop_visible
        and '免费1次' in tower_button_keys
        and sum(
            normalize_label(candidate.label) == '变化法阵'
            for candidate in buttons
        ) >= 4
    )
    tower_card_change_cull_visible = bool(
        automation_config is not None
        and
        tower_card_change_visible
        and any(
            tower_card_cull_bonus(
                automation_config.game,
                candidate.label,
                visible_labels=tower_visible_labels,
            ) > 0
            for candidate in buttons
        )
    )
    tower_recent_change_selected = bool(
        automation_config is not None
        and normalize_label(automation_config.game) == 'tower'
        and any(
            tower_card_cull_bonus(automation_config.game, label) > 0
            for label in (recent_actions or [])[-2:]
        )
    )
    tower_recent_change_completed = any(
        normalize_label(label) in {'变化', '确定', 'confirm'}
        for label in (recent_actions or [])[-3:]
    )
    tower_talking_stairs_visible = (
        automation_config is not None
        and normalize_label(automation_config.game) == 'tower'
        and '说话的楼梯' in tower_button_keys
    )
    tower_mysterious_trade_visible = (
        automation_config is not None
        and normalize_label(automation_config.game) == 'tower'
        and '神秘交易' in tower_button_keys
        and any('财运' in key for key in tower_button_keys)
    )
    tower_life_beggar_visible = (
        automation_config is not None
        and normalize_label(automation_config.game) == 'tower'
        and any(key in {'生命乞丐', '生命之丐'} for key in tower_button_keys)
    )
    tower_sold_out_shop_visible = (
        automation_config is not None
        and normalize_label(automation_config.game) == 'tower'
        and '商品已售馨' in tower_button_keys
        and bool(tower_button_keys & PLAIN_BACK_LABELS)
    )
    tower_selected_choice_modal_visible = (
        automation_config is not None
        and normalize_label(automation_config.game) == 'tower'
        and not tower_shop_visible
        and not ad_revive_context
        and not end_visible
        and any(
            normalize_label(button.label) in CONFIRM_LABELS and button.y >= 0.6
            for button in buttons
        )
        and any(
            normalize_label(button.label) in PLAIN_BACK_LABELS and button.y >= 0.6
            for button in buttons
        )
        and not any(
            normalize_label(button.label) in HARD_AVOID_LABELS for button in buttons
        )
    )
    energy_empty_visible = configured_energy_empty_visible(
        automation_config,
        buttons,
    )
    energy_empty_action_exemption_visible = (
        configured_energy_empty_action_exemption_visible(
            automation_config,
            buttons,
        )
    )
    assist_pack_popup_visible = configured_assist_pack_popup_visible(buttons)
    shop_screen_visible = (
        configured_shop_screen_visible(automation_config, buttons)
        if automation_config is not None
        else False
    )
    safe_confirm_visible = configured_safe_confirm_visible(
        automation_config,
        buttons,
    )
    weekly_goodies_visible = weekly_goodies_popup_visible(buttons)
    shop_escape_label = (
        normalize_label(automation_config.shop_escape_candidate.label)
        if automation_config is not None
        and automation_config.shop_escape_candidate is not None
        else ''
    )
    challenge_detail_visible = (
        configured_challenge_detail_visible(automation_config, buttons)
        if automation_config is not None
        else False
    )
    challenge_detail_action_labels = (
        set(automation_config.challenge_detail_action_labels)
        if automation_config is not None
        else set()
    )
    result_progress_visible = (
        configured_result_progress_visible(automation_config, buttons)
        if automation_config is not None
        else False
    )
    reward_close_visible = (
        configured_reward_close_visible(automation_config, buttons)
        if automation_config is not None
        else False
    )
    result_confirm_visible = any(
        normalize_label(button.label) in CONFIRM_LABELS
        for button in buttons
        if button.source != 'template'
    )
    result_progress_labels = (
        set(automation_config.result_progress_labels)
        if automation_config is not None
        else set()
    )
    main_challenge_grid_labels = {
        normalize_label(button.label)
        for button in buttons
        if button.source != 'template'
    }
    main_challenge_grid_visible = (
        automation_config is not None
        and automation_config.target_level is not None
        and 'back to top' in main_challenge_grid_labels
        and (
            configured_level_grid_visible(automation_config, buttons)
            or configured_claimed_visible(automation_config, buttons)
        )
    )
    main_challenge_next = (
        main_challenge_next_level(automation_config)
        if main_challenge_grid_visible and automation_config is not None
        else None
    )
    defeat_recovery_labels = set(DEFEAT_RECOVERY_LABELS)
    current_room_labels = set(CURRENT_ROOM_ICON_LABELS)
    energy_empty_destination_labels: set[str] = set()
    if automation_config is not None:
        defeat_recovery_labels |= set(automation_config.defeat_recovery_labels)
        current_room_labels |= set(automation_config.current_room_icon_labels)
        energy_empty_destination_labels = set(
            automation_config.energy_empty_destination_labels
        )
    defeat_context = is_defeat_context(buttons, defeat_recovery_labels)
    fast_challenge_action_visible = challenge_detail_visible and any(
        normalize_label(candidate.label) in CHALLENGE_DETAIL_FAST_ACTION_KEYS
        for candidate in buttons
        if candidate.source != 'template'
    )
    scored = []
    for button in buttons:
        key = normalize_label(button.label)
        reason = button.reason
        is_defeat_recovery = key in defeat_recovery_labels
        score = button.confidence + (0.4 * button.clickability)
        if key == normalize_label(TOWER_SHOP_SPARKLE_LABEL):
            score += 80.0
            reason = (
                f'{reason} Claim the free shop sparkle before every purchase, '
                'refresh, or exit.'
            ).strip()
        score += tower_trainer_task_bonus(button, buttons, automation_config)
        score += tower_card_upgrade_bonus(button, buttons, automation_config)
        if tower_talking_stairs_visible:
            if '深渊龙血' in key:
                score += 10.0
            elif button.source == 'template':
                score -= 5.0
        if tower_mysterious_trade_visible:
            if key == '我再想想':
                score += 12.0
            elif '财运' in key or button.source == 'template':
                score -= 8.0
        if tower_life_beggar_visible:
            if key == '离开':
                score += 12.0
            elif '生命' in key or button.source == 'template':
                score -= 8.0
        if (
            key == '拿走前辈的宝物'
            and button.source == 'template'
            and not tower_predecessor_context_visible
        ):
            score -= 20.0
        if tower_sold_out_shop_visible:
            if key in PLAIN_BACK_LABELS:
                score += 10.0
                reason = f'{reason} Leave the sold-out Tower shop.'.strip()
            else:
                score -= 6.0
        if tower_card_pickup_visible:
            if key in CONFIRM_LABELS:
                score += 12.0
                reason = f'{reason} Confirm the currently selected card.'.strip()
            elif is_configured_combat_card_label(button.label, automation_config):
                score -= 6.0
        if tower_recent_room_visible:
            if is_navigation_arrow_label(button.label, automation_config):
                score += 2.0
                reason = f'{reason} Leave recently completed Tower room.'.strip()
            elif (
                (
                    key in recent_action_keys
                    or key == tower_last_named_room_key
                )
                and not is_configured_command_label(button.label, automation_config)
            ):
                score -= 8.0
                reason = f'{reason} Leave recently completed Tower room.'.strip()
            if (
                len(tower_last_room_position) == 2
                and normalize_label(button.label)
                != 'visible next-floor stair room'
                and not is_tower_next_floor_action(button.label)
                and (
                    abs(button.x - float(tower_last_room_position[0]))
                    + abs(button.y - float(tower_last_room_position[1]))
                )
                < 0.10
            ):
                score -= 8.0
            elif (
                tower_awaiting_route_after_reward
                and not navigation_arrow_visible
                and is_tower_room_vision_candidate(button)
            ):
                score += 3.0
                reason = f'{reason} Enter a new Tower room after reward.'.strip()
        if key in preferred and not (is_defeat_recovery and not defeat_context):
            score += 1.0
        if (
            button.source != 'template'
            and button.y <= 0.46
            and configured_always_preferred_choice_match(
                button.label,
                button.reason,
                automation_config,
            )
        ):
            score += 4.0
        if energy_empty_visible:
            if key in energy_empty_destination_labels:
                score += 2.25
            if (
                key in CHALLENGE_DETAIL_ACTION_KEYS
                and not energy_empty_action_exemption_visible
            ):
                score -= 3.0
        if (
            energy_empty_action_exemption_visible
            and key in CHALLENGE_DETAIL_ACTION_KEYS
        ):
            score += 3.0
        if assist_pack_popup_visible:
            dismiss_ineffective = 'dismiss assist pack popup' in ineffective
            if key == 'dismiss assist pack popup' and not dismiss_ineffective:
                score += 5.0
            elif key == 'dismiss assist pack popup':
                score -= 4.0
            elif key == 'view' and dismiss_ineffective:
                score += 4.0
            elif key in (CHALLENGE_DETAIL_ACTION_KEYS | {'view'}):
                score -= 5.0
        if shop_screen_visible and key == shop_escape_label:
            score += 4.0
        if tower_shop_visible:
            tower_purchase_bonus = tower_shop_purchase_bonus(
                automation_config.game,
                button.label,
            )
            tower_cull_bonus = tower_card_cull_bonus(
                automation_config.game,
                button.label,
                visible_labels=tower_visible_labels,
            )
            if tower_card_change_visible:
                if tower_cull_bonus > 0 and not tower_recent_change_selected:
                    score += 18.0 + tower_cull_bonus
                    reason = (
                        f'{reason} Transform a non-core card to improve the '
                        'short-cycle Tower deck.'
                    ).strip()
                elif key == '变化' and tower_recent_change_selected:
                    score += 24.0
                    reason = f'{reason} Confirm the selected junk-card change.'.strip()
                elif key in CONFIRM_LABELS and tower_recent_change_completed:
                    score += 20.0
                elif key == '放弃':
                    score += 12.0 if not tower_card_change_cull_visible else -10.0
                elif key in PLAIN_BACK_LABELS:
                    score += 8.0 if not tower_card_change_cull_visible else -10.0
                else:
                    score -= 5.0
            elif tower_magic_shop_visible:
                if key in CONFIRM_LABELS and tower_free_magic_array_selected:
                    score += 18.0
                    reason = (
                        f'{reason} Confirm the default-selected free change array.'
                    ).strip()
                elif (
                    key == '变化法阵'
                    and not tower_recent_change_completed
                    and latest_action_key != '变化法阵'
                ):
                    score += 12.0 - (2.0 * button.y) - button.x
                    reason = (
                        f'{reason} Use the cheapest visible card-change array '
                        'to replace a non-core card.'
                    ).strip()
                elif key in PLAIN_BACK_LABELS and tower_recent_change_completed:
                    score += 14.0
                elif key in PLAIN_BACK_LABELS:
                    score += 6.0
                else:
                    score -= 5.0
            elif key == '放弃':
                score += 10.0
            elif key in CONFIRM_LABELS and latest_action_key == '马上融合':
                score += 14.0
                reason = f'{reason} Tower shop fusion confirmation.'.strip()
            elif key in CONFIRM_LABELS and selected_tower_shop_item_bonus > 0:
                score += 40.0
                reason = (
                    f'{reason} Confirm the selected in-run gold or crystal '
                    'purchase because it directly strengthens the current build.'
                ).strip()
            elif key in PLAIN_BACK_LABELS:
                score += 6.0
            elif tower_purchase_bonus > 0:
                if key in tower_failed_shop_items:
                    score -= 40.0
                    reason = (
                        f'{reason} The previous confirmation left this shop '
                        'unchanged, so treat this item as unaffordable.'
                    ).strip()
                elif key == latest_action_key:
                    score -= 5.0
                else:
                    score += tower_purchase_bonus
                    reason = (
                        f'{reason} Spend in-run gold or crystals on a card, '
                        'treasure, or consumable with direct build synergy.'
                    ).strip()
            else:
                score -= 5.0
        if tower_card_forgetting_visible:
            tower_cull_bonus = tower_card_cull_bonus(
                automation_config.game,
                button.label,
                visible_labels=tower_visible_labels,
            )
            if tower_cull_bonus > 0 and not tower_recent_cull_selected:
                score += 22.0 + tower_cull_bonus
                reason = (
                    f'{reason} Forget a known non-core card to tighten the '
                    'Traveler cycle.'
                ).strip()
            elif key == '遗忘' and tower_recent_cull_selected:
                score += 28.0
                reason = f'{reason} Confirm forgetting the selected junk card.'.strip()
            elif key in ({'放弃'} | PLAIN_BACK_LABELS):
                score += 10.0 if not tower_recent_cull_selected else -10.0
            elif key not in {'卡牌遗忘', '遗忘法阵', '遗忘卡牌'}:
                score -= 5.0
        if (
            end_visible
            and button.source == 'ocr'
            and button.y < 0.45
            and not is_configured_command_label(button.label, automation_config)
            and key not in CONFIRM_LABELS
        ):
            score -= 8.0
            reason = f'{reason} Ignore upper-screen combat text.'.strip()
        if (
            end_visible
            and automation_config is not None
            and normalize_label(automation_config.game) == 'tower'
            and key in TOWER_COMBAT_METADATA_LABELS
        ):
            score -= 8.0
            reason = f'{reason} Ignore the card-type metadata label.'.strip()
        if safe_confirm_visible:
            if button.source == 'template':
                score -= 5.0
            elif key in CONFIRM_LABELS:
                score += 4.0
            else:
                score -= 1.0
        if weekly_goodies_visible:
            if key == 'claim':
                score += 5.0
            elif key in CHALLENGE_DETAIL_ACTION_KEYS:
                score -= 5.0
        if (
            challenge_detail_visible
            and button.source != 'template'
            and key in challenge_detail_action_labels
        ):
            if button.y >= 0.93:
                score -= 2.5
            else:
                score += 2.5
                if key in CHALLENGE_DETAIL_FAST_ACTION_KEYS:
                    score += 3.0
                elif key == 'start' and fast_challenge_action_visible:
                    score -= 2.0
        if result_progress_visible and result_confirm_visible:
            if key in CONFIRM_LABELS:
                score += 5.0
            elif key in result_progress_labels:
                score -= 2.0
            if button.source == 'template':
                score -= 5.0
        if reward_close_visible:
            if configured_reward_close_label_match(button.label, automation_config):
                score += 4.0
            elif button.source == 'template':
                score -= 3.0
        if (
            main_challenge_grid_visible
            and not challenge_detail_visible
            and not result_progress_visible
            and not reward_close_visible
        ):
            if key == 'back to top' and main_challenge_next is not None:
                score -= 6.0
            if button.source in {'ocr', 'llm'} and configured_level_row_label(
                automation_config,
                button.label,
            ):
                score -= 3.0
        prefer_watch_ads = bool(
            automation_config is not None and automation_config.prefer_watch_ads
        )
        if key in avoid and not (ad_revive_context and key in CANCEL_LABELS):
            score -= 1.25
        if ad_revive_context and prefer_watch_ads and is_watch_ad_button(button):
            score += 4.0
        elif ad_revive_context and prefer_watch_ads and key in CANCEL_LABELS:
            score -= 4.0
        elif ad_revive_context and key in CANCEL_LABELS:
            score += 4.0
        elif ad_revive_context and is_watch_ad_button(button):
            score -= 4.0
        elif ad_revive_context:
            score -= 2.5
        if tower_selected_choice_modal_visible:
            if key in CONFIRM_LABELS:
                score += 1.1
            elif key in PLAIN_BACK_LABELS:
                score -= 1.1
        if is_defeat_recovery and defeat_context:
            score += 2.5
        elif is_defeat_recovery:
            score -= 3.0
        if any(keyword in key for keyword in NEVER_SELL_LABEL_KEYWORDS):
            score -= 100.0
        if (
            automation_config is not None
            and normalize_label(automation_config.game) == 'tower'
            and key == '马上融合'
            and (
                not tower_shop_visible
                or latest_action_key not in {'马上融合', '确定', 'confirm'}
            )
        ):
            score += 15.0
            if tower_shop_visible:
                reason = f'{reason} Tower shop fusion selection.'.strip()
        if (
            automation_config is not None
            and normalize_label(automation_config.game) == 'tower'
            and not tower_shop_visible
        ):
            if key == '拿走前辈的宝物':
                score += 4.0
            elif key == '前辈的宝物' and any(
                normalize_label(candidate.label) == '拿走前辈的宝物'
                for candidate in buttons
            ):
                score -= 2.0
            tower_shop_route_penalties = {
                '魔术商店': 2.0,
                '金币商店': 2.0,
                '钱袋商店': 2.0,
                '水晶商店': 1.0,
                '神秘商店': 0.5,
                '神桃商店': 0.5,
                '变化法阵': 1.0,
            }
            if not tower_map_context_visible:
                score -= tower_shop_route_penalties.get(key, 0.0)
            if tower_map_context_visible:
                score += tower_deep_map_room_bonus(button.label)
                if (
                    isinstance(tower_battle_state, dict)
                    and tower_battle_state.get('player_hp_critical')
                    and key == '休息点'
                ):
                    score += 12.0
                    reason = (
                        f'{reason} Recover before optional deck or economy '
                        'rooms while current health is critical.'
                    ).strip()
                if is_tower_status_fraction_label(button.label):
                    score -= 8.0
                near_completed_shop = any(
                    (
                        (button.x - completed.x) ** 2
                        + (button.y - completed.y) ** 2
                    )
                    < 0.15**2
                    for completed in tower_completed_shop_buttons
                )
                if key in tower_completed_shop_labels:
                    score -= 20.0
                    reason = (
                        f'{reason} This Tower shop is already complete on the '
                        'current floor.'
                    ).strip()
                elif near_completed_shop and (
                    is_navigation_arrow_label(button.label, automation_config)
                    or is_tower_room_vision_candidate(button)
                ):
                    score -= 20.0
                    reason = (
                        f'{reason} This entrance is attached to a completed '
                        'Tower shop.'
                    ).strip()
        if key in current_room_labels and navigation_arrow_visible and not end_visible:
            score -= 1.75
        if (
            center_navigation_visible
            and not end_visible
            and is_tower_room_vision_candidate(button)
            and button.bbox is None
        ):
            score -= 2.5
        if (
            bottom_center_down_navigation_visible
            and not end_visible
            and is_tower_room_vision_candidate(button)
        ):
            score -= 1.0
        if is_tower_combat_card_candidate(button, automation_config):
            score += 0.8
            if end_visible and not is_tower_playable_combat_card_candidate(
                button,
                automation_config,
            ):
                score -= 8.0
                reason = f'{reason} Ignore disabled combat card.'.strip()
            if (
                automation_config is not None
                and end_visible
                and combat_card_count > 1
            ):
                score += tower_combat_sequence_bonus(
                    automation_config.game,
                    button.label,
                )
            if (
                end_visible
                and combat_card_count > 1
                and is_tower_timing_sensitive_finisher_label(button.label)
            ):
                score -= 2.0 if '慈悲' in key else 4.0
            if (
                end_visible
                and combat_card_count > 1
                and key == 'visible playable card'
                and tower_discard_finisher_may_be_unnamed
            ):
                score -= 3.0
            if end_visible and is_direct_attack_combat_card_label(button.label):
                score += 1.35
            elif (
                direct_attack_combat_card_visible
                and is_defensive_or_setup_combat_card_label(button.label)
            ):
                score -= 1.0
            if tower_only_manufacture_core_cards_visible and '制造核心' in key:
                score += 14.0
                reason = (
                    f'{reason} Use remaining all-mana cores only after every '
                    'other playable card has resolved.'
                ).strip()
            if tower_shield_multiplier_visible:
                is_shield_builder = any(
                    label in key for label in tower_shield_builder_labels
                )
                if tower_basic_shield_visible and is_shield_builder:
                    score += 8.0
                    reason = (
                        f'{reason} Build shield before doubling it.'
                    ).strip()
                elif '防具加固' in key:
                    if tower_basic_shield_visible:
                        score -= 12.0
                    elif (
                        tower_recent_shield_builder
                        or tower_shield_built_this_turn
                    ):
                        score += 8.0
                        reason = (
                            f'{reason} Double shield created by a verified card '
                            'play in the current turn.'
                        ).strip()
                    else:
                        score -= 12.0
                        reason = (
                            f'{reason} Preserve 防具加固 until a shield '
                            'builder succeeds.'
                        ).strip()
            if (
                button.source == 'template'
                and navigation_arrow_visible
                and not end_visible
                and combat_card_count < 3
            ):
                score -= 2.75
        if tower_sacred_finisher_ready and end_visible:
            if (
                tower_playable_sacred_finisher_visible
                and '神圣斩击' in key
            ):
                score += 30.0
                reason = f'{reason} Use 神圣斩击 in its kill range.'.strip()
            elif (
                not tower_playable_sacred_finisher_visible
                and tower_sacred_finisher_can_wait
                and is_end_turn_label(button.label)
            ):
                score += 20.0
                reason = (
                    f'{reason} Enemy is in 神圣斩击 range; wait one turn '
                    'for mana or draw.'
                ).strip()
            elif (
                tower_playable_sacred_finisher_visible
                or tower_sacred_finisher_can_wait
            ) and is_tower_combat_card_candidate(button, automation_config):
                score -= 12.0
        if key in HARD_AVOID_LABELS:
            score -= 3.0
        if key in ineffective and not is_configured_combat_card_label(
            button.label,
            automation_config,
        ):
            score -= 1.75
        if navigation_arrow_count >= 2 and is_navigation_arrow_label(
            button.label,
            automation_config,
        ):
            score += 1.2 * button.clickability
            direction = navigation_direction(button.label)
            if (
                bottom_center_down_navigation_visible
                and direction == 'down'
                and 0.35 <= button.x <= 0.65
                and button.y >= 0.84
            ):
                score += 0.85
            elif (
                bottom_center_down_navigation_visible
                and direction in {'left', 'right'}
                and (button.x <= 0.16 or button.x >= 0.84)
            ):
                score -= 0.85
        if is_end_turn_label(button.label) and playable_combat_card_visible:
            score -= 1.5
        if is_end_turn_label(button.label) and not non_end_buttons:
            score = max(score, 1.05)
        scored.append(
            ButtonCandidate(
                label=button.label,
                x=button.x,
                y=button.y,
                confidence=button.confidence,
                clickability=button.clickability,
                source=button.source,
                reason=reason,
                score=score,
                bbox=button.bbox,
                template_path=button.template_path,
            )
        )
    return sorted(scored, key=lambda item: item.score, reverse=True)


def is_ad_revive_context(buttons: list[ButtonCandidate]) -> bool:
    labels = {normalize_label(button.label) for button in buttons}
    if labels & CANCEL_LABELS and labels & WATCH_AD_LABELS:
        return True
    for button in buttons:
        text = normalize_label(f'{button.label} {button.reason}')
        if any(hint in text for hint in AD_REVIVE_HINTS):
            return True
        if 'revive' in text and 'ad' in text:
            return True
        if '复活' in text and '广告' in text:
            return True
    return False


def is_defeat_context(
    buttons: list[ButtonCandidate],
    defeat_recovery_labels: set[str] | None = None,
) -> bool:
    for button in buttons:
        text = normalize_label(f'{button.label} {button.reason}')
        if any(hint in text for hint in DEFEAT_CONTEXT_HINTS):
            return True
    recovery_labels = (
        set(DEFEAT_RECOVERY_LABELS)
        if defeat_recovery_labels is None
        else set(defeat_recovery_labels)
    )
    live_continue_visible = any(
        normalize_label(button.label) in LIVE_RUN_CONTINUE_LABELS for button in buttons
    )
    if live_continue_visible:
        return False
    return any(
        normalize_label(button.label) in recovery_labels and button.y >= 0.88
        for button in buttons
    )


def is_watch_ad_button(button: ButtonCandidate) -> bool:
    key = normalize_label(button.label)
    text = normalize_label(f'{button.label} {button.reason}')
    if key in WATCH_AD_LABELS:
        return True
    if 'watch' in text and 'ad' in text:
        return True
    if '广告' in text and '复活' in text:
        return True
    return '观看' in text and '广告' in text


def tower_ad_revive_candidate(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> ButtonCandidate | None:
    if normalize_label(automation_config.game) != 'tower':
        return None
    labels = {
        normalize_label(button.label)
        for button in buttons
        if button.source != 'template'
    }
    if '看广告复活' not in labels or '取消' not in labels:
        return None
    return ButtonCandidate(
        label='复活（广告）',
        x=0.69,
        y=0.63,
        confidence=0.99,
        clickability=9.0,
        source='vision',
        reason=(
            'Tower ad-revive popup: click the stable yellow revive button '
            'instead of the non-action dialog title, then wait for the ad.'
        ),
    )


def is_generic_tower_room_vision_candidate(button: ButtonCandidate) -> bool:
    return (
        button.source == 'vision'
        and normalize_label(button.label) == 'visible room icon'
    )


def is_tower_room_vision_candidate(button: ButtonCandidate) -> bool:
    return button.source == 'vision' and normalize_label(button.label) in {
        'visible current room icon',
        'visible next-floor stair room',
        'visible rest room icon',
        'visible combat room icon',
        'visible room icon',
    }


def decide_next_move(
    buttons: list[ButtonCandidate],
    *,
    min_action_score: float,
    ambiguity_margin: float,
    ask_on_ambiguous: bool,
    fallback_labels: set[str] | None = None,
    automation_config: GameAutomationConfig | None = None,
) -> Decision:
    if not buttons:
        return Decision(
            status='needs_llm',
            reason='OCR and strategy did not find any actionable button text.',
            recommended=None,
            choices=[],
        )

    waiting = next((button for button in buttons if button.source == 'wait'), None)
    if waiting is not None:
        return Decision(
            status='ready',
            reason='A local loading state is visible; wait without using LLM vision.',
            recommended=waiting,
            choices=[waiting],
        )

    tower_prebattle_visible = bool(
        automation_config is not None
        and normalize_label(automation_config.game) == 'tower'
        and any(
            '即将发起战斗' in normalize_label(button.label)
            for button in buttons
        )
    )
    if tower_prebattle_visible:
        battle_buttons = [
            button
            for button in buttons
            if normalize_label(button.label) == '战斗'
            and button.score >= min_action_score
        ]
        if battle_buttons:
            battle = max(
                battle_buttons,
                key=lambda button: (
                    button.score,
                    button.confidence,
                    button.clickability,
                ),
            )
            return Decision(
                status='ready',
                reason=(
                    'The Tower prebattle panel is open; launch the fight instead '
                    'of probing the enemy name or build-room label.'
                ),
                recommended=battle,
                choices=sorted(
                    battle_buttons,
                    key=lambda button: button.score,
                    reverse=True,
                )[:3],
            )

    tower_next_floor = [
        button
        for button in buttons
        if normalize_label(button.label) == 'visible next-floor stair room'
        or is_tower_next_floor_action(button.label)
    ]
    tower_trainer_panel_visible = any(
        normalize_label(button.label) == '训练师任务' for button in buttons
    ) and any(
        normalize_label(button.label) in {'选择', '领取'} for button in buttons
    )
    strategic_build_rooms = [
        button
        for button in buttons
        if button not in tower_next_floor
        and not tower_trainer_panel_visible
        and tower_deep_map_room_bonus(button.label) >= 5.0
        and button.score >= min_action_score
    ]
    if tower_next_floor and not strategic_build_rooms:
        top_next_floor = max(
            tower_next_floor,
            key=lambda button: (button.score, button.confidence, button.clickability),
        )
        if top_next_floor.score >= min_action_score:
            return Decision(
                status='ready',
                reason=(
                    'The Tower next-floor room is visible; enter it before any '
                    'route-exit heuristic can send the run back to the prior room.'
                ),
                recommended=top_next_floor,
                choices=sorted(
                    tower_next_floor,
                    key=lambda button: button.score,
                    reverse=True,
                )[:3],
            )

    if strategic_build_rooms:
        top_strategic_room = max(
            strategic_build_rooms,
            key=lambda button: (button.score, button.confidence, button.clickability),
        )
        return Decision(
            status='ready',
            reason=(
                'A high-value Tower build room is available; resolve it before '
                'taking the route that leaves this floor.'
            ),
            recommended=top_strategic_room,
            choices=sorted(
                strategic_build_rooms,
                key=lambda button: button.score,
                reverse=True,
            )[:3],
        )

    fallback_labels = fallback_labels or set()
    viable_non_fallback = [
        button
        for button in buttons
        if button.score >= min_action_score
        and normalize_label(button.label) not in fallback_labels
        and not is_navigation_arrow_label(button.label, automation_config)
        and not is_tower_room_vision_candidate(button)
    ]
    recent_room_exit = next(
        button
        for button in buttons
        if 'leave recently completed tower room' in normalize_label(button.reason)
        and button.score >= min_action_score
    ) if any(
        'leave recently completed tower room' in normalize_label(button.reason)
        and button.score >= min_action_score
        for button in buttons
    ) else None
    if (
        recent_room_exit is not None
        and (
            not viable_non_fallback
            or recent_room_exit.score >= viable_non_fallback[0].score + 0.5
        )
    ):
        candidates = [recent_room_exit, *viable_non_fallback]
    else:
        candidates = viable_non_fallback or buttons
    top = candidates[0]
    if top.score < min_action_score:
        tower_state = (
            load_tower_run_state(automation_config.game)
            if automation_config is not None
            and normalize_label(automation_config.game) == 'tower'
            else {}
        )
        if normalize_label(str(tower_state.get('phase') or '')) == 'combat' and (
            is_end_turn_label(top.label)
            or is_tower_combat_card_candidate(top, automation_config)
        ):
            return Decision(
                status='ready',
                reason=(
                    'Tower combat has a deterministic local card or end-turn '
                    'action; continue without requesting LLM vision.'
                ),
                recommended=top,
                choices=buttons[:3],
            )
        return Decision(
            status='needs_llm',
            reason=(
                f'Top candidate score {top.score:.3f} is below {min_action_score:.3f}.'
            ),
            recommended=top,
            choices=buttons[:3],
        )

    close = [
        button
        for button in candidates[:4]
        if top.score - button.score <= ambiguity_margin
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
    if button.source == 'wait':
        return
    if button.source == 'launch_app':
        package = button.label.partition(':')[2].strip()
        command = ['adb']
        serial = str(getattr(args, 'current_device_serial', '') or '').strip()
        if serial:
            command.extend(['-s', serial])
        command.extend(
            [
                'shell',
                'monkey',
                '-p',
                package,
                '-c',
                'android.intent.category.LAUNCHER',
                '1',
            ]
        )
        subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=10.0,
        )
        return
    client = live_mcp_client(args)
    if is_swipe_candidate(button):
        client.call_tool('swipe', swipe_arguments_for_button(button))
        return
    if is_back_candidate(button):
        client.call_tool('back', {})
        return
    client.call_tool('click', {'x': button.x, 'y': button.y})
    if should_double_click_button(button, load_automation_config(args.game)):
        time.sleep(0.8 if normalize_label(args.game) == 'tower' else 0.15)
        client.call_tool('click', {'x': button.x, 'y': button.y})


def should_double_click_button(
    button: ButtonCandidate,
    automation_config: GameAutomationConfig | None = None,
) -> bool:
    return is_configured_combat_card_label(button.label, automation_config)


def tower_fast_batch_follow_up(
    buttons: list[ButtonCandidate],
) -> ButtonCandidate | None:
    playable = sorted(
        [
            button
            for button in buttons
            if button.source == 'vision'
            and normalize_label(button.label).startswith('visible playable card')
        ],
        key=lambda button: (button.y, button.x),
    )
    if len(playable) < 2:
        return None
    first_slot = playable[0]
    return ButtonCandidate(
        label='Visible playable card batch follow-up',
        x=first_slot.x,
        y=first_slot.y,
        confidence=0.95,
        clickability=7.0,
        source='vision',
        reason=(
            'After the first leftmost card is played, the next card reflows into '
            'the stable first slot; play at most one follow-up before rereading.'
        ),
    )


def tower_trainer_task_bonus(
    button: ButtonCandidate,
    buttons: list[ButtonCandidate],
    automation_config: GameAutomationConfig | None,
) -> float:
    if (
        automation_config is None
        or normalize_label(automation_config.game) != 'tower'
        or not any(
            normalize_label(candidate.label) == '训练师任务'
            for candidate in buttons
        )
    ):
        return 0.0
    button_key = normalize_label(button.label)
    if '不想遇到' in button_key and '训练师' in button_key:
        return -30.0
    if button_key == '告别':
        choice_bonuses = [
            tower_trainer_task_bonus(
                candidate,
                buttons,
                automation_config,
            )
            for candidate in buttons
            if normalize_label(candidate.label) == '选择'
        ]
        return 10.0 if max(choice_bonuses, default=0.0) <= 0 else -10.0
    if button_key != '选择':
        return 0.0
    choice_rows = sorted(
        candidate.y
        for candidate in buttons
        if normalize_label(candidate.label) == '选择'
    )
    row_index = min(
        range(len(choice_rows)),
        key=lambda index: abs(choice_rows[index] - button.y),
    )
    row_lower = (
        (choice_rows[row_index - 1] + button.y) / 2
        if row_index > 0
        else button.y - 0.07
    )
    row_upper = (
        (button.y + choice_rows[row_index + 1]) / 2
        if row_index + 1 < len(choice_rows)
        else button.y + 0.07
    )
    row_text = ' '.join(
        normalize_label(candidate.label)
        for candidate in buttons
        if candidate is not button
        and candidate.source != 'template'
        and candidate.x < 0.75
        and row_lower <= candidate.y < row_upper
    )
    condition_bonus = 0.0
    new_card_condition = re.search(r'直接获得(\d+)张新卡牌', row_text)
    if new_card_condition:
        condition_bonus -= min(float(new_card_condition.group(1)) * 3.0, 15.0)
    elif re.search(r'直接获得\d+张\d+级卡牌', row_text):
        condition_bonus -= 2.0
    elif re.search(r'直接获得\d+张', row_text):
        condition_bonus -= 6.0
    if '战斗胜利3次' in row_text:
        condition_bonus += 10.0
    if re.search(r'击败\d+只普通怪', row_text):
        condition_bonus += 12.0
    if '完成2层冒险' in row_text:
        condition_bonus += 6.0
    if '获得100个金币' in row_text:
        condition_bonus += 8.0
    if '击败2只哥布林' in row_text:
        condition_bonus += 4.0
    if '敌方物攻增加100点' in row_text:
        condition_bonus -= 6.0
    if '欢乐时光' in row_text or '金币利息' in row_text:
        return condition_bonus + 32.0
    if '谢幕' in row_text or '掉落物' in row_text and '倍' in row_text:
        return condition_bonus + 18.0
    if '和弦' in row_text:
        return condition_bonus + 12.0
    if '超时空之手' in row_text:
        return condition_bonus + 20.0
    profession = tower_run_profession(automation_config.game)
    if profession == '旅行者':
        if '牛脾气' in row_text:
            return condition_bonus + (
                36.0
                if tower_traveler_uses_prayer_build(automation_config.game)
                else 30.0
            )
        if '植物精华' in row_text:
            return condition_bonus + (
                4.0
                if tower_traveler_uses_prayer_build(automation_config.game)
                else 32.0
            )
        if '不朽之心' in row_text:
            return condition_bonus + 18.0
        if '毒性思考' in row_text:
            return condition_bonus + 16.0
        if '晶体冥想' in row_text or '品体冥想' in row_text:
            return condition_bonus + 7.0
        if '疾速施法' in row_text:
            return condition_bonus + 6.0
        if '元素感应' in row_text:
            return condition_bonus + 2.0
        if '谢幕' in row_text:
            return condition_bonus + 6.0
        if '身体强化' in row_text:
            return condition_bonus + 12.0
        if '啤酒肚' in row_text:
            return condition_bonus + 14.0
        return condition_bonus - 6.0
    if profession == '猎人':
        if '快速施法' in row_text or '双枪' in row_text:
            return condition_bonus + 22.0
        if '魔法熊手' in row_text:
            return condition_bonus + 20.0
        if '卖命挣钱' in row_text or '生死对决' in row_text:
            return condition_bonus + 10.0
    if profession == '法师':
        state = load_tower_run_state(automation_config.game)
        treasure_text = ' '.join(
            normalize_label(str(value))
            for value in [
                state.get('predecessor_treasure') or '',
                *(state.get('key_treasures') or []),
            ]
        )
        electric_route = '电虫药水' in treasure_text
        fire_route = '火焰草莓' in treasure_text
        if '独孤求败' in row_text:
            return condition_bonus - 30.0
        if '牛脾气' in row_text or '牛牌气' in row_text:
            return condition_bonus + (28.0 if electric_route else 22.0)
        if '火纹' in row_text:
            if electric_route:
                return condition_bonus - 18.0
            return condition_bonus + (24.0 if fire_route else 18.0)
        if '不朽之心' in row_text:
            return condition_bonus + (26.0 if electric_route else 18.0)
        if '能量转换' in row_text:
            return condition_bonus + (30.0 if electric_route else 24.0)
        if '变异血统' in row_text:
            return condition_bonus - (12.0 if electric_route else 6.0)
        if '骑士之力' in row_text:
            return condition_bonus + (18.0 if electric_route else 10.0)
        if '身体强化' in row_text:
            return condition_bonus + 14.0
        if '谢幕' in row_text:
            return condition_bonus + 10.0
    if profession == '战士' and '快速施法' in row_text:
        return condition_bonus + 18.0
    if '闪避' in row_text or '猪手本能' in row_text or '猎手本能' in row_text:
        return condition_bonus + 8.0
    if '灵巧身法' in row_text:
        return condition_bonus + 6.0
    if '游盗车厢' in row_text or '随机道具牌' in row_text:
        return condition_bonus + 3.0
    if '毒性思考' in row_text:
        return condition_bonus + 1.0
    return condition_bonus


def tower_card_upgrade_bonus(
    button: ButtonCandidate,
    buttons: list[ButtonCandidate],
    automation_config: GameAutomationConfig | None,
) -> float:
    if (
        automation_config is None
        or normalize_label(automation_config.game) != 'tower'
        or not any(
            normalize_label(candidate.label) == '卡牌强化'
            for candidate in buttons
        )
    ):
        return 0.0
    key = normalize_label(button.label)
    if key == '卡牌强化':
        return -10.0
    profession = tower_run_profession(automation_config.game)
    state = load_tower_run_state(automation_config.game)
    treasures = ' '.join(
        normalize_label(str(value))
        for value in [
            state.get('predecessor_treasure') or '',
            *(state.get('key_treasures') or []),
        ]
    )
    if profession == '旅行者' and '烈性毒药' in key and '魔法面具' in treasures:
        return -20.0
    traveler_priorities = (
        (
            ('天使', 18.0),
            ('救赎', 16.0),
            ('无限宝石', 15.0),
            ('黑神话', 14.0),
            ('奉献', 13.0),
            ('献祭', 12.0),
            ('回忆', 11.0),
            ('慈悲', -12.0),
            ('灵魂燃烧', -12.0),
        )
        if tower_traveler_uses_prayer_build(automation_config.game)
        else (
            ('剧毒晶石', 16.0),
            ('烈性毒药', 15.0),
            ('安乐毒药', 14.0),
            ('黑神话', 13.0),
            ('无限宝石', 13.0),
            ('毒药攻击', 12.0),
            ('涂毒小刀', 12.0),
            ('献祭', 11.0),
            ('回忆', 10.0),
            ('救赎', -12.0),
            ('慈悲', -12.0),
        )
    )
    profession_priorities = {
        '旅行者': traveler_priorities,
        '猎人': (
            ('捕猎陷阱', 14.0),
            ('猎人嗅觉', 13.0),
            ('大力射击', 11.0),
            ('瞄准', 9.0),
        ),
        '法师': (
            ('电解冰', 14.0),
            ('火焰打击', 14.0),
            ('快速思考', 13.0),
            ('燃烧晶石', 12.0),
            ('闪电晶石', 12.0),
            ('小雷虫', 11.0),
        ),
        '战士': (
            ('幽灵剑', 14.0),
            ('弱点加倍', 13.0),
            ('弱点打击', 12.0),
            ('发现弱点', 11.0),
            ('换血', 10.0),
        ),
    }
    priorities = (
        *profession_priorities.get(str(profession or ''), ()),
        ('以物易物', 10.0),
        ('杂念', 9.0),
        ('特殊信念', 8.0),
        ('医疗人偶', 7.0),
        ('慈悲', 6.0),
        ('救赎', 5.0),
        ('毒药攻击', 3.0),
        ('涂毒小刀', 2.0),
    )
    for pattern, bonus in priorities:
        if normalize_label(pattern) in key:
            return bonus
    return 0.0


def inspect_item_choices(
    args: argparse.Namespace,
    *,
    buttons: list[ButtonCandidate],
    memory: dict[str, Any],
    artifact_paths: dict[str, Path],
    automation_config: GameAutomationConfig | None = None,
) -> tuple[list[ItemInspection], Decision | None]:
    if args.image or not args.click_recommended:
        return [], None
    automation_config = automation_config or load_automation_config(args.game)
    if configured_result_progress_visible(automation_config, buttons) and any(
        is_confirm_button(button) for button in buttons
    ):
        return [], None

    configured_inspections, configured_decision = inspect_configured_skill_choice(
        args,
        automation_config=automation_config,
        buttons=buttons,
        artifact_paths=artifact_paths,
    )
    if configured_decision is not None:
        return configured_inspections, configured_decision
    if automation_config.skill_choice_required_labels:
        return [], None

    confirm_buttons = [button for button in buttons if is_confirm_button(button)]
    if not confirm_buttons:
        return [], None
    if any(normalize_label(button.label) == '道具口袋' for button in buttons):
        healing_patterns = (
            '深澜龙血',
            '深渊龙血',
            '恢复药水',
            '生命药水',
            '治疗药水',
        )
        cycle_patterns = ('迅捷药水', '唤回药水', '宝石药水')
        item_buttons = [
            button
            for button in buttons
            if button.source != 'template' and 0.54 <= button.y <= 0.78
        ]
        target = next(
            (
                button
                for pattern in healing_patterns
                for button in item_buttons
                if pattern in normalize_label(button.label)
            ),
            None,
        )
        target = target or next(
            (
                button
                for pattern in cycle_patterns
                for button in item_buttons
                if pattern in normalize_label(button.label)
            ),
            None,
        )
        if target is not None:
            click_button(args, target)
            time.sleep(args.item_inspection_interval)
        visible_text = ' '.join(normalize_label(button.label) for button in buttons)
        if target is not None or (
            ('恢复' in visible_text and '生命' in visible_text)
            or ('抽' in visible_text and '张牌' in visible_text)
        ):
            confirm = max(
                confirm_buttons,
                key=lambda button: (
                    button.score,
                    button.confidence,
                    button.clickability,
                ),
            )
            return [], Decision(
                status='ready',
                reason=(
                    f'低血道具口袋优先选择{target.label if target else "当前消耗品"}'
                    '并确认；回血优先，无回血时用循环或回收争取本回合斩杀。'
                ),
                recommended=confirm,
                choices=[button for button in (target, confirm) if button is not None],
            )
    stair_choice = tower_stair_choice_candidate(automation_config, buttons)
    if stair_choice is not None:
        click_button(args, stair_choice)
        time.sleep(args.item_inspection_interval)
        confirm = max(
            confirm_buttons,
            key=lambda button: (button.score, button.confidence, button.clickability),
        )
        return [], Decision(
            status='ready',
            reason=(
                f'Selected {stair_choice.label} once using the safer route policy; '
                'confirm without probing unrelated labels.'
            ),
            recommended=confirm,
            choices=[stair_choice, confirm],
        )
    card_choice = tower_card_reward_candidate(automation_config, buttons)
    if card_choice is not None:
        if normalize_label(card_choice.label) == '放弃':
            return [], Decision(
                status='ready',
                reason=card_choice.reason,
                recommended=card_choice,
                choices=[card_choice],
            )
        click_button(args, card_choice)
        record_tower_run_choice(args.game, 'card', card_choice.label)
        time.sleep(args.item_inspection_interval)
        confirm = max(
            confirm_buttons,
            key=lambda button: (button.score, button.confidence, button.clickability),
        )
        return [], Decision(
            status='ready',
            reason=(
                f'Selected {card_choice.label} once using the short-cycle card '
                'policy; confirm without inspecting unrelated screen text.'
            ),
            recommended=confirm,
            choices=[card_choice, confirm],
        )
    rest_choice = tower_rest_choice_candidate(automation_config, buttons)
    if rest_choice is not None:
        click_button(args, rest_choice)
        time.sleep(args.item_inspection_interval)
        confirm = max(
            confirm_buttons,
            key=lambda button: (button.score, button.confidence, button.clickability),
        )
        return [], Decision(
            status='ready',
            reason=(
                f'Selected {rest_choice.label} using the current stage survival '
                'policy before confirming the camp panel.'
            ),
            recommended=confirm,
            choices=[rest_choice, confirm],
        )
    if is_non_item_confirmation_dialog(buttons):
        return [], None
    treasure_choice = tower_treasure_choice_candidate(automation_config, buttons)
    if treasure_choice is not None:
        click_button(args, treasure_choice)
        record_tower_run_choice(args.game, 'treasure', treasure_choice.label)
        time.sleep(args.item_inspection_interval)
        confirm = max(
            confirm_buttons,
            key=lambda button: (button.score, button.confidence, button.clickability),
        )
        return [], Decision(
            status='ready',
            reason='Selected a real treasure card and will confirm the treasure panel.',
            recommended=confirm,
            choices=[treasure_choice, confirm],
        )
    if normalize_label(automation_config.game) == 'tower':
        return [], None

    fallback = {normalize_label(label) for label in memory.get('fallback', [])}
    avoid = {normalize_label(label) for label in memory.get('avoid', [])}
    ineffective = {normalize_label(label) for label in memory.get('ineffective', [])}
    candidates = [
        button
        for button in buttons
        if is_inspectable_item_candidate(
            button,
            fallback_labels=fallback,
            avoid_labels=avoid,
            ineffective_labels=ineffective,
            automation_config=automation_config,
        )
    ]
    if len(candidates) < 2:
        return [], None

    inspection_dir = artifact_paths['item_inspection_dir']
    inspection_dir.mkdir(parents=True, exist_ok=True)
    inspections: list[ItemInspection] = []
    for index, candidate in enumerate(
        candidates[: args.item_inspection_limit], start=1
    ):
        click_button(args, candidate)
        time.sleep(args.item_inspection_interval)
        image, _metadata = load_image(args)
        screenshot_name = f'{index:02d}-{template_stem_for_label(candidate.label)}.png'
        image.save(inspection_dir / screenshot_name)
        after_buttons = analyze_buttons(
            image,
            confidence=args.confidence,
            game=args.game,
            template_match_threshold=args.template_match_threshold,
        )
        labels = item_description_labels(
            before_buttons=buttons,
            after_buttons=after_buttons,
            candidate=candidate,
            automation_config=automation_config,
        )
        description = '; '.join(labels[: args.item_description_label_limit])
        item_score, reasons = configured_item_preference_score(
            candidate.label,
            description,
            automation_config,
            game=args.game,
        )
        inspection = ItemInspection(
            candidate=candidate,
            description=description,
            score=item_score,
            reasons=reasons,
            screenshot=str(Path('item_inspections') / screenshot_name),
            ocr_labels=labels,
            kind=classify_game_info_entry(candidate.label, description),
        )
        inspections.append(inspection)

    write_item_inspections_yaml(artifact_paths['item_inspections'], inspections)
    write_game_info_markdown(
        args.game,
        additional_inspection_path=artifact_paths['item_inspections'],
    )
    if not inspections:
        return [], None

    best = max(
        inspections,
        key=lambda item: (item.score, item.candidate.score, item.candidate.confidence),
    )
    chosen = best.candidate
    if inspections[-1].candidate != chosen:
        click_button(args, chosen)
        time.sleep(args.item_inspection_interval)
    confirm = max(
        confirm_buttons,
        key=lambda button: (button.score, button.confidence, button.clickability),
    )
    return inspections, Decision(
        status='ready',
        reason=(
            f'Inspected {len(inspections)} item choices, selected '
            f'{chosen.label}, and will confirm because: '
            f'{", ".join(best.reasons) or "best score"}'
        ),
        recommended=confirm,
        choices=[
            item.candidate
            for item in sorted(
                inspections,
                key=lambda item: (item.score, item.candidate.score),
                reverse=True,
            )
        ],
    )


def image_similarity(
    before: Image.Image,
    after: Image.Image,
    *,
    sample_size: tuple[int, int] = (128, 128),
    box: tuple[int, int, int, int] | None = None,
) -> float:
    if box is not None:
        before = before.crop(box)
        after = after.crop(box)
    before_sample = before.convert('RGB').resize(sample_size, Image.Resampling.LANCZOS)
    after_sample = after.convert('RGB').resize(sample_size, Image.Resampling.LANCZOS)
    diff = ImageChops.difference(before_sample, after_sample)
    mean_delta = sum(ImageStat.Stat(diff).mean) / 3.0
    return max(0.0, min(1.0, 1.0 - (mean_delta / 255.0)))


def is_mostly_blank_screen(image: Image.Image) -> bool:
    grayscale = image.convert('L')
    width, height = grayscale.size
    content = grayscale.crop((0, 0, width, max(1, int(height * 0.92))))
    stat = ImageStat.Stat(content)
    mean = stat.mean[0] / 255.0
    stddev = stat.stddev[0] / 255.0
    return mean <= 0.025 and stddev <= 0.025


def is_loading_spinner_screen(image: Image.Image) -> bool:
    rgb = np.asarray(image.convert('RGB'))
    height, width = rgb.shape[:2]
    if height < 10 or width < 10 or float(rgb.mean()) > 24.0:
        return False

    left, right = int(width * 0.37), int(width * 0.63)
    top, bottom = int(height * 0.46), int(height * 0.58)
    roi = rgb[top:bottom, left:right]
    if roi.size == 0:
        return False
    cyan = (
        (roi[:, :, 1] > 90)
        & (roi[:, :, 2] > 100)
        & (roi[:, :, 1] > roi[:, :, 0] * 1.5)
        & (roi[:, :, 2] > roi[:, :, 0] * 1.5)
    )
    cyan_y, cyan_x = np.where(cyan)
    if cyan_x.size < 60:
        return False
    return bool(
        np.ptp(cyan_x) >= width * 0.05
        and np.ptp(cyan_y) >= height * 0.04
    )


def progress_region_for_button(
    image: Image.Image,
    button: ButtonCandidate,
    automation_config: GameAutomationConfig | None = None,
) -> tuple[str, tuple[int, int, int, int]]:
    width, height = image.size
    if normalize_label(button.label).startswith('选择新招募角色'):
        return 'main_screen_without_status_bar', (0, int(height * 0.06), width, height)
    if (
        automation_config is not None
        and normalize_label(button.label)
        in automation_config.main_screen_verification_labels
    ):
        return 'main_screen_without_status_bar', (0, int(height * 0.06), width, height)
    if button.y >= 0.55:
        return 'lower_progress_region', (0, int(height * 0.55), width, height)
    return 'main_screen_without_status_bar', (0, int(height * 0.06), width, height)


def state_change_similarities(
    before: Image.Image,
    after: Image.Image,
    button: ButtonCandidate,
    automation_config: GameAutomationConfig | None = None,
) -> tuple[float, float, str]:
    progress_region, progress_box = progress_region_for_button(
        before,
        button,
        automation_config,
    )
    return (
        image_similarity(before, after),
        image_similarity(before, after, box=progress_box),
        progress_region,
    )


def recent_turn_dirs(root: Path, limit: int) -> list[Path]:
    if limit <= 0 or not root.exists():
        return []
    turn_dirs = sorted(
        [path for path in root.iterdir() if path.is_dir()],
        key=lambda path: (path.stat().st_mtime, path.name),
    )
    return turn_dirs[-limit:]


def action_label_from_metadata(
    turn_dir: Path,
    *,
    require_changed: bool = False,
) -> str | None:
    metadata_path = turn_dir / 'metadata.yaml'
    if not metadata_path.exists():
        return None
    payload = yaml.safe_load(metadata_path.read_text()) or {}
    worklog = payload.get('worklog') or {}
    if require_changed:
        verification = worklog.get('state_verification') or {}
        if normalize_label(str(verification.get('status') or '')) != 'changed':
            return None
    action = worklog.get('action_taken') or {}
    label = str(action.get('label') or '').strip()
    return label or None


def recent_action_labels(root: Path, limit: int) -> list[str]:
    labels = [
        label
        for turn_dir in recent_turn_dirs(root, limit * 4)
        if (label := action_label_from_metadata(turn_dir))
    ]
    return labels[-limit:]


def recent_successful_action_labels(root: Path, limit: int) -> list[str]:
    labels = [
        label
        for turn_dir in recent_turn_dirs(root, limit * 4)
        if (
            label := action_label_from_metadata(
                turn_dir,
                require_changed=True,
            )
        )
    ]
    return labels[-limit:]


def repeated_blank_wait_detected(
    recent_actions: list[str],
    *,
    min_repeats: int = 3,
) -> bool:
    wait_label = normalize_label(wait_for_loading_candidate().label)
    wait_count = 0
    for label in reversed(recent_actions):
        if normalize_label(label) != wait_label:
            break
        wait_count += 1
    return wait_count >= min_repeats


def navigation_oscillation_avoid_labels(
    root: Path,
    *,
    window_size: int = 4,
    automation_config: GameAutomationConfig | None = None,
) -> set[str]:
    labels = recent_action_labels(root, window_size)
    if len(labels) < window_size:
        return set()
    directions = [
        navigation_direction(label)
        for label in labels
        if is_navigation_arrow_label(label, automation_config)
    ]
    if len(directions) < window_size:
        return set()
    if (
        all(directions)
        and directions[0] == directions[2]
        and directions[1] == directions[3]
        and directions[0] != directions[1]
    ):
        return {normalize_label(label) for label in labels}
    return set()


def navigation_only_loop_avoid_labels(
    root: Path,
    *,
    window_size: int = 6,
    minimum_actions: int = 4,
    automation_config: GameAutomationConfig | None = None,
) -> set[str]:
    labels = recent_action_labels(root, window_size)
    if len(labels) < minimum_actions:
        return set()
    recent_labels = labels[-minimum_actions:]
    if all(
        is_navigation_arrow_label(label, automation_config) for label in recent_labels
    ):
        return {normalize_label(label) for label in recent_labels}
    return set()


def assess_unblock_window(
    root: Path,
    *,
    window_size: int,
    threshold: float,
) -> UnblockAssessment:
    turn_dirs = recent_turn_dirs(root, window_size)
    turn_names = [path.name for path in turn_dirs]
    if len(turn_dirs) < window_size:
        return UnblockAssessment(
            status='not_checked',
            reason=(
                f'Only {len(turn_dirs)} turn folders are available; need '
                f'{window_size} before checking for a blocked loop.'
            ),
            window_size=window_size,
            threshold=threshold,
            similarities=[],
            turn_dirs=turn_names,
            repeated_actions=[],
        )

    screenshots = [turn_dir / 'screenshot.png' for turn_dir in turn_dirs]
    missing = [path for path in screenshots if not path.exists()]
    if missing:
        return UnblockAssessment(
            status='not_checked',
            reason=f'Missing screenshots: {", ".join(path.name for path in missing)}.',
            window_size=window_size,
            threshold=threshold,
            similarities=[],
            turn_dirs=turn_names,
            repeated_actions=[],
        )

    baseline = Image.open(screenshots[0]).convert('RGB')
    similarities = [
        image_similarity(baseline, Image.open(path).convert('RGB'))
        for path in screenshots[1:]
    ]
    actions = [
        label
        for turn_dir in turn_dirs
        if (label := action_label_from_metadata(turn_dir))
    ]
    repeated_actions = list(dict.fromkeys(actions))
    if similarities and all(similarity >= threshold for similarity in similarities):
        return UnblockAssessment(
            status='stuck',
            reason=(
                f'The last {window_size} turn screenshots are all similar enough '
                'to indicate a blocked loop.'
            ),
            window_size=window_size,
            threshold=threshold,
            similarities=similarities,
            turn_dirs=turn_names,
            repeated_actions=repeated_actions,
        )

    return UnblockAssessment(
        status='not_stuck',
        reason=f'The last {window_size} turn screenshots show enough change.',
        window_size=window_size,
        threshold=threshold,
        similarities=similarities,
        turn_dirs=turn_names,
        repeated_actions=repeated_actions,
    )


def decide_unblock_move(
    buttons: list[ButtonCandidate],
    repeated_actions: set[str],
) -> Decision:
    if not buttons:
        return Decision(
            status='needs_llm',
            reason='Unblock mode found no OCR/template candidates to explore.',
            recommended=None,
            choices=[],
        )

    normalized_repeated_actions = {normalize_label(label) for label in repeated_actions}
    untried_candidates = [
        button
        for button in buttons
        if normalize_label(button.label) not in normalized_repeated_actions
    ]
    candidates = untried_candidates or buttons
    repeated_navigation_actions = {
        normalize_label(label)
        for label in normalized_repeated_actions
        if is_navigation_arrow_label(label)
        or any(token in normalize_label(label) for token in ('道路', '路线', '箭头'))
    }
    navigation_layers_exhausted = len(repeated_navigation_actions) >= 2
    viable_non_menu_candidates = [
        button
        for button in candidates
        if not is_escape_menu_probe_button(button)
        and button.score >= MIN_UNBLOCK_NON_MENU_SCORE
    ]
    if viable_non_menu_candidates:
        candidates = viable_non_menu_candidates
    elif navigation_layers_exhausted and any(
        is_escape_menu_probe_button(button) for button in candidates
    ):
        candidates = [
            button for button in candidates if is_escape_menu_probe_button(button)
        ]
    else:
        viable_non_menu_buttons = [
            button
            for button in buttons
            if not is_escape_menu_probe_button(button)
            and button.score >= MIN_UNBLOCK_NON_MENU_SCORE
        ]
        if viable_non_menu_buttons:
            candidates = viable_non_menu_buttons
        else:
            non_menu_candidates = [
                button
                for button in candidates
                if not is_escape_menu_probe_button(button)
            ]
            if non_menu_candidates:
                candidates = non_menu_candidates
    top = candidates[0]
    return Decision(
        status='ready',
        reason=(
            'Unblock mode is active because recent screenshots stayed similar. '
            'Trying a different visible candidate before repeating the same action.'
        ),
        recommended=top,
        choices=candidates[:3],
    )


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
            progress_threshold=args.state_progress_similarity_threshold,
            progress_similarities=[],
            progress_region='skipped',
        )

    similarities: list[float] = []
    progress_similarities: list[float] = []
    progress_region = 'unknown'
    automation_config = load_automation_config(args.game)
    interval = args.state_change_interval
    max_retries = args.state_change_retries
    wait_without_reclick = False
    if 'tower shop fusion' in normalize_label(button.reason):
        max_retries = 1
    if is_watch_ad_button(button):
        interval = max(interval, 3.0)
        max_retries = max(max_retries, 4)
        wait_without_reclick = True
    if is_configured_combat_card_label(button.label, automation_config):
        interval = min(interval, 0.25)
        max_retries = 1
    elif is_end_turn_label(button.label):
        interval = max(interval, 1.1)
        max_retries = max(max_retries, 4)
        wait_without_reclick = True
    for attempt in range(1, max_retries + 1):
        time.sleep(interval)
        after_image, _metadata = load_image(args)
        after_image.save(last_screenshot_path)
        similarity, progress_similarity, progress_region = state_change_similarities(
            before_image,
            after_image,
            button,
            automation_config,
        )
        similarities.append(similarity)
        progress_similarities.append(progress_similarity)
        if (
            similarity < threshold
            and progress_similarity < args.state_progress_similarity_threshold
        ):
            return StateVerification(
                status='changed',
                reason=(
                    f'Screen changed after attempt {attempt}; similarity '
                    f'{similarity:.4f} is below threshold {threshold:.4f}, and '
                    f'{progress_region} similarity {progress_similarity:.4f} is '
                    f'below threshold {args.state_progress_similarity_threshold:.4f}.'
                ),
                attempts=attempt,
                threshold=threshold,
                similarities=similarities,
                progress_threshold=args.state_progress_similarity_threshold,
                progress_similarities=progress_similarities,
                progress_region=progress_region,
                last_screenshot=last_screenshot_path.name,
            )
        if attempt < max_retries and not wait_without_reclick:
            click_button(args, button)

    verification = StateVerification(
        status='unchanged',
        reason=(
            f'Screen did not show stable progress after '
            f'{max_retries} click attempts. Full-screen '
            f'similarity threshold: {threshold:.4f}; {progress_region} '
            f'threshold: {args.state_progress_similarity_threshold:.4f}.'
        ),
        attempts=max_retries,
        threshold=threshold,
        similarities=similarities,
        progress_threshold=args.state_progress_similarity_threshold,
        progress_similarities=progress_similarities,
        progress_region=progress_region,
        strategy_updated=False,
        last_screenshot=last_screenshot_path.name,
    )
    strategy_updated = append_no_change_learning(args.game, button, verification)
    return replace(verification, strategy_updated=strategy_updated)


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


def save_turn_detection_overlays(
    image: Image.Image,
    *,
    artifact_paths: dict[str, Path],
    ocr_buttons: list[ButtonCandidate],
    template_buttons: list[ButtonCandidate],
    llm_buttons: list[ButtonCandidate],
) -> None:
    save_overlay(
        image,
        [*ocr_buttons, *template_buttons],
        artifact_paths['ocr_overlay'],
    )
    if llm_buttons:
        save_overlay(
            image,
            llm_buttons,
            artifact_paths['llm_overlay'],
        )
    elif artifact_paths['llm_overlay'].exists():
        artifact_paths['llm_overlay'].unlink()


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
game_info:
  - name: exact in-game item/skill/treasure name when visible
    type: item
    description: exact visible in-game effect/description text from the same screenshot
objects:
  - label: exact in-game object name, preserving original language when visible
    description: exact in-game description text when visible
    clickable: false
    x: 0.5
    y: 0.5
    bbox:
      x1: 0.42
      y1: 0.46
      x2: 0.58
      y2: 0.54
    template_bbox:
      x1: 0.42
      y1: 0.46
      x2: 0.58
      y2: 0.54
buttons:
  - label: exact in-game button/action label, preserving original language when visible
    x: 0.5
    y: 0.5
    bbox:
      x1: 0.42
      y1: 0.46
      x2: 0.58
      y2: 0.54
    template_bbox:
      x1: 0.42
      y1: 0.46
      x2: 0.58
      y2: 0.54
    confidence: 0.8
    reason: why this is clickable and what it likely does

Do not include Markdown in the response YAML.
Use the original in-game name and description as-is whenever the game shows
them. Do not translate, summarize, or rename visible game terms. Do not
translate descriptions. Only include `game_info` when both the exact visible
name and exact visible effect/description are readable in the screenshot. If a
non-text icon needs a label for clicking, use a short stable descriptive label
for the object/button only, not as game info.
If the screen shows an item/skill/treasure name and its effect/description
together, put that exact pair in `game_info` even if it also appears in
`objects`.
For each clickable icon/object and each button, include a tight normalized bbox
around the actionable visual area or button. Also include `template_bbox` for
the reusable crop. `template_bbox` must contain exactly one clickable
button/card/icon and exclude neighboring cards, adjacent buttons, unrelated
labels, empty panel space, and duplicate UI. Include only a tiny visual border
needed for matching. If `bbox` is already exact, repeat the same coordinates in
`template_bbox`. If an icon or object can be clicked, set `clickable: true` and
use its future action name as the label.

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
    item_inspections: list[ItemInspection],
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
    lines.append(f'- OCR overlay: {artifact_paths["ocr_overlay"]}')
    if artifact_paths['llm_overlay'].exists():
        lines.append(f'- LLM overlay: {artifact_paths["llm_overlay"]}')
    lines.append(f'- OCR YAML: {artifact_paths["ocr"]}')
    lines.append(f'- LLM YAML: {artifact_paths["llm"]} (optional)')
    lines.append(f'- Metadata YAML: {artifact_paths["metadata"]}')
    lines.append(f'- Strategy memory: {memory_path}')
    lines.append(f'- Game info: {game_info_path_for(args.game)}')
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
            if verification.progress_similarities:
                similarities = ', '.join(
                    f'{similarity:.4f}'
                    for similarity in verification.progress_similarities
                )
                lines.append(
                    f'- Progress region `{verification.progress_region}` '
                    f'similarities: `{similarities}`.'
                )
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
            source = markdown_escape(str(item.get('source') or 'llm'))
            path = item.get('path')
            if path:
                lines.append(f'- **{label}**: `{status}` from `{source}` at `{path}`')
            else:
                reason = markdown_escape(str(item.get('reason') or ''))
                lines.append(f'- **{label}**: `{status}` from `{source}` {reason}')
        lines.append('')
    if item_inspections:
        lines.extend(['## Item Inspections', ''])
        for item in sorted(item_inspections, key=lambda x: x.score, reverse=True):
            reasons = ', '.join(item.reasons) if item.reasons else 'no strong cue'
            description = markdown_escape(
                item.description or 'description not captured'
            )
            lines.append(
                f'- **{markdown_escape(item.candidate.label)}**: '
                f'item score `{item.score:.2f}`; {description}; cues: {reasons}'
            )
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


def render_unblock_assessment(assessment: UnblockAssessment) -> str:
    lines = ['# Auto Play Unblock Check', '']
    lines.append(f'- Status: `{assessment.status}`')
    lines.append(f'- Reason: {assessment.reason}')
    lines.append(f'- Window size: {assessment.window_size}')
    lines.append(f'- Similarity threshold: `{assessment.threshold:.4f}`')
    if assessment.similarities:
        similarities = ', '.join(
            f'{similarity:.4f}' for similarity in assessment.similarities
        )
        lines.append(f'- Similarities: `{similarities}`')
    if assessment.repeated_actions:
        actions = ', '.join(assessment.repeated_actions)
        lines.append(f'- Recent actions: {actions}')
    if assessment.strategy_updated:
        lines.append(
            '- Strategy memory updated; the next turn will temporarily '
            'deprioritize recent repeated actions when another candidate is '
            'available.'
        )
    return '\n'.join(lines)


def should_run_periodic_ocr_tuning(args: argparse.Namespace, turn: int) -> bool:
    game = str(getattr(args, 'game', '') or '')
    if normalize_label(game) == 'tower' and load_tower_run_state(game):
        return False
    return (
        bool(args.loop)
        and args.ocr_tune_every_turns > 0
        and args.ocr_tune_iterations > 0
        and turn > 0
        and turn % args.ocr_tune_every_turns == 0
    )


def should_run_stuck_ocr_tuning(args: argparse.Namespace) -> bool:
    game = str(getattr(args, 'game', '') or '')
    if normalize_label(game) == 'tower' and load_tower_run_state(game):
        return False
    return bool(args.click_recommended) and args.ocr_tune_on_stuck_iterations > 0


def ocr_tuning_run_name(prefix: str, turn: int, iteration: int) -> str:
    return f'{prefix}-turn-{turn:06d}-iter-{iteration:02d}'


def periodic_ocr_tuning_run_name(turn: int, iteration: int) -> str:
    return ocr_tuning_run_name('periodic', turn, iteration)


def stuck_ocr_tuning_run_name(turn: int, iteration: int) -> str:
    return ocr_tuning_run_name('stuck', turn, iteration)


def periodic_ocr_tuning_output_dir(args: argparse.Namespace) -> Path:
    return args.ocr_tune_output_dir or (game_root_for(args.game) / 'ocr-tuning')


def periodic_ocr_tuning_command(
    args: argparse.Namespace,
    *,
    turn: int,
    iteration: int,
    run_name_prefix: str = 'periodic',
    recent_turns: int | None = None,
) -> list[str]:
    command = [
        sys.executable,
        str(skill_root() / 'scripts' / 'tune_ocr.py'),
        '--game',
        args.game,
        '--mode',
        'regenerate',
        '--turns-dir',
        str(turns_root(args)),
        '--output-dir',
        str(periodic_ocr_tuning_output_dir(args)),
        '--run-name',
        ocr_tuning_run_name(run_name_prefix, turn, iteration),
        '--recent-turns',
        str(recent_turns if recent_turns is not None else args.ocr_tune_recent_turns),
        '--confidence',
        str(args.confidence),
        '--template-match-threshold',
        str(args.template_match_threshold),
    ]
    return command


def latest_periodic_ocr_tuning_run(
    args: argparse.Namespace,
    *,
    turn: int,
    iteration: int,
    run_name_prefix: str = 'periodic',
) -> Path | None:
    output_dir = periodic_ocr_tuning_output_dir(args)
    prefix = ocr_tuning_run_name(run_name_prefix, turn, iteration)
    if not output_dir.exists():
        return None
    candidates = [
        path
        for path in output_dir.iterdir()
        if path.is_dir() and path.name.startswith(prefix)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def summarize_periodic_ocr_tuning_report(report_path: Path) -> str:
    report = yaml.safe_load(report_path.read_text()) or {}
    captured = int(report.get('ready_actions_captured_by_ocr', 0) or 0)
    ready = int(report.get('ready_actions', 0) or 0)
    missing = int(report.get('ready_actions_missing_from_ocr', 0) or 0)
    rate = float(report.get('capture_rate', 0.0) or 0.0) * 100.0
    return f'`{captured} / {ready}` captured (`{rate:.1f}%`), `{missing}` missing'


def ocr_tuning_report_is_complete(report_path: Path) -> bool:
    report = yaml.safe_load(report_path.read_text()) or {}
    ready = int(report.get('ready_actions', 0) or 0)
    missing = int(report.get('ready_actions_missing_from_ocr', 0) or 0)
    rate = float(report.get('capture_rate', 0.0) or 0.0)
    return ready > 0 and missing == 0 and rate >= 1.0


def run_ocr_tuning(
    args: argparse.Namespace,
    turn: int,
    *,
    title: str,
    run_name_prefix: str,
    iterations: int,
    recent_turns: int,
    reason: str,
) -> None:
    lines = [
        f'# {title}',
        '',
        f'- Trigger turn: `{turn}`',
        f'- Reason: {reason}',
        f'- Turn window: last `{recent_turns}` turns',
        f'- Iterations: `{iterations}`',
    ]
    for iteration in range(1, iterations + 1):
        command = periodic_ocr_tuning_command(
            args,
            turn=turn,
            iteration=iteration,
            run_name_prefix=run_name_prefix,
            recent_turns=recent_turns,
        )
        try:
            completed = subprocess.run(
                command,
                cwd=skill_root(),
                capture_output=True,
                text=True,
                check=False,
                timeout=args.ocr_tune_timeout,
            )
        except subprocess.TimeoutExpired:
            lines.append(
                f'- Iteration `{iteration}` timed out after '
                f'`{args.ocr_tune_timeout:.1f}` seconds; keeping play moving.'
            )
            break
        run_dir = latest_periodic_ocr_tuning_run(
            args,
            turn=turn,
            iteration=iteration,
            run_name_prefix=run_name_prefix,
        )
        if completed.returncode != 0:
            lines.append(
                f'- Iteration `{iteration}` failed with exit `{completed.returncode}`.'
            )
            stderr = completed.stderr.strip()
            if stderr:
                lines.append(f'  stderr: `{stderr.splitlines()[-1]}`')
            continue
        if run_dir is None or not (run_dir / 'report.yaml').exists():
            lines.append(f'- Iteration `{iteration}` completed; report not found.')
            continue
        report_path = run_dir / 'report.yaml'
        summary = summarize_periodic_ocr_tuning_report(report_path)
        lines.append(f'- Iteration `{iteration}`: {summary}; report `{run_dir}`')
        if ocr_tuning_report_is_complete(report_path):
            lines.append(
                '- Stopping early because OCR already captures every ready action '
                'in the recent turn window.'
            )
            break
    print('\n'.join(lines))


def run_periodic_ocr_tuning(args: argparse.Namespace, turn: int) -> None:
    run_ocr_tuning(
        args,
        turn,
        title='Periodic OCR Tuning',
        run_name_prefix='periodic',
        iterations=args.ocr_tune_iterations,
        recent_turns=args.ocr_tune_recent_turns,
        reason='Scheduled loop tuning interval.',
    )


def run_stuck_ocr_tuning(args: argparse.Namespace, turn: int, reason: str) -> None:
    run_ocr_tuning(
        args,
        turn,
        title='Stuck OCR Tuning',
        run_name_prefix='stuck',
        iterations=args.ocr_tune_on_stuck_iterations,
        recent_turns=args.ocr_tune_on_stuck_recent_turns,
        reason=reason,
    )


def clear_consumed_llm_result(args: argparse.Namespace) -> None:
    args.llm_result = None


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
    parser.add_argument(
        '--tower-daily',
        action='store_true',
        help=(
            '执行可恢复的魔塔每日流程：深渊楼梯、旅馆招募、'
            '新招募角色尖塔木屋。'
        ),
    )
    parser.add_argument(
        '--tower-daily-focus',
        choices=('workflow', 'abyss', 'spire', 'recruit_spire'),
        default='workflow',
        help=(
            '魔塔每日流程目标；abyss 会持续重开深渊且不转去招募，'
            'spire 会直接挑战尖塔，recruit_spire 会先招募一次再用新人挑战。'
        ),
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
        default=DEFAULT_TURN_HISTORY_LIMIT,
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
        '--item-inspection-limit',
        type=int,
        default=4,
        help='Maximum item choices to inspect before selecting the best one.',
    )
    parser.add_argument(
        '--item-inspection-interval',
        type=float,
        default=0.5,
        help='Seconds to wait after tapping an item before reading its description.',
    )
    parser.add_argument(
        '--item-description-label-limit',
        type=int,
        default=12,
        help='Maximum OCR labels to keep as an inspected item description.',
    )
    parser.add_argument(
        '--state-similarity-threshold',
        type=float,
        default=0.995,
        help='Post-click similarity at or above this value counts as unchanged.',
    )
    parser.add_argument(
        '--state-progress-similarity-threshold',
        type=float,
        default=0.985,
        help=(
            'Post-click stable progress-region similarity at or above this value '
            'counts as unchanged even if the animated full screen changed.'
        ),
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
    parser.add_argument(
        '--unblock-check-interval',
        type=int,
        default=5,
        help='Loop turns between stagnant-screenshot unblock checks. Use 0 to disable.',
    )
    parser.add_argument(
        '--unblock-window-size',
        type=int,
        default=5,
        help='Recent turn screenshots to compare during each unblock check.',
    )
    parser.add_argument(
        '--unblock-similarity-threshold',
        type=float,
        default=0.975,
        help=(
            'All recent screenshot similarities at or above this value count as stuck.'
        ),
    )
    parser.add_argument(
        '--ocr-tune-every-turns',
        type=int,
        default=DEFAULT_PERIODIC_OCR_TUNE_EVERY_TURNS,
        help=(
            'Loop turns between periodic OCR tuning runs. Use 0 to disable. '
            'Only applies with --loop.'
        ),
    )
    parser.add_argument(
        '--ocr-tune-iterations',
        type=int,
        default=DEFAULT_PERIODIC_OCR_TUNE_ITERATIONS,
        help='OCR tuning report iterations to run at each periodic trigger.',
    )
    parser.add_argument(
        '--ocr-tune-on-stuck-iterations',
        type=int,
        default=DEFAULT_STUCK_OCR_TUNE_ITERATIONS,
        help=(
            'OCR tuning report iterations to run immediately after stuck/no-change '
            'detection. Use 0 to disable.'
        ),
    )
    parser.add_argument(
        '--ocr-tune-on-stuck-recent-turns',
        type=int,
        default=DEFAULT_STUCK_OCR_TUNE_RECENT_TURNS,
        help=(
            'Recent turn folders to include in stuck-triggered OCR tuning. '
            'Kept smaller than periodic tuning so play can continue.'
        ),
    )
    parser.add_argument(
        '--ocr-tune-recent-turns',
        type=int,
        default=DEFAULT_PERIODIC_OCR_TUNE_RECENT_TURNS,
        help='Recent turn folders to include in each periodic OCR tuning run.',
    )
    parser.add_argument(
        '--ocr-tune-timeout',
        type=float,
        default=DEFAULT_OCR_TUNE_TIMEOUT_SECONDS,
        help='Maximum seconds to allow each OCR tuning subprocess iteration.',
    )
    parser.add_argument(
        '--ocr-tune-output-dir',
        type=Path,
        help='Optional output directory for periodic OCR tuning reports.',
    )
    args = parser.parse_args()
    if not 0.0 <= args.state_similarity_threshold <= 1.0:
        parser.error('--state-similarity-threshold must be between 0.0 and 1.0')
    if not 0.0 <= args.state_progress_similarity_threshold <= 1.0:
        parser.error(
            '--state-progress-similarity-threshold must be between 0.0 and 1.0'
        )
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
    if args.unblock_check_interval < 0:
        parser.error('--unblock-check-interval must be non-negative')
    if args.unblock_window_size < 2:
        parser.error('--unblock-window-size must be at least 2')
    if not 0.0 <= args.unblock_similarity_threshold <= 1.0:
        parser.error('--unblock-similarity-threshold must be between 0.0 and 1.0')
    if args.ocr_tune_every_turns < 0:
        parser.error('--ocr-tune-every-turns must be non-negative')
    if args.ocr_tune_iterations < 0:
        parser.error('--ocr-tune-iterations must be non-negative')
    if args.ocr_tune_on_stuck_iterations < 0:
        parser.error('--ocr-tune-on-stuck-iterations must be non-negative')
    if args.ocr_tune_on_stuck_recent_turns < 1:
        parser.error('--ocr-tune-on-stuck-recent-turns must be at least 1')
    if args.ocr_tune_recent_turns < 1:
        parser.error('--ocr-tune-recent-turns must be at least 1')
    if args.ocr_tune_timeout <= 0:
        parser.error('--ocr-tune-timeout must be greater than 0')
    if args.item_inspection_limit < 1:
        parser.error('--item-inspection-limit must be at least 1')
    if args.item_inspection_interval < 0.0:
        parser.error('--item-inspection-interval must be non-negative')
    if args.item_description_label_limit < 1:
        parser.error('--item-description-label-limit must be at least 1')
    args.force_unblock_next = False
    args.force_top_path_probe_next = False
    args.force_escape_menu_probe_next = False
    args.unblock_avoid_labels = set()
    return args


def run_turn(args: argparse.Namespace) -> TurnResult:
    debug_progress('turn: create artifacts')
    artifact_paths, timestamp = create_turn_artifacts(args)

    debug_progress('turn: load image')
    image, metadata = load_image(args)
    args.current_device_serial = metadata.get('serial') or metadata.get('device_serial')

    debug_progress('turn: save screenshot')
    artifact_paths['screen'].parent.mkdir(parents=True, exist_ok=True)
    image.save(artifact_paths['screen'])
    image = Image.open(artifact_paths['screen']).convert('RGB')
    if args.save_screen:
        args.save_screen.parent.mkdir(parents=True, exist_ok=True)
        image.save(args.save_screen)

    memory_path = ensure_strategy_memory(args.game)
    memory = load_memory(args.game)
    strategy_text = load_strategy_text(args.game)
    automation_config = load_automation_config(args.game)
    llm_result_path = stage_llm_result(args.llm_result, artifact_paths['llm'])
    debug_progress('turn: analyze buttons')
    external_recovery = (
        None
        if args.image
        else external_android_recovery_candidate(args.game, metadata)
    )
    if external_recovery is not None:
        new_tower_battle = False
        fast_tower_combat = False
        detected_buttons = [external_recovery]
        debug_progress('turn: recover from external Android package; skip OCR')
    else:
        new_tower_battle = tower_battle_needs_initial_read(args.game, image)
        fast_tower_combat = bool(
            tower_fast_combat_buttons(image, automation_config)
        ) and not new_tower_battle and not tower_battle_requires_precise_read(
            args.game
        ) and not tower_daily_result_requires_ocr(
            args.game, getattr(args, 'tower_daily', False)
        )
        if fast_tower_combat:
            debug_progress('turn: tower combat CV fast path; skip OCR')
            detected_buttons = tower_fast_combat_buttons(image, automation_config)
        else:
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
    llm_buttons = load_llm_buttons(llm_result_path, automation_config)
    llm_icon_buttons = load_llm_icon_candidates(llm_result_path, automation_config)
    llm_candidates = [*llm_buttons, *llm_icon_buttons]
    learned_templates = learn_templates_from_llm(
        game=args.game,
        image=image,
        llm_buttons=llm_candidates,
        non_llm_buttons=[*ocr_buttons, *template_buttons],
        turn_name=artifact_paths['turn_dir'].name,
    )
    if not fast_tower_combat and any(
        item.get('status') == 'saved' for item in learned_templates
    ):
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
    if new_tower_battle:
        start_tower_battle_state(args.game, image, detected_buttons)
    update_tower_run_state(args.game, image, detected_buttons)
    save_turn_detection_overlays(
        image,
        artifact_paths=artifact_paths,
        ocr_buttons=ocr_buttons,
        template_buttons=template_buttons,
        llm_buttons=llm_candidates,
    )
    debug_progress('turn: score buttons')
    candidate_buttons = filter_conflicting_template_buttons(
        [*ocr_buttons, *template_buttons, *llm_candidates]
    )
    candidate_buttons = filter_configured_non_action_buttons(
        automation_config,
        candidate_buttons,
    )
    recent_actions = recent_action_labels(turns_root(args), 6)
    recent_successful_actions = recent_successful_action_labels(
        turns_root(args),
        6,
    )
    candidate_buttons = [
        *candidate_buttons,
        *configured_extra_candidates(
            automation_config,
            candidate_buttons,
            recent_actions=recent_actions,
            image=image,
            context_buttons=detected_buttons,
        ),
    ]
    candidate_buttons = [
        *candidate_buttons,
        *configured_image_candidates(automation_config, image, detected_buttons),
        *tower_recruit_blocking_modal_candidates(args.game, image),
    ]
    candidate_buttons = filter_configured_disabled_gray_buttons(
        automation_config,
        image,
        candidate_buttons,
    )
    if getattr(args, 'tower_daily', False):
        update_tower_daily_state(
            args.game,
            merge_buttons([*candidate_buttons, *detected_buttons]),
        )
        run_state = load_tower_run_state(args.game)
        daily_state = load_tower_daily_state(args.game)
        daily_phase = normalize_label(str(daily_state.get('phase') or ''))
        run_stage = normalize_label(str(run_state.get('stage') or ''))
        run_phase = normalize_label(str(run_state.get('phase') or ''))
        if (
            (
                run_state.get('reroll_predecessor')
                or (daily_phase == 'go_to_spire' and run_stage == '深渊楼梯')
            )
            and run_phase in {'combat', 'climbing_map', 'prebattle'}
        ):
            candidate_buttons = [
                *candidate_buttons,
                *(
                    button
                    for button in [*detected_buttons, *ocr_buttons]
                    if normalize_label(button.label) in {'设置', 'settings'}
                    and all(
                        normalize_label(existing.label)
                        != normalize_label(button.label)
                        for existing in candidate_buttons
                    )
                ),
            ]
        daily_buttons = tower_daily_policy_candidates(args.game, candidate_buttons)
        if daily_buttons is not None:
            candidate_buttons = daily_buttons
    if google_play_purchase_sheet_visible(candidate_buttons):
        candidate_buttons = [
            android_back_candidate(
                'Google Play purchase sheet is visible; press Android Back '
                'to avoid buying anything.'
            )
        ]
    elif android_system_screen_visible(candidate_buttons):
        candidate_buttons = [wait_for_android_unlock_candidate()]
    elif is_mostly_blank_screen(image) or is_loading_spinner_screen(image):
        if repeated_blank_wait_detected(recent_actions):
            candidate_buttons = [
                android_back_candidate(
                    'Blank/loading screen repeated without progress; '
                    'press Android Back to escape the blocked transition.'
                )
            ]
        else:
            candidate_buttons = [wait_for_loading_candidate()]
    elif not candidate_buttons and automation_config.empty_screen_candidate is not None:
        candidate_buttons = [automation_config.empty_screen_candidate.to_button()]
    if getattr(args, 'force_escape_menu_probe_next', False):
        candidate_buttons = [
            *candidate_buttons,
            *escape_menu_probe_candidates(),
        ]
        args.unblock_avoid_labels = set(
            getattr(args, 'unblock_avoid_labels', set())
        ) | {
            normalize_label(button.label)
            for button in candidate_buttons
            if is_navigation_arrow_label(button.label, automation_config)
        }
        args.force_escape_menu_probe_next = False
        args.force_top_path_probe_next = False
    elif getattr(args, 'force_top_path_probe_next', False):
        candidate_buttons = [
            *candidate_buttons,
            *top_playfield_path_probe_candidates(
                candidate_buttons,
                automation_config,
            ),
        ]
        args.force_top_path_probe_next = False
    energy_empty_visible = configured_energy_empty_visible(
        automation_config,
        candidate_buttons,
    )
    energy_empty_navigation_turns = int(
        getattr(args, 'energy_empty_navigation_turns', 0)
    )
    if energy_empty_visible:
        args.energy_empty_navigation_turns = max(energy_empty_navigation_turns, 6)
    elif energy_empty_navigation_turns > 0:
        args.energy_empty_navigation_turns = energy_empty_navigation_turns - 1
        candidate_buttons.append(
            ButtonCandidate(
                label='Not enough Energy',
                x=0.5,
                y=0.38,
                confidence=0.01,
                clickability=0.0,
                source='state',
                reason=(
                    'Recent low-energy popup; keep navigating toward the '
                    'configured low-energy fallback destination.'
                ),
            )
        )
    if (
        energy_empty_visible
        or int(getattr(args, 'energy_empty_navigation_turns', 0)) > 0
    ) and automation_config.energy_empty_candidate is not None:
        candidate_buttons.append(automation_config.energy_empty_candidate.to_button())
    buttons = score_buttons(
        merge_buttons(candidate_buttons),
        memory,
        automation_config,
        recent_actions=recent_actions,
        recent_successful_actions=recent_successful_actions,
    )
    daily_state = (
        load_tower_daily_state(args.game)
        if getattr(args, 'tower_daily', False)
        else {}
    )
    completion_reason = configured_level_grid_complete_reason(
        automation_config,
        buttons,
        recent_actions=recent_actions,
    )
    if normalize_label(str(daily_state.get('phase') or '')) == 'complete':
        decision = Decision(
            status='complete',
            reason=tower_daily_completion_reason(daily_state),
            recommended=None,
            choices=[],
        )
    elif completion_reason is not None:
        decision = Decision(
            status='complete',
            reason=completion_reason,
            recommended=None,
            choices=[],
        )
    else:
        decision = decide_next_move(
            buttons,
            min_action_score=args.min_action_score,
            ambiguity_margin=args.ambiguity_margin,
            ask_on_ambiguous=args.ask_on_ambiguous,
            fallback_labels={
                normalize_label(label) for label in memory.get('fallback', [])
            },
            automation_config=automation_config,
        )
    if getattr(args, 'force_unblock_next', False):
        decision = decide_unblock_move(
            buttons,
            getattr(args, 'unblock_avoid_labels', set()),
        )
        args.force_unblock_next = False
    item_inspections: list[ItemInspection] = []
    inspected_decision = None
    if decision.status == 'ready':
        label = decision.recommended.label if decision.recommended else 'none'
        debug_progress(f'turn: inspect choices for {label}')
        item_inspections, inspected_decision = inspect_item_choices(
            args,
            buttons=buttons,
            memory=memory,
            artifact_paths=artifact_paths,
            automation_config=automation_config,
        )
    if inspected_decision is not None:
        decision = inspected_decision

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
        debug_progress(f'turn: click {clicked.label}')
        click_button(args, clicked)
        if fast_tower_combat and is_configured_combat_card_label(
            clicked.label,
            automation_config,
        ):
            follow_up = tower_fast_batch_follow_up(buttons)
            if follow_up is not None:
                debug_progress('turn: fast combat batch follow-up')
                time.sleep(0.2)
                click_button(args, follow_up)
        debug_progress('turn: verify state change')
        verification = verify_state_changed_after_click(
            args,
            before_image=image,
            button=clicked,
            last_screenshot_path=artifact_paths['last_screen'],
        )
        update_main_challenge_progress_after_action(
            args.game,
            automation_config,
            buttons,
            clicked,
        )
        update_tower_run_state(
            args.game,
            image,
            merge_buttons([*detected_buttons, *buttons]),
            clicked_label=clicked.label,
            action_succeeded=bool(
                verification is not None and verification.status == 'changed'
            ),
        )
        if getattr(args, 'tower_daily', False):
            update_tower_daily_state(
                args.game,
                detected_buttons,
                clicked_label=clicked.label,
                action_succeeded=bool(
                    verification is not None and verification.status == 'changed'
                ),
            )

    debug_progress('turn: write artifacts')
    write_ocr_yaml(
        artifact_paths['ocr'],
        game=args.game,
        image=image,
        metadata=metadata,
        strategy_path=memory_path,
        ocr_buttons=ocr_buttons,
        template_buttons=template_buttons,
        llm_buttons=llm_candidates,
        learned_templates=learned_templates,
        buttons=buttons,
        decision=decision,
        verification=verification,
        item_inspections=item_inspections,
    )
    if not fast_tower_combat or item_inspections or llm_candidates:
        debug_progress('turn: refresh durable game info')
        write_game_info_markdown(args.game)
    else:
        debug_progress('turn: skip durable game info during Tower combat fast path')
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
        llm_used=bool(llm_candidates),
        learned_templates=learned_templates,
        item_inspections=item_inspections,
    )

    debug_progress('turn: render report')
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
        item_inspections,
    )
    print(report, flush=True)
    return TurnResult(decision=decision, verification=verification)


def run_main(args: argparse.Namespace) -> int:
    if args.remember_choice:
        if not args.choice_reason:
            raise SystemExit('--choice-reason is required with --remember-choice')
        append_learned_choice(args.game, args.remember_choice, args.choice_reason)
    if getattr(args, 'tower_daily', False):
        ensure_tower_daily_state(args.game)
        configure_tower_daily_focus(args.game, args.tower_daily_focus)

    turn = 0
    unchanged_restarts = 0
    while True:
        turn += 1
        if args.loop:
            automation_config = load_automation_config(args.game)
            oscillation_avoid_labels = navigation_oscillation_avoid_labels(
                turns_root(args),
                automation_config=automation_config,
            )
            navigation_loop_avoid_labels = oscillation_avoid_labels or (
                navigation_only_loop_avoid_labels(
                    turns_root(args),
                    automation_config=automation_config,
                )
            )
            if navigation_loop_avoid_labels:
                args.force_unblock_next = True
                if any(
                    label.startswith('top path')
                    for label in navigation_loop_avoid_labels
                ):
                    args.force_escape_menu_probe_next = True
                else:
                    args.force_top_path_probe_next = True
                args.unblock_avoid_labels = (
                    set(getattr(args, 'unblock_avoid_labels', set()))
                    | navigation_loop_avoid_labels
                )
        result = run_turn(args)
        clear_consumed_llm_result(args)
        no_change = (
            result.verification is not None
            and result.verification.status == 'unchanged'
        )
        if no_change and result.decision.recommended is not None:
            args.force_unblock_next = True
            args.unblock_avoid_labels = {
                normalize_label(result.decision.recommended.label)
            }
        stuck_tuning_ran = False
        if no_change and should_run_stuck_ocr_tuning(args):
            run_stuck_ocr_tuning(
                args,
                turn,
                'State verification found no stable progress after the clicked action.',
            )
            stuck_tuning_ran = True
        unblock_assessment = None
        if (
            args.loop
            and args.unblock_check_interval
            and turn % args.unblock_check_interval == 0
        ):
            unblock_assessment = assess_unblock_window(
                turns_root(args),
                window_size=args.unblock_window_size,
                threshold=args.unblock_similarity_threshold,
            )
            if unblock_assessment.status == 'stuck':
                strategy_updated = append_unblock_learning(
                    args.game,
                    unblock_assessment,
                )
                unblock_assessment = replace(
                    unblock_assessment,
                    strategy_updated=strategy_updated,
                )
                args.force_unblock_next = True
                args.unblock_avoid_labels = {
                    normalize_label(label)
                    for label in unblock_assessment.repeated_actions
                }
                if should_run_stuck_ocr_tuning(args) and not stuck_tuning_ran:
                    run_stuck_ocr_tuning(
                        args,
                        turn,
                        'Recent turn screenshots stayed similar during unblock check.',
                    )
                    stuck_tuning_ran = True
            print(render_unblock_assessment(unblock_assessment))
        if should_run_periodic_ocr_tuning(args, turn):
            run_periodic_ocr_tuning(args, turn)
        if no_change and not args.loop:
            if unchanged_restarts < args.max_unchanged_restarts:
                unchanged_restarts += 1
                time.sleep(args.interval)
                continue
            break

        if args.max_turns and turn >= args.max_turns:
            break
        if not args.loop or result.decision.status != 'ready':
            if (
                args.loop
                and unblock_assessment is not None
                and unblock_assessment.status == 'stuck'
            ):
                time.sleep(args.interval)
                continue
            break
        time.sleep(args.interval)
    return 0


def main() -> int:
    args = parse_args()
    try:
        return run_main(args)
    finally:
        close_live_mcp_client()


if __name__ == '__main__':
    raise SystemExit(main())

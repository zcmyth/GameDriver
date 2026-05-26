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
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from shutil import rmtree
from typing import Any

import numpy as np
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
CANCEL_LABELS = {
    'cancel',
    '取消',
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
DEFAULT_TURN_HISTORY_LIMIT = 500
DEFAULT_PERIODIC_OCR_TUNE_EVERY_TURNS = 50
DEFAULT_PERIODIC_OCR_TUNE_ITERATIONS = 10
DEFAULT_PERIODIC_OCR_TUNE_RECENT_TURNS = 50
DEFAULT_STUCK_OCR_TUNE_ITERATIONS = 10
DEFAULT_STUCK_OCR_TUNE_RECENT_TURNS = 10
DEFAULT_OCR_TUNE_TIMEOUT_SECONDS = 60.0
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
    'tower map',
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
    re.compile(r'^\d+[./:]?\d*[kmb%]?$', re.I),
    re.compile(r'^lv[.\s]*\d+$', re.I),
    re.compile(r'^v[.\s]*\d+$', re.I),
    re.compile(r'^[x×]\s*\d+$', re.I),
    re.compile(r'^[x×][x*×]\s*\d+$', re.I),
    re.compile(r'^[a-z]\s*\d+$', re.I),
    re.compile(r'^[()\[\]{}%.,:;!?+\-*/\\|_~<>]+$'),
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
class AutomationCandidateSpec:
    label: str
    x: float
    y: float
    clickability: float
    reason: str = ''
    confidence: float = 1.0
    source: str = 'vision'

    def to_button(self) -> ButtonCandidate:
        return ButtonCandidate(
            label=self.label,
            x=max(0.0, min(1.0, self.x)),
            y=max(0.0, min(1.0, self.y)),
            confidence=max(0.0, min(1.0, self.confidence)),
            clickability=self.clickability,
            source=self.source,
            reason=self.reason,
        )


@dataclass(frozen=True)
class AutomationRowCandidateSpec:
    label: str
    x: float
    y_offset: float
    clickability: float
    reason: str = ''
    confidence: float = 1.0
    source: str = 'vision'

    def to_button_for_row(
        self,
        row: ButtonCandidate,
        *,
        x: float | None = None,
    ) -> ButtonCandidate:
        return ButtonCandidate(
            label=self.label,
            x=max(0.0, min(1.0, self.x if x is None else x)),
            y=max(0.12, min(0.90, row.y + self.y_offset)),
            confidence=max(0.0, min(1.0, self.confidence)),
            clickability=self.clickability,
            source=self.source,
            reason=self.reason,
        )


@dataclass(frozen=True)
class AutomationRepeatedActionSwipeSpec:
    trigger_label: str
    min_count: int
    label: str
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    clickability: float
    reason: str = ''
    confidence: float = 1.0

    def to_button(self) -> ButtonCandidate:
        return ButtonCandidate(
            label=self.label,
            x=max(0.0, min(1.0, self.end_x)),
            y=max(0.0, min(1.0, self.end_y)),
            confidence=max(0.0, min(1.0, self.confidence)),
            clickability=self.clickability,
            source='swipe',
            reason=self.reason,
            bbox=(
                max(0.0, min(1.0, self.start_x)),
                max(0.0, min(1.0, self.start_y)),
                max(0.0, min(1.0, self.end_x)),
                max(0.0, min(1.0, self.end_y)),
            ),
        )


@dataclass(frozen=True)
class GameAutomationConfig:
    game: str
    noise_pattern_text: tuple[str, ...] = ()
    noise_patterns: tuple[re.Pattern[str], ...] = ()
    navigation_labels: frozenset[str] = frozenset()
    navigation_keywords: tuple[str, ...] = ()
    navigation_glyphs: tuple[str, ...] = ()
    command_labels: frozenset[str] = frozenset()
    defeat_recovery_labels: frozenset[str] = frozenset()
    recruit_labels: frozenset[str] = frozenset()
    combat_card_double_tap_labels: frozenset[str] = frozenset()
    current_room_icon_labels: frozenset[str] = frozenset()
    claimed_labels: frozenset[str] = frozenset()
    reward_overlay_labels: frozenset[str] = frozenset()
    reward_close_labels: frozenset[str] = frozenset()
    passive_non_action_labels: frozenset[str] = frozenset()
    result_progress_labels: frozenset[str] = frozenset()
    skill_choice_required_labels: tuple[str, ...] = ()
    skill_choice_instruction_labels: tuple[str, ...] = ()
    skill_choice_split_instruction_labels: tuple[tuple[str, ...], ...] = ()
    skill_choice_ignored_labels: frozenset[str] = frozenset()
    level_row_patterns: tuple[re.Pattern[str], ...] = ()
    challenge_detail_action_labels: frozenset[str] = frozenset()
    challenge_detail_patterns: tuple[re.Pattern[str], ...] = ()
    recent_reentry_keywords: tuple[str, ...] = ()
    waiting_required_groups: tuple[tuple[str, ...], ...] = ()
    waiting_hint_groups: tuple[tuple[str, ...], ...] = ()
    shop_screen_required_groups: tuple[tuple[str, ...], ...] = ()
    safe_confirm_required_groups: tuple[tuple[str, ...], ...] = ()
    energy_empty_labels: frozenset[str] = frozenset()
    energy_empty_destination_labels: frozenset[str] = frozenset()
    energy_empty_action_exemption_labels: frozenset[str] = frozenset()
    energy_empty_candidate: AutomationCandidateSpec | None = None
    shop_escape_candidate: AutomationCandidateSpec | None = None
    empty_screen_candidate: AutomationCandidateSpec | None = None
    waiting_candidate: AutomationCandidateSpec | None = None
    claimed_back_candidate: AutomationCandidateSpec | None = None
    third_column_unclaimed_row_candidate: AutomationRowCandidateSpec | None = None
    repeated_action_swipe_candidate: AutomationRepeatedActionSwipeSpec | None = None
    disabled_visual_filters: frozenset[str] = frozenset()
    passive_nameplate_region: tuple[float, float, float, float, float] | None = None
    main_screen_verification_labels: frozenset[str] = frozenset()
    always_preferred_choice_terms: tuple[str, ...] = ()
    ignored_game_info_types: frozenset[str] = frozenset()
    no_change_skill_choice_rule: str = ''
    no_change_empty_screen_rule: str = ''


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
    progress_threshold: float
    progress_similarities: list[float]
    progress_region: str
    strategy_updated: bool = False
    last_screenshot: str | None = None


@dataclass(frozen=True)
class UnblockAssessment:
    status: str
    reason: str
    window_size: int
    threshold: float
    similarities: list[float]
    turn_dirs: list[str]
    repeated_actions: list[str]
    strategy_updated: bool = False


@dataclass(frozen=True)
class TurnResult:
    decision: Decision
    verification: StateVerification | None


@dataclass(frozen=True)
class ItemInspection:
    candidate: ButtonCandidate
    description: str
    score: float
    reasons: list[str]
    screenshot: str
    ocr_labels: list[str]
    kind: str | None = None


@dataclass(frozen=True)
class GameInfoEntry:
    label: str
    kind: str
    description: str
    score: float
    reasons: list[str]
    sources: list[str]
    seen_count: int
    first_seen: str
    last_seen: str
    last_screenshot: str


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


def is_combat_card_label(value: str) -> bool:
    return normalize_label(value) in COMBAT_CARD_DOUBLE_TAP_LABELS


def is_configured_combat_card_label(
    value: str,
    automation_config: GameAutomationConfig | None = None,
) -> bool:
    key = normalize_label(value)
    if key in COMBAT_CARD_DOUBLE_TAP_LABELS:
        return True
    if automation_config is None:
        return False
    return key in automation_config.combat_card_double_tap_labels


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
    if not automation_config.claimed_labels:
        return False
    for button in buttons:
        key = normalize_label(button.label)
        if key in automation_config.claimed_labels:
            return True
        if any(label in key for label in automation_config.claimed_labels):
            return True
    return False


def configured_reward_overlay_visible(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    if not automation_config.reward_overlay_labels:
        return False
    return any(
        normalize_label(button.label) in automation_config.reward_overlay_labels
        for button in buttons
        if button.source != 'template'
    )


def configured_reward_close_visible(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    if not automation_config.reward_close_labels:
        return False
    return any(
        configured_reward_close_label_match(button.label, automation_config)
        for button in buttons
        if button.source != 'template'
    )


def configured_reward_close_label_match(
    label: str,
    automation_config: GameAutomationConfig | None,
) -> bool:
    if automation_config is None or not automation_config.reward_close_labels:
        return False
    key = normalize_label(label)
    if key in automation_config.reward_close_labels:
        return True
    if 'skip' in key and any(
        'skip' in close_label for close_label in automation_config.reward_close_labels
    ):
        return True
    return any(
        len(key) >= 4
        and len(close_label) >= 4
        and (key in close_label or close_label in key)
        for close_label in automation_config.reward_close_labels
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
    return any(
        pattern.search(label) for pattern in automation_config.level_row_patterns
    )


def configured_level_grid_visible(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    return any(
        configured_level_row_label(automation_config, button.label)
        for button in buttons
        if button.source != 'template'
    )


def configured_level_rows(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    return [
        button
        for button in buttons
        if button.source != 'template'
        and configured_level_row_label(automation_config, button.label)
    ]


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


def configured_challenge_detail_visible(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    if (
        not automation_config.challenge_detail_action_labels
        or not automation_config.challenge_detail_patterns
    ):
        return False
    labels = [
        normalize_label(button.label)
        for button in buttons
        if button.source != 'template'
    ]
    action_visible = any(
        label in automation_config.challenge_detail_action_labels for label in labels
    )
    chapter_visible = any(
        pattern.search(label)
        for label in labels
        for pattern in automation_config.challenge_detail_patterns
    )
    return action_visible and chapter_visible


def configured_claimed_y_positions(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[float]:
    return [
        button.y for button in configured_claimed_buttons(automation_config, buttons)
    ]


def configured_claimed_buttons(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    if not automation_config.claimed_labels:
        return []
    return [
        button
        for button in buttons
        if normalize_label(button.label) in automation_config.claimed_labels
        or any(
            label in normalize_label(button.label)
            for label in automation_config.claimed_labels
        )
    ]


def configured_recently_reentered(
    automation_config: GameAutomationConfig,
    recent_actions: list[str] | None,
) -> bool:
    if not automation_config.recent_reentry_keywords:
        return False
    return any(
        keyword in normalize_label(label)
        for label in recent_actions or []
        for keyword in automation_config.recent_reentry_keywords
    )


def configured_third_column_unclaimed_row_candidate(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> ButtonCandidate | None:
    spec = automation_config.third_column_unclaimed_row_candidate
    if spec is None:
        return None
    claimed_buttons = configured_claimed_buttons(automation_config, buttons)
    rows = sorted(
        configured_level_rows(automation_config, buttons),
        key=lambda button: button.y,
    )
    if not rows:
        return None

    max_safe_click_y = 0.86
    deepest_claimed_y = (
        max(claimed.y for claimed in claimed_buttons) if claimed_buttons else None
    )
    for row in sorted(rows, key=lambda button: button.y, reverse=True):
        if row.y + spec.y_offset > max_safe_click_y:
            continue
        row_button = spec.to_button_for_row(row)
        if deepest_claimed_y is not None and row_button.y <= deepest_claimed_y + 0.03:
            continue
        row_claimed = any(
            abs(claimed.y - row_button.y) <= 0.12 for claimed in claimed_buttons
        )
        if not row_claimed:
            return row_button
    return None


def main_challenge_scroll_candidate() -> ButtonCandidate:
    return ButtonCandidate(
        label='Scroll main challenge to higher levels',
        x=0.5,
        y=0.55,
        confidence=1.0,
        clickability=3.0,
        source='swipe',
        reason='Visible main-challenge cells are claimed; scroll for higher levels.',
        bbox=(0.5, 0.78, 0.5, 0.35),
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


def configured_extra_candidates(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
    recent_actions: list[str] | None = None,
) -> list[ButtonCandidate]:
    extras: list[ButtonCandidate] = []
    repeated_swipe = configured_repeated_action_swipe_candidate(
        automation_config,
        buttons,
        recent_actions,
    )
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
    third_column = configured_third_column_unclaimed_row_candidate(
        automation_config,
        buttons,
    )
    if configured_claimed_visible(automation_config, buttons):
        if (
            configured_recently_reentered(automation_config, recent_actions)
            and third_column
        ):
            extras.append(third_column)
        elif configured_recently_reentered(automation_config, recent_actions):
            extras.append(main_challenge_scroll_candidate())
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


def memory_path_for(game: str) -> Path:
    return game_root_for(game) / 'strategy.md'


def game_info_path_for(game: str) -> Path:
    return game_root_for(game) / 'game_info.md'


def ocr_config_path_for(game: str) -> Path:
    return game_root_for(game) / 'ocr_config.yaml'


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
        energy_empty_candidate=parse_first_candidate_section(
            text,
            'Automation Energy Empty Candidate',
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
    key = normalize_label(button.label)
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

    automation_config = load_automation_config(game)
    analyzer = create_analyzer(
        template_dirs=[template_images_dir_for(game)],
        template_match_threshold=template_match_threshold,
        template_configs=load_ocr_config(game),
        noise_text_patterns=list(automation_config.noise_pattern_text),
        navigation_template_labels=list(automation_config.navigation_labels),
        navigation_template_keywords=list(automation_config.navigation_keywords),
        navigation_template_glyphs=list(automation_config.navigation_glyphs),
    )
    locations = analyzer.extract_text_locations(image, confidence_threshold=confidence)
    buttons = []
    for item in locations:
        label = str(item.get('text', '')).strip()
        if not label or looks_like_noise_label(label, automation_config):
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
                score=float(item.get('score') or 0.0),
            )
        )
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
    if key in CONFIRM_LABELS or is_configured_command_label(
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


def is_configured_disabled_gray_button(
    automation_config: GameAutomationConfig,
    image: Image.Image,
    button: ButtonCandidate,
) -> bool:
    if 'gray-disabled-buttons' not in automation_config.disabled_visual_filters:
        return False
    if button.source == 'vision':
        return False
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
        if not is_configured_disabled_gray_button(automation_config, image, button)
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

    if compact_term == 'drone':
        return 'dron' in compact_text
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
) -> tuple[float, list[str]]:
    score, reasons = item_preference_score(label, description)
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
) -> tuple[float, list[str]]:
    score, reasons = configured_item_preference_score(
        label,
        description,
        automation_config,
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
        score, fallback_reasons = record_score_and_reasons(
            label,
            description,
            automation_config,
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
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = safe_load_yaml_mapping(path)
    if not payload:
        return loose_llm_object_records_from_yaml(path, automation_config)
    summary = str(payload.get('summary') or '').strip()
    records = llm_records_from_items(
        payload.get('game_info', []),
        path,
        source='llm game_info',
        summary=summary,
        automation_config=automation_config,
    )
    records.extend(
        llm_records_from_items(
            payload.get('objects', []),
            path,
            source='llm object',
            summary=summary,
            require_durable=True,
            automation_config=automation_config,
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
        records.extend(inspection_records_from_yaml(path, automation_config))
    for turn_dir in game_turn_dirs(game):
        records.extend(llm_records_from_yaml(turn_dir / 'llm.yaml', automation_config))
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
        '## Ranking',
        '',
    ]
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
) -> list[ButtonCandidate]:
    preferred = {normalize_label(item) for item in memory['preferred']}
    avoid = {normalize_label(item) for item in memory['avoid']}
    ineffective = {normalize_label(item) for item in memory['ineffective']}
    non_end_buttons = [
        button for button in buttons if normalize_label(button.label) != 'end'
    ]
    navigation_arrow_count = sum(
        1
        for button in buttons
        if is_navigation_arrow_label(button.label, automation_config)
    )
    navigation_arrow_visible = navigation_arrow_count > 0
    combat_card_count = sum(
        1
        for button in non_end_buttons
        if is_configured_combat_card_label(button.label, automation_config)
    )
    end_visible = any(normalize_label(button.label) == 'end' for button in buttons)
    playable_combat_card_visible = combat_card_count > 0
    ad_revive_context = is_ad_revive_context(buttons)
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
    defeat_recovery_labels = set(DEFEAT_RECOVERY_LABELS)
    recruit_labels = set(RECRUIT_LABELS)
    current_room_labels = set(CURRENT_ROOM_ICON_LABELS)
    energy_empty_destination_labels: set[str] = set()
    if automation_config is not None:
        defeat_recovery_labels |= set(automation_config.defeat_recovery_labels)
        recruit_labels |= set(automation_config.recruit_labels)
        current_room_labels |= set(automation_config.current_room_icon_labels)
        energy_empty_destination_labels = set(
            automation_config.energy_empty_destination_labels
        )
    scored = []
    for button in buttons:
        key = normalize_label(button.label)
        score = button.confidence + (0.4 * button.clickability)
        if key in preferred:
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
                key in {'steamroll', 'start', 'battle', 'fight'}
                and not energy_empty_action_exemption_visible
            ):
                score -= 3.0
        if energy_empty_action_exemption_visible and key == 'start':
            score += 3.0
        if assist_pack_popup_visible:
            dismiss_ineffective = 'dismiss assist pack popup' in ineffective
            if key == 'dismiss assist pack popup' and not dismiss_ineffective:
                score += 5.0
            elif key == 'dismiss assist pack popup':
                score -= 4.0
            elif key == 'view' and dismiss_ineffective:
                score += 4.0
            elif key in {'start', 'steamroll', 'battle', 'fight', 'view'}:
                score -= 5.0
        if shop_screen_visible and key == shop_escape_label:
            score += 4.0
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
            elif key in {'start', 'steamroll', 'battle', 'fight'}:
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
        if key in avoid and not (ad_revive_context and key in CANCEL_LABELS):
            score -= 1.25
        if ad_revive_context and key in CANCEL_LABELS:
            score += 1.5
        if ad_revive_context and is_watch_ad_button(button):
            score -= 2.5
        if key in defeat_recovery_labels:
            score += 2.5
        if key in recruit_labels:
            score += 2.5
        if key in current_room_labels and navigation_arrow_visible and not end_visible:
            score -= 1.75
        if is_configured_combat_card_label(button.label, automation_config):
            score += 0.8
            if (
                button.source == 'template'
                and navigation_arrow_visible
                and not end_visible
                and combat_card_count < 3
            ):
                score -= 2.75
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
        if key == 'end' and playable_combat_card_visible:
            score -= 0.75
        if key == 'end' and not non_end_buttons:
            score = max(score, 1.05)
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


def is_ad_revive_context(buttons: list[ButtonCandidate]) -> bool:
    for button in buttons:
        text = normalize_label(f'{button.label} {button.reason}')
        if any(hint in text for hint in AD_REVIVE_HINTS):
            return True
        if 'revive' in text and 'ad' in text:
            return True
        if '复活' in text and '广告' in text:
            return True
    return False


def is_watch_ad_button(button: ButtonCandidate) -> bool:
    key = normalize_label(button.label)
    text = normalize_label(f'{button.label} {button.reason}')
    if key in WATCH_AD_LABELS:
        return True
    if 'watch' in key and 'ad' in text:
        return True
    return '观看' in key and '广告' in text


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

    fallback_labels = fallback_labels or set()
    viable_non_fallback = [
        button
        for button in buttons
        if button.score >= min_action_score
        and normalize_label(button.label) not in fallback_labels
        and not is_navigation_arrow_label(button.label, automation_config)
    ]
    candidates = viable_non_fallback or buttons
    top = candidates[0]
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
    command = (
        shlex.split(args.mcp_command) if args.mcp_command else default_mcp_command()
    )
    with McpClient(command, timeout=args.timeout) as client:
        if is_swipe_candidate(button):
            client.call_tool('swipe', swipe_arguments_for_button(button))
            return
        if is_back_candidate(button):
            client.call_tool('back', {})
            return
        client.call_tool('click', {'x': button.x, 'y': button.y})
        if should_double_click_button(button, load_automation_config(args.game)):
            time.sleep(0.3)
            client.call_tool('click', {'x': button.x, 'y': button.y})


def should_double_click_button(
    button: ButtonCandidate,
    automation_config: GameAutomationConfig | None = None,
) -> bool:
    return is_configured_combat_card_label(button.label, automation_config)


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
        )
        inspection = ItemInspection(
            candidate=candidate,
            description=description,
            score=item_score,
            reasons=reasons,
            screenshot=str(Path('item_inspections') / screenshot_name),
            ocr_labels=labels,
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


def progress_region_for_button(
    image: Image.Image,
    button: ButtonCandidate,
    automation_config: GameAutomationConfig | None = None,
) -> tuple[str, tuple[int, int, int, int]]:
    width, height = image.size
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


def action_label_from_metadata(turn_dir: Path) -> str | None:
    metadata_path = turn_dir / 'metadata.yaml'
    if not metadata_path.exists():
        return None
    payload = yaml.safe_load(metadata_path.read_text()) or {}
    action = (payload.get('worklog') or {}).get('action_taken') or {}
    label = str(action.get('label') or '').strip()
    return label or None


def recent_action_labels(root: Path, limit: int) -> list[str]:
    labels = [
        label
        for turn_dir in recent_turn_dirs(root, limit * 4)
        if (label := action_label_from_metadata(turn_dir))
    ]
    return labels[-limit:]


def repeated_blank_wait_detected(
    recent_actions: list[str],
    *,
    min_repeats: int = 3,
) -> bool:
    wait_label = normalize_label(wait_for_loading_candidate().label)
    wait_count = sum(
        1 for label in recent_actions if normalize_label(label) == wait_label
    )
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

    candidates = [
        button
        for button in buttons
        if normalize_label(button.label) not in repeated_actions
    ]
    if not candidates:
        candidates = buttons
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
    for attempt in range(1, args.state_change_retries + 1):
        time.sleep(args.state_change_interval)
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
        if attempt < args.state_change_retries:
            click_button(args, button)

    verification = StateVerification(
        status='unchanged',
        reason=(
            f'Screen did not show stable progress after '
            f'{args.state_change_retries} click attempts. Full-screen '
            f'similarity threshold: {threshold:.4f}; {progress_region} '
            f'threshold: {args.state_progress_similarity_threshold:.4f}.'
        ),
        attempts=args.state_change_retries,
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
    return (
        bool(args.loop)
        and args.ocr_tune_every_turns > 0
        and args.ocr_tune_iterations > 0
        and turn > 0
        and turn % args.ocr_tune_every_turns == 0
    )


def should_run_stuck_ocr_tuning(args: argparse.Namespace) -> bool:
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
    automation_config = load_automation_config(args.game)
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
    save_turn_detection_overlays(
        image,
        artifact_paths=artifact_paths,
        ocr_buttons=ocr_buttons,
        template_buttons=template_buttons,
        llm_buttons=llm_candidates,
    )
    candidate_buttons = filter_conflicting_template_buttons(
        [*ocr_buttons, *template_buttons, *llm_candidates]
    )
    candidate_buttons = filter_configured_non_action_buttons(
        automation_config,
        candidate_buttons,
    )
    recent_actions = recent_action_labels(turns_root(args), 6)
    candidate_buttons = [
        *candidate_buttons,
        *configured_extra_candidates(
            automation_config,
            candidate_buttons,
            recent_actions=recent_actions,
        ),
    ]
    candidate_buttons = filter_configured_disabled_gray_buttons(
        automation_config,
        image,
        candidate_buttons,
    )
    if google_play_purchase_sheet_visible(candidate_buttons):
        candidate_buttons = [
            android_back_candidate(
                'Google Play purchase sheet is visible; press Android Back '
                'to avoid buying anything.'
            )
        ]
    elif android_system_screen_visible(candidate_buttons):
        candidate_buttons = [wait_for_android_unlock_candidate()]
    elif is_mostly_blank_screen(image):
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
                    'Recent low-energy popup; keep navigating toward Challenge, '
                    'Trial, or Main Challenge.'
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
    )
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
        llm_buttons=llm_candidates,
        learned_templates=learned_templates,
        buttons=buttons,
        decision=decision,
        verification=verification,
        item_inspections=item_inspections,
    )
    write_game_info_markdown(args.game)
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


if __name__ == '__main__':
    raise SystemExit(main())

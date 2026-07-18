from __future__ import annotations

from dataclasses import dataclass
from re import Pattern


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
class ItemPreferenceRule:
    pattern: str
    points: float
    reason: str = ''


@dataclass(frozen=True)
class GameAutomationConfig:
    game: str
    noise_pattern_text: tuple[str, ...] = ()
    noise_patterns: tuple[Pattern[str], ...] = ()
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
    level_row_patterns: tuple[Pattern[str], ...] = ()
    challenge_detail_action_labels: frozenset[str] = frozenset()
    challenge_detail_patterns: tuple[Pattern[str], ...] = ()
    recent_reentry_keywords: tuple[str, ...] = ()
    waiting_required_groups: tuple[tuple[str, ...], ...] = ()
    waiting_hint_groups: tuple[tuple[str, ...], ...] = ()
    shop_screen_required_groups: tuple[tuple[str, ...], ...] = ()
    safe_confirm_required_groups: tuple[tuple[str, ...], ...] = ()
    energy_empty_labels: frozenset[str] = frozenset()
    energy_empty_destination_labels: frozenset[str] = frozenset()
    energy_empty_action_exemption_labels: frozenset[str] = frozenset()
    loadout_start_labels: frozenset[str] = frozenset()
    energy_empty_candidate: AutomationCandidateSpec | None = None
    loadout_select_candidate: AutomationCandidateSpec | None = None
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
    item_preference_rules: tuple[ItemPreferenceRule, ...] = ()
    ignored_game_info_types: frozenset[str] = frozenset()
    no_change_skill_choice_rule: str = ''
    no_change_empty_screen_rule: str = ''
    target_level: int | None = None


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

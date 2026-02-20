from enum import StrEnum


class SequentialClickReason(StrEnum):
    STATE_CHANGED = 'state_changed'
    NO_STATE_CHANGE = 'no_state_change'
    NO_MATCH = 'no_match'


class SurvivorDecisionReason(StrEnum):
    BOOT = 'boot'
    POST_CLICK_SIGNATURE_CHECK = 'post_click_signature_check'
    STREAK_BREAKER = 'streak_breaker'
    CYCLE_GUARD = 'cycle_guard'
    ENERGY_MODE = 'energy_mode'
    FREE_OR_REWARD = 'free_or_reward'
    CARD_FORCE_SELECT_DIRECT = 'card_force_select_direct'
    SKILL_CHOICE_STREAK_BREAKER = 'skill_choice_streak_breaker'
    BATTLE_HEARTBEAT = 'battle_heartbeat'
    BATTLE_WAIT_WINDOW = 'battle_wait_window'
    START_COOLDOWN_ACTIVE = 'start_cooldown_active'
    CRITICAL_CONTROL = 'critical_control'
    NAV_LABEL = 'nav_label'
    HIGH_RISK_NO_BUY = 'high_risk_no_buy'
    SAFE_BACKTRACK = 'safe_backtrack'
    CRITICAL_TEXT_MISS = 'critical_text_miss'
    ICON_TEMPLATE = 'icon_template'
    NAV_LABEL_FUZZY = 'nav_label_fuzzy'
    START_AREA_TAP = 'start_area_tap'
    SCAN_POINT_TAP = 'scan_point_tap'
    PERIODIC_RECOVERY = 'periodic_recovery'
    NO_MATCH = 'no_match'

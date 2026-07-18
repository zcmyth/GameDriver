from __future__ import annotations

import re
from typing import Any

from automation_types import ButtonCandidate, GameAutomationConfig

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


def normalize_label(value: str) -> str:
    return re.sub(r'\s+', ' ', value.strip().lower())


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


def configured_claimed_label_matches(
    automation_config: GameAutomationConfig,
    value: str,
) -> bool:
    if not automation_config.claimed_labels:
        return False
    key = normalize_label(value)
    if 'unclaimed' in key:
        return False
    if key in automation_config.claimed_labels:
        return True
    return any(label in key for label in automation_config.claimed_labels)


def configured_claimed_visible(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    if not automation_config.claimed_labels:
        return False
    return any(
        configured_claimed_label_matches(automation_config, button.label)
        for button in buttons
    )


def configured_claimed_buttons(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[ButtonCandidate]:
    if not automation_config.claimed_labels:
        return []
    return [
        button
        for button in buttons
        if configured_claimed_label_matches(automation_config, button.label)
    ]


def configured_claimed_y_positions(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[float]:
    return [
        button.y for button in configured_claimed_buttons(automation_config, buttons)
    ]


def configured_level_row_label(
    automation_config: GameAutomationConfig,
    label: str,
) -> bool:
    return any(
        pattern.search(label) for pattern in automation_config.level_row_patterns
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


def configured_level_grid_visible(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> bool:
    return any(
        configured_level_row_label(automation_config, button.label)
        for button in buttons
        if button.source != 'template'
    )


def configured_visible_level_numbers(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
) -> list[int]:
    numbers: list[int] = []
    for button in configured_level_rows(automation_config, buttons):
        number = configured_level_number(button)
        if number is not None:
            numbers.append(number)
    return numbers


def configured_level_number(button: ButtonCandidate) -> int | None:
    match = re.search(r'\b(\d{1,4})\s*\.', button.label)
    if match:
        return int(match.group(1))
    return None


def visible_chapter_number(buttons: list[ButtonCandidate]) -> int | None:
    for button in buttons:
        match = re.search(r'\bchapter\s+(\d{1,4})\b', button.label, re.I)
        if match:
            return int(match.group(1))
    return None


def candidate_level_number(button: ButtonCandidate) -> int | None:
    match = re.search(r'\blevel\s+(\d{1,4})\b', button.reason, re.I)
    if match:
        return int(match.group(1))
    return None


def button_for_level_row(
    spec,
    row: ButtonCandidate,
    *,
    level: int | None,
) -> ButtonCandidate:
    button = spec.to_button_for_row(row)
    if level is None:
        return button
    reason = f'level {level}'
    if button.reason:
        reason = f'{reason}: {button.reason}'
    return ButtonCandidate(
        label=button.label,
        x=button.x,
        y=button.y,
        confidence=button.confidence,
        clickability=button.clickability,
        source=button.source,
        reason=reason,
        score=button.score,
        bbox=button.bbox,
        template_path=button.template_path,
    )


def main_challenge_next_level(
    automation_config: GameAutomationConfig,
    progress: dict[str, Any],
) -> int | None:
    if automation_config.target_level is None:
        return None
    value = progress.get('next_level')
    if not isinstance(value, int):
        return None
    if value > automation_config.target_level:
        return None
    return value


def normalized_progress_levels(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    levels: list[int] = []
    for item in value:
        if isinstance(item, int):
            levels.append(item)
    return sorted(set(levels))


def advance_main_challenge_next_level(
    progress: dict[str, Any],
    *,
    target_level: int | None,
) -> None:
    if target_level is None:
        return
    next_level = progress.get('next_level')
    if not isinstance(next_level, int):
        return
    cleared = set(normalized_progress_levels(progress.get('cleared_levels')))
    while next_level in cleared and next_level <= target_level:
        next_level += 1
    progress['next_level'] = next_level
    progress['complete'] = next_level > target_level


def mark_main_challenge_level_cleared(
    progress: dict[str, Any],
    level: int | None,
    *,
    target_level: int | None,
) -> None:
    if level is None:
        return
    cleared = set(normalized_progress_levels(progress.get('cleared_levels')))
    cleared.add(level)
    progress['cleared_levels'] = sorted(cleared)
    progress['last_cleared_level'] = level
    advance_main_challenge_next_level(progress, target_level=target_level)


def victory_result_visible(buttons: list[ButtonCandidate]) -> bool:
    labels = {normalize_label(button.label) for button in buttons}
    return 'victory' in labels and 'congratulations!' in labels


def update_main_challenge_progress_after_action(
    progress: dict[str, Any],
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
    clicked: ButtonCandidate | None,
) -> bool:
    if automation_config.target_level is None or clicked is None or not progress:
        return False
    clicked_label = normalize_label(clicked.label)
    spec = automation_config.third_column_unclaimed_row_candidate
    if spec is not None and clicked_label == normalize_label(spec.label):
        selected_level = candidate_level_number(clicked)
        if selected_level is None:
            return False
        progress['selected_level'] = selected_level
        progress['last_selected_level'] = selected_level
        return True
    if clicked_label in automation_config.challenge_detail_action_labels:
        chapter = visible_chapter_number(buttons)
        if chapter is None:
            return False
        progress['active_level'] = chapter
        progress.pop('selected_level', None)
        return True
    if clicked_label == 'confirm' and victory_result_visible(buttons):
        active_level = progress.get('active_level')
        mark_main_challenge_level_cleared(
            progress,
            active_level if isinstance(active_level, int) else None,
            target_level=automation_config.target_level,
        )
        progress.pop('active_level', None)
        progress.pop('selected_level', None)
        return True
    if (
        configured_reward_overlay_visible(automation_config, buttons)
        and clicked_label in automation_config.reward_close_labels
    ):
        selected_level = progress.get('selected_level')
        mark_main_challenge_level_cleared(
            progress,
            selected_level if isinstance(selected_level, int) else None,
            target_level=automation_config.target_level,
        )
        progress.pop('selected_level', None)
        return True
    return False


def configured_fallback_level_title_rows(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
    *,
    claimed_buttons: list[ButtonCandidate],
    existing_rows: list[ButtonCandidate],
    max_safe_click_y: float,
) -> list[ButtonCandidate]:
    spec = automation_config.third_column_unclaimed_row_candidate
    if spec is None or not claimed_buttons or not existing_rows:
        return []
    deepest_claimed_y = max(claimed.y for claimed in claimed_buttons)
    existing_row_ys = [row.y for row in existing_rows]
    ignored_labels = {
        'back to top',
        'rewards',
        'tap to close',
        'main challenge',
    }
    fallback_rows: list[ButtonCandidate] = []
    for button in buttons:
        if button.source == 'template':
            continue
        label = normalize_label(button.label)
        if not label or label in ignored_labels:
            continue
        if configured_level_row_label(automation_config, button.label):
            continue
        if configured_claimed_label_matches(automation_config, button.label):
            continue
        if not (0.35 <= button.x <= 0.65):
            continue
        if button.y <= deepest_claimed_y + 0.05:
            continue
        if button.y > max_safe_click_y:
            continue
        if any(abs(button.y - row_y) <= 0.04 for row_y in existing_row_ys):
            continue
        if not re.search(r'[a-z]', label):
            continue
        fallback_rows.append(button)
    return fallback_rows


def configured_inferred_missing_level_row(
    rows: list[ButtonCandidate],
    *,
    next_level: int,
    max_safe_click_y: float,
) -> ButtonCandidate | None:
    numbered_rows = [
        (number, row)
        for row in rows
        if (number := configured_level_number(row)) is not None
    ]
    lower_rows = [(number, row) for number, row in numbered_rows if number < next_level]
    upper_rows = [(number, row) for number, row in numbered_rows if number > next_level]
    if not lower_rows or not upper_rows:
        return None

    lower_number, lower_row = max(lower_rows, key=lambda item: item[0])
    upper_number, upper_row = min(upper_rows, key=lambda item: item[0])
    if not (lower_number < next_level < upper_number):
        return None
    if upper_number == lower_number:
        return None

    ratio = (next_level - lower_number) / (upper_number - lower_number)
    inferred_y = lower_row.y + ((upper_row.y - lower_row.y) * ratio)
    if not (0.08 <= inferred_y <= max_safe_click_y):
        return None

    return ButtonCandidate(
        label=f'{next_level}.Inferred Main Challenge Row',
        x=0.5,
        y=inferred_y,
        confidence=min(lower_row.confidence, upper_row.confidence, 0.95),
        clickability=2.0,
        source='vision',
        reason=(
            f'OCR missed level {next_level}; inferred its row between '
            f'visible levels {lower_number} and {upper_number}.'
        ),
    )


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


def configured_reentry_loop_visible(
    automation_config: GameAutomationConfig,
    recent_actions: list[str] | None,
) -> bool:
    if (
        automation_config.claimed_back_candidate is None
        or not automation_config.recent_reentry_keywords
        or not recent_actions
    ):
        return False
    recent = [normalize_label(label) for label in recent_actions[-8:]]
    back_label = normalize_label(automation_config.claimed_back_candidate.label)
    back_count = sum(1 for label in recent if label == back_label)
    reentry_count = sum(
        1
        for label in recent
        if any(
            keyword in label for keyword in automation_config.recent_reentry_keywords
        )
    )
    return back_count >= 2 and reentry_count >= 2


def configured_third_column_unclaimed_row_candidate(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
    next_level: int | None,
) -> ButtonCandidate | None:
    spec = automation_config.third_column_unclaimed_row_candidate
    if spec is None:
        return None
    claimed_buttons = configured_claimed_buttons(automation_config, buttons)
    max_safe_click_y = 0.94
    rows = configured_level_rows(automation_config, buttons)
    rows.extend(
        configured_fallback_level_title_rows(
            automation_config,
            buttons,
            claimed_buttons=claimed_buttons,
            existing_rows=rows,
            max_safe_click_y=max_safe_click_y,
        )
    )
    rows = sorted(rows, key=lambda button: button.y)
    if not rows:
        return None

    deepest_claimed_y = (
        max(claimed.y for claimed in claimed_buttons) if claimed_buttons else None
    )
    if next_level is not None:
        numbered_rows = [
            row for row in rows if configured_level_number(row) == next_level
        ]
        if not numbered_rows:
            inferred_row = configured_inferred_missing_level_row(
                rows,
                next_level=next_level,
                max_safe_click_y=max_safe_click_y,
            )
            if inferred_row is None:
                return None
            candidate_rows = [inferred_row]
        else:
            candidate_rows = numbered_rows
    else:
        candidate_rows = sorted(rows, key=lambda button: button.y)
    for row in candidate_rows:
        row_button = button_for_level_row(
            spec,
            row,
            level=configured_level_number(row),
        )
        if row.y > max_safe_click_y or row_button.y > max_safe_click_y:
            continue
        if deepest_claimed_y is not None and row_button.y <= deepest_claimed_y + 0.03:
            continue
        row_claimed = any(
            abs(claimed.y - row_button.y) <= 0.12 for claimed in claimed_buttons
        )
        if not row_claimed:
            return row_button
    return None


def configured_higher_levels_scroll_candidate(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
    next_level: int | None,
) -> ButtonCandidate | None:
    target_level = automation_config.target_level
    if target_level is None:
        return None
    if configured_reward_overlay_visible(automation_config, buttons):
        return None
    labels = {
        normalize_label(button.label)
        for button in buttons
        if button.source != 'template'
    }
    if 'back to top' not in labels:
        return None
    if next_level is None and not configured_claimed_visible(
        automation_config,
        buttons,
    ):
        return None
    if configured_third_column_unclaimed_row_candidate(
        automation_config,
        buttons,
        next_level,
    ):
        return None
    visible_numbers = configured_visible_level_numbers(automation_config, buttons)
    if not visible_numbers:
        return None
    if next_level is not None:
        if max(visible_numbers) < next_level:
            return ButtonCandidate(
                label='Scroll to higher challenge levels',
                x=0.5,
                y=0.35,
                confidence=1.0,
                clickability=8.0,
                source='swipe',
                reason=(
                    f'Next Main Challenge level is {next_level}, but visible '
                    f'levels only reach {max(visible_numbers)}; use a short '
                    'swipe up to reveal the next level without skipping rows.'
                ),
                bbox=(0.5, 0.64, 0.5, 0.38),
            )
        if min(visible_numbers) > next_level:
            return ButtonCandidate(
                label='Scroll to lower challenge levels',
                x=0.5,
                y=0.65,
                confidence=1.0,
                clickability=8.0,
                source='swipe',
                reason=(
                    f'Next Main Challenge level is {next_level}, but the '
                    f'lowest visible level is {min(visible_numbers)}; use a '
                    'short swipe down to return to the skipped level.'
                ),
                bbox=(0.5, 0.38, 0.5, 0.64),
            )
        return None
    if max(visible_numbers) >= target_level:
        return None
    return ButtonCandidate(
        label='Scroll to higher challenge levels',
        x=0.5,
        y=0.35,
        confidence=1.0,
        clickability=8.0,
        source='swipe',
        reason=(
            f'Visible Main Challenge levels only reach {max(visible_numbers)}, '
            f'below target {target_level}; swipe up to reveal higher levels.'
        ),
        bbox=(0.5, 0.64, 0.5, 0.38),
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


def configured_level_grid_complete_reason(
    automation_config: GameAutomationConfig,
    buttons: list[ButtonCandidate],
    progress: dict[str, Any],
    next_level: int | None,
) -> str | None:
    spec = automation_config.third_column_unclaimed_row_candidate
    if spec is None or not automation_config.claimed_labels:
        return None
    if configured_reward_overlay_visible(automation_config, buttons):
        return None
    if (
        automation_config.target_level is not None
        and isinstance(progress.get('next_level'), int)
        and progress['next_level'] > automation_config.target_level
    ):
        return (
            f'Main Challenge target {automation_config.target_level} is complete '
            'according to the progress tracker.'
        )
    labels = {
        normalize_label(button.label)
        for button in buttons
        if button.source != 'template'
    }
    if 'back to top' not in labels:
        return None
    claimed_buttons = configured_claimed_buttons(automation_config, buttons)
    if not claimed_buttons:
        return None
    if configured_third_column_unclaimed_row_candidate(
        automation_config,
        buttons,
        next_level,
    ):
        return None
    rows = configured_level_rows(automation_config, buttons)
    rows.extend(
        configured_fallback_level_title_rows(
            automation_config,
            buttons,
            claimed_buttons=claimed_buttons,
            existing_rows=rows,
            max_safe_click_y=0.94,
        )
    )
    if not rows:
        return None
    visible_numbers = configured_visible_level_numbers(automation_config, buttons)
    if (
        automation_config.target_level is not None
        and visible_numbers
        and max(visible_numbers) < automation_config.target_level
    ):
        return None
    deepest_row = max(rows, key=lambda button: button.y)
    deepest_row_button = spec.to_button_for_row(deepest_row)
    deepest_row_claimed = any(
        abs(claimed.y - deepest_row_button.y) <= 0.12 for claimed in claimed_buttons
    )
    if not deepest_row_claimed:
        return None
    return (
        'Main Challenge appears complete: the level list is at Back to top, '
        'the deepest visible row is claimed, and no unclaimed third-column '
        'row is available.'
    )

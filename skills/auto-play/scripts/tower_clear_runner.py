#!/usr/bin/env python3
"""Run tower autoplay turns while conservatively tracking full tower clears."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

FULL_CLEAR_HINTS = (
    '通关',
    '已通关',
    '冒险完成',
    '挑战成功',
    '全部完成',
    '全部通关',
    'tower clear',
    'tower cleared',
    'run complete',
    'adventure complete',
)
FLOOR_SIX_HINTS = (
    '6/6',
    '当前层数 6/6',
    '当前层数6/6',
    'floor 6/6',
)
ORDINARY_VICTORY_HINTS = (
    '胜利',
    'victory',
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def game_root(game: str) -> Path:
    return Path(__file__).resolve().parents[1] / 'games' / game


def default_state_path(game: str) -> Path:
    return game_root(game) / 'clear_goal_state.yaml'


def default_turns_root(game: str) -> Path:
    return game_root(game) / 'turns'


def load_yaml(path: Path) -> Any:
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text()) or None


def load_state(path: Path, target_clears: int) -> dict[str, Any]:
    state = load_yaml(path)
    if not isinstance(state, dict):
        state = {}
    state.setdefault('target_clears', target_clears)
    state.setdefault('verified_clears', 0)
    state.setdefault('counted_turns', [])
    state.setdefault('possible_clear_turns', [])
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(state, sort_keys=False, allow_unicode=True))


def flatten_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        labels: list[str] = []
        for key, child in value.items():
            labels.extend(flatten_strings(key))
            labels.extend(flatten_strings(child))
        return labels
    if isinstance(value, (list, tuple)):
        labels = []
        for child in value:
            labels.extend(flatten_strings(child))
        return labels
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    return []


def turn_text(turn_dir: Path) -> str:
    chunks: list[str] = [turn_dir.name]
    for name in ('ocr.yaml', 'metadata.yaml', 'llm.yaml'):
        path = turn_dir / name
        data = load_yaml(path)
        if data is not None:
            chunks.extend(flatten_strings(data))
    return '\n'.join(chunks).lower()


def detect_clear_status(turn_dir: Path) -> tuple[str, str]:
    text = turn_text(turn_dir)
    has_full_clear = any(hint.lower() in text for hint in FULL_CLEAR_HINTS)
    has_floor_six = any(hint.lower() in text for hint in FLOOR_SIX_HINTS)
    has_victory = any(hint.lower() in text for hint in ORDINARY_VICTORY_HINTS)
    if has_full_clear and has_floor_six:
        return 'clear', 'full-clear wording appeared with floor-6 context'
    if has_full_clear:
        return 'possible', 'full-clear wording appeared without floor-6 context'
    if has_victory and has_floor_six:
        return 'possible', 'ordinary victory wording appeared on floor 6/6'
    return 'none', 'no full-clear signal found'


def latest_turn(turns_root: Path) -> Path | None:
    if not turns_root.exists():
        return None
    turn_dirs = [path for path in turns_root.iterdir() if path.is_dir()]
    if not turn_dirs:
        return None
    return max(turn_dirs, key=lambda path: path.name)


def adb_device_available() -> bool:
    try:
        completed = subprocess.run(
            ['adb', 'devices'],
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return False
    for line in completed.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == 'device':
            return True
    return False


def wait_for_adb(seconds: float) -> bool:
    deadline = time.monotonic() + max(0.0, seconds)
    while True:
        if adb_device_available():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(min(5.0, deadline - time.monotonic()))


def auto_play_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).with_name('auto_play.py')),
        '--game',
        args.game,
        '--width',
        str(args.width),
        '--height',
        str(args.height),
    ]
    if args.click_recommended:
        command.append('--click-recommended')
    if args.turns_dir:
        command.extend(['--turns-dir', str(args.turns_dir)])
    return command


def record_turn_status(
    state: dict[str, Any],
    turn_dir: Path,
) -> tuple[dict[str, Any], str, str]:
    status, reason = detect_clear_status(turn_dir)
    turn_name = turn_dir.name
    counted_turns = set(state.get('counted_turns') or [])
    possible_turns = set(state.get('possible_clear_turns') or [])
    state['last_turn'] = turn_name
    state['last_status'] = status
    state['last_reason'] = reason
    if status == 'clear' and turn_name not in counted_turns:
        state['verified_clears'] = int(state.get('verified_clears') or 0) + 1
        state.setdefault('counted_turns', []).append(turn_name)
    elif status == 'possible' and turn_name not in possible_turns:
        state.setdefault('possible_clear_turns', []).append(turn_name)
    return state, status, reason


def run_goal_loop(args: argparse.Namespace) -> int:
    state_path = args.state_path or default_state_path(args.game)
    turns_root = args.turns_dir or default_turns_root(args.game)
    state = load_state(state_path, args.target_clears)
    state['target_clears'] = args.target_clears

    if args.inspect_latest:
        turn_dir = latest_turn(turns_root)
        if turn_dir is None:
            print(f'No turn folders found under {turns_root}', file=sys.stderr)
            return 1
        state, status, reason = record_turn_status(state, turn_dir)
        save_state(state_path, state)
        print_progress(state, status, reason)
        return 0

    if not wait_for_adb(args.wait_adb_seconds):
        print('No ADB-visible Android device; tower run not started.', file=sys.stderr)
        save_state(state_path, state)
        return 2

    command = auto_play_command(args)
    turns_run = 0
    while int(state.get('verified_clears') or 0) < args.target_clears:
        if args.max_turns and turns_run >= args.max_turns:
            break
        completed = subprocess.run(command, cwd=repo_root(), check=False)
        turns_run += 1
        if completed.returncode != 0:
            save_state(state_path, state)
            return completed.returncode
        turn_dir = latest_turn(turns_root)
        if turn_dir is None:
            save_state(state_path, state)
            print(f'No turn folder created under {turns_root}', file=sys.stderr)
            return 1
        state, status, reason = record_turn_status(state, turn_dir)
        save_state(state_path, state)
        print_progress(state, status, reason)
        if args.interval > 0:
            time.sleep(args.interval)
    return 0


def print_progress(state: dict[str, Any], status: str, reason: str) -> None:
    print(
        'Tower clears: '
        f'{state.get("verified_clears", 0)} / {state.get("target_clears")}; '
        f'last turn {state.get("last_turn")} => {status} ({reason})'
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run tower autoplay turns and track verified 6-floor clears.'
    )
    parser.add_argument('--game', default='tower')
    parser.add_argument('--target-clears', type=int, default=10)
    parser.add_argument('--width', type=int, default=360)
    parser.add_argument('--height', type=int, default=800)
    parser.add_argument('--max-turns', type=int, default=1, help='0 means unlimited.')
    parser.add_argument('--interval', type=float, default=1.0)
    parser.add_argument('--wait-adb-seconds', type=float, default=0.0)
    parser.add_argument('--click-recommended', action='store_true')
    parser.add_argument('--inspect-latest', action='store_true')
    parser.add_argument('--state-path', type=Path)
    parser.add_argument('--turns-dir', type=Path)
    args = parser.parse_args()
    if args.target_clears < 1:
        parser.error('--target-clears must be at least 1')
    if args.max_turns < 0:
        parser.error('--max-turns must be non-negative')
    if args.interval < 0:
        parser.error('--interval must be non-negative')
    if args.wait_adb_seconds < 0:
        parser.error('--wait-adb-seconds must be non-negative')
    return args


def main() -> int:
    return run_goal_loop(parse_args())


if __name__ == '__main__':
    raise SystemExit(main())

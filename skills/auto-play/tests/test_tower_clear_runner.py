import importlib.util
import sys
from pathlib import Path

import yaml


def load_runner_module():
    path = Path(__file__).resolve().parents[1] / 'scripts'
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    spec = importlib.util.spec_from_file_location(
        'tower_clear_runner_script', path / 'tower_clear_runner.py'
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_turn(tmp_path, payload):
    turn_dir = tmp_path / '20260705T010000-0700-tower'
    turn_dir.mkdir()
    (turn_dir / 'ocr.yaml').write_text(yaml.safe_dump(payload, allow_unicode=True))
    return turn_dir


def test_detect_clear_status_counts_strong_floor_six_completion(tmp_path):
    runner = load_runner_module()
    turn_dir = write_turn(
        tmp_path,
        {
            'ocr_buttons': [
                {'label': '当前层数 6/6'},
                {'label': '恭喜通关'},
            ]
        },
    )

    status, reason = runner.detect_clear_status(turn_dir)

    assert status == 'clear'
    assert 'floor-6' in reason


def test_detect_clear_status_does_not_count_ordinary_floor_six_victory(tmp_path):
    runner = load_runner_module()
    turn_dir = write_turn(
        tmp_path,
        {
            'ocr_buttons': [
                {'label': '当前层数 6/6'},
                {'label': '胜利'},
                {'label': '+20'},
            ]
        },
    )

    status, reason = runner.detect_clear_status(turn_dir)

    assert status == 'possible'
    assert 'ordinary victory' in reason


def test_record_turn_status_increments_each_clear_once(tmp_path):
    runner = load_runner_module()
    turn_dir = write_turn(
        tmp_path,
        {
            'ocr_buttons': [
                {'label': '当前层数 6/6'},
                {'label': '挑战成功 通关'},
            ]
        },
    )
    state = runner.load_state(tmp_path / 'state.yaml', target_clears=10)

    state, status, _ = runner.record_turn_status(state, turn_dir)
    state, second_status, _ = runner.record_turn_status(state, turn_dir)

    assert status == 'clear'
    assert second_status == 'clear'
    assert state['verified_clears'] == 1
    assert state['counted_turns'] == [turn_dir.name]

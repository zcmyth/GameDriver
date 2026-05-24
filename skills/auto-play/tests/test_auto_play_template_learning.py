import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def load_auto_play_module():
    path = Path(__file__).resolve().parents[1] / 'scripts'
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    spec = importlib.util.spec_from_file_location(
        'auto_play_script', path / 'auto_play.py'
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_llm_only_bbox_is_saved_as_game_template(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    screenshot = Image.new('RGB', (100, 100), color='black')
    draw = ImageDraw.Draw(screenshot)
    draw.rectangle((20, 20, 50, 45), fill='white')

    button = auto_play.ButtonCandidate(
        label='Fight',
        x=0.35,
        y=0.325,
        confidence=0.9,
        clickability=0.8,
        source='llm',
        bbox=(0.2, 0.2, 0.5, 0.45),
    )

    learned = auto_play.learn_templates_from_llm(
        game='Tower',
        image=screenshot,
        llm_buttons=[button],
        non_llm_buttons=[],
        turn_name='turn-001',
    )

    assert learned[0]['status'] == 'saved'
    saved_path = Path(learned[0]['path'])
    assert saved_path.exists()
    assert saved_path.parent == tmp_path / 'games' / 'tower' / 'images'
    assert saved_path.name == 'fight--turn-001.png'

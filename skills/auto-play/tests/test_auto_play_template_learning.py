import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
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


def load_tune_ocr_module():
    path = Path(__file__).resolve().parents[1] / 'scripts'
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    spec = importlib.util.spec_from_file_location(
        'tune_ocr_script', path / 'tune_ocr.py'
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def game_strategy_text(game: str) -> str:
    slug = game.strip().lower()
    return (
        Path(__file__).resolve().parents[1] / 'games' / slug / 'strategy.md'
    ).read_text()


def write_game_strategy(root: Path, game: str) -> Path:
    slug = game.strip().lower()
    path = root / 'games' / slug / 'strategy.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(game_strategy_text(slug))
    return path


def automation_config(auto_play, game: str):
    return auto_play.load_automation_config(game)


def isolated_automation_config(auto_play, game: str, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    write_game_strategy(tmp_path, game)
    return auto_play.load_automation_config(game)


def test_turn_detection_overlays_are_saved(tmp_path):
    auto_play = load_auto_play_module()
    image = Image.new('RGB', (120, 120), color='black')
    artifact_paths = {
        'ocr_overlay': tmp_path / 'ocr_overlay.png',
        'llm_overlay': tmp_path / 'llm_overlay.png',
    }

    auto_play.save_turn_detection_overlays(
        image,
        artifact_paths=artifact_paths,
        ocr_buttons=[
            auto_play.ButtonCandidate(
                label='Start',
                x=0.25,
                y=0.4,
                confidence=0.92,
                clickability=1.0,
                source='ocr',
            )
        ],
        template_buttons=[
            auto_play.ButtonCandidate(
                label='Fight template',
                x=0.75,
                y=0.4,
                confidence=0.88,
                clickability=1.2,
                source='template',
            )
        ],
        llm_buttons=[
            auto_play.ButtonCandidate(
                label='LLM button',
                x=0.5,
                y=0.7,
                confidence=0.75,
                clickability=0.8,
                source='llm',
            )
        ],
    )

    assert artifact_paths['ocr_overlay'].exists()
    assert artifact_paths['llm_overlay'].exists()
    assert Image.open(artifact_paths['ocr_overlay']).size == image.size
    assert Image.open(artifact_paths['llm_overlay']).size == image.size


def test_noisy_survivor_hud_labels_are_ignored():
    auto_play = load_auto_play_module()

    assert auto_play.looks_like_noise_label('4.778,77B7')
    assert auto_play.looks_like_noise_label('06:2!')
    assert auto_play.looks_like_noise_label('(5.06B')
    assert auto_play.looks_like_noise_label('xK6224')
    assert auto_play.looks_like_noise_label('374KS374')
    assert auto_play.looks_like_noise_label('•02')
    assert not auto_play.looks_like_noise_label('Drone')
    assert not auto_play.looks_like_noise_label('Twinborn Type-B Drone')
    assert not auto_play.looks_like_noise_label('1-tap buy')
    assert not auto_play.looks_like_noise_label('322.Refraction Passage')


def test_turn_detection_overlays_skip_llm_when_no_llm_detections(tmp_path):
    auto_play = load_auto_play_module()
    image = Image.new('RGB', (120, 120), color='black')
    artifact_paths = {
        'ocr_overlay': tmp_path / 'ocr_overlay.png',
        'llm_overlay': tmp_path / 'llm_overlay.png',
    }
    artifact_paths['llm_overlay'].write_bytes(b'old overlay')

    auto_play.save_turn_detection_overlays(
        image,
        artifact_paths=artifact_paths,
        ocr_buttons=[
            auto_play.ButtonCandidate(
                label='Start',
                x=0.25,
                y=0.4,
                confidence=0.92,
                clickability=1.0,
                source='ocr',
            )
        ],
        template_buttons=[],
        llm_buttons=[],
    )

    assert artifact_paths['ocr_overlay'].exists()
    assert not artifact_paths['llm_overlay'].exists()


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
    assert saved_path.name == 'fight.png'


def test_learned_template_paths_use_short_slug_names(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    images_dir = tmp_path / 'games' / 'tower' / 'images'
    images_dir.mkdir(parents=True)
    (images_dir / 'next-room.png').write_bytes(b'placeholder')

    path = auto_play.unique_template_path(images_dir, 'Next Room', 'turn-001')

    assert path.name == 'next-room--02.png'


def test_parse_normalized_bbox_prefers_llm_template_bbox():
    auto_play = load_auto_play_module()

    bbox = auto_play.parse_normalized_bbox(
        {
            'bbox': {
                'x1': 0.1,
                'y1': 0.1,
                'x2': 0.9,
                'y2': 0.9,
            },
            'template_bbox': {
                'x1': 0.2,
                'y1': 0.3,
                'x2': 0.4,
                'y2': 0.5,
            },
        }
    )

    assert bbox == (0.2, 0.3, 0.4, 0.5)


def test_learned_template_crop_keeps_only_focused_button(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    screenshot = Image.new('RGB', (120, 220), color='black')
    draw = ImageDraw.Draw(screenshot)
    draw.rounded_rectangle((12, 12, 104, 94), radius=5, fill=(155, 92, 52))
    draw.rectangle((22, 24, 94, 68), fill=(230, 192, 80))
    draw.text((45, 72), 'A', fill='white')
    draw.rounded_rectangle((12, 122, 104, 204), radius=5, fill=(52, 110, 155))
    draw.rectangle((22, 134, 94, 178), fill=(80, 192, 230))
    draw.text((45, 182), 'B', fill='white')

    button = auto_play.ButtonCandidate(
        label='Focused Card',
        x=0.48,
        y=0.24,
        confidence=0.9,
        clickability=0.8,
        source='llm',
        bbox=(0.05, 0.02, 0.95, 0.98),
    )

    learned = auto_play.learn_templates_from_llm(
        game='Tower',
        image=screenshot,
        llm_buttons=[button],
        non_llm_buttons=[],
        turn_name='turn-001',
    )

    saved_path = Path(learned[0]['path'])
    saved = Image.open(saved_path)
    assert learned[0]['status'] == 'saved'
    assert saved.height < 120
    assert saved.width < 110


def test_clickable_llm_object_bbox_is_saved_as_game_template(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    screenshot = Image.new('RGB', (100, 100), color='black')
    draw = ImageDraw.Draw(screenshot)
    draw.rectangle((60, 30, 86, 58), fill='white')

    llm_result = tmp_path / 'llm.yaml'
    llm_result.write_text(
        """
summary: Detail screen with a clickable avatar icon.
objects:
  - label: Adventurer Avatar
    description: Character portrait icon that opens adventurer details.
    clickable: true
    x: 0.73
    y: 0.44
    bbox:
      x1: 0.60
      y1: 0.30
      x2: 0.86
      y2: 0.58
  - label: Background Statue
    description: Decorative statue.
    clickable: false
    x: 0.20
    y: 0.30
    bbox:
      x1: 0.10
      y1: 0.20
      x2: 0.30
      y2: 0.40
buttons: []
"""
    )

    icons = auto_play.load_llm_icon_candidates(llm_result)
    learned = auto_play.learn_templates_from_llm(
        game='Tower',
        image=screenshot,
        llm_buttons=icons,
        non_llm_buttons=[],
        turn_name='turn-001',
    )

    assert len(icons) == 1
    assert icons[0].source == 'llm_icon'
    assert learned[0]['status'] == 'saved'
    assert learned[0]['source'] == 'llm_icon'
    saved_path = Path(learned[0]['path'])
    assert saved_path.exists()
    assert saved_path.name == 'adventurer-avatar.png'


def test_clickable_llm_object_prefers_original_game_label(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    screenshot = Image.new('RGB', (100, 100), color='black')
    draw = ImageDraw.Draw(screenshot)
    draw.rectangle((40, 70, 70, 90), fill='white')

    llm_result = tmp_path / 'llm.yaml'
    llm_result.write_text(
        """
summary: Main screen with a visible Chinese adventure icon.
objects:
  - label: Adventure
    original_label: 冒险
    original_description: 进入冒险
    description: Enter adventure.
    clickable: true
    x: 0.55
    y: 0.80
    bbox:
      x1: 0.40
      y1: 0.70
      x2: 0.70
      y2: 0.90
buttons: []
"""
    )

    icons = auto_play.load_llm_icon_candidates(llm_result)
    learned = auto_play.learn_templates_from_llm(
        game='Tower',
        image=screenshot,
        llm_buttons=icons,
        non_llm_buttons=[],
        turn_name='turn-001',
    )

    assert icons[0].label == '冒险'
    assert icons[0].reason == '进入冒险'
    assert Path(learned[0]['path']).name == '冒险.png'


def test_turn_history_limit_defaults_to_500(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(sys, 'argv', ['auto_play.py'])

    args = auto_play.parse_args()

    assert args.turn_history_limit == 500
    assert args.unblock_check_interval == 5
    assert args.unblock_window_size == 5
    assert args.ocr_tune_every_turns == 50
    assert args.ocr_tune_iterations == 10
    assert args.ocr_tune_on_stuck_iterations == 10
    assert args.ocr_tune_on_stuck_recent_turns == 10
    assert args.ocr_tune_recent_turns == 50
    assert args.ocr_tune_timeout == 60.0


def test_ad_revive_context_prefers_cancel_over_watch_ad():
    auto_play = load_auto_play_module()
    memory = {
        'preferred': [],
        'avoid': ['Cancel'],
        'ineffective': [],
    }
    buttons = [
        auto_play.ButtonCandidate(
            label='Cancel',
            x=0.3,
            y=0.64,
            confidence=0.95,
            clickability=0.8,
            source='llm',
            reason='Cancels the ad revive.',
        ),
        auto_play.ButtonCandidate(
            label='观看',
            x=0.7,
            y=0.64,
            confidence=0.95,
            clickability=0.8,
            source='llm',
            reason='Watches an ad to revive.',
        ),
    ]

    scored = auto_play.score_buttons(buttons, memory)
    decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.95,
        ambiguity_margin=0.2,
        ask_on_ambiguous=False,
    )

    assert scored[0].label == 'Cancel'
    assert decision.status == 'ready'
    assert decision.recommended.label == 'Cancel'


def test_ad_revive_context_prefers_watch_ad_when_configured():
    auto_play = load_auto_play_module()
    config = auto_play.GameAutomationConfig(
        game='tower',
        prefer_watch_ads=True,
    )
    memory = {
        'preferred': [],
        'avoid': [],
        'ineffective': [],
    }
    buttons = [
        auto_play.ButtonCandidate(
            label='Cancel',
            x=0.3,
            y=0.64,
            confidence=0.95,
            clickability=0.8,
            source='llm',
            reason='Cancels the ad revive.',
        ),
        auto_play.ButtonCandidate(
            label='观看',
            x=0.7,
            y=0.64,
            confidence=0.95,
            clickability=0.8,
            source='llm',
            reason='Watches an ad to revive.',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory,
        automation_config=config,
    )

    assert scored[0].label == '观看'


def test_tower_config_enables_watch_ads():
    auto_play = load_auto_play_module()

    assert automation_config(auto_play, 'tower').prefer_watch_ads is True


def test_tower_ocr_config_uses_chinese_mobile_model(monkeypatch):
    auto_play = load_auto_play_module()
    auto_play.ensure_script_imports()
    import image_analyzer

    captured = {}

    def fake_paddle_ocr(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(image_analyzer, 'PaddleOCR', fake_paddle_ocr)

    image_analyzer.PaddleOCRAnalyzer(
        template_configs=auto_play.load_ocr_config('tower')
    )

    assert captured['lang'] == 'ch'
    assert captured['text_recognition_model_name'] == 'PP-OCRv5_mobile_rec'


def test_sell_action_is_never_selected_for_tower():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    sell = auto_play.ButtonCandidate(
        label='出售宝物',
        x=0.3,
        y=0.7,
        confidence=1.0,
        clickability=2.0,
        source='ocr',
    )
    back = auto_play.ButtonCandidate(
        label='返回',
        x=0.7,
        y=0.7,
        confidence=0.8,
        clickability=1.0,
        source='ocr',
    )

    scored = auto_play.score_buttons(
        [sell, back],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '返回'
    assert next(button for button in scored if button.label == '出售宝物').score < -90


def test_ad_revive_watch_beats_stale_card_templates_without_prompt_ocr():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    scored = auto_play.score_buttons(
        [
            auto_play.ButtonCandidate(
                label='Cancel',
                x=0.30,
                y=0.64,
                confidence=0.999,
                clickability=1.82,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='观看',
                x=0.69,
                y=0.64,
                confidence=1.0,
                clickability=1.8,
                source='template',
            ),
            auto_play.ButtonCandidate(
                label='迅捷',
                x=0.75,
                y=0.64,
                confidence=1.0,
                clickability=1.55,
                source='template',
            ),
            auto_play.ButtonCandidate(
                label='发现弱点',
                x=0.26,
                y=0.64,
                confidence=1.0,
                clickability=1.45,
                source='template',
            ),
        ],
        memory={'preferred': ['迅捷', '发现弱点'], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '观看'
    assert scored[-1].label == 'Cancel'


def test_defeat_recovery_beats_stale_combat_card_templates():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    defeat_banner = auto_play.ButtonCandidate(
        label='游戏失败',
        x=0.5,
        y=0.35,
        confidence=0.95,
        clickability=0.2,
        source='ocr',
    )
    return_to_inn = auto_play.ButtonCandidate(
        label='返回旅馆',
        x=0.5,
        y=0.96,
        confidence=1.0,
        clickability=1.8,
        source='template',
    )
    stale_card = auto_play.ButtonCandidate(
        label='普通木剑',
        x=0.5,
        y=0.76,
        confidence=0.88,
        clickability=1.75,
        source='template',
    )

    scored = auto_play.score_buttons(
        [stale_card, return_to_inn, defeat_banner],
        memory={'preferred': ['普通木剑'], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )
    decision = auto_play.decide_unblock_move(scored, {'普通攻击'})

    assert scored[0].label == '返回旅馆'
    assert decision.recommended.label == '返回旅馆'


def test_bottom_defeat_recovery_beats_stale_templates_without_ocr_banner():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    return_to_inn = auto_play.ButtonCandidate(
        label='返回旅馆',
        x=0.51,
        y=0.96,
        confidence=1.0,
        clickability=1.82,
        source='template',
    )
    stale_card = auto_play.ButtonCandidate(
        label='灵魂收割',
        x=0.2,
        y=0.76,
        confidence=0.99,
        clickability=1.74,
        source='template',
    )
    stale_back = auto_play.ButtonCandidate(
        label='返回',
        x=0.44,
        y=0.67,
        confidence=0.84,
        clickability=0.9,
        source='template',
    )

    scored = auto_play.score_buttons(
        [stale_card, stale_back, return_to_inn],
        memory={'preferred': ['灵魂收割'], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '返回旅馆'


def test_return_to_inn_loses_to_continue_without_defeat_context():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    return_to_inn = auto_play.ButtonCandidate(
        label='返回旅馆',
        x=0.5,
        y=0.58,
        confidence=1.0,
        clickability=1.8,
        source='template',
    )
    continue_adventure = auto_play.ButtonCandidate(
        label='继续冒险',
        x=0.5,
        y=0.72,
        confidence=0.95,
        clickability=1.6,
        source='ocr',
    )

    scored = auto_play.score_buttons(
        [return_to_inn, continue_adventure],
        memory={'preferred': ['继续冒险', '返回旅馆'], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '继续冒险'


def test_bottom_return_to_inn_loses_to_continue_on_live_settings_screen():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    return_to_inn = auto_play.ButtonCandidate(
        label='返回旅馆',
        x=0.5,
        y=0.96,
        confidence=1.0,
        clickability=1.8,
        source='template',
    )
    continue_adventure = auto_play.ButtonCandidate(
        label='继续冒险',
        x=0.5,
        y=0.63,
        confidence=0.84,
        clickability=1.9,
        source='template',
    )

    scored = auto_play.score_buttons(
        [return_to_inn, continue_adventure],
        memory={'preferred': ['继续冒险', '返回旅馆'], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '继续冒险'


def test_survivor_energy_empty_prefers_main_challenge_over_start():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')
    memory = {
        'preferred': ['Start', 'Battle', 'Trial', 'Main Challenge'],
        'avoid': [],
        'ineffective': [],
    }
    buttons = [
        auto_play.ButtonCandidate(
            label='Start',
            x=0.5,
            y=0.81,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Battle',
            x=0.47,
            y=0.87,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Main Challenge',
            x=0.1,
            y=0.85,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Not enough Energy',
            x=0.5,
            y=0.38,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory,
        automation_config=config,
    )

    assert scored[0].label == 'Main Challenge'


def test_survivor_energy_empty_allows_main_challenge_detail_start():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')
    memory = {
        'preferred': ['Battle'],
        'avoid': [],
        'ineffective': [],
    }
    buttons = [
        auto_play.ButtonCandidate(
            label='Battle',
            x=0.79,
            y=0.68,
            confidence=1.0,
            clickability=1.8,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Start',
            x=0.5,
            y=0.71,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Chapter 258',
            x=0.48,
            y=0.32,
            confidence=0.97,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Rewards',
            x=0.5,
            y=0.58,
            confidence=1.0,
            clickability=1.95,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Not enough Energy',
            x=0.5,
            y=0.38,
            confidence=0.01,
            clickability=0.0,
            source='state',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory,
        automation_config=config,
    )

    assert scored[0].label == 'Start'


def test_survivor_progress_clicks_tracked_bottom_level(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    write_game_strategy(tmp_path, 'survivor')
    progress_path = tmp_path / 'games' / 'survivor' / 'main_challenge_progress.yaml'
    progress_path.write_text(
        """
target_level: 330
next_level: 315
active_level: null
cleared_levels:
  - 314
complete: false
"""
    )
    config = automation_config(auto_play, 'survivor')
    buttons = [
        auto_play.ButtonCandidate(
            label='Back to top',
            x=0.84,
            y=0.96,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='312.Book Dimension',
            x=0.5,
            y=0.15,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='313.Prologue Prison',
            x=0.5,
            y=0.36,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='314.Spatial Crystal',
            x=0.5,
            y=0.58,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='315.Crystal Forest',
            x=0.5,
            y=0.80,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
    ]

    extras = auto_play.configured_extra_candidates(config, buttons)

    assert extras[0].label == 'Third column unclaimed row'
    assert round(extras[0].y, 4) == 0.69
    assert auto_play.candidate_level_number(extras[0]) == 315


def test_survivor_progress_clicks_tracked_clamped_bottom_level(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    write_game_strategy(tmp_path, 'survivor')
    progress_path = tmp_path / 'games' / 'survivor' / 'main_challenge_progress.yaml'
    progress_path.write_text(
        """
target_level: 330
next_level: 317
active_level: null
cleared_levels:
  - 314
  - 315
  - 316
complete: false
"""
    )
    config = automation_config(auto_play, 'survivor')
    buttons = [
        auto_play.ButtonCandidate(
            label='Back to top',
            x=0.84,
            y=0.96,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Claimed',
            x=0.83,
            y=0.31,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='314.Spatial Crystal',
            x=0.5,
            y=0.21,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='315.Crystal Forest',
            x=0.5,
            y=0.43,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='316.Battle of Past',
            x=0.5,
            y=0.64,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='317.Dawnlight Path',
            x=0.5,
            y=0.86,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
    ]

    extras = auto_play.configured_extra_candidates(config, buttons)

    assert extras[0].label == 'Third column unclaimed row'
    assert extras[0].y == 0.75
    assert auto_play.candidate_level_number(extras[0]) == 317


def test_survivor_progress_scrolls_down_to_skipped_level(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    write_game_strategy(tmp_path, 'survivor')
    progress_path = tmp_path / 'games' / 'survivor' / 'main_challenge_progress.yaml'
    progress_path.write_text(
        """
target_level: 330
next_level: 315
active_level: 319
cleared_levels:
  - 314
complete: false
"""
    )
    config = automation_config(auto_play, 'survivor')
    buttons = [
        auto_play.ButtonCandidate(
            label='Back to top',
            x=0.84,
            y=0.96,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='317.Dawnlight Path',
            x=0.5,
            y=0.18,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='318.Final Vortex',
            x=0.5,
            y=0.40,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='319.Breaching Codex',
            x=0.5,
            y=0.61,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='320.Stargate Arrival',
            x=0.5,
            y=0.83,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
    ]

    extras = auto_play.configured_extra_candidates(config, buttons)

    assert extras[0].label == 'Scroll to lower challenge levels'
    assert extras[0].bbox == (0.5, 0.38, 0.5, 0.64)


def test_recruit_does_not_override_adventure_without_daily_phase():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    recruit = auto_play.ButtonCandidate(
        label='招募',
        x=0.82,
        y=0.39,
        confidence=0.96,
        clickability=1.4,
        source='template',
    )
    adventure = auto_play.ButtonCandidate(
        label='冒险',
        x=0.52,
        y=0.96,
        confidence=1.0,
        clickability=1.43,
        source='template',
    )

    scored = auto_play.score_buttons(
        [adventure, recruit],
        memory={'preferred': ['冒险', '招募'], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '冒险'


def test_hire_beats_return_when_recruit_detail_is_open():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    hire = auto_play.ButtonCandidate(
        label='雇佣',
        x=0.72,
        y=0.96,
        confidence=0.98,
        clickability=1.8,
        source='template',
    )
    back = auto_play.ButtonCandidate(
        label='返回冒险',
        x=0.08,
        y=0.96,
        confidence=0.9,
        clickability=1.4,
        source='template',
    )

    scored = auto_play.score_buttons(
        [back, hire],
        memory={'preferred': ['雇佣'], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '雇佣'


def test_combat_card_beats_end_when_card_is_visible():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    end = auto_play.ButtonCandidate(
        label='End',
        x=0.5,
        y=0.92,
        confidence=1.0,
        clickability=1.88,
        source='ocr',
    )
    shield = auto_play.ButtonCandidate(
        label='举盾',
        x=0.46,
        y=0.56,
        confidence=0.9,
        clickability=1.7,
        source='template',
    )

    scored = auto_play.score_buttons(
        [end, shield],
        memory={'preferred': ['举盾'], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '举盾'


def test_attack_number_card_beats_shield_in_combat():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    end = auto_play.ButtonCandidate(
        label='End',
        x=0.5,
        y=0.92,
        confidence=1.0,
        clickability=1.88,
        source='ocr',
    )
    shield = auto_play.ButtonCandidate(
        label='举盾',
        x=0.46,
        y=0.56,
        confidence=0.99,
        clickability=1.9,
        source='template',
    )
    attack = auto_play.ButtonCandidate(
        label='普通攻击',
        x=0.28,
        y=0.56,
        confidence=0.86,
        clickability=1.3,
        source='template',
    )

    scored = auto_play.score_buttons(
        [end, shield, attack],
        memory={'preferred': ['举盾', '普通攻击'], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '普通攻击'


def test_tower_attack_number_card_vision_candidates_beat_shield():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(20, 24, 28))
    draw = ImageDraw.Draw(image)

    for index, (center_x, center_y) in enumerate(
        auto_play.TOWER_COMBAT_CARD_SLOT_CENTERS
    ):
        card_center_x = int(center_x * 360)
        card_center_y = int(center_y * 800)
        x1 = card_center_x - 43
        x2 = card_center_x + 43
        y1 = card_center_y - 61
        y2 = card_center_y + 61
        is_attack = index in {1, 2, 4}
        fill = (176, 77, 45) if is_attack else (56, 122, 158)
        draw.rounded_rectangle((x1, y1, x2, y2), radius=8, fill=fill)
        draw.rectangle(
            (card_center_x - 10, y2 - 34, card_center_x + 10, y2 - 20),
            fill=(235, 230, 216),
        )

    end = auto_play.ButtonCandidate(
        label='End',
        x=0.5,
        y=0.92,
        confidence=1.0,
        clickability=1.88,
        source='ocr',
    )
    shield = auto_play.ButtonCandidate(
        label='举盾',
        x=0.17,
        y=0.73,
        confidence=0.98,
        clickability=1.65,
        source='template',
    )

    attack_cards = auto_play.tower_attack_number_card_candidates(
        image,
        config,
        [end, shield],
    )
    scored = auto_play.score_buttons(
        [end, shield, *attack_cards],
        memory={'preferred': ['举盾'], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert len(attack_cards) == 3
    assert {round(card.x, 3) for card in attack_cards} == {0.5, 0.795}
    assert scored[0].label == 'Visible attack-number card'


def test_tower_combat_card_detector_finds_enabled_cards_and_skips_dim_card():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(18, 21, 24))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((22, 426, 118, 556), radius=7, fill=(154, 81, 49))
    draw.rounded_rectangle((132, 426, 228, 556), radius=7, fill=(73, 132, 158))
    draw.rounded_rectangle((242, 426, 338, 556), radius=7, fill=(42, 45, 48))
    draw.rectangle((100, 735, 260, 782), fill=(221, 176, 40))

    assert auto_play.tower_combat_screen_visible(image)

    cards = auto_play.tower_combat_card_candidates(image, config, [])

    assert len(cards) == 2
    assert all(card.label.startswith('Visible playable card') for card in cards)
    assert [round(card.x, 2) for card in cards] == [0.19, 0.5]
    assert all(0.54 < card.y < 0.56 for card in cards)


def test_tower_combat_emergency_item_requires_low_hp_and_positive_count():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(18, 21, 24))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((22, 426, 118, 556), radius=7, fill=(154, 81, 49))
    draw.rectangle((100, 735, 260, 782), fill=(221, 176, 40))
    draw.rectangle((291, 740, 293, 747), fill='white')

    assert auto_play.tower_combat_hp_looks_critical(image)
    assert auto_play.tower_combat_item_pouch_has_consumable(image)
    assert auto_play.tower_combat_emergency_item_candidates(image, config)

    draw.rectangle((86, 356, 90, 362), fill=(203, 94, 47))
    assert not auto_play.tower_combat_hp_looks_critical(image)
    assert not auto_play.tower_combat_emergency_item_candidates(image, config)


def test_tower_enemy_hp_cv_detects_sacred_finisher_range():
    auto_play = load_auto_play_module()
    low_hp = Image.new('RGB', (360, 800), color=(18, 21, 24))
    healthy = low_hp.copy()
    ImageDraw.Draw(low_hp).rectangle((219, 56, 224, 63), fill=(198, 86, 36))
    ImageDraw.Draw(healthy).rectangle((219, 56, 250, 63), fill=(198, 86, 36))

    assert auto_play.tower_enemy_hp_looks_sacred_finisher_ready(low_hp)
    assert not auto_play.tower_enemy_hp_looks_sacred_finisher_ready(healthy)


def test_tower_combat_saves_giant_potion_at_healthy_hp(monkeypatch):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'shop_purchases': ['巨人药水'],
            'used_consumables': [],
        },
    )
    image = Image.new('RGB', (360, 800), color=(18, 21, 24))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((22, 426, 118, 556), radius=7, fill=(154, 81, 49))
    draw.rectangle((100, 735, 260, 782), fill=(221, 176, 40))
    draw.rectangle((291, 740, 293, 747), fill='white')
    draw.rectangle((86, 356, 90, 362), fill=(203, 94, 47))

    assert not auto_play.tower_combat_hp_looks_critical(image)
    assert not auto_play.tower_combat_emergency_item_candidates(image, config)


def test_tower_combat_item_counter_recognizes_zero_ring():
    auto_play = load_auto_play_module()
    image = Image.new('RGB', (360, 800), color=(18, 21, 24))
    draw = ImageDraw.Draw(image)
    draw.rectangle((287, 740, 298, 747), fill='white')
    draw.rectangle((290, 741, 295, 746), fill='black')

    assert not auto_play.tower_combat_item_pouch_has_consumable(image)


def test_tower_combat_card_detector_rejects_selected_but_unaffordable_card():
    auto_play = load_auto_play_module()
    crop = np.full((154, 114, 3), 75, dtype=np.uint8)
    crop[:77] = 110

    assert float(crop.max(axis=2).mean()) > 85.0
    assert not auto_play.tower_combat_card_looks_enabled(crop)


def test_tower_ocr_card_clickability_accepts_observed_bright_card_boundary():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    bright_card = auto_play.ButtonCandidate(
        label='迅捷',
        x=0.2,
        y=0.6375,
        confidence=0.98,
        clickability=1.684,
        source='ocr',
    )
    dim_card = auto_play.ButtonCandidate(
        label='全力一击',
        x=0.2,
        y=0.6375,
        confidence=0.96,
        clickability=1.13,
        source='ocr',
    )

    assert auto_play.is_tower_playable_combat_card_candidate(
        bright_card,
        config,
    )
    assert not auto_play.is_tower_playable_combat_card_candidate(
        dim_card,
        config,
    )


def test_chinese_end_turn_label_loses_to_playable_card_then_remains_actionable():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    end = auto_play.ButtonCandidate(
        label='结束第3回合',
        x=0.5,
        y=0.92,
        confidence=0.95,
        clickability=1.5,
        source='ocr',
    )
    card = auto_play.ButtonCandidate(
        label='Visible playable card: 毒药攻击II',
        x=0.5,
        y=0.6,
        confidence=0.96,
        clickability=7.4,
        source='vision',
    )

    with_card = auto_play.score_buttons(
        [end, card],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )
    end_only = auto_play.score_buttons(
        [end],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert with_card[0].label.startswith('Visible playable card')
    assert end_only[0].score >= 1.05


def test_tower_context_filter_rejects_navigation_templates_in_wrong_positions():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color='black')
    false_down = auto_play.ButtonCandidate(
        label='下方道路',
        x=0.78,
        y=0.18,
        confidence=0.95,
        clickability=1.0,
        source='template',
    )
    valid_right = auto_play.ButtonCandidate(
        label='右侧道路',
        x=0.91,
        y=0.71,
        confidence=0.91,
        clickability=1.0,
        source='template',
    )

    filtered = auto_play.filter_tower_context_buttons(
        image,
        [false_down, valid_right],
        config,
    )

    assert filtered == [valid_right]


def test_tower_context_filter_rejects_navigation_during_combat():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color='black')
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((22, 426, 118, 556), radius=7, fill=(154, 81, 49))
    draw.rectangle((100, 735, 260, 782), fill=(221, 176, 40))
    route = auto_play.ButtonCandidate(
        label='右侧道路',
        x=0.91,
        y=0.71,
        confidence=0.91,
        clickability=1.0,
        source='template',
    )
    card = auto_play.ButtonCandidate(
        label='普通攻击',
        x=0.2,
        y=0.63,
        confidence=0.91,
        clickability=1.0,
        source='template',
    )

    filtered = auto_play.filter_tower_context_buttons(image, [route, card], config)

    assert filtered == [card]


def test_tower_combat_detector_rejects_yellow_prebattle_button_without_cards():
    auto_play = load_auto_play_module()
    image = Image.new('RGB', (360, 800), color='black')
    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 735, 260, 782), fill=(221, 176, 40))

    assert not auto_play.tower_combat_screen_visible(image)


def test_tower_combat_detector_rejects_victory_deck_cards_near_bottom():
    auto_play = load_auto_play_module()
    image = Image.new('RGB', (360, 800), color=(18, 21, 24))
    draw = ImageDraw.Draw(image)
    for x1 in (22, 132, 242):
        draw.rounded_rectangle(
            (x1, 599, x1 + 96, 715),
            radius=7,
            fill=(154, 81, 49),
        )
    draw.rectangle((100, 735, 260, 782), fill=(221, 176, 40))

    assert not auto_play.tower_combat_screen_visible(image)


def test_tower_prebattle_adds_stable_battle_button_and_drops_stale_recruit():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color='black')
    title = auto_play.ButtonCandidate(
        label='即将发起战斗',
        x=0.5,
        y=0.1,
        confidence=1.0,
        clickability=2.0,
        source='ocr',
    )
    stale_recruit = auto_play.ButtonCandidate(
        label='雇佣',
        x=0.7,
        y=0.95,
        confidence=0.9,
        clickability=2.0,
        source='template',
    )

    filtered = auto_play.filter_tower_context_buttons(
        image,
        [title, stale_recruit],
        config,
    )
    battle = auto_play.tower_prebattle_start_candidates(config, image, filtered)

    assert filtered == [title]
    assert battle[0].label == '战斗'
    assert battle[0].x == 0.715


def test_tower_prebattle_uses_visual_vs_fallback_without_ocr():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(8, 8, 12))
    pixels = image.load()
    for y in range(380, 470):
        for x in range(130, 230):
            if (x + y) % 4 == 0:
                pixels[x, y] = (160, 160, 165)
    for y in range(740, 790):
        for x in range(35, 170):
            pixels[x, y] = (70, 130, 145)
        for x in range(195, 330):
            pixels[x, y] = (170, 135, 60)

    battle = auto_play.tower_prebattle_start_candidates(config, image, [])

    assert [candidate.label for candidate in battle] == ['战斗']
    assert battle[0].source == 'vision'


def test_tower_map_exit_is_detected_from_stable_cyan_control():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(25, 27, 29))
    draw = ImageDraw.Draw(image)
    draw.ellipse((150, 704, 210, 766), fill=(45, 145, 160))
    draw.polygon([(180, 750), (164, 733), (174, 733), (174, 716),
                  (186, 716), (186, 733), (196, 733)], fill='white')
    floor_label = auto_play.ButtonCandidate(
        label='当前所在层数',
        x=0.62,
        y=0.52,
        confidence=1.0,
        clickability=1.0,
        source='ocr',
    )

    candidates = auto_play.tower_map_exit_candidates(
        image,
        config,
        [floor_label],
    )

    assert len(candidates) == 1
    assert candidates[0].label == '下方道路'
    assert abs(candidates[0].x - 0.5) < 0.01


def test_spire_map_exit_accepts_fractional_floor_hud():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(25, 27, 29))
    draw = ImageDraw.Draw(image)
    draw.ellipse((150, 704, 210, 766), fill=(45, 145, 160))
    draw.polygon(
        [
            (180, 750),
            (164, 733),
            (174, 733),
            (174, 716),
            (186, 716),
            (186, 733),
            (196, 733),
        ],
        fill='white',
    )
    floor_label = auto_play.ButtonCandidate(
        label='当前层数1/7',
        x=0.53,
        y=0.53,
        confidence=1.0,
        clickability=1.0,
        source='ocr',
    )

    candidates = auto_play.tower_map_exit_candidates(
        image,
        config,
        [floor_label],
    )

    assert [candidate.label for candidate in candidates] == ['下方道路']


def test_tower_map_detects_center_up_arrow_and_ignores_stale_left_template():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(25, 27, 29))
    draw = ImageDraw.Draw(image)
    draw.ellipse((150, 470, 210, 535), fill=(45, 145, 160))
    draw.polygon(
        [
            (180, 482),
            (164, 501),
            (174, 501),
            (174, 521),
            (186, 521),
            (186, 501),
            (196, 501),
        ],
        fill='white',
    )
    floor_label = auto_play.ButtonCandidate(
        label='当前所在层数',
        x=0.62,
        y=0.52,
        confidence=1.0,
        clickability=1.0,
        source='ocr',
    )
    stale_left = auto_play.ButtonCandidate(
        label='左侧道路',
        x=0.12,
        y=0.72,
        confidence=0.94,
        clickability=1.0,
        source='template',
    )

    candidates = auto_play.tower_map_exit_candidates(
        image,
        config,
        [floor_label, stale_left],
    )
    selected = auto_play.tower_daily_matching_button(
        [stale_left, *candidates],
        {'上方道路', '左侧道路'},
    )

    assert [candidate.label for candidate in candidates] == ['上方道路']
    assert selected is not None
    assert selected.label == '上方道路'
    assert selected.source == 'vision'


def test_tower_treasure_panel_selects_real_card_before_confirming():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    back = auto_play.ButtonCandidate(
        label='返回',
        x=0.29,
        y=0.70,
        confidence=1.0,
        clickability=2.0,
        source='ocr',
    )
    confirm = auto_play.ButtonCandidate(
        label='确定',
        x=0.74,
        y=0.70,
        confidence=1.0,
        clickability=2.0,
        source='template',
    )
    treasure_title = auto_play.ButtonCandidate(
        label='时之沙漏',
        x=0.50,
        y=0.48,
        confidence=0.98,
        clickability=1.5,
        source='ocr',
    )
    panel_title = auto_play.ButtonCandidate(
        label='宝物选择',
        x=0.50,
        y=0.31,
        confidence=0.99,
        clickability=1.8,
        source='ocr',
    )

    choice = auto_play.tower_treasure_choice_candidate(
        config,
        [back, confirm, treasure_title, panel_title],
    )

    assert choice is not None
    assert choice.label == 'Tower treasure choice: 时之沙漏'
    assert choice.x == 0.5
    assert not auto_play.is_inspectable_item_candidate(
        back,
        fallback_labels=set(),
        avoid_labels=set(),
        ineffective_labels=set(),
        automation_config=config,
    )


def test_tower_predecessor_panel_finds_target_in_any_column_with_abandon_footer(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'awaiting_predecessor_treasure': True},
    )
    monkeypatch.setattr(auto_play, 'load_tower_daily_state', lambda _game: {})
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('宝物选择', 0.5, 0.31),
            ('花喇叭', 0.2, 0.48),
            ('巨人之花', 0.5, 0.48),
            ('毒龙匕首', 0.8, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_treasure_choice_candidate(config, buttons)

    assert choice is not None
    assert '毒龙匕首' in choice.label
    assert choice.x == 0.8
    assert choice.y == 0.37


def test_tower_predecessor_panel_accepts_knight_mace_ocr_typo(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '战士')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'awaiting_predecessor_treasure': True},
    )
    monkeypatch.setattr(auto_play, 'load_tower_daily_state', lambda _game: {})
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('宝物选择', 0.5, 0.31),
            ('燃烧辣椒', 0.2, 0.48),
            ('骑土狼牙棒', 0.5, 0.48),
            ('骑士之翼', 0.8, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_treasure_choice_candidate(config, buttons)

    assert choice is not None
    assert '骑土狼牙棒' in choice.label
    assert choice.x == 0.5


def test_tower_mage_predecessor_panel_prefers_electric_potion_after_reroll_limit(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '法师')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'floor': 1, 'phase': 'climbing_map'},
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {
            'phase': 'abyss_retry',
            'predecessor_rerolls': auto_play.TOWER_PREDECESSOR_REROLL_LIMIT,
        },
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('宝物选择', 0.5, 0.31),
            ('草龙蛋', 0.2, 0.48),
            ('过期卷轴', 0.5, 0.48),
            ('电虫药水', 0.8, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_treasure_choice_candidate(config, buttons)

    assert choice is not None
    assert '电虫药水' in choice.label
    assert choice.x == 0.8


def test_tower_predecessor_panel_uses_observed_profession_over_preference(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '战士')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'awaiting_predecessor_treasure': True},
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {
            'phase': 'abyss_retry',
            'preferred_abyss_profession': '法师',
            'predecessor_rerolls': 0,
        },
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('宝物选择', 0.5, 0.31),
            ('骑士狼牙棒', 0.2, 0.48),
            ('电虫药水', 0.5, 0.48),
            ('骑士之翼', 0.8, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_treasure_choice_candidate(config, buttons)

    assert choice is not None
    assert '骑士狼牙棒' in choice.label
    assert choice.x == 0.2


def test_tower_predecessor_panel_prefers_trumpet_after_reroll_limit(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'awaiting_predecessor_treasure': False,
            'floor': 1,
            'phase': 'climbing_map',
        },
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {
            'phase': 'abyss_retry',
            'predecessor_rerolls': auto_play.TOWER_PREDECESSOR_REROLL_LIMIT,
        },
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('宝物选择', 0.5, 0.31),
            ('安全出口', 0.2, 0.48),
            ('花喇叭', 0.5, 0.48),
            ('巨人之花', 0.8, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_treasure_choice_candidate(config, buttons)

    assert choice is not None
    assert '花喇叭' in choice.label
    assert choice.x == 0.5


def test_tower_predecessor_panel_accepts_trumpet_ocr_transposition_after_limit(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'floor': 1, 'phase': 'climbing_map'},
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {
            'phase': 'abyss_retry',
            'predecessor_rerolls': auto_play.TOWER_PREDECESSOR_REROLL_LIMIT,
        },
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('宝物选择', 0.5, 0.31),
            ('贵族拖鞋', 0.2, 0.48),
            ('花叭喇', 0.5, 0.48),
            ('能量棒', 0.8, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_treasure_choice_candidate(config, buttons)

    assert choice is not None
    assert '花叭喇' in choice.label
    assert choice.x == 0.5


def test_create_turn_artifacts_recovers_from_directory_creation_race(
    monkeypatch,
    tmp_path,
):
    auto_play = load_auto_play_module()
    args = type(
        'Args',
        (),
        {
            'game': 'tower',
            'turns_dir': tmp_path,
            'fixed_dir': None,
            'turn_history_limit': 20,
        },
    )()
    original_mkdir = auto_play.Path.mkdir
    raced = False

    def mkdir_with_race(path, *mkdir_args, **mkdir_kwargs):
        nonlocal raced
        if not raced and path.parent == tmp_path and path.name.endswith('-tower'):
            raced = True
            original_mkdir(path, parents=True)
            raise FileExistsError(path)
        return original_mkdir(path, *mkdir_args, **mkdir_kwargs)

    monkeypatch.setattr(auto_play.Path, 'mkdir', mkdir_with_race)

    artifacts, _timestamp = auto_play.create_turn_artifacts(args)

    assert raced
    assert artifacts['turn_dir'].name.endswith('-tower-02')
    assert artifacts['turn_dir'].is_dir()


def test_tower_selected_choice_modal_confirms_instead_of_backing_out():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    back = auto_play.ButtonCandidate(
        label='Back',
        x=0.29,
        y=0.70,
        confidence=1.0,
        clickability=2.0,
        source='ocr',
    )
    confirm = auto_play.ButtonCandidate(
        label='确定',
        x=0.74,
        y=0.70,
        confidence=1.0,
        clickability=2.0,
        source='template',
    )
    stale_card = auto_play.ButtonCandidate(
        label='迅捷攻击',
        x=0.61,
        y=0.70,
        confidence=0.88,
        clickability=1.5,
        source='template',
    )

    scored = auto_play.score_buttons(
        [back, confirm, stale_card],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '确定'


def test_periodic_ocr_tuning_runs_every_50_loop_turns():
    auto_play = load_auto_play_module()

    args = SimpleNamespace(
        loop=True,
        ocr_tune_every_turns=50,
        ocr_tune_iterations=10,
    )

    assert auto_play.should_run_periodic_ocr_tuning(args, 50)
    assert auto_play.should_run_periodic_ocr_tuning(args, 100)
    assert not auto_play.should_run_periodic_ocr_tuning(args, 49)
    assert not auto_play.should_run_periodic_ocr_tuning(
        SimpleNamespace(
            loop=False,
            ocr_tune_every_turns=50,
            ocr_tune_iterations=10,
        ),
        50,
    )


def test_stuck_ocr_tuning_requires_clicking_and_iterations():
    auto_play = load_auto_play_module()

    assert auto_play.should_run_stuck_ocr_tuning(
        SimpleNamespace(click_recommended=True, ocr_tune_on_stuck_iterations=10)
    )
    assert not auto_play.should_run_stuck_ocr_tuning(
        SimpleNamespace(click_recommended=False, ocr_tune_on_stuck_iterations=10)
    )
    assert not auto_play.should_run_stuck_ocr_tuning(
        SimpleNamespace(click_recommended=True, ocr_tune_on_stuck_iterations=0)
    )


def test_periodic_ocr_tuning_command_uses_last_50_turn_window(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    turns_dir = tmp_path / 'games' / 'tower' / 'turns'
    output_dir = tmp_path / 'games' / 'tower' / 'ocr-tuning'
    args = SimpleNamespace(
        game='tower',
        turns_dir=turns_dir,
        fixed_dir=None,
        ocr_tune_output_dir=output_dir,
        ocr_tune_recent_turns=50,
        confidence=0.72,
        template_match_threshold=0.91,
    )

    command = auto_play.periodic_ocr_tuning_command(args, turn=50, iteration=3)

    assert command[0] == sys.executable
    assert command[1].endswith('scripts/tune_ocr.py')
    assert command[command.index('--turns-dir') + 1] == str(turns_dir)
    assert command[command.index('--output-dir') + 1] == str(output_dir)
    assert command[command.index('--recent-turns') + 1] == '50'
    assert command[command.index('--run-name') + 1] == 'periodic-turn-000050-iter-03'


def test_stuck_ocr_tuning_command_uses_stuck_run_name(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    turns_dir = tmp_path / 'games' / 'tower' / 'turns'
    output_dir = tmp_path / 'games' / 'tower' / 'ocr-tuning'
    args = SimpleNamespace(
        game='tower',
        turns_dir=turns_dir,
        fixed_dir=None,
        ocr_tune_output_dir=output_dir,
        ocr_tune_recent_turns=50,
        confidence=0.72,
        template_match_threshold=0.91,
    )

    command = auto_play.periodic_ocr_tuning_command(
        args,
        turn=7,
        iteration=2,
        run_name_prefix='stuck',
        recent_turns=10,
    )

    assert command[command.index('--run-name') + 1] == 'stuck-turn-000007-iter-02'
    assert command[command.index('--recent-turns') + 1] == '10'


def test_ocr_tuning_report_complete_when_no_ready_actions_are_missing(tmp_path):
    auto_play = load_auto_play_module()
    report = tmp_path / 'report.yaml'
    report.write_text(
        """
ready_actions: 12
ready_actions_captured_by_ocr: 12
ready_actions_missing_from_ocr: 0
capture_rate: 1.0
"""
    )

    assert auto_play.ocr_tuning_report_is_complete(report)


def test_ocr_tuning_report_not_complete_without_ready_actions(tmp_path):
    auto_play = load_auto_play_module()
    report = tmp_path / 'report.yaml'
    report.write_text(
        """
ready_actions: 0
ready_actions_captured_by_ocr: 0
ready_actions_missing_from_ocr: 0
capture_rate: 1.0
"""
    )

    assert not auto_play.ocr_tuning_report_is_complete(report)


def test_tune_ocr_recent_turns_uses_latest_matching_game_turns(tmp_path):
    tune_ocr = load_tune_ocr_module()

    for name in [
        '20260101T000001-0800-tower',
        '20260101T000002-0800-tower',
        '20260101T000003-0800-other',
        '20260101T000004-0800-tower',
        '20260101T000005-0800-tower',
    ]:
        (tmp_path / name).mkdir()

    args = SimpleNamespace(
        turns_dir=tmp_path,
        game='tower',
        recent_turns=2,
        max_turns=0,
    )

    assert [path.name for path in tune_ocr.selected_turn_dirs(args)] == [
        '20260101T000004-0800-tower',
        '20260101T000005-0800-tower',
    ]


def test_tune_ocr_refreshes_game_info_after_scoring(tmp_path, monkeypatch):
    tune_ocr = load_tune_ocr_module()
    run_dir = tmp_path / 'run'
    game_info = tmp_path / 'games' / 'tower' / 'game_info.md'
    refreshed_games = []
    args = SimpleNamespace(
        game='tower',
        mode='regenerate',
        turns_dir=tmp_path / 'turns',
        recent_turns=0,
        disable_template_matching=False,
        template_match_threshold=0.82,
        confidence=0.8,
        label_threshold=0.68,
        coord_tolerance=0.06,
        example_labels=8,
        examples_per_label=3,
        baseline_report=None,
        minimum_captured_delta=1,
        fail_unless_improved=False,
    )

    def fake_refresh(game):
        refreshed_games.append(game)
        game_info.parent.mkdir(parents=True)
        game_info.write_text('# Game Info: tower\n')
        return game_info

    monkeypatch.setattr(tune_ocr, 'parse_args', lambda: args)
    monkeypatch.setattr(
        tune_ocr,
        'create_run_dir',
        lambda _args: run_dir.mkdir(parents=True) or run_dir,
    )
    monkeypatch.setattr(tune_ocr, 'score_turns', lambda _args, _run_dir: [])
    monkeypatch.setattr(tune_ocr, 'refresh_game_info', fake_refresh)

    assert tune_ocr.main() == 0

    assert refreshed_games == ['tower']
    report = (run_dir / 'report.yaml').read_text()
    summary = (run_dir / 'summary.md').read_text()
    assert 'game_info_refreshed: true' in report
    assert f'game_info_path: {game_info}' in report
    assert f'- Game info refreshed: `{game_info}`' in summary


def test_llm_result_is_consumed_after_one_turn():
    auto_play = load_auto_play_module()
    args = SimpleNamespace(llm_result=Path('turns/turn-001/llm.yaml'))

    auto_play.clear_consumed_llm_result(args)

    assert args.llm_result is None


def test_stat_delta_labels_are_not_action_candidates():
    auto_play = load_auto_play_module()

    assert auto_play.looks_like_noise_label('±2')
    assert auto_play.looks_like_noise_label('+4')
    assert auto_play.looks_like_noise_label('-5')
    assert auto_play.looks_like_noise_label('QQ')
    assert auto_play.looks_like_noise_label('QQ0')
    assert auto_play.looks_like_noise_label('xx')
    assert auto_play.looks_like_noise_label('XX')
    assert auto_play.looks_like_noise_label('BEA')
    assert auto_play.looks_like_noise_label('x1')
    assert auto_play.looks_like_noise_label('i2')
    assert auto_play.looks_like_noise_label('(%)')
    assert auto_play.looks_like_noise_label('CM')
    assert auto_play.looks_like_noise_label('50 >> 52')
    assert auto_play.looks_like_noise_label('>>')
    assert auto_play.looks_like_noise_label('@1943')
    assert auto_play.looks_like_noise_label('123)')
    assert auto_play.looks_like_noise_label('1-1')
    assert auto_play.looks_like_noise_label('58-8M')
    assert auto_play.looks_like_noise_label('-28M')
    assert auto_play.looks_like_noise_label('6.72M-6.726.7')
    assert auto_play.looks_like_noise_label('L-37B')
    assert auto_play.looks_like_noise_label('.5M')
    assert auto_play.looks_like_noise_label('.14BM')
    assert auto_play.looks_like_noise_label('72-5MEM')
    assert auto_play.looks_like_noise_label('33.9MK')
    assert auto_play.looks_like_noise_label('483M483')
    assert auto_play.looks_like_noise_label('267M342M2')
    assert auto_play.looks_like_noise_label('28.9M3.9M')
    assert auto_play.looks_like_noise_label('Lv.1')
    assert auto_play.looks_like_noise_label('V.2')
    assert auto_play.looks_like_noise_label('V.25')
    assert auto_play.looks_like_noise_label('xx2894')
    assert auto_play.looks_like_noise_label('x*3010')
    assert not auto_play.looks_like_noise_label('END')
    assert not auto_play.looks_like_noise_label('OK')


def test_template_overlapping_avoid_button_is_filtered():
    auto_play = load_auto_play_module()
    merge_template = auto_play.ButtonCandidate(
        label='merge weapon',
        x=0.5625,
        y=0.9187,
        confidence=0.84,
        clickability=0.75,
        source='template',
    )
    abandon_ocr = auto_play.ButtonCandidate(
        label='Abandon',
        x=0.5014,
        y=0.9163,
        confidence=1.0,
        clickability=0.91,
        source='ocr',
    )

    filtered = auto_play.filter_conflicting_template_buttons(
        [merge_template, abandon_ocr]
    )

    assert filtered == [abandon_ocr]


def test_combat_cards_are_double_clicked():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    assert auto_play.should_double_click_button(
        auto_play.ButtonCandidate(
            label='普通木剑',
            x=0.5,
            y=0.5,
            confidence=1.0,
            clickability=1.0,
        ),
        config,
    )
    assert auto_play.should_double_click_button(
        auto_play.ButtonCandidate(
            label='快速思考！',
            x=0.5,
            y=0.5,
            confidence=1.0,
            clickability=1.0,
        ),
        config,
    )
    assert auto_play.should_double_click_button(
        auto_play.ButtonCandidate(
            label='快速思考]',
            x=0.5,
            y=0.5,
            confidence=1.0,
            clickability=1.0,
        ),
        config,
    )
    assert not auto_play.should_double_click_button(
        auto_play.ButtonCandidate(
            label='进入冒险',
            x=0.5,
            y=0.5,
            confidence=1.0,
            clickability=1.0,
        ),
        config,
    )


def test_template_overlapping_llm_avoid_button_is_filtered():
    auto_play = load_auto_play_module()
    merge_template = auto_play.ButtonCandidate(
        label='merge weapon',
        x=0.7569,
        y=0.8375,
        confidence=0.92,
        clickability=0.89,
        source='template',
    )
    abandon_llm = auto_play.ButtonCandidate(
        label='放弃',
        x=0.72,
        y=0.84,
        confidence=0.9,
        clickability=0.8,
        source='llm',
    )

    filtered = auto_play.filter_conflicting_template_buttons(
        [merge_template, abandon_llm]
    )

    assert filtered == [abandon_llm]


def test_default_avoid_list_does_not_block_uncertain_utility_actions():
    auto_play = load_auto_play_module()

    defaults = {auto_play.normalize_label(item) for item in auto_play.DEFAULT_AVOID}

    assert '融合' not in defaults
    assert 'back' not in defaults
    assert 'shop' not in defaults
    assert '遗忘法阵' not in defaults
    assert '放弃冒险' in defaults


def test_lower_progress_verification_ignores_upper_animation():
    auto_play = load_auto_play_module()
    before = Image.new('RGB', (100, 100), color='black')
    after = Image.new('RGB', (100, 100), color='black')
    draw = ImageDraw.Draw(after)
    draw.rectangle((0, 0, 100, 40), fill='navy')

    button = auto_play.ButtonCandidate(
        label='Next Room',
        x=0.5,
        y=0.9,
        confidence=0.9,
        clickability=0.8,
        source='template',
    )

    full_similarity, progress_similarity, region = auto_play.state_change_similarities(
        before,
        after,
        button,
    )

    assert region == 'lower_progress_region'
    assert full_similarity < 0.995
    assert progress_similarity == 1.0


def test_lower_progress_verification_sees_lower_ui_change():
    auto_play = load_auto_play_module()
    before = Image.new('RGB', (100, 100), color='black')
    after = Image.new('RGB', (100, 100), color='black')
    draw = ImageDraw.Draw(after)
    draw.rectangle((30, 70, 70, 95), fill='white')

    button = auto_play.ButtonCandidate(
        label='Next Room',
        x=0.5,
        y=0.9,
        confidence=0.9,
        clickability=0.8,
        source='template',
    )

    _full_similarity, progress_similarity, region = auto_play.state_change_similarities(
        before,
        after,
        button,
    )

    assert region == 'lower_progress_region'
    assert progress_similarity < 0.985


def test_tower_combat_card_verification_does_not_repeat_failed_clicks(
    monkeypatch,
    tmp_path,
):
    auto_play = load_auto_play_module()
    before = Image.new('RGB', (100, 100), color='black')
    clicks = []
    config = automation_config(auto_play, 'tower')
    monkeypatch.setattr(auto_play, 'load_automation_config', lambda _game: config)
    monkeypatch.setattr(
        auto_play,
        'load_image',
        lambda _args: (before.copy(), {}),
    )
    monkeypatch.setattr(auto_play, 'click_button', lambda *_args: clicks.append(True))
    monkeypatch.setattr(
        auto_play,
        'append_no_change_learning',
        lambda *_args: False,
    )
    args = SimpleNamespace(
        game='tower',
        image=None,
        state_similarity_threshold=0.995,
        state_progress_similarity_threshold=0.985,
        state_change_interval=0,
        state_change_retries=3,
    )
    button = auto_play.ButtonCandidate(
        label='Visible playable card: 投掷',
        x=0.5,
        y=0.6,
        confidence=0.96,
        clickability=7.4,
        source='vision',
    )

    verification = auto_play.verify_state_changed_after_click(
        args,
        before_image=before,
        button=button,
        last_screenshot_path=tmp_path / 'last.png',
    )

    assert verification.status == 'unchanged'
    assert verification.attempts == 1
    assert clicks == []


def test_unblock_window_detects_similar_screens_and_recent_actions(tmp_path):
    auto_play = load_auto_play_module()

    for index, label in enumerate(
        ['Chest', 'Next Room', 'Chest', 'Next Room', 'Chest']
    ):
        turn_dir = tmp_path / f'turn-{index:03d}'
        turn_dir.mkdir()
        Image.new('RGB', (40, 40), color='black').save(turn_dir / 'screenshot.png')
        (turn_dir / 'metadata.yaml').write_text(
            f"""
worklog:
  action_taken:
    label: {label}
"""
        )

    assessment = auto_play.assess_unblock_window(
        tmp_path,
        window_size=5,
        threshold=0.975,
    )

    assert assessment.status == 'stuck'
    assert assessment.repeated_actions == ['Chest', 'Next Room']
    assert assessment.similarities == [1.0, 1.0, 1.0, 1.0]


def test_unblock_decision_prefers_not_recently_repeated_candidate():
    auto_play = load_auto_play_module()

    repeated = auto_play.ButtonCandidate(
        label='Chest',
        x=0.2,
        y=0.6,
        confidence=0.95,
        clickability=0.8,
        score=2.0,
    )
    fresh = auto_play.ButtonCandidate(
        label='Close',
        x=0.9,
        y=0.2,
        confidence=0.7,
        clickability=0.8,
        score=1.0,
    )

    decision = auto_play.decide_unblock_move(
        [repeated, fresh],
        {'chest'},
    )

    assert decision.status == 'ready'
    assert decision.recommended.label == 'Close'


def test_navigation_oscillation_avoids_reversing_arrows(tmp_path):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    for index, label in enumerate(
        ['左侧道路', '右侧道路', '左侧道路', '右侧道路'], start=1
    ):
        turn_dir = tmp_path / f'turn-{index:03d}'
        turn_dir.mkdir()
        (turn_dir / 'metadata.yaml').write_text(
            f"""
worklog:
  action_taken:
    label: {label}
"""
        )

    avoid = auto_play.navigation_oscillation_avoid_labels(
        tmp_path,
        automation_config=config,
    )

    assert avoid == {'左侧道路', '右侧道路'}

    (tmp_path / 'turn-005').mkdir()
    inspect_only = tmp_path / 'turn-006'
    inspect_only.mkdir()
    (inspect_only / 'metadata.yaml').write_text('worklog:\n  action_taken: null\n')

    assert auto_play.navigation_oscillation_avoid_labels(
        tmp_path,
        automation_config=config,
    ) == {
        '左侧道路',
        '右侧道路',
    }


def test_navigation_only_loop_avoids_recent_minimap_arrows(tmp_path):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    for index, label in enumerate(
        ['右侧道路', '左侧道路', '右侧道路', '上方道路'], start=1
    ):
        turn_dir = tmp_path / f'turn-{index:03d}'
        turn_dir.mkdir()
        (turn_dir / 'metadata.yaml').write_text(
            f"""
worklog:
  action_taken:
    label: {label}
"""
        )

    assert auto_play.navigation_only_loop_avoid_labels(
        tmp_path,
        automation_config=config,
    ) == {
        '右侧道路',
        '左侧道路',
        '上方道路',
    }


def test_top_playfield_probe_beats_minimap_arrow_during_navigation_loop():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    minimap_arrow = auto_play.ButtonCandidate(
        label='上方道路',
        x=0.48,
        y=0.63,
        confidence=0.89,
        clickability=0.87,
        source='template',
    )
    probe = auto_play.top_playfield_path_probe_candidates(
        [minimap_arrow],
        config,
    )[0]

    scored = auto_play.score_buttons(
        [minimap_arrow, probe],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )
    decision = auto_play.decide_unblock_move(scored, {'上方道路'})

    assert probe.label == 'Top path up'
    assert decision.recommended.label == 'Top path up'


def test_tower_map_room_detector_prefers_concrete_room_over_arrows(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'load_tower_run_state', lambda _game: {})
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(28, 32, 34))
    draw = ImageDraw.Draw(image)
    draw.rectangle((55, 495, 132, 572), fill=(92, 178, 60))
    draw.rectangle((218, 492, 323, 584), fill=(80, 170, 210))
    arrows = [
        auto_play.ButtonCandidate(
            label='上方道路',
            x=0.48,
            y=0.63,
            confidence=0.89,
            clickability=0.87,
            source='template',
        ),
        auto_play.ButtonCandidate(
            label='下方道路',
            x=0.49,
            y=0.92,
            confidence=0.97,
            clickability=1.22,
            source='template',
        ),
    ]

    room_candidates = auto_play.tower_map_room_icon_candidates(
        image,
        config,
        arrows,
    )
    scored = auto_play.score_buttons(
        [*arrows, *room_candidates],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert [button.label for button in room_candidates] == [
        'Visible combat room icon',
        'Visible room icon',
    ]
    assert scored[0].label == 'Visible combat room icon'
    assert scored[0].source == 'vision'


def test_tower_map_room_detector_finds_only_room_from_map_hud():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(28, 32, 34))
    draw = ImageDraw.Draw(image)
    draw.rectangle((55, 495, 132, 572), fill=(92, 178, 60))
    floor_hud = auto_play.ButtonCandidate(
        label='当前所在层数',
        x=0.50,
        y=0.52,
        confidence=0.98,
        clickability=1.5,
        source='ocr',
    )
    room_candidates = auto_play.tower_map_room_icon_candidates(
        image,
        config,
        [floor_hud],
    )

    assert [button.label for button in room_candidates] == [
        'Visible combat room icon'
    ]
    assert room_candidates[0].x < 0.4


def test_tower_map_room_detector_prioritizes_next_floor_stair_room():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(28, 32, 34))
    draw = ImageDraw.Draw(image)
    draw.rectangle((53, 491, 132, 582), fill=(70, 135, 170))
    draw.rectangle((68, 506, 117, 564), fill=(170, 180, 185))
    draw.rectangle((224, 514, 267, 559), fill=(155, 86, 65))
    floor_hud = auto_play.ButtonCandidate(
        label='当前所在层数',
        x=0.50,
        y=0.52,
        confidence=0.98,
        clickability=1.5,
        source='ocr',
    )
    next_floor_label = auto_play.ButtonCandidate(
        label='进入下一层',
        x=0.26,
        y=0.69,
        confidence=0.98,
        clickability=1.5,
        source='ocr',
    )

    room_candidates = auto_play.tower_map_room_icon_candidates(
        image,
        config,
        [floor_hud, next_floor_label],
    )

    assert room_candidates[0].label == 'Visible next-floor stair room'
    assert room_candidates[0].x < 0.4
    assert room_candidates[0].clickability == 9.0

    route = auto_play.ButtonCandidate(
        label='右侧道路',
        x=0.93,
        y=0.75,
        confidence=0.99,
        clickability=1.0,
        source='template',
        score=8.0,
        reason='Leave recently completed Tower room.',
    )
    scored = auto_play.score_buttons(
        [route, *room_candidates],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )
    decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.5,
        ambiguity_margin=0.25,
        ask_on_ambiguous=False,
        automation_config=config,
    )

    assert decision.recommended.label == 'Visible next-floor stair room'


def test_tower_next_floor_does_not_skip_strategic_build_room():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='Visible next-floor stair room',
            x=0.26,
            y=0.67,
            confidence=0.98,
            clickability=9.0,
            source='vision',
            score=4.58,
        ),
        auto_play.ButtonCandidate(
            label='训练师任务',
            x=0.73,
            y=0.69,
            confidence=0.99,
            clickability=1.7,
            source='ocr',
            score=8.6,
        ),
    ]

    decision = auto_play.decide_next_move(
        buttons,
        min_action_score=0.5,
        ambiguity_margin=0.25,
        ask_on_ambiguous=False,
        automation_config=config,
    )

    assert decision.recommended.label == '训练师任务'


def test_tower_red_task_badge_is_hard_priority(monkeypatch):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {'phase': 'abyss_retry'},
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'stage': '深渊楼梯', 'phase': 'climbing_map'},
    )
    task = auto_play.ButtonCandidate(
        label='任务',
        x=0.11,
        y=0.556,
        confidence=0.99,
        clickability=1.8,
        source='ocr',
        bbox=(0.075, 0.546, 0.147, 0.565),
    )
    route = auto_play.ButtonCandidate(
        label='上方道路',
        x=0.49,
        y=0.64,
        confidence=0.99,
        clickability=7.0,
        source='vision',
    )
    end_turn = auto_play.ButtonCandidate(
        label='结束回合',
        x=0.5,
        y=0.92,
        confidence=0.99,
        clickability=4.0,
        source='vision',
    )
    no_badge = Image.new('RGB', (360, 800), color=(20, 20, 20))
    assert auto_play.tower_task_reward_badge_candidate(
        config,
        [task, route],
        no_badge,
    ) is None

    image = no_badge.copy()
    ImageDraw.Draw(image).ellipse((59, 430, 73, 443), fill=(220, 25, 25))
    assert auto_play.tower_task_reward_badge_candidate(
        config,
        [end_turn, route],
        image,
    ) is None
    assert auto_play.tower_task_reward_badge_candidate(
        config,
        [task, end_turn, route],
        image,
    ) is None

    reward = auto_play.tower_task_reward_badge_candidate(
        config,
        [task, route],
        image,
    )

    assert reward is not None
    selected = auto_play.tower_daily_policy_candidates(
        'tower',
        [task, route, reward],
    )
    assert selected is not None
    assert selected[0].label == '任务'
    assert selected[0].clickability == 25.0

    assert auto_play.tower_task_reward_badge_candidate(
        config,
        [
            auto_play.ButtonCandidate(
                label='角色',
                x=0.6,
                y=0.95,
                confidence=0.99,
                clickability=1.8,
                source='ocr',
            )
        ],
        image,
    ) is None

    inn_button = auto_play.ButtonCandidate(
        label='旅馆',
        x=0.3,
        y=0.98,
        confidence=0.99,
        clickability=1.8,
        source='ocr',
    )
    assert auto_play.tower_task_reward_badge_candidate(
        config,
        [inn_button],
        image,
    ) is None


def test_tower_checks_task_panel_once_per_run_without_badge(monkeypatch):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    state = {
        'stage': '深渊楼梯',
        'phase': 'climbing_map',
        'battle_number': 3,
        'trainer_task_checked_once': False,
    }
    monkeypatch.setattr(auto_play, 'load_tower_run_state', lambda _game: state)
    task = auto_play.ButtonCandidate(
        label='任务',
        x=0.11,
        y=0.556,
        confidence=0.99,
        clickability=1.8,
        source='ocr',
        bbox=(0.075, 0.546, 0.147, 0.565),
    )
    image = Image.new('RGB', (360, 800), color=(20, 20, 20))

    check = auto_play.tower_task_reward_badge_candidate(
        config,
        [task],
        image,
    )

    assert check is not None
    assert 'post-battle check' in check.reason
    state['trainer_task_checked_once'] = True
    assert auto_play.tower_task_reward_badge_candidate(
        config,
        [task],
        image,
    ) is None


def test_tower_daily_claims_completed_trainer_task(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {'phase': 'abyss_retry'},
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'stage': '深渊楼梯', 'phase': 'climbing_map'},
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='训练师任务',
            x=0.5,
            y=0.12,
            confidence=0.99,
            clickability=0.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='还可以领取2个任务',
            x=0.5,
            y=0.16,
            confidence=0.99,
            clickability=0.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='领取',
            x=0.829,
            y=0.212,
            confidence=0.99,
            clickability=1.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='点击空白处关闭',
            x=0.5,
            y=0.81,
            confidence=0.99,
            clickability=1.0,
            source='ocr',
        ),
    ]

    selected = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selected is not None
    assert selected[0].label == '领取'
    assert selected[0].clickability == 25.0


def test_tower_daily_closes_empty_trainer_task_panel(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {'phase': 'abyss_retry'},
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'stage': '深渊楼梯', 'phase': 'climbing_map'},
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='训练师任务',
            x=0.5,
            y=0.09,
            confidence=0.99,
            clickability=0.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='还可以领取3个任务',
            x=0.5,
            y=0.12,
            confidence=0.99,
            clickability=0.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='点击空白处关闭',
            x=0.5,
            y=0.885,
            confidence=0.99,
            clickability=1.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='右侧道路',
            x=0.92,
            y=0.74,
            confidence=0.94,
            clickability=1.0,
            source='template',
        ),
    ]

    selected = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selected is not None
    assert selected[0].label == '点击空白处关闭'
    assert selected[0].clickability == 25.0


def test_tower_daily_checks_but_skips_unsafe_trainer_reward(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {'phase': 'abyss_retry'},
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'stage': '深渊楼梯',
            'phase': 'climbing_map',
            'skip_unsafe_trainer_reward': True,
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=1.0,
            source='ocr',
        )
        for label, x, y in (
            ('训练师任务', 0.5, 0.12),
            ('还可以领取2个任务', 0.5, 0.16),
            ('领取', 0.829, 0.212),
            ('敌方物攻增加100点', 0.5, 0.25),
            ('返回', 0.5, 0.96),
        )
    ]

    selected = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selected is not None
    assert selected[0].label == '返回'
    assert selected[0].clickability == 25.0


def test_tower_exit_route_does_not_skip_card_forgetting_room():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='上方道路',
            x=0.49,
            y=0.64,
            confidence=0.99,
            clickability=7.0,
            source='vision',
            score=14.19,
            reason='Leave recently completed Tower room.',
        ),
        auto_play.ButtonCandidate(
            label='遗忘法阵',
            x=0.70,
            y=0.69,
            confidence=0.98,
            clickability=1.6,
            source='ocr',
            score=10.42,
        ),
        auto_play.ButtonCandidate(
            label='休息点',
            x=0.27,
            y=0.69,
            confidence=0.98,
            clickability=1.6,
            source='ocr',
            score=6.42,
        ),
    ]

    decision = auto_play.decide_next_move(
        buttons,
        min_action_score=0.5,
        ambiguity_margin=0.25,
        ask_on_ambiguous=False,
        automation_config=config,
    )

    assert decision.recommended.label == '遗忘法阵'


def test_tower_mysterious_trade_exits_without_spending_fortune():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source=source,
        )
        for label, x, y, source in (
            ('神秘交易', 0.5, 0.35, 'ocr'),
            ('用2点财运换取1张超越卡', 0.5, 0.62, 'ocr'),
            ('我再想想', 0.5, 0.69, 'ocr'),
            ('拿走前辈的宝物', 0.49, 0.66, 'template'),
        )
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '我再想想'


def test_tower_life_beggar_leaves_without_spending_health():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source=source,
        )
        for label, y, source in (
            ('生命乞丐', 0.35, 'ocr'),
            ('分它15点生命，拿走卡牌', 0.62, 'ocr'),
            ('离开', 0.69, 'ocr'),
            ('拿走前辈的宝物', 0.66, 'template'),
        )
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '离开'
    assert scored[-1].label == '拿走前辈的宝物'


def test_tower_map_room_detector_uses_pure_cv_when_ocr_is_empty():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(28, 32, 34))
    draw = ImageDraw.Draw(image)
    draw.rectangle((55, 495, 132, 572), fill=(92, 178, 60))

    room_candidates = auto_play.tower_map_room_icon_candidates(
        image,
        config,
        [],
    )

    assert [button.label for button in room_candidates] == [
        'Visible combat room icon'
    ]
    assert auto_play.filter_configured_disabled_gray_buttons(
        config,
        image,
        room_candidates,
    ) == room_candidates

def test_tower_unactivated_treasure_banner_is_passive_text():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    banner = auto_play.ButtonCandidate(
        label='冒险者携带的未激活宝物',
        x=0.50,
        y=0.30,
        confidence=0.98,
        clickability=1.5,
        source='ocr',
    )

    filtered = auto_play.filter_configured_non_action_buttons(config, [banner])

    assert filtered == []


def test_tower_dynamic_floor_status_is_passive_text():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.50,
            y=y,
            confidence=0.98,
            clickability=1.6,
            source='ocr',
        )
        for label, y in (
            ('当前层数1/7', 0.53),
            ('该层剩余冒险事件：8', 0.50),
        )
    ]

    assert auto_play.filter_configured_non_action_buttons(config, buttons) == []


def test_tower_map_floor_number_cannot_beat_visible_room():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    floor_number = auto_play.ButtonCandidate(
        label='2',
        x=0.6347,
        y=0.5331,
        confidence=0.993,
        clickability=1.948,
        source='ocr',
    )
    room = auto_play.ButtonCandidate(
        label='Visible combat room icon',
        x=0.2542,
        y=0.6631,
        confidence=0.98,
        clickability=7.0,
        source='vision',
    )

    filtered = auto_play.filter_configured_non_action_buttons(
        config,
        [floor_number, room],
    )
    scored = auto_play.score_buttons(
        filtered,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )
    decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.5,
        ambiguity_margin=0.25,
        ask_on_ambiguous=False,
        automation_config=config,
    )

    assert [button.label for button in filtered] == ['Visible combat room icon']
    assert decision.recommended.label == 'Visible combat room icon'


def test_tower_loading_text_becomes_wait_candidate():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    loading = auto_play.ButtonCandidate(
        label='正在前往魔塔冒险..',
        x=0.50,
        y=0.87,
        confidence=0.98,
        clickability=1.6,
        source='ocr',
    )

    assert auto_play.filter_configured_non_action_buttons(config, [loading]) == []
    wait = auto_play.tower_loading_wait_candidates(config, [loading])

    assert len(wait) == 1
    assert wait[0].source == 'wait'
    assert wait[0].label == '等待页面加载'


def test_tower_reward_overlay_gets_visual_close_candidate():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(5, 5, 5))
    pixels = image.load()
    for y in range(90, 150):
        for x in range(100, 260):
            if (x + y) % 4 == 0:
                pixels[x, y] = (210, 145, 20)
    for y in range(270, 430):
        for x in range(115, 245):
            if (x + y) % 3 == 0:
                pixels[x, y] = (190, 190, 190)

    candidates = auto_play.tower_reward_overlay_close_candidates(config, image)

    assert [candidate.label for candidate in candidates] == ['点击空白处关闭']
    assert candidates[0].source == 'vision'


def test_tower_stair_modal_gets_visual_route_and_confirm_candidates():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(8, 8, 8))
    pixels = image.load()
    for y in range(540, 610):
        for x in range(40, 160):
            pixels[x, y] = (65, 115, 125)
        for x in range(205, 325):
            pixels[x, y] = (175, 135, 55)

    candidates = auto_play.tower_stair_choice_visual_candidates(config, image, [])

    assert [candidate.label for candidate in candidates] == [
        '选择一个楼梯',
        '左侧楼梯',
        '右侧楼梯',
        '确定',
    ]
    assert auto_play.tower_stair_choice_candidate(config, candidates).label == (
        '右侧楼梯'
    )


def test_tower_unreadable_card_reward_uses_visual_skip(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text('stage: 深渊楼梯\nphase: card_reward\n')
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(8, 8, 8))
    pixels = image.load()
    for y in range(540, 575):
        for x in range(45, 165):
            pixels[x, y] = (80, 150, 165)
        for x in range(205, 325):
            pixels[x, y] = (180, 145, 70)

    candidates = auto_play.tower_unreadable_card_reward_skip_candidates(
        config,
        image,
        [],
    )

    assert [candidate.label for candidate in candidates] == ['放弃']
    assert candidates[0].source == 'vision'


def test_tower_ad_revive_uses_stable_yellow_button_not_dialog_title():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('看广告复活', 0.5, 0.55),
            ('取消', 0.30, 0.63),
            ('复活', 0.69, 0.63),
        )
    ]

    candidate = auto_play.tower_ad_revive_candidate(config, buttons)

    assert candidate is not None
    assert candidate.label == '复活（广告）'
    assert candidate.x == 0.69
    assert candidate.y == 0.63
    assert auto_play.is_watch_ad_button(candidate)


def test_tower_ad_revive_sets_guard_and_prefers_rest_room(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'abyss_retry'},
    )
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: climbing_map\nfloor: 11\n'
    )
    image = Image.new('RGB', (360, 800), color='black')

    auto_play.update_tower_run_state(
        'tower',
        image,
        [],
        clicked_label='复活（广告）',
        action_succeeded=True,
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=0.68,
            confidence=0.99,
            clickability=2.0,
            source=source,
        )
        for label, x, source in (
            ('Visible combat room icon', 0.28, 'vision'),
            ('Visible rest room icon', 0.72, 'vision'),
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert auto_play.load_tower_run_state('tower')['post_revive_route_guard']
    assert selection is not None
    assert selection[0].label == 'Visible rest room icon'


def test_tower_ad_revive_reenters_forced_current_combat_room(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'abyss_retry'},
    )
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: climbing_map\nfloor: 10\n'
        'post_revive_route_guard: true\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='当前所在层数',
            x=0.63,
            y=0.52,
            confidence=0.99,
            clickability=1.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='多目童子',
            x=0.27,
            y=0.69,
            confidence=0.95,
            clickability=1.8,
            source='ocr',
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == 'Visible current room icon'
    assert selection[0].source == 'vision'


def test_tower_ad_revive_uses_current_map_when_saved_phase_is_stale_combat(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'abyss_retry'},
    )
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: combat\nfloor: 11\n'
        'post_revive_route_guard: true\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='当前所在层数',
            x=0.63,
            y=0.52,
            confidence=0.99,
            clickability=1.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='恶龙',
            x=0.27,
            y=0.69,
            confidence=0.96,
            clickability=1.8,
            source='ocr',
        ),
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == 'Visible current room icon'
    assert selection[0].source == 'vision'


def test_tower_ad_revive_uses_room_vision_after_hud_labels_are_filtered(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'abyss_retry'},
    )
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: combat\nfloor: 11\n'
        'post_revive_route_guard: true\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='Visible combat room icon',
            x=0.26,
            y=0.67,
            confidence=0.98,
            clickability=7.0,
            source='vision',
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == 'Visible current room icon'
    assert selection[0].source == 'vision'


def test_tower_ad_revive_result_returns_to_inn_instead_of_clicking_cards(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'abyss_retry'},
    )
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: combat\nfloor: 10\n'
        'post_revive_route_guard: true\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='冒险结束',
            x=0.2,
            y=0.18,
            confidence=0.99,
            clickability=1.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='毒药攻击II',
            x=0.5,
            y=0.69,
            confidence=0.99,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='返回旅馆',
            x=0.5,
            y=0.95,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == '返回旅馆'


def test_tower_completed_revive_run_can_start_next_abyss(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'abyss_retry'},
    )
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: complete\nfloor: 10\n'
        'post_revive_route_guard: true\n'
    )
    adventure = auto_play.ButtonCandidate(
        label='冒险',
        x=0.52,
        y=0.96,
        confidence=0.95,
        clickability=1.5,
        source='template',
    )

    selection = auto_play.tower_daily_policy_candidates('tower', [adventure])

    assert selection is not None
    assert selection[0].label == '冒险'


def test_tower_ad_revive_allows_forced_prebattle_and_clears_guard(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'abyss_retry'},
    )
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: prebattle\nfloor: 10\n'
        'post_revive_route_guard: true\n'
    )
    battle = auto_play.ButtonCandidate(
        label='战斗',
        x=0.715,
        y=0.948,
        confidence=0.99,
        clickability=5.0,
        source='vision',
    )

    selection = auto_play.tower_daily_policy_candidates('tower', [battle])
    assert selection is not None
    assert selection[0].label == '战斗'

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        [battle],
        clicked_label='战斗',
        action_succeeded=True,
    )
    assert not auto_play.load_tower_run_state('tower').get('post_revive_route_guard')


def test_tower_successful_rest_room_clears_post_revive_guard(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: climbing_map\nfloor: 11\n'
        'post_revive_route_guard: true\n'
    )

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        [],
        clicked_label='Visible rest room icon',
        action_succeeded=True,
    )

    assert not auto_play.load_tower_run_state('tower')['post_revive_route_guard']


def test_tower_live_run_disables_automatic_ocr_tuning(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    game_root = tmp_path / 'games' / 'tower'
    game_root.mkdir(parents=True)
    (game_root / 'active_run.yaml').write_text(
        'stage: 深渊楼梯\nphase: combat\n'
    )
    args = SimpleNamespace(
        game='tower',
        loop=True,
        click_recommended=True,
        ocr_tune_every_turns=1,
        ocr_tune_iterations=10,
        ocr_tune_on_stuck_iterations=10,
    )

    assert not auto_play.should_run_periodic_ocr_tuning(args, 1)
    assert not auto_play.should_run_stuck_ocr_tuning(args)


def test_tower_route_confirmation_advances_floor():
    auto_play = load_auto_play_module()

    assert auto_play.tower_action_advances_floor('确定', 'route_choice')
    assert not auto_play.tower_action_advances_floor('确定', 'card_reward')
    assert auto_play.tower_action_advances_floor('进入下一层', 'climbing_map')


def test_tower_card_reward_abandon_requires_route_before_reentering_room(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'abyss_retry'},
    )
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: card_reward\nfloor: 1\n'
    )
    image = Image.new('RGB', (360, 800), color='black')

    auto_play.update_tower_run_state(
        'tower',
        image,
        [],
        clicked_label='放弃',
        action_succeeded=True,
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='职业牌包',
            x=0.73,
            y=0.66,
            confidence=0.99,
            clickability=8.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='右侧道路',
            x=0.92,
            y=0.74,
            confidence=0.96,
            clickability=1.8,
            source='template',
        ),
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert auto_play.load_tower_run_state('tower')[
        'awaiting_route_after_reward'
    ]
    assert selection is not None
    assert selection[0].label == '右侧道路'


def test_tower_reward_exit_guard_does_not_hide_current_card_reward(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'abyss_retry'},
    )
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: card_reward\n'
        'floor: 2\nawaiting_route_after_reward: true\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='放弃',
            x=0.29,
            y=0.70,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is None


def test_tower_reward_exit_guard_allows_next_prebattle(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'abyss_retry'},
    )
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: prebattle\n'
        'floor: 3\nawaiting_route_after_reward: true\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='战斗',
            x=0.715,
            y=0.948,
            confidence=0.99,
            clickability=5.0,
            source='vision',
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == '战斗'
    assert '战斗预览' in selection[0].reason


def test_tower_successful_route_clears_reward_exit_guard(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: climbing_map\n'
        'floor: 1\nawaiting_route_after_reward: true\n'
    )
    image = Image.new('RGB', (360, 800), color='black')

    auto_play.update_tower_run_state(
        'tower',
        image,
        [],
        clicked_label='右侧道路',
        action_succeeded=True,
    )

    assert not auto_play.load_tower_run_state('tower')[
        'awaiting_route_after_reward'
    ]


def test_tower_next_floor_clears_previous_room_position(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: climbing_map\n'
        'floor: 5\nlast_room_action: Visible next-floor stair room\n'
        'last_room_position: [0.256944, 0.665625]\n'
    )
    image = Image.new('RGB', (360, 800), color='black')

    auto_play.update_tower_run_state(
        'tower',
        image,
        [],
        clicked_label='进入下一层',
        action_succeeded=True,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['floor'] == 6
    assert 'last_room_action' not in state
    assert 'last_room_position' not in state


def test_tower_reward_exit_guard_uses_off_center_room_without_route(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'abyss_retry'},
    )
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: climbing_map\n'
        'floor: 3\nawaiting_route_after_reward: true\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='宝石牌包',
            x=0.49,
            y=0.77,
            confidence=0.99,
            clickability=8.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Visible room icon',
            x=0.49,
            y=0.75,
            confidence=0.98,
            clickability=3.2,
            source='vision',
        ),
        auto_play.ButtonCandidate(
            label='Visible room icon',
            x=0.74,
            y=0.67,
            confidence=0.98,
            clickability=3.2,
            source='vision',
        ),
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].x == 0.74
    assert '侧边的新房间' in selection[0].reason


def test_tower_reward_exit_guard_avoids_last_room_and_uses_center_room(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'abyss_retry'},
    )
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: climbing_map\n'
        'floor: 3\nawaiting_route_after_reward: true\n'
        'last_room_position: [0.27, 0.82]\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='Visible room icon',
            x=x,
            y=y,
            confidence=0.98,
            clickability=3.2,
            source='vision',
        )
        for x, y in ((0.27, 0.82), (0.49, 0.74))
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].x == 0.49
    assert selection[0].y == 0.74


def test_tower_successful_off_center_room_clears_reward_exit_guard(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: climbing_map\n'
        'floor: 3\nawaiting_route_after_reward: true\n'
    )
    image = Image.new('RGB', (360, 800), color='black')

    auto_play.update_tower_run_state(
        'tower',
        image,
        [],
        clicked_label='Visible room icon',
        action_succeeded=True,
    )

    assert not auto_play.load_tower_run_state('tower')[
        'awaiting_route_after_reward'
    ]


def test_tower_victory_confirmation_requires_leaving_completed_room(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: combat\nfloor: 4\n'
    )
    image = Image.new('RGB', (360, 800), color='black')
    buttons = [
        auto_play.ButtonCandidate(
            label='胜利',
            x=0.5,
            y=0.4,
            confidence=0.99,
            clickability=1.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='好的',
            x=0.5,
            y=0.68,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
    ]

    auto_play.update_tower_run_state(
        'tower',
        image,
        buttons,
        clicked_label='好的',
        action_succeeded=True,
    )

    assert auto_play.load_tower_run_state('tower')[
        'awaiting_route_after_reward'
    ]


def test_tower_reward_exit_guard_closes_level_up_before_stale_route(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'abyss_retry'},
    )
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: combat\nfloor: 4\n'
        'awaiting_route_after_reward: true\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='角色升级',
            x=0.5,
            y=0.37,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='好的',
            x=0.5,
            y=0.76,
            confidence=0.99,
            clickability=2.0,
            source='template',
        ),
        auto_play.ButtonCandidate(
            label='下方道路',
            x=0.42,
            y=0.91,
            confidence=0.98,
            clickability=0.3,
            source='template',
        ),
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == '好的'
    assert '升级弹窗' in selection[0].reason


def test_tower_new_abyss_run_clears_stale_daily_profession(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-14',
            'phase': 'abyss_retry',
            'abyss_profession': '法师',
        },
    )
    image = Image.new('RGB', (360, 800), color='black')

    auto_play.update_tower_run_state(
        'tower',
        image,
        [],
        clicked_label='进入冒险',
        action_succeeded=True,
    )

    assert 'abyss_profession' not in auto_play.load_tower_daily_state('tower')


def test_tower_stage_battle_button_starts_fresh_run(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: stale-run\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 1\n'
        'reroll_predecessor: true\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='深渊楼梯',
            x=0.84,
            y=0.25,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='战斗',
            x=0.72,
            y=0.95,
            confidence=0.99,
            clickability=5.0,
            source='vision',
        )
    ]

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        buttons,
        clicked_label='战斗',
        action_succeeded=True,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['run_id'] != 'stale-run'
    assert state['stage'] == '深渊楼梯'
    assert state['floor'] == 1
    assert not state.get('reroll_predecessor')


def test_tower_map_room_detector_skips_confirm_dialogs():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(28, 32, 34))
    draw = ImageDraw.Draw(image)
    draw.rectangle((55, 495, 132, 572), fill=(92, 178, 60))

    candidates = auto_play.tower_map_room_icon_candidates(
        image,
        config,
        [
            auto_play.ButtonCandidate(
                label='下方道路',
                x=0.49,
                y=0.92,
                confidence=0.97,
                clickability=1.22,
                source='template',
            ),
            auto_play.ButtonCandidate(
                label='确定',
                x=0.74,
                y=0.69,
                confidence=1.0,
                clickability=2.0,
                source='template',
            ),
        ],
    )

    assert candidates == []


def test_tower_map_room_detector_skips_loadout_cards():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(28, 32, 34))
    draw = ImageDraw.Draw(image)
    for left in (55, 125, 195, 265):
        draw.rectangle((left, 525, left + 50, 610), fill=(92, 178, 60))

    candidates = auto_play.tower_map_room_icon_candidates(
        image,
        config,
        [
            auto_play.ButtonCandidate(
                label='开始冒险',
                x=0.56,
                y=0.96,
                confidence=1.0,
                clickability=2.0,
                source='template',
            ),
            auto_play.ButtonCandidate(
                label='下方道路',
                x=0.17,
                y=0.49,
                confidence=0.85,
                clickability=0.64,
                source='template',
            ),
        ],
    )

    assert candidates == []


def test_tower_map_room_detector_skips_event_pickup_screen_with_ocr_arrow_noise():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(28, 32, 34))
    draw = ImageDraw.Draw(image)
    draw.rectangle((292, 530, 339, 588), fill=(80, 170, 210))
    buttons = [
        auto_play.ButtonCandidate(
            label='↑!',
            x=0.34,
            y=0.46,
            confidence=0.84,
            clickability=1.55,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='捡起木剑',
            x=0.50,
            y=0.57,
            confidence=1.0,
            clickability=1.01,
            source='template',
        ),
        auto_play.ButtonCandidate(
            label='下方道路',
            x=0.82,
            y=0.82,
            confidence=0.84,
            clickability=0.79,
            source='template',
        ),
    ]

    candidates = auto_play.tower_map_room_icon_candidates(
        image,
        config,
        buttons,
    )
    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': ['捡起木剑'], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert candidates == []
    assert scored[0].label == '捡起木剑'


def test_configured_tower_image_candidates_skip_unreliable_current_room_detector():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(28, 32, 34))
    draw = ImageDraw.Draw(image)
    draw.rectangle((146, 496, 214, 603), fill=(116, 76, 150))
    draw.rectangle((164, 485, 194, 510), fill=(210, 40, 45))
    draw.ellipse((158, 520, 202, 570), fill=(205, 178, 90))
    lower_route = auto_play.ButtonCandidate(
        label='下方道路',
        x=0.44,
        y=0.92,
        confidence=0.98,
        clickability=0.84,
        source='template',
    )

    candidates = auto_play.configured_image_candidates(
        config,
        image,
        [lower_route],
    )
    scored = auto_play.score_buttons(
        [lower_route, *candidates],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert candidates == []
    assert scored[0].label == '下方道路'


def test_tower_current_room_detector_skips_center_navigation_arrow():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(28, 32, 34))
    draw = ImageDraw.Draw(image)
    draw.rectangle((150, 485, 205, 540), fill=(120, 210, 210))
    up_route = auto_play.ButtonCandidate(
        label='上方道路',
        x=0.48,
        y=0.64,
        confidence=0.99,
        clickability=1.13,
        source='template',
    )
    down_route = auto_play.ButtonCandidate(
        label='下方道路',
        x=0.44,
        y=0.92,
        confidence=0.98,
        clickability=0.84,
        source='template',
    )

    candidates = auto_play.tower_current_room_icon_candidates(
        image,
        config,
        [up_route, down_route],
    )
    scored = auto_play.score_buttons(
        [up_route, down_route, *candidates],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert candidates == []
    assert scored[0].label == '上方道路'


def test_generic_tower_room_icon_loses_to_strong_route_arrow():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(28, 32, 34))
    draw = ImageDraw.Draw(image)
    draw.rectangle((50, 486, 136, 580), fill=(120, 82, 164))
    draw.rectangle((70, 505, 114, 554), fill=(150, 92, 170))
    left_route = auto_play.ButtonCandidate(
        label='左侧道路',
        x=0.10,
        y=0.75,
        confidence=1.0,
        clickability=1.13,
        source='template',
    )
    lower_route = auto_play.ButtonCandidate(
        label='下方道路',
        x=0.50,
        y=0.92,
        confidence=0.88,
        clickability=0.86,
        source='template',
    )

    room_candidates = auto_play.tower_map_room_icon_candidates(
        image,
        config,
        [left_route, lower_route],
    )
    scored = auto_play.score_buttons(
        [left_route, lower_route, *room_candidates],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )
    decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.5,
        ambiguity_margin=0.25,
        ask_on_ambiguous=False,
        automation_config=config,
    )

    assert [button.label for button in room_candidates] == ['Visible room icon']
    assert scored[0].label == '下方道路'
    assert decision.recommended.label == '下方道路'


def test_bottom_center_down_route_beats_edge_back_arrow():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    left_route = auto_play.ButtonCandidate(
        label='左侧道路',
        x=0.10,
        y=0.75,
        confidence=1.0,
        clickability=1.13,
        source='template',
    )
    down_route = auto_play.ButtonCandidate(
        label='下方道路',
        x=0.50,
        y=0.92,
        confidence=0.88,
        clickability=0.86,
        source='template',
    )

    scored = auto_play.score_buttons(
        [left_route, down_route],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )
    decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.5,
        ambiguity_margin=0.25,
        ask_on_ambiguous=False,
        automation_config=config,
    )

    assert scored[0].label == '下方道路'
    assert decision.recommended.label == '下方道路'


def test_bottom_center_down_route_beats_stale_combat_room_icon():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    stale_room = auto_play.ButtonCandidate(
        label='Visible combat room icon',
        x=0.68,
        y=0.67,
        confidence=0.98,
        clickability=7.0,
        source='vision',
    )
    down_route = auto_play.ButtonCandidate(
        label='下方道路',
        x=0.50,
        y=0.92,
        confidence=0.88,
        clickability=0.86,
        source='template',
    )
    edge_route = auto_play.ButtonCandidate(
        label='左侧道路',
        x=0.10,
        y=0.75,
        confidence=0.96,
        clickability=1.12,
        source='template',
    )

    scored = auto_play.score_buttons(
        [stale_room, down_route, edge_route],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )
    decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.5,
        ambiguity_margin=0.25,
        ask_on_ambiguous=False,
        automation_config=config,
    )

    assert scored[0].label == '下方道路'
    assert decision.recommended.label == '下方道路'


def test_tower_map_room_detector_prefers_rest_when_hp_is_critical():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(28, 32, 34))
    draw = ImageDraw.Draw(image)
    draw.rectangle((56, 354, 69, 366), fill=(210, 30, 40))
    draw.rectangle((55, 495, 132, 572), fill=(92, 178, 60))
    draw.rectangle((218, 492, 323, 584), fill=(80, 170, 210))

    room_candidates = auto_play.tower_map_room_icon_candidates(
        image,
        config,
        [
            auto_play.ButtonCandidate(
                label='上方道路',
                x=0.48,
                y=0.63,
                confidence=0.89,
                clickability=0.87,
                source='template',
            ),
            auto_play.ButtonCandidate(
                label='下方道路',
                x=0.23,
                y=0.63,
                confidence=0.85,
                clickability=0.82,
                source='template',
            ),
        ],
    )

    assert [button.label for button in room_candidates] == [
        'Visible rest room icon',
        'Visible combat room icon',
    ]


def test_tower_map_room_detector_does_not_treat_half_hp_as_critical():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(28, 32, 34))
    draw = ImageDraw.Draw(image)
    draw.rectangle((56, 354, 101, 366), fill=(210, 30, 40))
    draw.rectangle((55, 495, 132, 572), fill=(92, 178, 60))
    draw.rectangle((218, 492, 323, 584), fill=(80, 170, 210))

    room_candidates = auto_play.tower_map_room_icon_candidates(
        image,
        config,
        [
            auto_play.ButtonCandidate(
                label='上方道路',
                x=0.48,
                y=0.63,
                confidence=0.89,
                clickability=0.87,
                source='template',
            ),
            auto_play.ButtonCandidate(
                label='下方道路',
                x=0.23,
                y=0.63,
                confidence=0.85,
                clickability=0.82,
                source='template',
            ),
        ],
    )

    assert auto_play.tower_hp_looks_critical(image) is False
    assert [button.label for button in room_candidates] == [
        'Visible combat room icon',
        'Visible room icon',
    ]


def test_escape_menu_probe_beats_navigation_when_top_paths_are_exhausted():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    minimap_arrow = auto_play.ButtonCandidate(
        label='左侧道路',
        x=0.10,
        y=0.75,
        confidence=0.95,
        clickability=1.1,
        source='template',
    )
    top_probe = auto_play.ButtonCandidate(
        label='Top path left',
        x=0.08,
        y=0.30,
        confidence=1.0,
        clickability=2.0,
        source='vision',
    )
    escape_probe = auto_play.escape_menu_probe_candidates()[0]

    scored = auto_play.score_buttons(
        [minimap_arrow, top_probe, escape_probe],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )
    decision = auto_play.decide_unblock_move(
        scored,
        {'左侧道路', 'top path left'},
    )

    assert decision.recommended.label == 'Open settings'


def test_survivor_claimed_page_creates_back_reset_candidate(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    config = isolated_automation_config(auto_play, 'survivor', tmp_path, monkeypatch)

    claimed = auto_play.ButtonCandidate(
        label='Claimed',
        x=0.5,
        y=0.45,
        confidence=0.95,
        clickability=0.7,
        source='ocr',
    )

    extras = auto_play.configured_extra_candidates(config, [claimed])

    assert len(extras) == 1
    assert extras[0].label == 'Back from main challenge'
    assert extras[0].source == 'vision'
    assert extras[0].x == 0.08
    assert extras[0].y == 0.965


def test_non_survivor_claimed_page_does_not_create_swipe_candidate():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    extras = auto_play.configured_extra_candidates(
        config,
        [
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.5,
                y=0.45,
                confidence=0.95,
                clickability=0.7,
                source='ocr',
            )
        ],
    )

    assert extras == []


def test_tower_loadout_adds_adventurer_selection_fallback():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    start = auto_play.ButtonCandidate(
        label='开始冒险',
        x=0.56,
        y=0.96,
        confidence=1.0,
        clickability=2.0,
        source='template',
    )

    extras = auto_play.configured_extra_candidates(config, [start])
    scored = auto_play.score_buttons(
        [start, *extras],
        memory={
            'preferred': ['开始冒险'],
            'avoid': [],
            'ineffective': [],
        },
        automation_config=config,
    )
    normal_decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.65,
        ambiguity_margin=0.2,
        ask_on_ambiguous=False,
        fallback_labels=set(),
        automation_config=config,
    )
    unblock_decision = auto_play.decide_unblock_move(
        scored,
        {'开始冒险'},
    )

    assert [button.label for button in extras] == ['选择冒险者']
    assert normal_decision.recommended.label == '开始冒险'
    assert unblock_decision.recommended.label == '选择冒险者'


def test_item_inspection_skips_hard_avoid_navigation_and_noise():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    for label in ['Abandon', '↑!', '••']:
        candidate = auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=0.6,
            confidence=1.0,
            clickability=1.0,
            source='ocr',
        )

        assert not auto_play.is_inspectable_item_candidate(
            candidate,
            fallback_labels=set(),
            avoid_labels=set(),
            ineffective_labels=set(),
            automation_config=config,
        )


def test_unblock_prefers_repeated_route_over_menu_probe():
    auto_play = load_auto_play_module()

    route = auto_play.ButtonCandidate(
        label='下方道路',
        x=0.5,
        y=0.93,
        confidence=0.76,
        clickability=0.81,
        source='template',
        score=2.05,
    )
    settings = auto_play.ButtonCandidate(
        label='Open settings',
        x=0.94,
        y=0.46,
        confidence=1.0,
        clickability=3.2,
        source='vision',
        score=1.03,
    )

    decision = auto_play.decide_unblock_move(
        [route, settings],
        {'下方道路'},
    )

    assert decision.recommended.label == '下方道路'


def test_unblock_prefers_viable_repeated_route_over_menu_probe_loophole():
    auto_play = load_auto_play_module()

    route = auto_play.ButtonCandidate(
        label='右侧道路',
        x=0.78,
        y=0.75,
        confidence=0.89,
        clickability=1.49,
        source='template',
        score=3.28,
    )
    settings = auto_play.ButtonCandidate(
        label='Open settings',
        x=0.94,
        y=0.46,
        confidence=1.0,
        clickability=3.2,
        source='vision',
        score=1.03,
    )
    stale_card = auto_play.ButtonCandidate(
        label='弱点打击',
        x=0.77,
        y=0.75,
        confidence=0.91,
        clickability=0.86,
        source='template',
        score=0.30,
    )

    decision = auto_play.decide_unblock_move(
        [route, settings, stale_card],
        {'右侧道路'},
    )

    assert decision.recommended.label == '右侧道路'


def test_survivor_level_grid_creates_last_challenge_icon_candidate(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    config = isolated_automation_config(auto_play, 'survivor', tmp_path, monkeypatch)

    extras = auto_play.configured_extra_candidates(
        config,
        [
            auto_play.ButtonCandidate(
                label='261.Autonomous',
                x=0.5,
                y=0.72,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            )
        ],
    )

    assert len(extras) == 1
    assert extras[0].label == 'Third column unclaimed row'
    assert extras[0].x == 0.83
    assert extras[0].y == 0.61


def test_survivor_unclaimed_row_candidate_is_not_claimed(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    config = isolated_automation_config(auto_play, 'survivor', tmp_path, monkeypatch)
    auto_play.write_main_challenge_progress(
        'survivor',
        {
            'target_level': 330,
            'next_level': 330,
            'cleared_levels': [329],
            'complete': False,
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='Third column unclaimed row',
            x=0.83,
            y=0.90,
            confidence=1.0,
            clickability=3.0,
            source='vision',
        ),
        auto_play.ButtonCandidate(
            label='330.Mysterious Star',
            x=0.5,
            y=0.91,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Back to top',
            x=0.83,
            y=0.96,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
    ]

    assert not auto_play.configured_claimed_visible(config, buttons)
    assert auto_play.configured_claimed_buttons(config, buttons) == []
    assert auto_play.configured_level_grid_complete_reason(config, buttons) is None


def test_survivor_claimed_page_after_main_challenge_clicks_unclaimed_third_column(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    config = isolated_automation_config(auto_play, 'survivor', tmp_path, monkeypatch)

    extras = auto_play.configured_extra_candidates(
        config,
        [
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.5,
                y=0.18,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='260.Recycling Center',
                x=0.5,
                y=0.51,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='261.Autonomous',
                x=0.5,
                y=0.72,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
        ],
        recent_actions=['Back from main challenge', 'Main Challenge'],
    )

    assert [button.label for button in extras] == ['Third column unclaimed row']
    assert extras[0].x == 0.83
    assert extras[0].y == 0.4


def test_survivor_main_challenge_claimed_labels_belong_to_row_below_label(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    config = isolated_automation_config(auto_play, 'survivor', tmp_path, monkeypatch)

    extras = auto_play.configured_extra_candidates(
        config,
        [
            auto_play.ButtonCandidate(
                label='258.Ordinary Breeding Room',
                x=0.5,
                y=0.1625,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.83,
                y=0.12,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='259.Combat Lab',
                x=0.5,
                y=0.3862,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.83,
                y=0.2762,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='260.Recycling Center',
                x=0.5,
                y=0.6019,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.83,
                y=0.4919,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='261.Autonomous Mech Base',
                x=0.5,
                y=0.8131,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
        ],
        recent_actions=['Back from main challenge', 'Main Challenge'],
    )

    assert [button.label for button in extras] == ['Third column unclaimed row']
    assert extras[0].source == 'vision'
    assert round(extras[0].y, 4) == 0.7031


def test_survivor_main_challenge_reenters_past_older_unclaimed_rewards(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    config = isolated_automation_config(auto_play, 'survivor', tmp_path, monkeypatch)

    extras = auto_play.configured_extra_candidates(
        config,
        [
            auto_play.ButtonCandidate(
                label='282.Wall of Entry',
                x=0.5,
                y=0.2838,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='283.Skirmish Within',
                x=0.5,
                y=0.4956,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='284.Maze Entrance',
                x=0.5,
                y=0.7181,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.83,
                y=0.8163,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
        ],
        recent_actions=['Back from main challenge', 'Main Challenge'],
    )

    assert [button.label for button in extras] == ['Back from main challenge']
    assert extras[0].source == 'vision'


def test_survivor_main_challenge_uses_rightmost_unclaimed_visible_cell(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    config = isolated_automation_config(auto_play, 'survivor', tmp_path, monkeypatch)

    extras = auto_play.configured_extra_candidates(
        config,
        [
            auto_play.ButtonCandidate(
                label='260.Recycling Center',
                x=0.5,
                y=0.8194,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.8236,
                y=0.9175,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
        ],
        recent_actions=['Back from main challenge', 'Main Challenge'],
    )

    assert [button.label for button in extras] == ['Back from main challenge']
    assert extras[0].source == 'vision'


def test_survivor_main_challenge_uses_centered_title_when_level_number_is_missing(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    config = isolated_automation_config(auto_play, 'survivor', tmp_path, monkeypatch)

    extras = auto_play.configured_extra_candidates(
        config,
        [
            auto_play.ButtonCandidate(
                label='297.Quantum Tunnel',
                x=0.5,
                y=0.1694,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='298.Tunnel Tempest',
                x=0.5,
                y=0.3862,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.8222,
                y=0.4844,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Anchor',
                x=0.4972,
                y=0.6100,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='300.Mirror Matrix',
                x=0.5,
                y=0.8187,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Back to top',
                x=0.8326,
                y=0.9625,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
        ],
        recent_actions=['Back from main challenge', 'Main Challenge'],
    )

    assert [button.label for button in extras] == ['Third column unclaimed row']
    assert extras[0].x == 0.83
    assert round(extras[0].y, 4) == 0.7087


def test_survivor_main_challenge_infers_missing_tracked_row_between_numbers(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    write_game_strategy(tmp_path, 'survivor')
    progress_path = tmp_path / 'games' / 'survivor' / 'main_challenge_progress.yaml'
    progress_path.write_text(
        """
target_level: 330
next_level: 324
cleared_levels:
  - 314
  - 315
  - 316
  - 317
  - 318
  - 319
  - 320
  - 321
  - 322
  - 323
complete: false
"""
    )
    config = automation_config(auto_play, 'survivor')

    extras = auto_play.configured_extra_candidates(
        config,
        [
            auto_play.ButtonCandidate(
                label='323.Starlit Knight',
                x=0.5,
                y=0.2781,
                confidence=0.996,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Array',
                x=0.4972,
                y=0.2919,
                confidence=0.998,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Barragi',
                x=0.4944,
                y=0.5106,
                confidence=0.949,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='325.Starglyph Plaza',
                x=0.4986,
                y=0.7212,
                confidence=0.999,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Back to top',
                x=0.8326,
                y=0.9631,
                confidence=0.991,
                clickability=2.0,
                source='ocr',
            ),
        ],
    )

    assert [button.label for button in extras] == ['Third column unclaimed row']
    assert auto_play.candidate_level_number(extras[0]) == 324
    assert extras[0].x == 0.83
    assert round(extras[0].y, 4) == 0.3896


def test_survivor_main_challenge_clicks_low_visible_row_after_reentry_loop(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    config = isolated_automation_config(auto_play, 'survivor', tmp_path, monkeypatch)

    extras = auto_play.configured_extra_candidates(
        config,
        [
            auto_play.ButtonCandidate(
                label='297.Quantum Tunnel',
                x=0.4986,
                y=0.1694,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='298.Tunnel Tempest',
                x=0.4972,
                y=0.3862,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.8222,
                y=0.4844,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Anchor',
                x=0.4972,
                y=0.6106,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.8250,
                y=0.5006,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='300.Mirror Matrix',
                x=0.4986,
                y=0.8194,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Back to top',
                x=0.8340,
                y=0.9625,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
        ],
        recent_actions=[
            'Back from main challenge',
            'Main Challenge',
            'Back from main challenge',
            'Main Challenge',
        ],
    )

    assert [button.label for button in extras] == ['Third column unclaimed row']
    assert extras[0].x == 0.83
    assert round(extras[0].y, 4) == 0.7094


def test_survivor_main_challenge_keeps_scrolling_when_bottom_row_below_target(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    config = isolated_automation_config(auto_play, 'survivor', tmp_path, monkeypatch)

    reason = auto_play.configured_level_grid_complete_reason(
        config,
        [
            auto_play.ButtonCandidate(
                label='297.Quantum Tunnel',
                x=0.4986,
                y=0.1694,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='298.Tunnel Tempest',
                x=0.4972,
                y=0.3862,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.8222,
                y=0.4844,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Anchor',
                x=0.4972,
                y=0.6106,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.8250,
                y=0.7013,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='300.Mirror Matrix',
                x=0.5,
                y=0.8194,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.8250,
                y=0.9175,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Back to top',
                x=0.8340,
                y=0.9631,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
        ],
        recent_actions=['Tap to Close', 'Back from main challenge', 'Main Challenge'],
    )

    assert reason is None

    extras = auto_play.configured_extra_candidates(
        config,
        [
            auto_play.ButtonCandidate(
                label='297.Quantum Tunnel',
                x=0.4986,
                y=0.1694,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='298.Tunnel Tempest',
                x=0.4972,
                y=0.3862,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.8222,
                y=0.4844,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Anchor',
                x=0.4972,
                y=0.6106,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.8250,
                y=0.7013,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='300.Mirror Matrix',
                x=0.5,
                y=0.8194,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.8250,
                y=0.9175,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Back to top',
                x=0.8340,
                y=0.9631,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
        ],
        recent_actions=['Tap to Close', 'Back from main challenge', 'Main Challenge'],
    )

    assert [button.label for button in extras] == [
        'Scroll to higher challenge levels',
    ]
    assert extras[0].source == 'swipe'


def test_survivor_main_challenge_detects_complete_at_target_level(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    config = isolated_automation_config(auto_play, 'survivor', tmp_path, monkeypatch)

    reason = auto_play.configured_level_grid_complete_reason(
        config,
        [
            auto_play.ButtonCandidate(
                label='327.End Times',
                x=0.4986,
                y=0.1694,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='328.Final Rampart',
                x=0.4972,
                y=0.3862,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.8222,
                y=0.4844,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='329.Last Defense',
                x=0.4972,
                y=0.6106,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.8250,
                y=0.7013,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='330.Zero Hour',
                x=0.5,
                y=0.8194,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.8250,
                y=0.9175,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Back to top',
                x=0.8340,
                y=0.9631,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
        ],
        recent_actions=['Tap to Close', 'Back from main challenge', 'Main Challenge'],
    )

    assert reason is not None
    assert 'Main Challenge appears complete' in reason


def test_survivor_reward_overlay_closes_before_grid_candidates():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    extras = auto_play.configured_extra_candidates(
        config,
        [
            auto_play.ButtonCandidate(
                label='Rewards',
                x=0.5,
                y=0.43,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Tap to Close',
                x=0.5,
                y=0.77,
                confidence=0.99,
                clickability=1.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='260.Recycling Center',
                x=0.5,
                y=0.8194,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
        ],
        recent_actions=['Back from main challenge', 'Main Challenge'],
    )

    assert extras == []


def test_survivor_reward_skip_beats_active_skill_template():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    scored = auto_play.score_buttons(
        [
            auto_play.ButtonCandidate(
                label='where to skip',
                x=0.58,
                y=0.74,
                confidence=0.988,
                clickability=1.625,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Lucky Train',
                x=0.50,
                y=0.27,
                confidence=0.985,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='battle active skill',
                x=0.87,
                y=0.79,
                confidence=0.401,
                clickability=1.015,
                source='template',
            ),
        ],
        memory={
            'preferred': ['Battle active skill'],
            'avoid': [],
            'ineffective': [],
        },
        automation_config=config,
    )

    assert scored[0].label == 'where to skip'
    assert scored[-1].label == 'battle active skill'


def test_survivor_main_challenge_scrolls_when_visible_cells_are_claimed_below_target(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    config = isolated_automation_config(auto_play, 'survivor', tmp_path, monkeypatch)

    extras = auto_play.configured_extra_candidates(
        config,
        [
            auto_play.ButtonCandidate(
                label='260.Recycling Center',
                x=0.5,
                y=0.8194,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.17,
                y=0.9175,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.50,
                y=0.9175,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Claimed',
                x=0.83,
                y=0.9175,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Back to top',
                x=0.8340,
                y=0.9631,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
        ],
        recent_actions=['Back from main challenge', 'Main Challenge'],
    )

    assert [button.label for button in extras] == ['Scroll to higher challenge levels']
    assert extras[0].source == 'swipe'


def test_survivor_main_challenge_beats_showdown_after_back_trick():
    auto_play = load_auto_play_module()

    buttons = [
        auto_play.ButtonCandidate(
            label='Showdown',
            x=0.15,
            y=0.72,
            confidence=0.999,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Main Challenge',
            x=0.21,
            y=0.38,
            confidence=0.992,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Mega Challenge',
            x=0.70,
            y=0.38,
            confidence=0.999,
            clickability=2.0,
            source='ocr',
        ),
    ]
    scored = auto_play.score_buttons(
        buttons,
        memory={
            'preferred': ['Main Challenge'],
            'avoid': [],
            'ineffective': [],
        },
    )

    decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.65,
        ambiguity_margin=0.2,
        ask_on_ambiguous=False,
        fallback_labels={auto_play.normalize_label('Back')},
    )

    assert decision.status == 'ready'
    assert decision.recommended.label == 'Main Challenge'


def test_survivor_waiting_showdown_creates_back_candidate():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    buttons = [
        auto_play.ButtonCandidate(
            label='Survivor Showdown',
            x=0.5,
            y=0.13,
            confidence=0.999,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Matching starts',
            x=0.5,
            y=0.96,
            confidence=0.999,
            clickability=1.9,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Start',
            x=0.5,
            y=0.86,
            confidence=0.999,
            clickability=2.0,
            source='ocr',
        ),
    ]

    extras = auto_play.configured_extra_candidates(config, buttons)
    scored = auto_play.score_buttons(
        [*buttons, *extras],
        memory={
            'preferred': ['Start', 'Back from unavailable showdown'],
            'avoid': [],
            'ineffective': [],
        },
        automation_config=config,
    )
    decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.65,
        ambiguity_margin=0.2,
        ask_on_ambiguous=False,
        fallback_labels=set(),
    )

    assert [button.label for button in extras] == ['Back from unavailable showdown']
    assert decision.status == 'ready'
    assert decision.recommended.label == 'Back from unavailable showdown'


def test_survivor_no_text_actual_battle_creates_active_skill_candidate():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    extras = auto_play.configured_extra_candidates(config, [])

    assert len(extras) == 1
    assert extras[0].label == 'Battle active skill'
    assert extras[0].x == 0.86
    assert extras[0].y == 0.79


def test_tower_magic_shop_empty_ocr_uses_colored_back_button(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(20, 20, 20))
    pixels = np.asarray(image).copy()
    pixels[672:740, 14:162] = (20, 170, 205)
    pixels[672:740, 198:346] = (230, 170, 20)
    image = Image.fromarray(pixels)
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'last_room_action': '魔术商店',
            'last_action': '点击空白处关闭',
        },
    )

    extras = auto_play.configured_extra_candidates(
        config,
        [],
        recent_actions=['变化', '点击空白处关闭'],
        image=image,
    )

    assert [button.label for button in extras] == ['返回']
    assert extras[0].source == 'vision'
    assert extras[0].x == 0.27
    assert extras[0].y == 0.883


def test_tower_gold_shop_empty_ocr_uses_colored_back_button(monkeypatch):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    image = Image.new('RGB', (360, 800), color=(20, 20, 20))
    pixels = np.asarray(image).copy()
    pixels[672:740, 14:162] = (20, 170, 205)
    pixels[672:740, 198:346] = (230, 170, 20)
    image = Image.fromarray(pixels)
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'last_room_action': '金币商店',
            'last_action': '点击空白处关闭',
        },
    )

    false_route_template = auto_play.ButtonCandidate(
        label='下方道路',
        x=0.33,
        y=0.74,
        confidence=0.75,
        clickability=0.5,
        source='template',
    )
    extras = auto_play.configured_extra_candidates(
        config,
        [false_route_template],
        recent_actions=['融合', '点击空白处关闭'],
        image=image,
    )

    assert [button.label for button in extras] == ['刷新商店']


def test_tower_magic_shop_empty_ocr_does_not_click_loading_screen(monkeypatch):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'last_room_action': '魔术商店',
            'last_action': '点击空白处关闭',
        },
    )

    extras = auto_play.configured_extra_candidates(
        config,
        [],
        recent_actions=['点击空白处关闭'],
        image=Image.new('RGB', (360, 800), color=(0, 0, 0)),
    )

    assert extras == []


def test_tower_daily_policy_preserves_magic_shop_vision_exit(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {'phase': 'abyss_retry'},
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'awaiting_route_after_reward': True},
    )
    exit_button = auto_play.ButtonCandidate(
        label='返回',
        x=0.27,
        y=0.883,
        confidence=0.99,
        clickability=5.0,
        source='vision',
        reason='Tower shop footer detected by paired cyan/yellow controls.',
    )

    selected = auto_play.tower_daily_policy_candidates('tower', [exit_button])

    assert selected is not None
    assert [button.label for button in selected] == ['返回']
    assert selected[0].clickability == 20.0


def test_tower_daily_policy_allows_magic_shop_card_change(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {'phase': 'abyss_retry'},
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'awaiting_route_after_reward': True,
            'last_room_action': '魔术商店',
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=0.5,
            confidence=0.99,
            clickability=2.0,
        )
        for label, x in (
            ('魔术商店', 0.5),
            ('变化法阵', 0.2),
            ('返回', 0.27),
        )
    ]

    selected = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selected is None

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=automation_config(auto_play, 'tower'),
    )

    assert scored[0].label == '变化法阵'


def test_tower_daily_exits_magic_shop_after_one_card_change(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {'phase': 'abyss_retry'},
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'last_room_action': '魔术商店',
            'magic_shop_change_complete': True,
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=0.5,
            confidence=0.99,
            clickability=2.0,
        )
        for label, x in (
            ('魔术商店', 0.5),
            ('变化法阵', 0.2),
            ('返回', 0.27),
            ('确定', 0.72),
        )
    ]

    selected = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selected is not None
    assert selected[0].label == '返回'


def test_tower_daily_cancels_second_magic_shop_card_change(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {'phase': 'abyss_retry'},
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'last_room_action': '魔术商店',
            'magic_shop_change_complete': True,
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=2.0,
        )
        for label, x, y in (
            ('卡牌变化', 0.5, 0.12),
            ('能量飞弹', 0.2, 0.4),
            ('放弃', 0.5, 0.92),
        )
    ]

    selected = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selected is not None
    assert selected[0].label == '放弃'


def test_tower_daily_policy_exits_ocr_visible_gold_shop(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {'phase': 'abyss_retry'},
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'awaiting_route_after_reward': True,
            'last_room_action': '金币商店',
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=0.5,
            confidence=0.99,
            clickability=2.0,
        )
        for label, x in (
            ('金币商店', 0.5),
            ('返回', 0.27),
        )
    ]

    selected = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selected is not None
    assert [button.label for button in selected] == ['返回']


def test_tower_daily_policy_finishes_card_fusion_before_route(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {'phase': 'abyss_retry'},
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'awaiting_route_after_reward': True},
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='融合',
            x=0.72,
            y=0.84,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='消耗2张相同的牌进行融合，并且获得水晶',
            x=0.5,
            y=0.77,
            confidence=0.96,
            clickability=0.2,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='下方道路',
            x=0.33,
            y=0.74,
            confidence=0.75,
            clickability=0.5,
            source='template',
        ),
    ]

    selected = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selected is not None
    assert [button.label for button in selected] == ['融合']
    assert selected[0].clickability == 24.0


def test_tower_daily_policy_opens_settings_immediately_after_bad_predecessor(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {'phase': 'abyss_retry'},
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'phase': 'climbing_map',
            'awaiting_route_after_reward': True,
            'reroll_predecessor': True,
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='设置',
            x=0.94,
            y=0.48,
            confidence=0.99,
            clickability=1.0,
        ),
        auto_play.ButtonCandidate(
            label='左侧道路',
            x=0.1,
            y=0.75,
            confidence=0.99,
            clickability=1.0,
        ),
    ]

    selected = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selected is not None
    assert [button.label for button in selected] == ['设置']


def test_tower_daily_policy_leaves_settings_after_bad_predecessor(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {'phase': 'abyss_retry'},
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'phase': 'defeated',
            'awaiting_route_after_reward': True,
            'reroll_predecessor': True,
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=1.0,
            source=source,
        )
        for label, x, y, source in (
            ('返回旅馆', 0.5, 0.59, 'ocr'),
            ('继续冒险', 0.5, 0.65, 'ocr'),
            ('下方道路', 0.42, 0.91, 'template'),
        )
    ]

    selected = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selected is not None
    assert [button.label for button in selected] == ['返回旅馆']


def test_tower_daily_policy_reenters_adventure_while_rerolling(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {'phase': 'abyss_retry'},
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'phase': 'complete',
            'awaiting_route_after_reward': True,
            'reroll_predecessor': True,
        },
    )
    adventure = auto_play.ButtonCandidate(
        label='冒险',
        x=0.5,
        y=0.985,
        confidence=0.99,
        clickability=2.0,
    )

    selected = auto_play.tower_daily_policy_candidates('tower', [adventure])

    assert selected is not None
    assert [button.label for button in selected] == ['冒险']


def test_survivor_strategy_configures_repeated_active_skill_swipe():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    spec = config.repeated_action_swipe_candidate

    assert spec is not None
    assert spec.trigger_label == 'battle active skill'
    assert spec.min_count == 6
    assert spec.label == 'Battle move toward boss'
    assert spec.to_button().source == 'swipe'
    assert spec.to_button().bbox == (0.22, 0.78, 0.22, 0.48)


def test_survivor_repeated_active_skill_adds_movement_swipe():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    extras = auto_play.configured_extra_candidates(
        config,
        [],
        recent_actions=['Battle active skill'] * 6,
    )

    assert [button.label for button in extras] == [
        'Battle move toward boss',
        'Battle active skill',
    ]
    assert extras[0].source == 'swipe'
    assert extras[0].bbox == (0.22, 0.78, 0.22, 0.48)


def test_survivor_repeated_active_skill_swipe_does_not_interrupt_skill_choice():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    extras = auto_play.configured_extra_candidates(
        config,
        [
            auto_play.ButtonCandidate(
                label='Skill Choice',
                x=0.5,
                y=0.23,
                confidence=0.95,
                clickability=0.2,
            ),
            auto_play.ButtonCandidate(
                label='Select a skill to learn',
                x=0.5,
                y=0.72,
                confidence=0.95,
                clickability=0.2,
            ),
        ],
        recent_actions=['Battle active skill'] * 6,
    )

    assert extras == []


def test_survivor_repeated_active_skill_swipe_ignores_popup_with_stale_template():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    extras = auto_play.configured_extra_candidates(
        config,
        [
            auto_play.ButtonCandidate(
                label='battle active skill',
                x=0.86,
                y=0.79,
                confidence=0.45,
                clickability=1.0,
                source='template',
            ),
            auto_play.ButtonCandidate(
                label='OK',
                x=0.5,
                y=0.59,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
            auto_play.ButtonCandidate(
                label='Revival',
                x=0.5,
                y=0.38,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            ),
        ],
        recent_actions=['Battle active skill'] * 6,
    )

    assert extras == []


def test_survivor_safe_revival_popup_prefers_ok_over_stale_template():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')
    buttons = [
        auto_play.ButtonCandidate(
            label='battle active skill',
            x=0.86,
            y=0.79,
            confidence=0.66,
            clickability=0.38,
            source='template',
        ),
        auto_play.ButtonCandidate(
            label='OK',
            x=0.5,
            y=0.59,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Revival',
            x=0.5,
            y=0.38,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label="Oops, you're nearly there!",
            x=0.5,
            y=0.55,
            confidence=0.97,
            clickability=1.7,
            source='ocr',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={
            'preferred': ['Battle active skill'],
            'avoid': [],
            'ineffective': [],
        },
        automation_config=config,
    )
    decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.95,
        ambiguity_margin=0.2,
        ask_on_ambiguous=False,
        automation_config=config,
    )

    assert scored[0].label == 'OK'
    assert decision.recommended.label == 'OK'


def test_survivor_safe_revival_confirm_does_not_fire_for_ad_prompt():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')
    buttons = [
        auto_play.ButtonCandidate(
            label='OK',
            x=0.5,
            y=0.59,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Revival',
            x=0.5,
            y=0.38,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Watch Ad',
            x=0.5,
            y=0.66,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
    ]

    assert not auto_play.configured_safe_confirm_visible(config, buttons)


def test_survivor_generic_item_inspection_skips_non_skill_choice_popup(tmp_path):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')
    buttons = [
        auto_play.ButtonCandidate(
            label='OK',
            x=0.5,
            y=0.59,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Revival',
            x=0.5,
            y=0.38,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='battle active skill',
            x=0.86,
            y=0.79,
            confidence=0.45,
            clickability=1.0,
            source='template',
        ),
    ]

    inspections, decision = auto_play.inspect_item_choices(
        SimpleNamespace(game='survivor', image=None, click_recommended=True),
        buttons=buttons,
        memory={'fallback': [], 'avoid': [], 'ineffective': []},
        artifact_paths={
            'item_inspections': tmp_path / 'item_inspections.yaml',
            'item_inspection_dir': tmp_path / 'item_inspections',
        },
        automation_config=config,
    )

    assert inspections == []
    assert decision is None


def test_survivor_game_info_filters_non_action_battle_labels():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')
    entries = [
        auto_play.GameInfoEntry(
            label='battle active skill',
            kind='skill',
            description='Shuttle',
            score=0.0,
            reasons=['observed detail'],
            sources=['item inspection'],
            seen_count=1,
            first_seen='turn-001',
            last_seen='turn-001',
            last_screenshot='screenshot.png',
        ),
        auto_play.GameInfoEntry(
            label='Oil Bond',
            kind='skill',
            description='Gold gain +40%',
            score=7.0,
            reasons=['coin gain'],
            sources=['item inspection'],
            seen_count=1,
            first_seen='turn-001',
            last_seen='turn-001',
            last_screenshot='screenshot.png',
        ),
    ]

    filtered = auto_play.filter_game_info_entries_for_config(entries, config)

    assert [entry.label for entry in filtered] == ['Oil Bond']


def test_survivor_gray_disabled_button_is_filtered_without_active_skill_fallback():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    image = Image.new('RGB', (360, 800), color='black')
    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 560, 260, 610), fill=(112, 112, 112))
    disabled = auto_play.ButtonCandidate(
        label='Start',
        x=0.5,
        y=0.731,
        confidence=0.99,
        clickability=2.0,
        source='ocr',
        bbox=(0.43, 0.704, 0.57, 0.743),
    )

    extras = auto_play.configured_extra_candidates(config, [disabled])
    filtered = auto_play.filter_configured_disabled_gray_buttons(
        config,
        image,
        [disabled, *extras],
    )

    assert auto_play.is_configured_disabled_gray_button(config, image, disabled)
    assert extras == []
    assert filtered == []


def test_survivor_enabled_colored_buttons_are_not_gray_filtered():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    image = Image.new('RGB', (360, 800), color='black')
    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 560, 260, 610), fill=(235, 124, 35))
    draw.rectangle((10, 295, 112, 330), fill=(238, 201, 35))
    start = auto_play.ButtonCandidate(
        label='Start',
        x=0.5,
        y=0.731,
        confidence=0.99,
        clickability=2.0,
        source='ocr',
        bbox=(0.43, 0.704, 0.57, 0.743),
    )
    skill_card = auto_play.ButtonCandidate(
        label='Boomerang',
        x=0.17,
        y=0.397,
        confidence=0.99,
        clickability=2.0,
        source='ocr',
        bbox=(0.08, 0.382, 0.25, 0.412),
    )

    filtered = auto_play.filter_configured_disabled_gray_buttons(
        config,
        image,
        [start, skill_card],
    )

    assert not auto_play.is_configured_disabled_gray_button(config, image, start)
    assert not auto_play.is_configured_disabled_gray_button(config, image, skill_card)
    assert filtered == [start, skill_card]


def test_survivor_next_screen_does_not_add_main_challenge_candidate():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    buttons = [
        auto_play.ButtonCandidate(
            label='Next',
            x=0.5014,
            y=0.7344,
            confidence=1.0,
            clickability=2.0,
        ),
        auto_play.ButtonCandidate(
            label='Lucky Train',
            x=0.4986,
            y=0.2750,
            confidence=0.97,
            clickability=2.0,
        ),
        auto_play.ButtonCandidate(
            label='28.9M3.9M',
            x=0.6521,
            y=0.6863,
            confidence=0.92,
            clickability=1.35,
        ),
    ]

    assert auto_play.configured_level_rows(config, buttons) == []
    assert auto_play.configured_extra_candidates(config, buttons) == []

    stage_row = auto_play.ButtonCandidate(
        label='262.Energy Research',
        x=0.5,
        y=0.8137,
        confidence=0.99,
        clickability=2.0,
    )
    assert auto_play.configured_level_rows(config, [stage_row]) == [stage_row]


def test_survivor_passive_battle_labels_fall_back_to_active_skill():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    buttons = [
        auto_play.ButtonCandidate(
            label='Shuttler',
            x=0.21,
            y=0.31,
            confidence=0.9,
            clickability=1.0,
        ),
        auto_play.ButtonCandidate(
            label='Dawnguard',
            x=0.19,
            y=0.38,
            confidence=0.9,
            clickability=1.0,
        ),
    ]

    filtered = auto_play.filter_configured_non_action_buttons(config, buttons)
    extras = auto_play.configured_extra_candidates(config, filtered)

    assert filtered == []
    assert [button.label for button in extras] == ['Battle active skill']


def test_survivor_top_right_counter_noise_falls_back_to_active_skill():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    assert auto_play.looks_like_noise_label('671N335M7', config)
    assert auto_play.looks_like_noise_label('203M7 203N7 203M7', config)
    assert auto_play.looks_like_noise_label('223 223N', config)
    assert auto_play.looks_like_noise_label('589N 3.38B', config)

    buttons = [
        auto_play.ButtonCandidate(
            label='Kx3437',
            x=0.9139,
            y=0.0887,
            confidence=0.85,
            clickability=1.64,
        ),
        auto_play.ButtonCandidate(
            label='*x4681',
            x=0.9139,
            y=0.0887,
            confidence=0.84,
            clickability=1.65,
        ),
        auto_play.ButtonCandidate(
            label='B45B',
            x=0.0653,
            y=0.66,
            confidence=0.98,
            clickability=2.0,
        ),
    ]

    filtered = [
        button
        for button in buttons
        if not auto_play.looks_like_noise_label(button.label, config)
    ]
    extras = auto_play.configured_extra_candidates(config, filtered)

    assert filtered == []
    assert [button.label for button in extras] == ['Battle active skill']


def test_survivor_top_left_battle_nameplates_fall_back_to_active_skill():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    buttons = [
        auto_play.ButtonCandidate(
            label='Black Hole Ruler',
            x=0.2139,
            y=0.1437,
            confidence=0.99,
            clickability=1.54,
        ),
        auto_play.ButtonCandidate(
            label='Lightning Steelguard',
            x=0.2389,
            y=0.1938,
            confidence=0.98,
            clickability=1.47,
        ),
    ]

    filtered = auto_play.filter_configured_non_action_buttons(config, buttons)
    extras = auto_play.configured_extra_candidates(config, filtered)

    assert filtered == []
    assert [button.label for button in extras] == ['Battle active skill']


def test_survivor_top_left_battle_nameplate_does_not_hide_active_skill():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    buttons = [
        auto_play.ButtonCandidate(
            label='Divine Sage',
            x=0.1208,
            y=0.1938,
            confidence=0.958,
            clickability=1.678,
        ),
        auto_play.ButtonCandidate(
            label='battle active skill',
            x=0.86,
            y=0.79,
            confidence=0.58,
            clickability=1.45,
            source='template',
        ),
    ]

    filtered = auto_play.filter_configured_non_action_buttons(config, buttons)

    assert [button.label for button in filtered] == ['battle active skill']


def test_survivor_skill_choice_keeps_passive_named_card_titles():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    buttons = [
        auto_play.ButtonCandidate(
            label='Skill Choice',
            x=0.5,
            y=0.23,
            confidence=0.95,
            clickability=0.2,
        ),
        auto_play.ButtonCandidate(
            label='Select a skill to learn',
            x=0.5,
            y=0.29,
            confidence=0.95,
            clickability=0.2,
        ),
        auto_play.ButtonCandidate(
            label='Dawnguard',
            x=0.18,
            y=0.39,
            confidence=0.9,
            clickability=1.0,
        ),
    ]

    assert auto_play.filter_configured_non_action_buttons(config, buttons) == buttons


def test_survivor_skill_choice_visible_when_instruction_is_split():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    buttons = [
        auto_play.ButtonCandidate(
            label='Skill Choice',
            x=0.5,
            y=0.23,
            confidence=0.95,
            clickability=0.2,
        ),
        auto_play.ButtonCandidate(
            label='Select a',
            x=0.4,
            y=0.72,
            confidence=0.95,
            clickability=0.2,
        ),
        auto_play.ButtonCandidate(
            label='skill to learn',
            x=0.57,
            y=0.72,
            confidence=0.95,
            clickability=0.2,
        ),
        auto_play.ButtonCandidate(
            label='Refresh',
            x=0.5,
            y=0.81,
            confidence=0.95,
            clickability=2.0,
        ),
        auto_play.ButtonCandidate(
            label='Energy Drink',
            x=0.17,
            y=0.397,
            confidence=0.95,
            clickability=2.0,
        ),
    ]

    inspections = auto_play.configured_skill_choice_inspections(
        automation_config=config,
        game='survivor',
        buttons=buttons,
    )

    assert auto_play.configured_skill_choice_visible(config, buttons)
    assert [inspection.candidate.label for inspection in inspections] == [
        'Energy Drink'
    ]


def test_survivor_skill_choice_ignores_damage_text_in_title_band():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    buttons = [
        auto_play.ButtonCandidate(
            label='Skill Choice',
            x=0.5,
            y=0.23,
            confidence=0.95,
            clickability=0.2,
        ),
        auto_play.ButtonCandidate(
            label='Select a skill to learn',
            x=0.5,
            y=0.72,
            confidence=0.95,
            clickability=0.2,
        ),
        auto_play.ButtonCandidate(
            label='267M342M2',
            x=0.59,
            y=0.351,
            confidence=0.89,
            clickability=1.3,
        ),
        auto_play.ButtonCandidate(
            label='Twinborn',
            x=0.5,
            y=0.388,
            confidence=1.0,
            clickability=2.0,
        ),
        auto_play.ButtonCandidate(
            label='Guardian',
            x=0.5,
            y=0.404,
            confidence=1.0,
            clickability=2.0,
        ),
        auto_play.ButtonCandidate(
            label='+1 top',
            x=0.42,
            y=0.50,
            confidence=0.99,
            clickability=1.4,
        ),
    ]

    inspections = auto_play.configured_skill_choice_inspections(
        automation_config=config,
        game='survivor',
        buttons=buttons,
    )

    assert [inspection.candidate.label for inspection in inspections] == [
        'Twinborn Guardian'
    ]


def test_survivor_skill_choice_closes_detail_overlay_before_clicking_fragments(
    tmp_path,
):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    buttons = [
        auto_play.ButtonCandidate(
            label='Skill Choice',
            x=0.5,
            y=0.218,
            confidence=0.99,
            clickability=1.0,
        ),
        auto_play.ButtonCandidate(
            label='Select a skill to learn',
            x=0.5,
            y=0.718,
            confidence=0.99,
            clickability=0.7,
        ),
        auto_play.ButtonCandidate(
            label='Exo-radicator',
            x=0.5,
            y=0.33,
            confidence=0.99,
            clickability=1.8,
        ),
        auto_play.ButtonCandidate(
            label='(Guardian Mode)',
            x=0.5,
            y=0.349,
            confidence=0.99,
            clickability=1.8,
        ),
        auto_play.ButtonCandidate(
            label='Twinborn Guardian. Can be evolved',
            x=0.51,
            y=0.536,
            confidence=0.98,
            clickability=1.8,
        ),
        auto_play.ButtonCandidate(
            label='Twinborn Guardian: Knockback',
            x=0.48,
            y=0.569,
            confidence=0.99,
            clickability=1.8,
        ),
        auto_play.ButtonCandidate(
            label='cher',
            x=0.918,
            y=0.398,
            confidence=1.0,
            clickability=1.1,
        ),
    ]

    inspections, decision = auto_play.inspect_configured_skill_choice(
        SimpleNamespace(game='survivor'),
        automation_config=config,
        buttons=buttons,
        artifact_paths={'item_inspections': tmp_path / 'item_inspections.yaml'},
    )

    assert inspections == []
    assert decision is not None
    assert decision.recommended.label == 'Close skill detail'


def test_survivor_strategy_prefers_always_preferred_skill_choices():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    assert config.always_preferred_choice_terms == (
        'drone',
        'twinborn type-a',
        'twinborn type-b',
        'type-a drone',
        'type-b drone',
        'havoc',
        'havo',
        'lavoc',
        'lova havo',
        'havoo',
        'avoc',
        'starforge',
        'starforg',
    )
    assert any(
        rule.pattern == 'gold gain' and rule.points < 0
        for rule in config.item_preference_rules
    )

    buttons = [
        auto_play.ButtonCandidate(
            label='Skill Choice',
            x=0.5,
            y=0.23,
            confidence=0.95,
            clickability=0.2,
        ),
        auto_play.ButtonCandidate(
            label='Select a skill to learn',
            x=0.5,
            y=0.72,
            confidence=0.95,
            clickability=0.2,
        ),
        auto_play.ButtonCandidate(
            label='Oil Bond',
            x=0.17,
            y=0.40,
            confidence=0.96,
            clickability=2.0,
        ),
        auto_play.ButtonCandidate(
            label='Gold gain +40%',
            x=0.17,
            y=0.52,
            confidence=0.94,
            clickability=1.0,
        ),
        auto_play.ButtonCandidate(
            label='New Twinborn',
            x=0.50,
            y=0.39,
            confidence=0.96,
            clickability=2.0,
        ),
        auto_play.ButtonCandidate(
            label='Type-A Drone',
            x=0.50,
            y=0.41,
            confidence=0.96,
            clickability=2.0,
        ),
        auto_play.ButtonCandidate(
            label='Drone fires many missiles',
            x=0.50,
            y=0.52,
            confidence=0.94,
            clickability=1.0,
        ),
    ]

    inspections = auto_play.configured_skill_choice_inspections(
        automation_config=config,
        game='survivor',
        buttons=buttons,
    )
    ranked = sorted(inspections, key=lambda item: item.score, reverse=True)

    assert ranked[0].candidate.label == 'Twinborn Type-A Drone'
    assert ranked[0].score > ranked[1].score
    assert ranked[0].reasons[0] == 'always preferred by strategy: drone'

    havoc_score, havoc_reasons = auto_play.configured_item_preference_score(
        'Havoc',
        'Damage up',
        config,
    )
    starforge_score, starforge_reasons = auto_play.configured_item_preference_score(
        'Starforge',
        'Damage up',
        config,
    )
    oil_score, _oil_reasons = auto_play.configured_item_preference_score(
        'Oil Bond',
        'Gold gain +40%',
        config,
    )
    fitness_score, fitness_reasons = auto_play.configured_item_preference_score(
        'Fitness Guide',
        'Max HP +40%',
        config,
    )
    bullet_score, bullet_reasons = auto_play.configured_item_preference_score(
        'Hi-Power Bullet',
        'ATK +10%',
        config,
    )

    assert havoc_score > oil_score
    assert starforge_score > oil_score
    assert fitness_score > oil_score
    assert bullet_score > oil_score
    assert havoc_reasons[0] == 'always preferred by strategy: havoc'
    assert starforge_reasons[0] == 'always preferred by strategy: starforge'
    assert 'survivor chapter clear: prefer survivability' in fitness_reasons
    assert 'survivor chapter clear: prefer damage' in bullet_reasons

    split_drone_score, split_drone_reasons = auto_play.configured_item_preference_score(
        'Twinborn Type-B',
        'Summons Type-B; d r 0 n e',
        config,
    )

    assert split_drone_score > oil_score
    assert split_drone_reasons[0] == 'always preferred by strategy: drone'


def test_survivor_button_scoring_prefers_drone_title_not_description():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')
    memory = {
        'preferred': ['Drone', 'Havoc', 'Starforge'],
        'avoid': [],
        'ineffective': [],
    }
    buttons = [
        auto_play.ButtonCandidate(
            label='Boomerang',
            x=0.83,
            y=0.40,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Type-A Drone',
            x=0.50,
            y=0.41,
            confidence=0.96,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Drone fires many missiles',
            x=0.50,
            y=0.53,
            confidence=1.0,
            clickability=1.5,
            source='ocr',
        ),
    ]

    scored = auto_play.score_buttons(buttons, memory, automation_config=config)

    assert scored[0].label == 'Type-A Drone'
    assert scored[-1].label == 'Drone fires many missiles'


def test_survivor_game_info_ranking_uses_strategy_always_preferred_choices(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    write_game_strategy(tmp_path, 'survivor')

    turn = tmp_path / 'games' / 'survivor' / 'turns' / 'turn-001'
    turn.mkdir(parents=True)
    (turn / 'item_inspections.yaml').write_text(
        """
items:
  - candidate:
      label: Oil Bond
    description: Gold gain +40%
    kind: skill
    item_score: 5.0
    reasons:
      - coin or gold gain
    screenshot: item_inspections/01-oil-bond.png
  - candidate:
      label: New Twinborn Type-A Drone
    description: Drone fires many missiles
    kind: skill
    item_score: 0.0
    reasons:
      - observed detail
    screenshot: item_inspections/02-drone.png
  - candidate:
      label: Havoc
    description: Damage up
    kind: skill
    item_score: 4.0
    reasons:
      - stat increase
    screenshot: item_inspections/03-havoc.png
  - candidate:
      label: Starforge
    description: Damage up
    kind: skill
    item_score: 4.0
    reasons:
      - stat increase
    screenshot: item_inspections/04-starforge.png
  - candidate:
      label: Congratulations!
    description: Victory; Confirm
    kind: item
    item_score: 0.0
    reasons:
      - observed detail
    screenshot: item_inspections/05-noise.png
"""
    )

    path = auto_play.write_game_info_markdown('survivor')
    knowledge = path.read_text()

    assert '### item' not in knowledge
    assert 'Congratulations!' not in knowledge
    assert knowledge.index('Twinborn Type-A Drone') < knowledge.index('Oil Bond')
    assert knowledge.index('Havoc') < knowledge.index('Oil Bond')
    assert knowledge.index('Starforge') < knowledge.index('Oil Bond')
    assert '| Twinborn Type-A Drone | 100.00 |' in knowledge
    assert '| Havoc | 106.00 |' in knowledge
    assert '| Starforge | 106.00 |' in knowledge
    assert 'New Twinborn Type-A Drone' not in knowledge
    assert 'always preferred by strategy: drone' in knowledge
    assert 'always preferred by strategy: havoc' in knowledge
    assert 'always preferred by strategy: starforge' in knowledge


def test_survivor_game_info_strips_misread_new_badge_prefix(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    write_game_strategy(tmp_path, 'survivor')

    turn = tmp_path / 'games' / 'survivor' / 'turns' / 'turn-001'
    turn.mkdir(parents=True)
    (turn / 'item_inspections.yaml').write_text(
        """
items:
  - candidate:
      label: Ney Hi-Power Magnet
    description: Item loot range
    kind: skill
    item_score: 0.0
    reasons:
      - no strong cue
    screenshot: item_inspections/01-magnet.png
"""
    )

    knowledge = auto_play.write_game_info_markdown('survivor').read_text()

    assert '| Hi-Power Magnet | 1.00 |' in knowledge
    assert 'Ney Hi-Power Magnet' not in knowledge


def test_survivor_game_info_merges_bad_duplicate_item_names(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    write_game_strategy(tmp_path, 'survivor')

    turns = tmp_path / 'games' / 'survivor' / 'turns'
    for index, label in enumerate(
        ['Gold Pouch', 'Gold Pouch', 'Gold Pouch', 'ioldr'],
        start=1,
    ):
        turn = turns / f'turn-{index:03d}'
        turn.mkdir(parents=True)
        (turn / 'item_inspections.yaml').write_text(
            f"""
items:
  - candidate:
      label: {label}
    description: Obtain 50 Gold
    kind: skill
    item_score: 5.0
    reasons:
      - coin gain
    screenshot: item_inspections/01-item.png
"""
        )

    knowledge = auto_play.write_game_info_markdown('survivor').read_text()

    assert '| Gold Pouch | 5.00 | 4 |' in knowledge
    assert 'ioldr' not in knowledge


def test_survivor_active_skill_verifies_main_battle_area():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    region, box = auto_play.progress_region_for_button(
        Image.new('RGB', (360, 800), color='black'),
        auto_play.ButtonCandidate(
            label='Battle active skill',
            x=0.86,
            y=0.79,
            confidence=1.0,
            clickability=2.6,
            source='vision',
        ),
        config,
    )

    assert region == 'main_screen_without_status_bar'
    assert box == (0, 48, 360, 800)


def test_tower_recruit_selection_verifies_character_grid():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    region, box = auto_play.progress_region_for_button(
        Image.new('RGB', (360, 800), color='black'),
        auto_play.ButtonCandidate(
            label='选择新招募角色：逗比的守夜人',
            x=0.86,
            y=0.82,
            confidence=1.0,
            clickability=20.0,
            source='state',
        ),
        config,
    )

    assert region == 'main_screen_without_status_bar'
    assert box == (0, 48, 360, 800)


def test_survivor_challenge_detail_does_not_reclick_grid_cell():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    buttons = [
        auto_play.ButtonCandidate(
            label='Chapter 259',
            x=0.48,
            y=0.32,
            confidence=0.98,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Start',
            x=0.50,
            y=0.71,
            confidence=0.999,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Battle',
            x=0.79,
            y=0.68,
            confidence=0.999,
            clickability=1.8,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='260.Recycling Center',
            x=0.50,
            y=0.82,
            confidence=0.997,
            clickability=0.9,
            source='ocr',
        ),
    ]

    extras = auto_play.configured_extra_candidates(config, buttons)
    scored = auto_play.score_buttons(
        [*buttons, *extras],
        memory={
            'preferred': ['Start', 'Battle', 'Third column unclaimed row'],
            'avoid': [],
            'ineffective': [],
        },
        automation_config=config,
    )
    decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.65,
        ambiguity_margin=0.2,
        ask_on_ambiguous=False,
        fallback_labels=set(),
    )

    assert extras == []
    assert decision.status == 'ready'
    assert decision.recommended.label == 'Start'


def test_survivor_challenge_detail_prefers_start_over_bottom_nav_battle():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    buttons = [
        auto_play.ButtonCandidate(
            label='316.Battle of Past',
            x=0.5014,
            y=0.1981,
            confidence=0.999,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Battle',
            x=0.4958,
            y=0.9825,
            confidence=0.999,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Start',
            x=0.5,
            y=0.8069,
            confidence=0.999,
            clickability=2.0,
            source='ocr',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={
            'preferred': ['Battle'],
            'avoid': [],
            'ineffective': [],
        },
        automation_config=config,
    )
    decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.65,
        ambiguity_margin=0.2,
        ask_on_ambiguous=False,
        fallback_labels=set(),
        automation_config=config,
    )

    assert decision.status == 'ready'
    assert decision.recommended.label == 'Start'


def test_survivor_assist_pack_popup_dismisses_before_start_or_view():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    buttons = [
        auto_play.ButtonCandidate(
            label='320.Stargate Arrival',
            x=0.495,
            y=0.2,
            confidence=0.999,
            clickability=0.95,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Chapter 320 Assist',
            x=0.714,
            y=0.476,
            confidence=0.989,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Assist Pack',
            x=0.26,
            y=0.642,
            confidence=0.966,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='unlocked in Shop',
            x=0.699,
            y=0.523,
            confidence=0.958,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='View',
            x=0.743,
            y=0.616,
            confidence=0.999,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Start',
            x=0.499,
            y=0.806,
            confidence=0.999,
            clickability=0.9,
            source='ocr',
        ),
    ]

    extras = auto_play.configured_extra_candidates(config, buttons)
    scored = auto_play.score_buttons(
        [*buttons, *extras],
        memory={
            'preferred': ['Start', 'Battle'],
            'avoid': [],
            'ineffective': [],
        },
        automation_config=config,
    )
    decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.65,
        ambiguity_margin=0.2,
        ask_on_ambiguous=False,
        fallback_labels=set(),
        automation_config=config,
    )

    assert [button.label for button in extras] == ['Dismiss assist pack popup']
    assert decision.status == 'ready'
    assert decision.recommended.label == 'Dismiss assist pack popup'


def test_survivor_assist_pack_popup_uses_view_after_dismiss_fails():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    buttons = [
        auto_play.ButtonCandidate(
            label='Chapter 330 Assist',
            x=0.714,
            y=0.476,
            confidence=0.989,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Part Assist Pack',
            x=0.26,
            y=0.642,
            confidence=0.966,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Pack has been unlocked in Shop',
            x=0.699,
            y=0.523,
            confidence=0.958,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='View',
            x=0.743,
            y=0.616,
            confidence=0.999,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Start',
            x=0.499,
            y=0.806,
            confidence=0.999,
            clickability=0.9,
            source='ocr',
        ),
    ]

    extras = auto_play.configured_extra_candidates(config, buttons)
    scored = auto_play.score_buttons(
        [*buttons, *extras],
        memory={
            'preferred': ['Start', 'Battle'],
            'avoid': [],
            'ineffective': ['Dismiss assist pack popup'],
        },
        automation_config=config,
    )
    decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.65,
        ambiguity_margin=0.2,
        ask_on_ambiguous=False,
        fallback_labels=set(),
        automation_config=config,
    )

    assert decision.status == 'ready'
    assert decision.recommended.label == 'View'


def test_survivor_shop_screen_uses_battle_tab_escape():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')

    buttons = [
        auto_play.ButtonCandidate(
            label='Limited Chapter Assist Pack',
            x=0.5,
            y=0.13,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Daily Shop',
            x=0.5,
            y=0.39,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Gems',
            x=0.18,
            y=0.47,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Tech Parts Crate',
            x=0.61,
            y=0.87,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
    ]

    extras = auto_play.configured_extra_candidates(config, buttons)
    scored = auto_play.score_buttons(
        [*buttons, *extras],
        memory={
            'preferred': ['Start', 'Battle'],
            'avoid': [],
            'ineffective': ['Gems', 'Tech Parts Crate'],
        },
        automation_config=config,
    )
    decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.65,
        ambiguity_margin=0.2,
        ask_on_ambiguous=False,
        fallback_labels=set(),
        automation_config=config,
    )

    assert [button.label for button in extras] == ['Battle tab from shop']
    assert decision.status == 'ready'
    assert decision.recommended.label == 'Battle tab from shop'


def test_survivor_weekly_goodies_claim_blocks_underlying_battle():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'survivor')
    buttons = [
        auto_play.ButtonCandidate(
            label='Weekly Goodies',
            x=0.5,
            y=0.4,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Claim',
            x=0.5,
            y=0.6,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Battle',
            x=0.47,
            y=0.87,
            confidence=1.0,
            clickability=0.7,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Start',
            x=0.5,
            y=0.81,
            confidence=1.0,
            clickability=0.8,
            source='ocr',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={
            'preferred': ['Start', 'Battle', 'Claim'],
            'avoid': [],
            'ineffective': [],
        },
        automation_config=config,
    )
    decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.65,
        ambiguity_margin=0.2,
        ask_on_ambiguous=False,
        fallback_labels=set(),
        automation_config=config,
    )

    assert auto_play.weekly_goodies_popup_visible(buttons)
    assert decision.status == 'ready'
    assert decision.recommended.label == 'Claim'


def test_blank_loading_screen_uses_wait_candidate():
    auto_play = load_auto_play_module()

    assert auto_play.is_mostly_blank_screen(Image.new('RGB', (360, 800), 'black'))
    assert not auto_play.is_mostly_blank_screen(Image.new('RGB', (360, 800), 'white'))
    assert auto_play.wait_for_loading_candidate().source == 'wait'


def test_blank_loading_screen_ignores_bottom_gesture_bar():
    auto_play = load_auto_play_module()
    image = Image.new('RGB', (360, 800), 'black')
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((132, 786, 228, 790), radius=2, fill='white')

    assert auto_play.is_mostly_blank_screen(image)


def test_repeated_blank_wait_escalates_to_back_candidate():
    auto_play = load_auto_play_module()

    assert auto_play.repeated_blank_wait_detected(
        [
            'Wait for loading screen',
            'Wait for loading screen',
            'Wait for loading screen',
        ]
    )
    assert auto_play.android_back_candidate('stuck').source == 'back'


def test_back_candidate_uses_android_mcp_back_tool(monkeypatch):
    auto_play = load_auto_play_module()
    calls = []

    class FakeMcpClient:
        def __init__(self, command, timeout):
            self.command = command
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def call_tool(self, name, arguments):
            calls.append((name, arguments))

    monkeypatch.setattr(auto_play, 'McpClient', FakeMcpClient)

    args = SimpleNamespace(mcp_command='python -m android_access_mcp', timeout=3)
    auto_play.click_button(args, auto_play.android_back_candidate('stuck'))

    assert calls == [('back', {})]


def test_tower_external_app_recovery_avoids_clicking_external_content(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play.subprocess,
        'run',
        lambda *args, **kwargs: SimpleNamespace(
            stdout=(
                'mCurrentFocus=Window{x u0 '
                'com.taptap/com.taptap.other.ExternalActivity}'
            )
        ),
    )
    metadata = {'serial': 'phone-1'}

    candidate = auto_play.external_android_recovery_candidate('tower', metadata)

    assert candidate is not None
    assert candidate.source == 'back'
    assert metadata['foreground_package'] == 'com.taptap'


def test_tower_launcher_recovery_reopens_expected_game(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play.subprocess,
        'run',
        lambda *args, **kwargs: SimpleNamespace(
            stdout=(
                'mCurrentFocus=Window{x u0 '
                'com.google.android.apps.nexuslauncher/'
                'com.google.android.apps.nexuslauncher.NexusLauncherActivity}'
            )
        ),
    )

    candidate = auto_play.external_android_recovery_candidate(
        'tower',
        {'serial': 'phone-1'},
    )

    assert candidate is not None
    assert candidate.source == 'launch_app'
    assert candidate.label.endswith('cn.thearky.projectrl')


def test_tower_taptap_login_is_allowed_to_finish(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play.subprocess,
        'run',
        lambda *args, **kwargs: SimpleNamespace(
            stdout=(
                'mCurrentFocus=Window{x u0 '
                'com.taptap/com.taptap.common.account.ui.login.LoginActivity}'
            )
        ),
    )

    candidate = auto_play.external_android_recovery_candidate(
        'tower',
        {'serial': 'phone-1'},
    )

    assert candidate is not None
    assert candidate.source == 'wait'


def test_tower_expected_game_package_needs_no_recovery(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play.subprocess,
        'run',
        lambda *args, **kwargs: SimpleNamespace(
            stdout=(
                'mCurrentFocus=Window{x u0 '
                'cn.thearky.projectrl/cn.thearky.projectrl.GamePlayerActivity}'
            )
        ),
    )

    assert (
        auto_play.external_android_recovery_candidate(
            'tower',
            {'serial': 'phone-1'},
        )
        is None
    )


def test_google_play_purchase_sheet_is_back_context():
    auto_play = load_auto_play_module()
    buttons = [
        auto_play.ButtonCandidate(
            label='Google Play',
            x=0.15,
            y=0.49,
            confidence=0.98,
            clickability=1.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='1-tap buy',
            x=0.5,
            y=0.94,
            confidence=0.95,
            clickability=1.8,
            source='ocr',
        ),
    ]

    assert auto_play.google_play_purchase_sheet_visible(buttons)


def test_survivor_skill_choice_captures_game_info_and_selects_skill(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    write_game_strategy(tmp_path, 'survivor')

    buttons = [
        auto_play.ButtonCandidate(
            label='Skill Choice',
            x=0.50,
            y=0.22,
            confidence=0.98,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Select a skill to learn',
            x=0.50,
            y=0.72,
            confidence=0.99,
            clickability=1.6,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Refresh',
            x=0.50,
            y=0.80,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Adrenaline',
            x=0.16,
            y=0.40,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Each time HP is',
            x=0.15,
            y=0.50,
            confidence=0.99,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='lost, damage',
            x=0.13,
            y=0.52,
            confidence=0.97,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='+18% for 10s',
            x=0.13,
            y=0.53,
            confidence=0.99,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Boomerang',
            x=0.50,
            y=0.40,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Throws 1',
            x=0.44,
            y=0.50,
            confidence=0.98,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='boomerang',
            x=0.46,
            y=0.52,
            confidence=1.0,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Twinborn Soccer',
            x=0.83,
            y=0.39,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Ball',
            x=0.83,
            y=0.41,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Shoots 1',
            x=0.77,
            y=0.50,
            confidence=0.97,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='bouncing soccer',
            x=0.82,
            y=0.52,
            confidence=0.99,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='ball',
            x=0.73,
            y=0.53,
            confidence=0.99,
            clickability=1.5,
            source='ocr',
        ),
    ]
    args = SimpleNamespace(
        image=None,
        click_recommended=True,
        game='survivor',
        item_description_label_limit=12,
    )
    turn_dir = tmp_path / 'games' / 'survivor' / 'turns' / 'turn-001'
    turn_dir.mkdir(parents=True)
    artifact_paths = {
        'item_inspections': turn_dir / 'item_inspections.yaml',
        'item_inspection_dir': turn_dir / 'item_inspections',
    }

    inspections, decision = auto_play.inspect_item_choices(
        args,
        buttons=buttons,
        memory={'fallback': [], 'avoid': [], 'ineffective': []},
        artifact_paths=artifact_paths,
    )

    assert decision is not None
    assert decision.recommended.label == 'Adrenaline'
    assert 0.39 <= decision.recommended.y <= 0.41
    assert [item.candidate.label for item in inspections] == [
        'Adrenaline',
        'Boomerang',
        'Twinborn Soccer Ball',
    ]
    assert all(0.36 <= item.candidate.y <= 0.42 for item in inspections)
    assert all(item.kind == 'skill' for item in inspections)
    payload = artifact_paths['item_inspections'].read_text()
    assert 'kind: skill' in payload
    knowledge = (tmp_path / 'games' / 'survivor' / 'game_info.md').read_text()
    assert '### skill' in knowledge
    assert 'Adrenaline' in knowledge
    assert 'Each time HP is; lost, damage; +18% for 10s' in knowledge
    assert 'Boomerang' in knowledge
    assert 'Twinborn Soccer Ball' in knowledge


def test_survivor_no_change_skill_card_updates_rule_not_ineffective(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    strategy = write_game_strategy(tmp_path, 'survivor')

    auto_play.append_no_change_learning(
        'survivor',
        auto_play.ButtonCandidate(
            label='New occer',
            x=0.83,
            y=0.39,
            confidence=1.0,
            clickability=2.4,
            source='ocr',
            reason='Survivor actual-battle skill choice yellow title banner.',
        ),
        auto_play.StateVerification(
            status='unchanged',
            reason='No screen change after repeated taps.',
            attempts=3,
            threshold=0.995,
            similarities=[1.0, 1.0, 1.0],
            progress_threshold=0.985,
            progress_similarities=[1.0, 1.0, 1.0],
            progress_region='main_screen_without_status_bar',
        ),
    )

    text = strategy.read_text()
    ineffective = auto_play.extract_section(text, 'Ineffective Buttons')
    assert '- New occer' not in ineffective
    assert 'try another visible skill card' in text


def test_survivor_no_change_active_skill_updates_rule_not_ineffective(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    strategy = write_game_strategy(tmp_path, 'survivor')

    auto_play.append_no_change_learning(
        'survivor',
        auto_play.ButtonCandidate(
            label='Battle active skill',
            x=0.86,
            y=0.79,
            confidence=1.0,
            clickability=2.6,
            source='vision',
            reason='Survivor actual battle has no text actions.',
        ),
        auto_play.StateVerification(
            status='unchanged',
            reason='No stable progress by lower UI.',
            attempts=3,
            threshold=0.995,
            similarities=[0.91, 0.93, 0.92],
            progress_threshold=0.985,
            progress_similarities=[0.986, 0.987, 0.986],
            progress_region='lower_progress_region',
        ),
    )

    text = strategy.read_text()
    ineffective = auto_play.extract_section(text, 'Ineffective Buttons')
    assert '- Battle active skill' not in ineffective
    assert 'keep treating it as an actual-battle fallback' in text


def test_wait_candidate_no_change_is_not_learned_ineffective(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    strategy = write_game_strategy(tmp_path, 'survivor')
    wait = auto_play.ButtonCandidate(
        label='Wait for loading screen',
        x=0.5,
        y=0.5,
        confidence=1.0,
        clickability=3.0,
        source='wait',
        reason='Mostly blank loading screen.',
    )
    verification = auto_play.StateVerification(
        status='unchanged',
        reason='Loading screen still blank.',
        attempts=3,
        threshold=0.995,
        similarities=[1.0, 1.0, 1.0],
        progress_threshold=0.985,
        progress_similarities=[1.0, 1.0, 1.0],
        progress_region='full',
        strategy_updated=True,
    )

    changed = auto_play.append_no_change_learning('survivor', wait, verification)

    text = strategy.read_text()
    ineffective = auto_play.extract_section(text, 'Ineffective Buttons')
    assert changed is False
    assert '- Wait for loading screen' not in ineffective
    assert (
        auto_play.strategy_change_recommendation(
            wait,
            verification,
            auto_play.load_automation_config('survivor'),
        )
        is None
    )


def test_android_lock_screen_uses_wait_candidate_not_system_text():
    auto_play = load_auto_play_module()
    buttons = [
        auto_play.ButtonCandidate(
            label='Mon, May 25',
            x=0.66,
            y=0.11,
            confidence=0.99,
            clickability=1.7,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Charging is limited to protect...',
            x=0.48,
            y=0.25,
            confidence=0.96,
            clickability=1.7,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='91% - Done charging',
            x=0.5,
            y=0.94,
            confidence=0.94,
            clickability=1.5,
            source='ocr',
        ),
    ]

    assert auto_play.android_system_screen_visible(buttons)
    candidate = auto_play.wait_for_android_unlock_candidate()
    assert candidate.source == 'wait'
    assert candidate.label == 'Wait for Android unlock'


def test_fallback_arrow_loses_to_viable_strength_action():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    arrow = auto_play.ButtonCandidate(
        label='上方道路',
        x=0.5,
        y=0.9,
        confidence=0.95,
        clickability=0.8,
        source='template',
        score=2.2,
    )
    chest = auto_play.ButtonCandidate(
        label='Chest',
        x=0.3,
        y=0.65,
        confidence=0.7,
        clickability=0.8,
        source='template',
        score=1.02,
    )

    decision = auto_play.decide_next_move(
        [arrow, chest],
        min_action_score=0.95,
        ambiguity_margin=0.2,
        ask_on_ambiguous=False,
        fallback_labels=set(),
        automation_config=config,
    )

    assert decision.status == 'ready'
    assert decision.recommended.label == 'Chest'


def test_fallback_arrow_is_allowed_when_it_is_the_only_viable_action():
    auto_play = load_auto_play_module()

    arrow = auto_play.ButtonCandidate(
        label='Next Room',
        x=0.5,
        y=0.9,
        confidence=0.95,
        clickability=0.8,
        source='template',
        score=1.1,
    )

    decision = auto_play.decide_next_move(
        [arrow],
        min_action_score=0.95,
        ambiguity_margin=0.2,
        ask_on_ambiguous=False,
        fallback_labels={'next room'},
    )

    assert decision.status == 'ready'
    assert decision.recommended.label == 'Next Room'


def test_multiple_navigation_arrows_prefer_bright_clickable_arrow():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    dim_arrow = auto_play.ButtonCandidate(
        label='左侧道路',
        x=0.4,
        y=0.9,
        confidence=0.98,
        clickability=0.15,
        source='template',
    )
    bright_arrow = auto_play.ButtonCandidate(
        label='右侧道路',
        x=0.6,
        y=0.9,
        confidence=0.72,
        clickability=0.85,
        source='template',
    )

    scored = auto_play.score_buttons(
        [dim_arrow, bright_arrow],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '右侧道路'


def test_abandon_loses_to_confirm_even_when_strategy_omits_avoid_label():
    auto_play = load_auto_play_module()

    abandon = auto_play.ButtonCandidate(
        label='Abandon',
        x=0.3,
        y=0.7,
        confidence=1.0,
        clickability=2.0,
        source='ocr',
    )
    confirm = auto_play.ButtonCandidate(
        label='confirm',
        x=0.7,
        y=0.7,
        confidence=1.0,
        clickability=1.5,
        source='template',
    )

    scored = auto_play.score_buttons(
        [abandon, confirm],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
    )

    assert scored[0].label == 'confirm'


def test_end_is_allowed_only_when_it_is_the_only_detected_action():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    end = auto_play.ButtonCandidate(
        label='End',
        x=0.5,
        y=0.9,
        confidence=1.0,
        clickability=1.8,
        source='ocr',
    )

    scored = auto_play.score_buttons(
        [end],
        memory={'preferred': [], 'avoid': ['End'], 'ineffective': ['End']},
    )

    assert scored[0].score >= 1.0

    attack = auto_play.ButtonCandidate(
        label='普通攻击',
        x=0.4,
        y=0.6,
        confidence=0.9,
        clickability=1.5,
        source='template',
    )
    scored_with_attack = auto_play.score_buttons(
        [end, attack],
        memory={'preferred': ['普通攻击'], 'avoid': ['End'], 'ineffective': ['End']},
        automation_config=config,
    )

    assert scored_with_attack[0].label == '普通攻击'


def test_combat_cards_ignore_stale_ineffective_memory():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    card = auto_play.ButtonCandidate(
        label='普通木剑',
        x=0.2,
        y=0.6,
        confidence=0.9,
        clickability=1.6,
        source='template',
    )

    scored = auto_play.score_buttons(
        [card],
        memory={'preferred': ['普通木剑'], 'avoid': [], 'ineffective': ['普通木剑']},
        automation_config=config,
    )

    assert scored[0].score > 2.0


def test_life_sacrifice_card_is_treated_as_combat_card():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    assert auto_play.should_double_click_button(
        auto_play.ButtonCandidate(
            label='舍命一击',
            x=0.2,
            y=0.8,
            confidence=1.0,
            clickability=1.0,
        ),
        config,
    )


def test_stale_combat_card_template_loses_when_navigation_arrow_is_visible():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    stale_card = auto_play.ButtonCandidate(
        label='弱点打击',
        x=0.83,
        y=0.82,
        confidence=0.99,
        clickability=0.77,
        source='template',
    )
    arrow = auto_play.ButtonCandidate(
        label='右侧道路',
        x=0.86,
        y=0.75,
        confidence=0.79,
        clickability=1.4,
        source='template',
    )

    scored = auto_play.score_buttons(
        [stale_card, arrow],
        memory={'preferred': ['弱点打击'], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )
    decision = auto_play.decide_unblock_move(scored, set())

    assert scored[0].label == '右侧道路'
    assert decision.recommended.label == '右侧道路'


def test_exit_arrow_beats_current_room_icon_when_arrow_is_visible():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    current_room = auto_play.ButtonCandidate(
        label='岩壳龙',
        x=0.27,
        y=0.67,
        confidence=0.94,
        clickability=1.63,
        source='template',
    )
    exit_arrow = auto_play.ButtonCandidate(
        label='右侧道路',
        x=0.78,
        y=0.75,
        confidence=1.0,
        clickability=0.98,
        source='template',
    )

    scored = auto_play.score_buttons(
        [current_room, exit_arrow],
        memory={'preferred': ['岩壳龙'], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '右侧道路'


def test_center_route_arrow_beats_stale_vision_room_icon():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    stale_room = auto_play.ButtonCandidate(
        label='Visible combat room icon',
        x=0.19,
        y=0.66,
        confidence=0.98,
        clickability=7.0,
        source='vision',
    )
    center_arrow = auto_play.ButtonCandidate(
        label='上方道路',
        x=0.48,
        y=0.64,
        confidence=0.97,
        clickability=1.12,
        source='template',
    )

    scored = auto_play.score_buttons(
        [stale_room, center_arrow],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '上方道路'


def test_bright_navigation_arrow_wins_even_when_other_arrow_not_in_fallback_list():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')

    bright_arrow = auto_play.ButtonCandidate(
        label='右侧道路',
        x=0.93,
        y=0.71,
        confidence=1.0,
        clickability=0.53,
        source='template',
        score=1.85,
    )
    dim_arrow = auto_play.ButtonCandidate(
        label='上方道路',
        x=0.49,
        y=0.63,
        confidence=1.0,
        clickability=0.43,
        source='template',
        score=1.69,
    )

    decision = auto_play.decide_next_move(
        [bright_arrow, dim_arrow],
        min_action_score=0.95,
        ambiguity_margin=0.2,
        ask_on_ambiguous=False,
        fallback_labels={'右侧道路'},
        automation_config=config,
    )

    assert decision.status == 'ready'
    assert decision.recommended.label == '右侧道路'


def test_no_change_learning_does_not_globally_mark_navigation_arrow_ineffective(
    tmp_path, monkeypatch
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    strategy = write_game_strategy(tmp_path, 'tower')

    auto_play.append_no_change_learning(
        'Tower',
        auto_play.ButtonCandidate(
            label='右侧道路',
            x=0.6,
            y=0.9,
            confidence=0.8,
            clickability=0.15,
        ),
        auto_play.StateVerification(
            status='unchanged',
            reason='No screen change after repeated taps.',
            attempts=3,
            threshold=0.995,
            similarities=[1.0, 1.0, 1.0],
            progress_threshold=0.985,
            progress_similarities=[1.0, 1.0, 1.0],
            progress_region='lower_progress_region',
        ),
    )

    text = strategy.read_text()
    ineffective = auto_play.extract_section(text, 'Ineffective Buttons')
    assert '- 右侧道路' not in ineffective
    assert 'pick the brighter route' in text
    assert 'Strategy Improvements Needed' not in text


def test_no_change_learning_does_not_mark_preferred_action_ineffective(
    tmp_path, monkeypatch
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    strategy = tmp_path / 'games' / 'tower' / 'strategy.md'
    strategy.parent.mkdir(parents=True)
    strategy.write_text(
        """# Auto Play Strategy: Tower

## Preferred Buttons
- 开始冒险

## Avoid Buttons
- 放弃冒险

## Ineffective Buttons
None yet.

## Decision Rules
- Keep fighting.
"""
    )

    auto_play.append_no_change_learning(
        'Tower',
        auto_play.ButtonCandidate(
            label='开始冒险',
            x=0.5,
            y=0.8,
            confidence=0.99,
            clickability=1.0,
            source='template',
        ),
        auto_play.StateVerification(
            status='unchanged',
            reason='No screen change after repeated taps.',
            attempts=3,
            threshold=0.995,
            similarities=[1.0, 1.0, 1.0],
            progress_threshold=0.985,
            progress_similarities=[1.0, 1.0, 1.0],
            progress_region='full',
        ),
    )

    ineffective = auto_play.extract_section(strategy.read_text(), 'Ineffective Buttons')
    assert '- 开始冒险' not in ineffective


def test_no_change_learning_does_not_mark_end_ineffective(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    strategy = tmp_path / 'games' / 'tower' / 'strategy.md'
    strategy.parent.mkdir(parents=True)
    strategy.write_text(auto_play.default_strategy_markdown('Tower'))

    auto_play.append_no_change_learning(
        'Tower',
        auto_play.ButtonCandidate(
            label='End',
            x=0.5,
            y=0.9,
            confidence=1.0,
            clickability=1.8,
            source='ocr',
        ),
        auto_play.StateVerification(
            status='unchanged',
            reason='No screen change after repeated taps.',
            attempts=3,
            threshold=0.995,
            similarities=[1.0, 1.0, 1.0],
            progress_threshold=0.985,
            progress_similarities=[1.0, 1.0, 1.0],
            progress_region='lower_progress_region',
        ),
    )

    ineffective = auto_play.extract_section(strategy.read_text(), 'Ineffective Buttons')
    assert '- End' not in ineffective


def test_no_change_learning_can_mark_high_confidence_custom_action_ineffective(
    tmp_path, monkeypatch
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    strategy = tmp_path / 'games' / 'tower' / 'strategy.md'
    strategy.parent.mkdir(parents=True)
    strategy.write_text(auto_play.default_strategy_markdown('Tower'))

    auto_play.append_no_change_learning(
        'Tower',
        auto_play.ButtonCandidate(
            label='神秘按钮',
            x=0.4,
            y=0.7,
            confidence=0.97,
            clickability=0.9,
            source='template',
        ),
        auto_play.StateVerification(
            status='unchanged',
            reason='No screen change after repeated taps.',
            attempts=3,
            threshold=0.995,
            similarities=[1.0, 1.0, 1.0],
            progress_threshold=0.985,
            progress_similarities=[1.0, 1.0, 1.0],
            progress_region='full',
        ),
    )

    ineffective = auto_play.extract_section(strategy.read_text(), 'Ineffective Buttons')
    assert '- 神秘按钮' in ineffective
    assert 'Strategy Improvements Needed' not in strategy.read_text()


def test_unblock_learning_updates_decision_rules_without_backlog_section(
    tmp_path, monkeypatch
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    strategy = tmp_path / 'games' / 'tower' / 'strategy.md'
    strategy.parent.mkdir(parents=True)
    strategy.write_text(auto_play.default_strategy_markdown('Tower'))

    changed = auto_play.append_unblock_learning(
        'Tower',
        auto_play.UnblockAssessment(
            status='stuck',
            reason='Screenshots stayed similar.',
            window_size=5,
            threshold=0.975,
            similarities=[0.99, 0.99, 0.99, 0.99],
            turn_dirs=['one', 'five'],
            repeated_actions=['CM'],
        ),
    )

    text = strategy.read_text()
    assert changed
    assert 'temporarily deprioritize repeated actions' in text
    assert 'Strategy Improvements Needed' not in text


def test_item_preference_scores_permanent_and_per_battle_growth_highest():
    auto_play = load_auto_play_module()

    permanent_stat_score, permanent_stat_reasons = auto_play.item_preference_score(
        'Royal Training',
        'Permanent attack +1',
    )
    battle_coin_score, battle_coin_reasons = auto_play.item_preference_score(
        'Toll Collector',
        'Gain coins every battle',
    )
    temporary_score, temporary_reasons = auto_play.item_preference_score(
        'Quick Spark',
        'Temporary damage increase this battle, cost HP',
    )

    assert permanent_stat_score > temporary_score
    assert battle_coin_score > temporary_score
    assert 'permanent stat priority' in permanent_stat_reasons
    assert 'per-battle growth priority' in battle_coin_reasons
    assert 'temporary-only effect' in temporary_reasons


def test_item_preference_penalizes_self_sacrifice_card_names():
    auto_play = load_auto_play_module()

    sacrifice_score, sacrifice_reasons = auto_play.item_preference_score(
        '舍命一击',
        'Abandon',
    )
    neutral_score, _neutral_reasons = auto_play.item_preference_score(
        '闪耀挥击',
        'Abandon',
    )

    assert sacrifice_score < neutral_score
    assert 'self-sacrifice cue' in sacrifice_reasons


def test_item_preference_does_not_penalize_crystal_currency_costs():
    auto_play = load_auto_play_module()

    crystal_shop_score, crystal_shop_reasons = auto_play.item_preference_score(
        '水晶商店宝物',
        '消耗水晶 8；永久攻击 +2',
    )
    hp_cost_score, hp_cost_reasons = auto_play.item_preference_score(
        '血祭宝物',
        '消耗生命 8；永久攻击 +2',
    )

    assert crystal_shop_score > hp_cost_score
    assert 'currency cost ignored' in crystal_shop_reasons
    assert 'cost or loss' not in crystal_shop_reasons
    assert 'cost or loss' in hp_cost_reasons


def test_tower_does_not_blindly_inspect_generic_item_labels(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    best_item = auto_play.ButtonCandidate(
        label='Royal Training',
        x=0.25,
        y=0.45,
        confidence=0.8,
        clickability=0.7,
        source='ocr',
        score=1.08,
    )
    weak_item = auto_play.ButtonCandidate(
        label='Quick Spark',
        x=0.75,
        y=0.45,
        confidence=0.8,
        clickability=0.7,
        source='ocr',
        score=1.08,
    )
    confirm = auto_play.ButtonCandidate(
        label='Confirm',
        x=0.5,
        y=0.9,
        confidence=0.9,
        clickability=0.8,
        source='ocr',
        score=2.22,
    )
    buttons = [best_item, weak_item, confirm]
    clicks: list[str] = []

    def fake_click(_args, button):
        clicks.append(button.label)

    def fake_load_image(_args):
        return Image.new('RGB', (100, 100), color='black'), {}

    def fake_analyze_buttons(_image, *, confidence, game, template_match_threshold):
        label = clicks[-1]
        description = {
            'Royal Training': 'Permanent attack +1',
            'Quick Spark': 'Temporary damage increase this battle, cost HP',
        }[label]
        return [
            auto_play.ButtonCandidate(
                label=description,
                x=0.5,
                y=0.3,
                confidence=0.9,
                clickability=0.1,
                source='ocr',
            )
        ]

    monkeypatch.setattr(auto_play, 'click_button', fake_click)
    monkeypatch.setattr(auto_play, 'load_image', fake_load_image)
    monkeypatch.setattr(auto_play, 'analyze_buttons', fake_analyze_buttons)

    args = SimpleNamespace(
        image=None,
        click_recommended=True,
        item_inspection_limit=4,
        item_inspection_interval=0.0,
        item_description_label_limit=12,
        confidence=0.8,
        game='Tower',
        template_match_threshold=0.82,
    )
    turn_dir = tmp_path / 'turn'
    artifact_paths = {
        'item_inspections': turn_dir / 'item_inspections.yaml',
        'item_inspection_dir': turn_dir / 'item_inspections',
    }

    inspections, decision = auto_play.inspect_item_choices(
        args,
        buttons=buttons,
        memory={'fallback': [], 'avoid': [], 'ineffective': []},
        artifact_paths=artifact_paths,
    )

    assert clicks == []
    assert inspections == []
    assert decision is None
    assert not artifact_paths['item_inspections'].exists()


def test_tower_low_hp_pouch_prefers_healing_consumable(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    clicks: list[str] = []
    monkeypatch.setattr(
        auto_play,
        'click_button',
        lambda _args, button: clicks.append(button.label),
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
            score=2.0,
        )
        for label, x, y in (
            ('道具口袋', 0.5, 0.48),
            ('深澜龙血', 0.2, 0.64),
            ('迅捷药水', 0.5, 0.64),
            ('恢复10%生命上限的生命，消耗品', 0.5, 0.84),
            ('返回', 0.28, 0.94),
            ('确定', 0.72, 0.94),
        )
    ]
    args = SimpleNamespace(
        image=None,
        click_recommended=True,
        game='tower',
        item_inspection_interval=0.0,
    )

    inspections, decision = auto_play.inspect_item_choices(
        args,
        buttons=buttons,
        memory={'fallback': [], 'avoid': [], 'ineffective': []},
        artifact_paths={
            'item_inspections': tmp_path / 'item_inspections.yaml',
            'item_inspection_dir': tmp_path / 'item_inspections',
        },
    )

    assert inspections == []
    assert clicks == ['深澜龙血']
    assert decision is not None
    assert decision.recommended.label == '确定'


def test_tower_pouch_prefers_real_healing_before_giant_potion(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    clicks: list[str] = []
    monkeypatch.setattr(
        auto_play,
        'click_button',
        lambda _args, button: clicks.append(button.label),
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
            score=2.0,
        )
        for label, x, y in (
            ('道具口袋', 0.5, 0.48),
            ('深澜龙血', 0.2, 0.64),
            ('巨人药水', 0.5, 0.64),
            ('返回', 0.28, 0.94),
            ('确定', 0.72, 0.94),
        )
    ]
    args = SimpleNamespace(
        image=None,
        click_recommended=True,
        game='tower',
        item_inspection_interval=0.0,
    )

    _inspections, decision = auto_play.inspect_item_choices(
        args,
        buttons=buttons,
        memory={'fallback': [], 'avoid': [], 'ineffective': []},
        artifact_paths={
            'item_inspections': tmp_path / 'item_inspections.yaml',
            'item_inspection_dir': tmp_path / 'item_inspections',
        },
    )

    assert clicks == ['深澜龙血']
    assert decision is not None
    assert decision.recommended.label == '确定'


def test_replace_adventure_confirmation_is_not_item_inspected(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()

    buttons = [
        auto_play.ButtonCandidate(
            label='Replace Old Adventure and Enter Tower?',
            x=0.5,
            y=0.5,
            confidence=0.98,
            clickability=1.7,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='Cancel',
            x=0.3,
            y=0.6,
            confidence=1.0,
            clickability=1.8,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='OK',
            x=0.69,
            y=0.6,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
    ]

    def fail_click(_args, button):
        raise AssertionError(f'Unexpected item inspection click: {button.label}')

    monkeypatch.setattr(auto_play, 'click_button', fail_click)

    args = SimpleNamespace(
        image=None,
        click_recommended=True,
        game='Tower',
    )
    artifact_paths = {
        'item_inspections': tmp_path / 'item_inspections.yaml',
        'item_inspection_dir': tmp_path / 'item_inspections',
    }

    inspections, decision = auto_play.inspect_item_choices(
        args,
        buttons=buttons,
        memory={'fallback': [], 'avoid': [], 'ineffective': []},
        artifact_paths=artifact_paths,
    )

    assert inspections == []
    assert decision is None
    assert not artifact_paths['item_inspections'].exists()


def test_result_screen_does_not_trigger_item_inspection(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    write_game_strategy(tmp_path, 'survivor')

    clicks: list[str] = []

    def fake_click(_args, button):
        clicks.append(button.label)

    monkeypatch.setattr(auto_play, 'click_button', fake_click)

    args = SimpleNamespace(
        image=None,
        click_recommended=True,
        item_inspection_limit=4,
        item_inspection_interval=0.0,
        item_description_label_limit=12,
        confidence=0.8,
        game='survivor',
        template_match_threshold=0.82,
    )
    turn_dir = tmp_path / 'turn'
    artifact_paths = {
        'item_inspections': turn_dir / 'item_inspections.yaml',
        'item_inspection_dir': turn_dir / 'item_inspections',
    }
    buttons = [
        auto_play.ButtonCandidate(
            label='Victory',
            x=0.5,
            y=0.23,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
            score=-0.2,
        ),
        auto_play.ButtonCandidate(
            label='Best:05:00',
            x=0.5,
            y=0.39,
            confidence=1.0,
            clickability=1.9,
            source='ocr',
            score=1.8,
        ),
        auto_play.ButtonCandidate(
            label='Chapter 314',
            x=0.5,
            y=0.36,
            confidence=0.96,
            clickability=1.5,
            source='ocr',
            score=1.6,
        ),
        auto_play.ButtonCandidate(
            label='Confirm',
            x=0.5,
            y=0.81,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
            score=7.8,
        ),
    ]

    inspections, decision = auto_play.inspect_item_choices(
        args,
        buttons=buttons,
        memory={'fallback': [], 'avoid': [], 'ineffective': []},
        artifact_paths=artifact_paths,
    )

    assert inspections == []
    assert decision is None
    assert clicks == []
    assert not artifact_paths['item_inspections'].exists()


def test_game_info_marks_card_like_choices_as_skills(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    turn = tmp_path / 'games' / 'tower' / 'turns' / 'turn-001'
    turn.mkdir(parents=True)
    (turn / 'item_inspections.yaml').write_text(
        """
items:
  - candidate:
      label: Battle Focus Card
    description: Gain attack every battle
    item_score: 18.0
    reasons:
      - scales per battle
      - per-battle growth priority
    screenshot: item_inspections/01-card.png
  - candidate:
      label: Quick Potion
    description: Temporary damage this battle
    item_score: -1.0
    reasons:
      - temporary-only effect
    screenshot: item_inspections/02-potion.png
"""
    )

    path = auto_play.write_game_info_markdown('Tower')
    knowledge = path.read_text()

    assert '### skill' in knowledge
    assert '| 1 | Battle Focus Card | 18.00 |' in knowledge
    assert '### item' in knowledge
    assert '| 1 | Quick Potion | -1.00 |' in knowledge


def test_game_info_groups_by_type_and_sorts_each_group_by_score(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    turn = tmp_path / 'games' / 'tower' / 'turns' / 'turn-001'
    turn.mkdir(parents=True)
    (turn / 'llm.yaml').write_text(
        """
summary: Several durable choices are visible.
game_info:
  - name: 小宝物
    type: treasure
    description: 本次战斗伤害+1
  - name: 大宝物
    type: treasure
    description: 永久攻击+5；每场战斗获得金币
  - name: 战斗技能
    type: skill
    description: 获得5层专注
  - name: 普通武器
    type: weapon
    description: 对敌方使用2张普击II
"""
    )

    path = auto_play.write_game_info_markdown('Tower')
    knowledge = path.read_text()

    assert knowledge.index('### skill') < knowledge.index('### treasure')
    assert knowledge.index('### treasure') < knowledge.index('### weapon')
    treasure_section = knowledge[
        knowledge.index('### treasure') : knowledge.index('### weapon')
    ]
    assert treasure_section.index('大宝物') < treasure_section.index('小宝物')
    assert '| 1 | 大宝物 |' in treasure_section
    assert '| 2 | 小宝物 |' in treasure_section


def test_game_info_captures_explicit_original_text_and_ignores_ocr_observations(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    turn = tmp_path / 'games' / 'tower' / 'turns' / 'turn-001'
    turn.mkdir(parents=True)
    (turn / 'llm.yaml').write_text(
        """
summary: Treasure detail screen.
game_info:
  - name: 赤铁巨斧 IV
    type: treasure
    description: 物攻+5；暴击+4
buttons:
  - label: Activate Treasure
    x: 0.5
    y: 0.93
"""
    )
    (turn / 'ocr.yaml').write_text(
        """
ocr_buttons:
  - label: '+5'
    confidence: 0.95
  - label: '+4'
    confidence: 0.94
  - label: Back
    confidence: 0.9
  - label: 1-1
    confidence: 0.8
"""
    )

    path = auto_play.write_game_info_markdown('Tower')
    knowledge = path.read_text()

    assert '赤铁巨斧 IV' in knowledge
    assert '物攻+5；暴击+4' in knowledge
    assert 'Physical attack' not in knowledge
    assert 'llm game_info' in knowledge
    assert 'OCR detail: +5' not in knowledge
    assert '+5; +4' not in knowledge
    assert 'ocr observation' not in knowledge
    assert 'Back' not in knowledge
    assert '1-1' not in knowledge


def test_game_info_prefers_original_game_name_and_description(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    turn = tmp_path / 'games' / 'tower' / 'turns' / 'turn-001'
    turn.mkdir(parents=True)
    (turn / 'llm.yaml').write_text(
        """
summary: Treasure detail screen.
objects:
  - label: Treasure detail
    original_name: 赤铁巨斧 IV
    description: Physical attack +5 and crit +4.
    original_description: 物理攻击 +5；暴击 +4
    x: 0.5
    y: 0.4
buttons: []
"""
    )

    path = auto_play.write_game_info_markdown('Tower')
    knowledge = path.read_text()

    assert '赤铁巨斧 IV' in knowledge
    assert '物理攻击 +5；暴击 +4' in knowledge
    assert 'Physical attack +5 and crit +4.' not in knowledge
    assert '| 1 | Treasure detail |' not in knowledge


def test_game_info_ignores_translated_object_description_without_original_text(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    turn = tmp_path / 'games' / 'tower' / 'turns' / 'turn-001'
    turn.mkdir(parents=True)
    (turn / 'llm.yaml').write_text(
        """
summary: Treasure detail screen.
objects:
  - label: Red Iron Axe IV
    description: Physical attack +5 and crit +4.
    x: 0.5
    y: 0.4
buttons: []
"""
    )

    path = auto_play.write_game_info_markdown('Tower')
    knowledge = path.read_text()

    assert 'No captured skill or item descriptions yet.' in knowledge
    assert 'Physical attack +5 and crit +4.' not in knowledge


def test_game_info_uses_explicit_game_info_pairs_and_ignores_ui_objects(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    turn = tmp_path / 'games' / 'tower' / 'turns' / 'turn-001'
    turn.mkdir(parents=True)
    (turn / 'llm.yaml').write_text(
        """
summary: Treasure detail screen.
game_info:
  - name: 骑士之翼
    type: treasure
    description: 生命减少时：获得2层专注
objects:
  - label: Adventurer avatar
    description: Round portrait button at the lower-left status panel.
  - label: Treasure detail
    description: 骑士之翼 treasure detail is open.
buttons: []
"""
    )

    path = auto_play.write_game_info_markdown('Tower')
    knowledge = path.read_text()

    assert '### treasure' in knowledge
    assert '| 1 | 骑士之翼 |' in knowledge
    assert '生命减少时：获得2层专注' in knowledge
    assert 'Adventurer avatar' not in knowledge
    assert '| 1 | Treasure detail |' not in knowledge


def test_game_info_recovers_original_text_from_malformed_llm_yaml(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)

    turn = tmp_path / 'games' / 'tower' / 'turns' / 'turn-001'
    turn.mkdir(parents=True)
    (turn / 'llm.yaml').write_text(
        """
summary: Treasure detail screen: the capture has an unquoted colon.
objects:
  - label: Treasure detail
    original_name: 赤铁巨斧 IV
    original_description: 物攻+5：暴击+4
    x: 0.5
    y: 0.4
buttons:
  - label: Activate Treasure
    x: 0.5
    y: 0.93
"""
    )

    path = auto_play.write_game_info_markdown('Tower')
    knowledge = path.read_text()

    assert '赤铁巨斧 IV' in knowledge
    assert '物攻+5：暴击+4' in knowledge
    assert 'Red Iron Axe IV' not in knowledge
    assert '| 1 | Treasure detail |' not in knowledge


def test_tower_stair_choice_avoids_side_with_elite_enemy():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='选择一个楼梯',
            x=0.5,
            y=0.3,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='左侧楼梯',
            x=0.25,
            y=0.39,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='右侧楼梯',
            x=0.75,
            y=0.39,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='精英怪',
            x=0.23,
            y=0.44,
            confidence=1.0,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='确定',
            x=0.73,
            y=0.71,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
    ]

    choice = auto_play.tower_stair_choice_candidate(config, buttons)

    assert choice is not None
    assert choice.label == '右侧楼梯'


def test_tower_stair_choice_takes_task_even_when_guarded_by_elite():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        )
        for label, x, y in (
            ('选择一个楼梯', 0.5, 0.3),
            ('左侧楼梯', 0.25, 0.39),
            ('右侧楼梯', 0.75, 0.39),
            ('普通怪', 0.23, 0.44),
            ('精英怪', 0.73, 0.44),
            ('任务', 0.73, 0.51),
            ('确定', 0.73, 0.71),
        )
    ]

    choice = auto_play.tower_stair_choice_candidate(config, buttons)

    assert choice is not None
    assert choice.label == '右侧楼梯'


def test_tower_giant_warrior_sets_up_attack_gem_and_bear_hand_first(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '战士')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'profession': '战士',
            'predecessor_treasure': '巨人之拳',
            'key_treasures': ['魔法熊手'],
        },
    )

    attack_gem = auto_play.tower_combat_sequence_bonus('tower', '攻击宝石')
    swift = auto_play.tower_combat_sequence_bonus('tower', '迅捷')
    sacred = auto_play.tower_combat_sequence_bonus('tower', '神圣斩击')

    assert attack_gem > swift > sacred
    assert not auto_play.is_direct_attack_combat_card_label('攻击宝石')


def test_tower_warrior_plays_engine_and_draw_cards_before_plain_attacks(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '战士')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'profession': '战士',
            'predecessor_treasure': '骑士狼牙棒',
        },
    )

    attack_gem = auto_play.tower_combat_sequence_bonus('tower', '攻击宝石！')
    swift_attack = auto_play.tower_combat_sequence_bonus('tower', '迅捷攻击！')
    guarded_draw = auto_play.tower_combat_sequence_bonus('tower', '守势')
    plain_attack = auto_play.tower_combat_sequence_bonus('tower', '普通攻击')

    assert attack_gem > swift_attack > guarded_draw > plain_attack


def test_tower_mage_does_not_play_electrolysis_without_cold_source(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '法师')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'profession': '法师',
            'core_cards': ['Tower card choice: 电解冰！', '快速思考'],
        },
    )

    assert auto_play.tower_combat_sequence_bonus('tower', '电解冰') < 0


def test_tower_mage_plays_cold_source_before_electrolysis(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '法师')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'profession': '法师',
            'core_cards': ['Tower card choice: 寒流', 'Tower card choice: 电解冰'],
        },
    )

    assert auto_play.tower_combat_sequence_bonus('tower', '寒流') > (
        auto_play.tower_combat_sequence_bonus('tower', '电解冰')
    )


def test_tower_mage_tracks_cold_before_allowing_electrolysis(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: deep-run\n'
        'stage: 深渊楼梯\n'
        'phase: combat\n'
        'profession: 法师\n'
        'battle:\n'
        '  battle_id: deep-run-b001\n'
    )
    image = Image.new('RGB', (360, 800), color='black')

    assert auto_play.tower_combat_sequence_bonus('tower', '电解冰') < 0

    auto_play.update_tower_run_state(
        'tower',
        image,
        [],
        clicked_label='Visible playable card: 寒冰盾',
        action_succeeded=True,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['battle']['cold_applied'] is True
    assert auto_play.tower_combat_sequence_bonus('tower', '电解冰') > 0

    auto_play.update_tower_run_state(
        'tower',
        image,
        [],
        clicked_label='Visible playable card: 电解冰',
        action_succeeded=True,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['battle']['cold_applied'] is False


def test_tower_electrolysis_build_requires_per_action_local_ocr(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: deep-run\n'
        'stage: 深渊楼梯\n'
        'phase: combat\n'
        'profession: 法师\n'
        'core_cards:\n'
        '  - "Tower card choice: 电解冰"\n'
    )

    assert auto_play.tower_battle_requires_precise_read('tower') is True


def test_tower_quick_thinking_build_requires_per_action_local_ocr(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: deep-run\n'
        'stage: 深渊楼梯\n'
        'phase: combat\n'
        'profession: 法师\n'
        'core_cards:\n'
        '  - "Tower card choice: 快速思考"\n'
    )

    assert auto_play.tower_battle_requires_precise_read('tower') is True


def test_tower_manufacture_core_and_boss_floor_require_precise_reads(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: robot-run\n'
        'floor: 7\n'
        'battle:\n'
        '  initial_hand:\n'
        '    - 制造核心Ⅲ\n'
    )

    assert auto_play.tower_battle_requires_precise_read('tower') is True

    state_path.write_text('run_id: boss-run\nfloor: 20\n')

    assert auto_play.tower_battle_requires_precise_read('tower') is True


def test_tower_seen_manufacture_core_persists_precise_reads(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: robot-run\n'
        'stage: 深渊楼梯\n'
        'floor: 22\n'
        'battle:\n'
        '  initial_hand:\n'
        '    - 普通攻击\n'
    )
    image = Image.new('RGB', (360, 800), color='black')
    buttons = [
        auto_play.ButtonCandidate(
            label='制造核心Ⅱ',
            x=0.2,
            y=0.63,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
    ]

    auto_play.update_tower_run_state('tower', image, buttons)

    state = auto_play.load_tower_run_state('tower')
    assert state['timing_sensitive_cards_seen'] == ['制造核心Ⅱ']
    assert auto_play.tower_battle_requires_precise_read('tower') is True


def test_tower_warrior_orders_setup_before_attacks_and_mana_sink(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '战士')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'profession': '战士',
            'predecessor_treasure': '骑士狼牙棒',
            'floor': 20,
        },
    )

    attack_gem = auto_play.tower_combat_sequence_bonus('tower', '攻击宝石')
    weakness = auto_play.tower_combat_sequence_bonus('tower', '发现弱点')
    guard = auto_play.tower_combat_sequence_bonus('tower', '守势')
    attack = auto_play.tower_combat_sequence_bonus('tower', '迅捷攻击')
    mana_sink = auto_play.tower_combat_sequence_bonus('tower', '制造核心')

    assert attack_gem > weakness > guard > attack > mana_sink


def test_tower_giant_warrior_uses_attack_before_manufacture_core(monkeypatch):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '战士')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'stage': '深渊楼梯',
            'profession': '战士',
            'predecessor_treasure': '巨人之拳',
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=0.53,
            confidence=0.96,
            clickability=7.4,
            source='vision',
        )
        for label, x in (
            ('Visible playable card: 制造核心', 0.20),
            ('Visible playable card: 全力一击', 0.49),
        )
    ]
    buttons.append(
        auto_play.ButtonCandidate(
            label='结束第1回合',
            x=0.50,
            y=0.92,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        )
    )

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == 'Visible playable card: 全力一击'
    core = next(button for button in scored if '制造核心' in button.label)
    assert core.score < scored[0].score


def test_tower_manufacture_core_is_played_when_it_is_only_card(monkeypatch):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '战士')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'stage': '深渊楼梯',
            'profession': '战士',
            'predecessor_treasure': '巨人之拳',
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='Visible playable card: 制造核心',
            x=0.20,
            y=0.53,
            confidence=0.96,
            clickability=7.4,
            source='vision',
        ),
        auto_play.ButtonCandidate(
            label='结束第1回合',
            x=0.50,
            y=0.92,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='制造核心',
            x=0.20,
            y=0.64,
            confidence=0.99,
            clickability=1.7,
            source='ocr',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == 'Visible playable card: 制造核心'


def test_tower_manufacture_core_ocr_fallback_is_played_when_it_is_only_card(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '战士')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'stage': '深渊楼梯',
            'profession': '战士',
            'predecessor_treasure': '巨人之拳',
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='结束第2回合',
            x=0.50,
            y=0.92,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='制造核心训',
            x=0.20,
            y=0.635,
            confidence=0.86,
            clickability=1.65,
            source='ocr',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '制造核心训'


def test_tower_weakness_strike_becomes_finisher_after_setup(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '战士')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'profession': '战士',
            'predecessor_treasure': '骑士狼牙棒',
            'battle': {'weakness_applied': True},
        },
    )

    assert auto_play.tower_combat_sequence_bonus(
        'tower',
        '弱点打击Ⅱ',
    ) > auto_play.tower_combat_sequence_bonus('tower', '胜势')


def test_tower_low_score_combat_action_does_not_request_llm(monkeypatch):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'phase': 'combat'},
    )
    end_turn = auto_play.ButtonCandidate(
        label='结束第4回合',
        x=0.5,
        y=0.92,
        confidence=0.99,
        clickability=2.0,
        source='ocr',
        score=0.2,
    )

    decision = auto_play.decide_next_move(
        [end_turn],
        min_action_score=0.95,
        ambiguity_margin=0.2,
        ask_on_ambiguous=False,
        automation_config=config,
    )

    assert decision.status == 'ready'
    assert decision.recommended == end_turn


def test_tower_mage_plays_quick_thinking_before_setup_cards(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '法师')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'profession': '法师',
            'predecessor_treasure': '电虫药水',
            'core_cards': [
                'Tower card choice: 快速思考',
                'Tower card choice: 寒冷宝石',
            ],
        },
    )

    assert auto_play.tower_combat_sequence_bonus('tower', '快速思考') > (
        auto_play.tower_combat_sequence_bonus('tower', '寒冷宝石')
    )


def test_tower_mage_plays_cold_shield_before_lightning_dragon(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '法师')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'profession': '法师',
            'predecessor_treasure': '电虫药水',
            'core_cards': ['Tower card choice: 寒冰盾'],
        },
    )

    assert auto_play.tower_combat_sequence_bonus('tower', '寒冰盾') > (
        auto_play.tower_combat_sequence_bonus('tower', '雷龙')
    )


def test_tower_card_reward_prefers_short_cycle_draw_card():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='选一张卡牌学习',
            x=0.5,
            y=0.31,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='虔诚I',
            x=0.17,
            y=0.48,
            confidence=0.9,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='以物易物I',
            x=0.5,
            y=0.48,
            confidence=0.9,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='抽1张牌，被弃置时抽1张牌',
            x=0.5,
            y=0.59,
            confidence=0.9,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='毒龙弹I',
            x=0.83,
            y=0.48,
            confidence=0.9,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='确定',
            x=0.73,
            y=0.70,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.x == 0.5
    assert '以物易物I' in choice.label


def test_tower_fire_mage_uses_three_card_speed_clear_recipe(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'predecessor_treasure': '火焰草莓'},
    )

    priorities = dict(auto_play.tower_card_reward_priority_rules('tower', '法师'))

    assert priorities == {
        '燃烧晶石': 40.0,
        '太阳盾': 39.0,
        '火焰打击': 38.0,
    }


def test_tower_yolan_warrior_keeps_sacred_slash_as_growth_bridge(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '战士')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'profession': '战士',
            'phase': 'card_reward',
            'predecessor_treasure': '曜蓝水晶',
            'core_cards': [],
        },
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('神圣斩击！', 0.2, 0.48),
            ('启动防守！', 0.5, 0.48),
            ('撞击！', 0.8, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert '神圣斩击' in choice.label
    assert choice.x == 0.17


def test_tower_yolan_warrior_keeps_swiftness_for_draw_engine(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'predecessor_treasure': '曜蓝水晶',
            'floor': 3,
            'core_cards': [],
        },
    )

    priorities = dict(auto_play.tower_card_reward_priority_rules('tower', '战士'))

    assert priorities['迅捷'] > priorities['神圣斩击']
    assert priorities['未来汽水'] > priorities['巨人协议']


def test_tower_mage_reward_takes_energy_flying_lightning(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'stage': '深渊楼梯',
            'profession': '法师',
            'phase': 'card_reward',
        },
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('雷电回响！', 0.17, 0.48),
            ('能量飞电', 0.5, 0.48),
            ('能量飞弹', 0.83, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.label == 'Tower card choice: 能量飞电'


def test_tower_electric_potion_mage_takes_cold_current(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'stage': '深渊楼梯',
            'profession': '法师',
            'phase': 'card_reward',
            'predecessor_treasure': '电虫药水',
        },
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('充能', 0.17, 0.48),
            ('寒流', 0.5, 0.48),
            ('雷电飞弹', 0.83, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.label == 'Tower card choice: 寒流'


def test_tower_early_electric_mage_takes_bridge_damage_over_abandon(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'stage': '深渊楼梯',
            'floor': 3,
            'profession': '法师',
            'phase': 'card_reward',
            'predecessor_treasure': '电虫药水',
            'core_cards': ['Tower card choice: 寒冰盾'],
        },
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('法术手杖', 0.17, 0.48),
            ('火焰飞弹', 0.5, 0.48),
            ('冷静', 0.83, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.label == 'Tower card choice: 法术手杖'


def test_tower_electric_potion_mage_prefers_current_core_recipe(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'stage': '深渊楼梯',
            'profession': '法师',
            'phase': 'card_reward',
            'predecessor_treasure': '电虫药水',
        },
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('寒冷晶石', 0.17, 0.48),
            ('雷龙', 0.5, 0.48),
            ('寒冰盾', 0.83, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.label == 'Tower card choice: 寒冷晶石'


def test_tower_mage_reward_takes_cold_shield_to_enable_electrolysis(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'stage': '深渊楼梯',
            'profession': '法师',
            'phase': 'card_reward',
            'core_cards': ['Tower card choice: 电解冰'],
        },
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('寒冰盾', 0.17, 0.48),
            ('能量倾泻', 0.5, 0.48),
            ('闪电', 0.83, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.label == 'Tower card choice: 寒冰盾'


def test_tower_mage_reward_takes_instant_gem_instead_of_abandoning(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'stage': '深渊楼梯',
            'profession': '法师',
            'phase': 'card_reward',
        },
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('瞬发宝石', 0.17, 0.48),
            ('智慧之岩！', 0.5, 0.48),
            ('超越宝石！', 0.83, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.label == 'Tower card choice: 瞬发宝石'


def test_tower_warrior_defaults_to_infinite_vulnerability_recipe(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'predecessor_treasure': '燃烧辣椒'},
    )

    priorities = dict(auto_play.tower_card_reward_priority_rules('tower', '战士'))

    assert priorities['宝石手套'] > priorities['超时空宝石']
    assert priorities['迅捷'] > priorities['发现弱点']
    assert priorities['发现弱点'] > priorities['弱点打击']
    assert '换血' not in priorities


def test_tower_giant_warrior_keeps_infinite_attack_as_growth_bridge(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'predecessor_treasure': '巨人之拳',
            'floor': 6,
            'core_cards': [],
        },
    )

    priorities = dict(auto_play.tower_card_reward_priority_rules('tower', '战士'))

    assert priorities['无限攻击'] > 14.0


def test_tower_giant_warrior_shop_buys_synergy_not_unused_dragon_egg(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: giant-run\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 6\n'
        'profession: 战士\n'
        'predecessor_treasure: 巨人之拳\n'
        'core_cards: []\n'
        'key_treasures: [巨人之拳]\n'
    )

    dwarf_gem = auto_play.tower_shop_purchase_profile('tower', '矮人王宝石')
    giant_mask = auto_play.tower_shop_purchase_profile('tower', '巨人面罩I')
    dragon_egg = auto_play.tower_shop_purchase_profile('tower', '幻龙蛋')
    swift_potion = auto_play.tower_shop_purchase_profile('tower', '迅捷药水')
    fire_potion = auto_play.tower_shop_purchase_profile('tower', '火焰药水')
    giant_potion = auto_play.tower_shop_purchase_profile('tower', '巨人药水')
    healing_potion = auto_play.tower_shop_purchase_profile('tower', '恢复药水')
    lucky_coin = auto_play.tower_shop_purchase_profile('tower', '幸运币')
    ocr_lucky_coin = auto_play.tower_shop_purchase_profile('tower', '率运币')

    assert dwarf_gem == (42.0, 'treasure')
    assert giant_mask == (35.0, 'treasure')
    assert dragon_egg == (0.0, '')
    assert swift_potion == (34.0, 'consumable')
    assert fire_potion == (0.0, '')
    assert giant_potion == (22.0, 'consumable')
    assert healing_potion == (40.0, 'consumable')
    assert lucky_coin == (43.0, 'consumable')
    assert ocr_lucky_coin == (43.0, 'consumable')


def test_tower_plays_profit_consumable_before_plain_attack(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '战士')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'profession': '战士'},
    )

    lucky_coin = auto_play.tower_combat_sequence_bonus('tower', '幸运币')
    ocr_lucky_coin = auto_play.tower_combat_sequence_bonus('tower', '率运币')
    attack = auto_play.tower_combat_sequence_bonus('tower', '普通攻击')

    assert lucky_coin > attack
    assert ocr_lucky_coin == lucky_coin


def test_tower_shop_refreshes_twice_then_returns(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: giant-run\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 6\n'
        'profession: 战士\n'
        'predecessor_treasure: 巨人之拳\n'
        'last_room_action: 水晶商店\n'
        'shop_refresh_count: 0\n'
        'policy:\n'
        '  shop_refresh_limit: 2\n'
    )
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-15', 'phase': 'abyss'},
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('水晶商店', 0.5, 0.34),
            ('血虎 牙刀I', 0.5, 0.68),
            ('免费1次', 0.12, 0.27),
            ('刷新0', 0.12, 0.31),
            ('返回', 0.27, 0.88),
        )
    ]

    first = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert first is not None
    assert first[0].label == '免费1次'
    assert first[0].x == 0.14
    assert first[0].y == 0.303

    state_path.write_text(
        state_path.read_text().replace(
            'shop_refresh_count: 0',
            'shop_refresh_count: 2',
        )
    )
    finished = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert finished is not None
    assert finished[0].label == '返回'


def test_tower_shop_returns_after_paid_refresh_cannot_progress(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: giant-run\n'
        'stage: 深渊楼梯\n'
        'phase: reward_detail\n'
        'floor: 8\n'
        'profession: 战士\n'
        'active_shop: 神秘商店\n'
        'last_room_action: 神秘商店\n'
        'last_action: 刷新●20\n'
        'last_failed_action: 刷新●20\n'
        'shop_refresh_count: 1\n'
        'policy:\n'
        '  shop_refresh_limit: 2\n'
    )
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-15', 'phase': 'abyss'},
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('神秘商店', 0.5, 0.34),
            ('刷新●20', 0.14, 0.30),
            ('返回', 0.27, 0.88),
        )
    ]

    selected = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selected is not None
    assert selected[0].label == '返回'


def test_tower_does_not_globally_mark_shop_choices_or_refresh_ineffective(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text('stage: 深渊楼梯\nshop_purchases: []\n')
    config = automation_config(auto_play, 'tower')
    verification = auto_play.StateVerification(
        status='unchanged',
        reason='no progress',
        attempts=3,
        threshold=0.995,
        similarities=[0.999, 0.999, 0.999],
        progress_threshold=0.985,
        progress_similarities=[0.999, 0.999, 0.999],
        progress_region='full',
        strategy_updated=False,
    )

    for label in ('巨人药水', '金币哥布林', '刷新●20', '免费1次'):
        button = auto_play.ButtonCandidate(
            label=label,
            x=0.2,
            y=0.5,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        assert not auto_play.should_remember_ineffective_button(
            button,
            verification,
            '',
            config,
        )


def test_tower_shop_confirms_selected_core_before_refresh(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: giant-run\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 20\n'
        'profession: 战士\n'
        'predecessor_treasure: 巨人之拳\n'
        'active_shop: 金币商店\n'
        'last_room_action: 金币商店\n'
        'last_action: 迅捷攻击！\n'
        'shop_refresh_count: 1\n'
        'policy:\n'
        '  shop_refresh_limit: 2\n'
    )
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-15', 'phase': 'abyss'},
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('金币商店', 0.5, 0.34),
            ('刷新10', 0.14, 0.30),
            ('返回', 0.27, 0.88),
            ('确定', 0.72, 0.88),
        )
    ]

    selected = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selected is not None
    assert selected[0].label == '确定'
    assert '禁止刷新' in selected[0].reason


def test_tower_reentering_same_shop_preserves_refresh_count(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: giant-run\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 20\n'
        'shop_refresh_history:\n'
        "  '20:金币商店:0.272:0.689': 2\n"
    )
    shop = auto_play.ButtonCandidate(
        label='金币商店',
        x=0.2722,
        y=0.6894,
        confidence=0.99,
        clickability=1.8,
        source='ocr',
    )

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        [shop],
        clicked_label='金币商店',
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['active_shop_key'] == '20:金币商店'
    assert state['shop_refresh_count'] == 2


def test_tower_shop_panel_recovers_context_after_entering_through_arrow(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: arrow-shop\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 20\n'
        'last_room_action: Visible current room icon\n'
    )
    image = Image.new('RGB', (360, 800), color='black')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('金币商店', 0.50, 0.34),
            ('免费1次', 0.15, 0.28),
            ('返回', 0.27, 0.88),
        )
    ]

    auto_play.update_tower_run_state('tower', image, buttons)

    state = auto_play.load_tower_run_state('tower')
    assert state['last_room_action'] == '金币商店'
    assert state['active_shop'] == '金币商店'
    assert state['active_shop_key'] == '20:金币商店'
    assert state['shop_refresh_count'] == 0


def test_tower_return_marks_inferred_shop_complete(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: arrow-shop\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 20\n'
    )
    image = Image.new('RGB', (360, 800), color='black')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('金币商店', 0.50, 0.34),
            ('免费1次', 0.15, 0.28),
            ('返回', 0.27, 0.88),
        )
    ]

    auto_play.update_tower_run_state(
        'tower',
        image,
        buttons,
        clicked_label='返回',
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['completed_shop_keys'] == ['20:金币商店']
    assert state['last_room_action'] == '金币商店'
    assert 'active_shop' not in state
    assert 'active_shop_key' not in state


def test_tower_shop_refresh_history_merges_coordinate_drift(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'stage: 深渊楼梯\n'
        'floor: 17\n'
        'active_shop: 金币商店\n'
        'shop_refresh_count: 0\n'
        'shop_refresh_history:\n'
        "  '17:金币商店:0.271:0.689': 2\n"
        "  '17:金币商店:0.272:0.688': 2\n"
    )

    state = auto_play.load_tower_run_state('tower')

    assert state['shop_refresh_history'] == {'17:金币商店': 4}
    assert state['active_shop_key'] == '17:金币商店'
    assert state['shop_refresh_count'] == 4


def test_tower_empty_shop_uses_visual_refresh_then_returns(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: giant-run\n'
        'stage: 深渊楼梯\n'
        'active_shop: 神秘商店\n'
        'last_action: 点击空白处关闭\n'
        'shop_refresh_count: 0\n'
        'policy:\n'
        '  shop_refresh_limit: 2\n'
    )
    image = Image.new('RGB', (360, 800), color='black')
    draw = ImageDraw.Draw(image)
    draw.rectangle((15, 672, 160, 740), fill=(40, 180, 200))
    draw.rectangle((198, 672, 345, 740), fill=(220, 170, 40))
    config = automation_config(auto_play, 'tower')

    refresh = auto_play.tower_shop_empty_ocr_exit_candidate(
        config,
        image,
        ['点击空白处关闭'],
    )
    leave = auto_play.tower_shop_empty_ocr_exit_candidate(
        config,
        image,
        ['点击空白处关闭', '刷新商店'],
    )

    assert refresh is not None
    assert refresh.label == '刷新商店'
    assert leave is not None
    assert leave.label == '返回'


def test_tower_shop_purchase_is_recorded_in_its_own_category(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: giant-run\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 6\n'
        'profession: 战士\n'
        'predecessor_treasure: 巨人之拳\n'
        'last_room_action: 水晶商店\n'
        'last_action: 矮人王宝石\n'
        'core_cards: []\n'
        'key_treasures: [巨人之拳]\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='水晶商店',
            x=0.5,
            y=0.34,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
    ]

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        buttons,
        clicked_label='确定',
        action_succeeded=True,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['shop_purchases'] == ['矮人王宝石']
    assert state['key_treasures'] == ['巨人之拳', '矮人王宝石']
    assert state['core_cards'] == []


def test_tower_shop_consumable_does_not_pollute_core_cards(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: giant-run\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 8\n'
        'profession: 战士\n'
        'predecessor_treasure: 巨人之拳\n'
        'active_shop: 神秘商店\n'
        'last_action: 迅捷药水\n'
        'core_cards: [回忆]\n'
        'key_treasures: [巨人之拳]\n'
    )

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        [],
        clicked_label='确定',
        action_succeeded=True,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['shop_purchases'] == ['迅捷药水']
    assert state['core_cards'] == ['回忆']
    assert state['key_treasures'] == ['巨人之拳']


def test_tower_shop_rejects_real_money_products(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nprofession: 战士\n'
    )

    assert auto_play.tower_shop_purchase_bonus('tower', '购买水晶礼包') == 0.0
    assert auto_play.tower_real_money_purchase_prompt_visible(
        ['水晶不足', '￥6', '取消', '确定']
    )


def test_tower_healthy_route_values_crystal_shop_over_plain_rest():
    auto_play = load_auto_play_module()

    assert auto_play.tower_deep_map_room_bonus(
        '水晶商店'
    ) > auto_play.tower_deep_map_room_bonus('休息点')


def test_tower_trainer_prefers_gold_interest_over_saying_goodbye(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: giant-run\n'
        'stage: 深渊楼梯\n'
        'profession: 战士\n'
        'predecessor_treasure: 巨人之拳\n'
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('训练师任务', 0.5, 0.09),
            ('还可以领取2个任务', 0.5, 0.12),
            ('击败2只哥布林', 0.22, 0.57),
            ('和弦', 0.26, 0.60),
            ('选择', 0.82, 0.62),
            ('获得100个金币', 0.22, 0.68),
            ('欢乐时光', 0.29, 0.70),
            ('冒险中进入下一层时，获得10%金币利息', 0.44, 0.73),
            ('选择', 0.82, 0.72),
            ('击败2只哥布林', 0.22, 0.78),
            ('谢幕', 0.26, 0.81),
            ('BOSS的掉落物，数量翻倍', 0.36, 0.84),
            ('选择', 0.82, 0.83),
            ('告别', 0.78, 0.52),
        )
    ]

    bonuses = {
        (button.label, button.y): auto_play.tower_trainer_task_bonus(
            button,
            buttons,
            config,
        )
        for button in buttons
        if button.label in {'选择', '告别'}
    }

    assert bonuses[('选择', 0.72)] > bonuses[('选择', 0.83)]
    assert bonuses[('选择', 0.83)] > bonuses[('选择', 0.62)]
    assert bonuses[('选择', 0.72)] > bonuses[('告别', 0.52)]


def test_tower_trainer_takes_easy_shuffle_gem_cycle_task(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: giant-run\n'
        'stage: 深渊楼梯\n'
        'profession: 战士\n'
        'predecessor_treasure: 巨人之拳\n'
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('训练师任务', 0.5, 0.09),
            ('冒险中，直接获得2张技能牌', 0.33, 0.57),
            ('压迫', 0.26, 0.60),
            ('选择', 0.82, 0.62),
            ('冒险中，直接获得4张1级卡牌', 0.34, 0.68),
            ('残影', 0.26, 0.70),
            ('选择', 0.82, 0.72),
            ('击败3只普通怪', 0.22, 0.78),
            ('超时空之手', 0.30, 0.81),
            ('洗牌时，将1张随机宝石牌加入我方手牌', 0.44, 0.84),
            ('选择', 0.82, 0.83),
            ('告别', 0.78, 0.52),
        )
    ]

    bonuses = {
        (button.label, button.y): auto_play.tower_trainer_task_bonus(
            button,
            buttons,
            config,
        )
        for button in buttons
        if button.label in {'选择', '告别'}
    }

    assert bonuses[('选择', 0.83)] > bonuses[('告别', 0.52)]
    assert bonuses[('选择', 0.83)] > bonuses[('选择', 0.62)]


def test_tower_spire_card_reward_takes_power_instead_of_abandoning(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'stage': '尖塔木屋',
            'profession': '战士',
            'phase': 'card_reward',
        },
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('荆棘宝石', 0.17, 0.48),
            ('防守宝石', 0.5, 0.48),
            ('重击宝石', 0.83, 0.48),
            ('返回', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.label != '放弃'
    assert choice.x in {0.17, 0.5, 0.83}


def test_tower_card_reward_prefers_fast_wish_over_slow_chant_poison():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('烟歌', 0.17, 0.48),
            ('许愿！', 0.5, 0.48),
            ('奉献', 0.83, 0.48),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.x == 0.5
    assert '许愿' in choice.label


def test_tower_traveler_reward_prefers_potent_poison_core(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'profession': '旅行者', 'phase': 'card_reward'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('祈愿灯', 0.17, 0.48),
            ('烈性毒药', 0.5, 0.48),
            ('小灰盾', 0.83, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.x == 0.5
    assert '烈性毒药' in choice.label


def test_tower_traveler_flower_trumpet_switches_reward_to_prayer(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'profession': '旅行者',
            'phase': 'card_reward',
            'predecessor_treasure': '花喇叭',
            'key_treasures': ['花喇叭'],
        },
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('天使', 0.17, 0.48),
            ('烈性毒药', 0.5, 0.48),
            ('小灰盾', 0.83, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.x == 0.17
    assert '天使' in choice.label


def test_tower_traveler_prayer_build_keeps_finisher_and_culls_junk(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'stage': '深渊楼梯',
            'profession': '旅行者',
            'predecessor_treasure': '花喇叭',
        },
    )

    assert auto_play.tower_card_cull_bonus('tower', '救赎') == 0.0
    assert auto_play.tower_card_cull_bonus('tower', '灵魂燃烧') > 0
    assert auto_play.tower_card_cull_bonus('tower', '毒药攻击') > 0
    assert auto_play.tower_combat_sequence_bonus('tower', '天使') > (
        auto_play.tower_combat_sequence_bonus('tower', '救赎')
    )


def test_tower_prayer_build_stops_at_floor_six_without_a_starter():
    auto_play = load_auto_play_module()
    state = {
        'stage': '深渊楼梯',
        'profession': '旅行者',
        'floor': 6,
        'predecessor_treasure': '花喇叭',
        'core_cards': ['Tower card choice: 涂毒小刀'],
    }

    assert auto_play.tower_prayer_build_should_stop(state)

    state['core_cards'].append('Tower card choice: 天使')
    assert not auto_play.tower_prayer_build_should_stop(state)


def test_tower_traveler_reward_prefers_infinite_gem_over_prayer_branch(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'profession': '旅行者', 'phase': 'card_reward'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('慈悲', 0.17, 0.48),
            ('无限宝石', 0.5, 0.48),
            ('救赎', 0.83, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.x == 0.5
    assert '无限宝石' in choice.label


def test_tower_traveler_reward_uses_current_seven_card_recipe(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'profession': '旅行者', 'phase': 'card_reward'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('未来汽水', 0.17, 0.48),
            ('献祭', 0.5, 0.48),
            ('祈愿灯', 0.83, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.x == 0.5
    assert '献祭' in choice.label


def test_tower_traveler_reward_skips_prayer_and_thick_deck_branches(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'profession': '旅行者', 'phase': 'card_reward'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('救赎', 0.17, 0.48),
            ('慈悲', 0.5, 0.48),
            ('代号肉鸽', 0.83, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.label == '放弃'
    assert '10金币' in choice.reason


def test_tower_traveler_reward_skips_wish_setup_branch(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'profession': '旅行者', 'phase': 'card_reward'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('引雷针', 0.17, 0.48),
            ('退让', 0.5, 0.48),
            ('许愿！', 0.83, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.label == '放弃'


def test_tower_traveler_reward_skips_duplicate_cycle_slot(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'profession': '旅行者',
            'phase': 'card_reward',
            'core_cards': ['Tower card choice: 毒药攻击'],
        },
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('毒药攻击', 0.17, 0.48),
            ('祈愿灯', 0.5, 0.48),
            ('小灰盾', 0.83, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.label == '放弃'


def test_tower_traveler_equips_poison_gem_before_poison_attack(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'predecessor_treasure': '毒龙匕首'},
    )

    gem_bonus = auto_play.tower_combat_sequence_bonus('tower', '剧毒晶石')
    attack_bonus = auto_play.tower_combat_sequence_bonus('tower', '毒药攻击')

    assert gem_bonus > attack_bonus
    assert auto_play.tower_combat_sequence_bonus('tower', '黑神话') > attack_bonus


def test_tower_combat_ignores_upper_screen_status_card_text():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='迅捷',
            x=0.74,
            y=0.19,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='结束第1回合',
            x=0.50,
            y=0.92,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': ['迅捷'], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '结束第1回合'


def test_tower_combat_ignores_card_type_metadata():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='防御牌',
            x=0.92,
            y=0.36,
            confidence=0.99,
            clickability=1.6,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='结束第1回合',
            x=0.50,
            y=0.92,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '结束第1回合'


def test_tower_combat_ends_turn_when_only_disabled_cards_remain():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=confidence,
            clickability=clickability,
            source='ocr',
        )
        for label, x, y, confidence, clickability in (
            ('虚弱', 0.49, 0.64, 0.99, 0.93),
            ('闪电晶石', 0.20, 0.64, 0.97, 0.91),
            ('每对敌方添加3层电击：额外添加1层电击', 0.49, 0.40, 0.98, 1.87),
            ('结束第1回合', 0.50, 0.92, 0.99, 1.98),
        )
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': ['虚弱'], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '结束第1回合'


def test_tower_combat_uses_bright_ocr_card_when_vision_misses_its_border():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=confidence,
            clickability=clickability,
            source='ocr',
        )
        for label, x, y, confidence, clickability in (
            ('闪电！', 0.20, 0.64, 0.94, 1.75),
            ('绿舌头', 0.49, 0.64, 0.99, 1.68),
            ('结束第3回合', 0.50, 0.92, 0.99, 1.98),
        )
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '闪电！'
    assert scored[-1].label == '绿舌头'


def test_tower_deep_map_prioritizes_cycle_building_rooms():
    auto_play = load_auto_play_module()

    assert auto_play.tower_deep_map_room_bonus(
        '卡牌遗忘'
    ) > auto_play.tower_deep_map_room_bonus('休息点')
    assert auto_play.tower_deep_map_room_bonus(
        '训练师'
    ) > auto_play.tower_deep_map_room_bonus('金币商店')
    assert auto_play.tower_deep_map_room_bonus('护盾·金币哥布林') == 5.5
    assert auto_play.tower_deep_map_room_bonus('护盾·水晶哥布材') == 5.5
    assert auto_play.tower_deep_map_room_bonus('金币商店') >= 5.0
    assert auto_play.tower_deep_map_room_bonus('休息点') >= 5.0
    assert auto_play.tower_deep_map_room_bonus('训练师任务') == 7.0
    assert auto_play.tower_deep_map_room_bonus(
        '宝石牌包'
    ) > auto_play.tower_deep_map_room_bonus('职业牌包')
    assert auto_play.is_tower_status_fraction_label('[67/75】')
    assert not auto_play.is_tower_status_fraction_label('进入下一层')


def test_tower_traveler_reward_skips_non_core_cards_for_gold(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'profession': '旅行者', 'phase': 'card_reward'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('祈愿灯', 0.17, 0.48),
            ('病变', 0.5, 0.48),
            ('小灰盾', 0.83, 0.48),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.label == '放弃'
    assert '10金币' in choice.reason


def test_tower_traveler_reward_uses_fixed_abandon_position_when_ocr_misses_it(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'profession': '旅行者', 'phase': 'card_reward'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('毒药瓶', 0.17, 0.48),
            ('退让', 0.5, 0.48),
            ('烟歌', 0.83, 0.48),
            ('返回', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.label == '放弃'
    assert choice.source == 'vision'
    assert choice.x == 0.286
    assert choice.y == 0.696


def test_tower_card_reward_prefers_instant_gem_over_slow_poison_gem():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('剧毒晶石！', 0.17, 0.48),
            ('瞬发宝石！', 0.5, 0.48),
            ('智慧宝石！', 0.83, 0.48),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.x == 0.5
    assert '瞬发宝石' in choice.label


def test_tower_traveler_prefers_poison_engine_gem_over_generic_instant_gem(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: card_reward\n'
        'profession: 旅行者\n'
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('剧毒晶石！', 0.17, 0.48),
            ('瞬发宝石！', 0.5, 0.48),
            ('智慧宝石！', 0.83, 0.48),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.x == 0.17
    assert '剧毒晶石' in choice.label


def test_tower_card_reward_avoids_unplayable_junk_without_discard_engine():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('杂念', 0.17, 0.48),
            ('病变', 0.5, 0.48),
            ('杂物！', 0.83, 0.48),
            ('不能被打出，弃置时获得1点法力', 0.5, 0.60),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.x == 0.5
    assert '病变' in choice.label


def test_tower_card_reward_prefers_steadfast_gem_for_deep_survival():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('坚定宝石', 0.17, 0.48),
            ('恢复宝石！', 0.5, 0.48),
            ('风怒之岩', 0.83, 0.48),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.x == 0.17
    assert '坚定宝石' in choice.label


def test_tower_card_reward_always_prefers_immediate_fusion_column():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='选一张卡牌学习',
            x=0.5,
            y=0.31,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='以物易物I',
            x=0.17,
            y=0.48,
            confidence=0.9,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='普通攻击I',
            x=0.5,
            y=0.48,
            confidence=0.9,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='马上融合',
            x=0.83,
            y=0.36,
            confidence=0.9,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='盾牌I',
            x=0.83,
            y=0.48,
            confidence=0.9,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='确定',
            x=0.73,
            y=0.70,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.x == 0.83
    assert '盾牌I' in choice.label
    assert '马上融合' in choice.reason


def test_tower_card_reward_uses_fusion_badge_when_card_title_ocr_is_missing():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('引雷针', 0.17, 0.48),
            ('挣脱！', 0.5, 0.48),
            ('马上融合', 0.875, 0.365),
            ('放弃', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.x == 0.83
    assert '马上融合' in choice.reason


def test_tower_card_reward_does_not_assign_selected_description_to_middle_card():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('选一张卡牌学习', 0.5, 0.31),
            ('未来汽水', 0.17, 0.48),
            ('夺甲', 0.5, 0.48),
            ('失控', 0.83, 0.48),
            ('获得3点法力，移除', 0.5, 0.60),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_card_reward_candidate(config, buttons)

    assert choice is not None
    assert choice.x == 0.17
    assert '未来汽水' in choice.label


def test_tower_rest_point_prefers_permanent_training(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'stage': '尖塔木屋'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('破旧营地', 0.5, 0.31),
            ('休息', 0.2, 0.48),
            ('挖掘', 0.5, 0.48),
            ('锻炼', 0.8, 0.48),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_rest_choice_candidate(config, buttons)

    assert choice is not None
    assert choice.label == '锻炼'


def test_tower_rest_point_prefers_reading_over_full_health_rest(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'stage': '尖塔木屋'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('破旧营地', 0.5, 0.31),
            ('休息', 0.2, 0.48),
            ('阅读', 0.5, 0.48),
            ('冥想', 0.8, 0.48),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_rest_choice_candidate(config, buttons)

    assert choice is not None
    assert choice.label == '阅读'


def test_tower_abyss_rest_point_prefers_healing(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'stage': '深渊楼梯'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('破旧营地', 0.5, 0.31),
            ('休息', 0.2, 0.48),
            ('挖掘', 0.5, 0.48),
            ('锻炼', 0.8, 0.48),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_rest_choice_candidate(config, buttons)

    assert choice is not None
    assert choice.label == '休息'


def test_tower_treasure_panel_prioritizes_immortal_rarity():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('宝物选择', 0.5, 0.31),
            ('爱心三明治III', 0.2, 0.48),
            ('时之沙漏', 0.5, 0.48),
            ('不灭超越宝石', 0.8, 0.48),
            ('返回', 0.29, 0.70),
            ('确定', 0.73, 0.70),
        )
    ]

    choice = auto_play.tower_treasure_choice_candidate(config, buttons)

    assert choice is not None
    assert '不灭超越宝石' in choice.label
    assert choice.x == 0.8


def test_game_info_rewrite_preserves_manual_observations(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    write_game_strategy(tmp_path, 'tower')
    info_path = tmp_path / 'games' / 'tower' / 'game_info.md'
    info_path.write_text(
        '# Game Info: tower\n\n'
        '## Manual Observations\n\n'
        '- 保留这条实战心得。\n\n'
        '## Ranking\n\n'
    )

    auto_play.write_game_info_markdown('tower')

    assert '- 保留这条实战心得。' in info_path.read_text()


def test_tower_new_run_builds_setup_state_then_switches_to_combat(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    setup_image = Image.new('RGB', (360, 800), color='black')
    setup_buttons = [
        auto_play.ButtonCandidate(
            label='深渊楼梯',
            x=0.5,
            y=0.2,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='铁面奇莫',
            x=0.5,
            y=0.5,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='开始冒险',
            x=0.5,
            y=0.9,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
    ]

    auto_play.update_tower_run_state(
        'tower',
        setup_image,
        setup_buttons,
        clicked_label='开始冒险',
    )
    setup_state = auto_play.load_tower_run_state('tower')

    combat_image = Image.new('RGB', (360, 800), color=(18, 21, 24))
    draw = ImageDraw.Draw(combat_image)
    draw.rounded_rectangle((22, 426, 118, 556), radius=7, fill=(154, 81, 49))
    draw.rectangle((100, 735, 260, 782), fill=(221, 176, 40))
    auto_play.update_tower_run_state('tower', combat_image, [])
    combat_state = auto_play.load_tower_run_state('tower')

    assert setup_state['stage'] == '深渊楼梯'
    assert setup_state['character'] == '铁面奇莫'
    assert setup_state['policy']['never_sell'] is True
    assert combat_state['run_id'] == setup_state['run_id']
    assert combat_state['phase'] == 'combat'


def test_tower_world_map_does_not_replace_stage_when_multiple_stages_visible(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: deep-run\nstage: 深渊楼梯\nphase: complete\nfloor: 20\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=0.3,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        )
        for label in ('深渊楼梯', '尖塔木屋')
    ]

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        buttons,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['stage'] == '深渊楼梯'


def test_tower_floor_one_treasure_choice_restores_predecessor_context(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: deep-run\nstage: 深渊楼梯\nphase: climbing_map\nfloor: 1\n'
    )
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'abyss_retry'},
    )

    auto_play.record_tower_run_choice(
        'tower',
        'treasure',
        'Tower treasure choice: 花喇叭',
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['awaiting_predecessor_treasure'] is True


def test_tower_spire_treasure_never_requests_abyss_reroll(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: spire-run\n'
        'stage: 尖塔木屋\n'
        'phase: climbing_map\n'
        'floor: 1\n'
        'profession: 旅行者\n'
        'last_action: 拿走前辈的宝物\n'
        'key_treasures: []\n'
    )
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'spire_running'},
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, y in (
            ('恭喜获得', 0.15),
            ('燃烧辣椒', 0.51),
            ('点击空白处关闭', 0.95),
        )
    ]

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        buttons,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state.get('reroll_predecessor') is not True
    daily = auto_play.load_tower_daily_state('tower')
    assert daily.get('predecessor_rerolls') is None


def test_tower_late_reward_never_overwrites_abyss_predecessor_treasure(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: deep-run\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 10\n'
        'profession: 战士\n'
        'predecessor_treasure: 曜蓝水晶\n'
        'reroll_predecessor: false\n'
        'last_action: 拿走前辈的宝物\n'
        'awaiting_predecessor_treasure: true\n'
        'key_treasures:\n'
        '- 曜蓝水晶\n'
    )
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-15',
            'phase': 'abyss_retry',
            'accepted_predecessor_treasure': '曜蓝水晶',
            'accepted_predecessor_run_id': 'deep-run',
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, y in (
            ('恭喜获得', 0.15),
            ('深澜龙血', 0.51),
            ('点击空白处关闭', 0.95),
        )
    ]

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        buttons,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['predecessor_treasure'] == '曜蓝水晶'
    assert state['reroll_predecessor'] is False
    assert state['awaiting_predecessor_treasure'] is False
    daily = auto_play.load_tower_daily_state('tower')
    assert daily.get('last_rejected_predecessor_treasure') is None


def test_tower_enter_adventure_resets_stale_run_to_floor_one(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: stale-run\nstage: 深渊楼梯\nphase: complete\nfloor: 20\n'
    )

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        [],
        clicked_label='进入冒险',
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['run_id'] != 'stale-run'
    assert state['floor'] == 1
    assert state['phase'] == 'initial_setup'


def test_tower_profession_is_inferred_from_recorded_cards():
    auto_play = load_auto_play_module()

    profession = auto_play.tower_profession_from_text(
        ['Tower card choice: 祈愿灯', 'Tower card choice: 涂毒小刀']
    )

    assert profession == '旅行者'


def test_tower_profession_is_inferred_from_predecessor_treasure_pool():
    auto_play = load_auto_play_module()

    profession = auto_play.tower_profession_from_text(
        ['草龙蛋', '电虫药水', '过期卷轴']
    )

    assert profession == '法师'


def test_tower_mage_profession_is_not_replaced_by_character_card(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\n'
        'stage: 深渊楼梯\n'
        'phase: combat\n'
        'floor: 2\n'
        'profession: 法师\n'
        'predecessor_treasure: 电虫药水\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='绿舌头',
            x=0.2,
            y=0.63,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
    ]

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        buttons,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['profession'] == '法师'


def test_tower_treasure_pool_overrides_stale_preferred_profession(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 1\n'
        'last_action: 拿走前辈的宝物\n'
        'key_treasures: []\n'
    )
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-14',
            'phase': 'abyss_retry',
            'preferred_abyss_profession': '旅行者',
            'predecessor_rerolls': auto_play.TOWER_PREDECESSOR_REROLL_LIMIT,
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, y in (
            ('恭喜获得', 0.15),
            ('草龙蛋', 0.51),
            ('点击空白处关闭', 0.95),
        )
    ]

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        buttons,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['profession'] == '法师'
    assert state['predecessor_treasure'] == '草龙蛋'
    assert state['reroll_predecessor'] is False
    daily = auto_play.load_tower_daily_state('tower')
    assert daily['abyss_profession'] == '法师'
    assert daily['accepted_predecessor_treasure'] == '草龙蛋'


def test_tower_run_profession_uses_persistent_abyss_preference(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {
            'phase': 'abyss_retry',
            'preferred_abyss_profession': '猎人',
        },
    )

    assert auto_play.tower_run_profession('tower') == '猎人'


def test_tower_wrong_traveler_predecessor_treasure_requests_reroll(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 1\n'
        'profession: 旅行者\n'
        'last_action: 拿走前辈的宝物\n'
        'key_treasures: []\n'
    )
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'abyss_retry'},
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, y in (
            ('恭喜获得', 0.15),
            ('炸弹老虎机', 0.51),
            ('点击空白处关闭', 0.95),
        )
    ]

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        buttons,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['predecessor_treasure'] == '炸弹老虎机'
    assert state['key_treasures'] == ['炸弹老虎机']
    assert state['reroll_predecessor'] is True
    daily = auto_play.load_tower_daily_state('tower')
    assert daily['abyss_profession'] == '旅行者'
    assert daily['predecessor_rerolls'] == 1


def test_tower_observed_warrior_overrides_preferred_mage(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: fixed-daily-warrior\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 1\n'
        'last_action: 确定\n'
        'awaiting_predecessor_treasure: true\n'
        'key_treasures: []\n'
    )
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-15',
            'phase': 'abyss_retry',
            'preferred_abyss_profession': '法师',
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, y in (
            ('恭喜获得', 0.15),
            ('巨人之拳', 0.51),
            ('点击空白处关闭', 0.95),
        )
    ]

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        buttons,
    )

    state = auto_play.load_tower_run_state('tower')
    daily = auto_play.load_tower_daily_state('tower')
    assert state['predecessor_treasure'] == '巨人之拳'
    assert state['profession'] == '战士'
    assert state['reroll_predecessor'] is False
    assert daily['abyss_profession'] == '战士'
    assert daily['accepted_predecessor_treasure'] == '巨人之拳'
    assert daily['preferred_abyss_profession'] == '法师'
    assert int(daily.get('predecessor_rerolls') or 0) == 0


def test_tower_target_traveler_predecessor_treasure_keeps_run(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 1\n'
        'profession: 旅行者\n'
        'last_action: 拿走前辈的宝物\n'
        'key_treasures: []\n'
    )
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'abyss_retry'},
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, y in (
            ('恭喜获得', 0.15),
            ('毒龙匕首', 0.51),
            ('点击空白处关闭', 0.95),
        )
    ]

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        buttons,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['predecessor_treasure'] == '毒龙匕首'
    assert state['reroll_predecessor'] is False


def test_tower_accepted_predecessor_clears_stale_same_run_reroll(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: mage-run\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 1\n'
        'profession: 法师\n'
        'predecessor_treasure: 电虫药水\n'
        'reroll_predecessor: true\n'
        'key_treasures: [电虫药水]\n'
    )
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-15',
            'phase': 'abyss_retry',
            'accepted_predecessor_treasure': '电虫药水',
            'accepted_predecessor_run_id': 'mage-run',
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='当前所在层数',
            x=0.5,
            y=0.55,
            confidence=0.99,
            clickability=1.0,
            source='ocr',
        )
    ]

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        buttons,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['reroll_predecessor'] is False


def test_tower_prior_run_acceptance_does_not_clear_current_reroll(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: current-run\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 1\n'
        'profession: 法师\n'
        'predecessor_treasure: 电虫药水\n'
        'reroll_predecessor: true\n'
        'key_treasures: [电虫药水]\n'
    )
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-15',
            'phase': 'abyss_retry',
            'accepted_predecessor_treasure': '电虫药水',
            'accepted_predecessor_run_id': 'prior-run',
        },
    )

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        [],
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['reroll_predecessor'] is True


def test_tower_traveler_keeps_rerolling_trumpet_after_bounded_rerolls(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 1\n'
        'profession: 旅行者\n'
        'last_action: 拿走前辈的宝物\n'
        'key_treasures: []\n'
    )
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-13',
            'phase': 'abyss_retry',
            'predecessor_rerolls': auto_play.TOWER_PREDECESSOR_REROLL_LIMIT,
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, y in (
            ('恭喜获得', 0.15),
            ('花喇叭', 0.51),
            ('点击空白处关闭', 0.95),
        )
    ]

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        buttons,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['predecessor_treasure'] == '花喇叭'
    assert state['reroll_predecessor'] is False
    daily = auto_play.load_tower_daily_state('tower')
    assert daily['accepted_predecessor_treasure'] == '花喇叭'


def test_tower_traveler_targets_trumpet_after_reroll_limit(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {
            'predecessor_rerolls': auto_play.TOWER_PREDECESSOR_REROLL_LIMIT,
        },
    )

    assert auto_play.tower_predecessor_treasure_targets(
        'tower', '旅行者'
    ) == ('花喇叭',)


def test_tower_any_profession_accepts_current_treasure_at_reroll_limit():
    auto_play = load_auto_play_module()

    assert auto_play.tower_predecessor_treasure_is_target(
        '法师',
        '安全出口',
        reroll_count=auto_play.TOWER_PREDECESSOR_REROLL_LIMIT,
    )


def test_tower_traveler_rejects_unrelated_treasure_at_reroll_limit():
    auto_play = load_auto_play_module()

    assert not auto_play.tower_predecessor_treasure_is_target(
        '旅行者',
        '安全出口',
        reroll_count=auto_play.TOWER_PREDECESSOR_REROLL_LIMIT,
    )


def test_tower_predecessor_reward_survives_confirmation_step(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 1\n'
        'profession: 旅行者\n'
        'last_action: 确定\n'
        'awaiting_predecessor_treasure: true\n'
        'key_treasures: []\n'
    )
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'abyss_retry'},
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, y in (
            ('恭喜获得', 0.15),
            ('花叭喇', 0.51),
            ('点击空白处关闭', 0.95),
        )
    ]

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        buttons,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['predecessor_treasure'] == '花喇叭'
    assert state['reroll_predecessor'] is True
    assert state['awaiting_predecessor_treasure'] is False


def test_tower_predecessor_reward_ignores_background_sidebar_labels(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: mage-run\n'
        'stage: 深渊楼梯\n'
        'phase: climbing_map\n'
        'floor: 1\n'
        'profession: 法师\n'
        'last_action: 确定\n'
        'awaiting_predecessor_treasure: true\n'
        'key_treasures: []\n'
    )
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-15', 'phase': 'abyss_retry'},
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='融合',
            x=0.11,
            y=0.515,
            confidence=0.999,
            clickability=0.3,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='电虫药水',
            x=0.5,
            y=0.514,
            confidence=0.998,
            clickability=1.8,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='恭喜获得',
            x=0.5,
            y=0.15,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
    ]

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        buttons,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['predecessor_treasure'] == '电虫药水'
    assert state['reroll_predecessor'] is False
    assert state['awaiting_predecessor_treasure'] is False


def test_tower_room_battle_does_not_reset_active_run_when_title_ocr_is_missing(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\n'
        'stage: 深渊楼梯\n'
        'phase: prebattle\n'
        'floor: 1\n'
        'profession: 旅行者\n'
        'predecessor_treasure: 花喇叭\n'
        'reroll_predecessor: true\n'
        'key_treasures: [花喇叭]\n'
    )

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        [],
        clicked_label='战斗',
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['run_id'] == 'run-1'
    assert state['predecessor_treasure'] == '花喇叭'
    assert state['reroll_predecessor'] is True
    assert state['key_treasures'] == ['花喇叭']


def test_tower_stage_page_battle_starts_new_run_even_after_previous_run(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: old-run\n'
        'stage: 深渊楼梯\n'
        'phase: defeated\n'
        'floor: 15\n'
        'reroll_predecessor: true\n'
        'key_treasures: [花喇叭]\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='深渊楼梯',
            x=0.5,
            y=0.2,
            confidence=0.99,
            clickability=1.0,
        )
    ]

    auto_play.update_tower_run_state(
        'tower',
        Image.new('RGB', (360, 800), color='black'),
        buttons,
        clicked_label='战斗',
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['run_id'] != 'old-run'
    assert state['floor'] == 1
    assert state['key_treasures'] == []
    assert 'reroll_predecessor' not in state


def test_tower_deep_map_prefers_predecessor_treasure_over_career_pack():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=0.69,
            confidence=0.98,
            clickability=1.6,
            source='ocr',
        )
        for label, x in (
            ('当前所在层数', 0.5),
            ('前辈的宝物', 0.27),
            ('职业牌包', 0.71),
        )
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '前辈的宝物'


def test_tower_predecessor_dialog_prefers_take_action_over_heading():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, y in (
            ('前辈的宝物', 0.35),
            ('拿走前辈的宝物', 0.62),
            ('我再想想', 0.69),
        )
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '拿走前辈的宝物'


def test_tower_deep_map_avoids_cursed_treasure_vault():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=0.69,
            confidence=0.98,
            clickability=1.6,
            source='ocr',
        )
        for label, x in (
            ('当前所在层数', 0.5),
            ('诅咒宝库', 0.27),
            ('休息点', 0.71),
        )
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '休息点'
    assert scored[-1].label == '诅咒宝库'


def test_tower_deep_map_prefers_rest_when_floor_hud_ocr_is_missing():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=clickability,
            source=source,
        )
        for label, x, y, clickability, source in (
            ('左侧道路', 0.10, 0.75, 1.14, 'template'),
            ('休息点', 0.27, 0.70, 1.58, 'ocr'),
            ('强化法阵', 0.71, 0.70, 1.59, 'ocr'),
        )
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '休息点'


def test_live_mcp_client_is_reused_until_closed(monkeypatch):
    auto_play = load_auto_play_module()
    created = []
    closed = []

    class FakeMcpClient:
        process = None

        def __init__(self, command, timeout):
            created.append((command, timeout))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            closed.append(True)

    monkeypatch.setattr(auto_play, 'McpClient', FakeMcpClient)
    args = SimpleNamespace(mcp_command='fake mcp', timeout=3.0)

    first = auto_play.live_mcp_client(args)
    second = auto_play.live_mcp_client(args)
    auto_play.close_live_mcp_client()

    assert first is second
    assert len(created) == 1
    assert closed == [True]


def test_tower_battle_initial_read_is_once_per_battle(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\nphase: prebattle\nbattle_number: 0\n'
        'awaiting_route_after_reward: true\n'
    )
    image = Image.new('RGB', (360, 800), color=(18, 21, 24))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((22, 426, 118, 556), radius=7, fill=(154, 81, 49))
    draw.rectangle((100, 735, 260, 782), fill=(221, 176, 40))

    assert auto_play.tower_battle_needs_initial_read('tower', image)

    auto_play.start_tower_battle_state('tower', image, [])

    assert not auto_play.tower_battle_needs_initial_read('tower', image)
    state = auto_play.load_tower_run_state('tower')
    assert state['battle_number'] == 1
    assert state['battle']['max_actions_per_read'] == 2
    assert not state['awaiting_route_after_reward']


def test_tower_battle_uses_precise_reads_for_timing_sensitive_finisher(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\n'
        'phase: prebattle\n'
        'battle_number: 0\n'
        'core_cards:\n'
        "  - 'Tower card choice: 慈悲'\n"
    )
    image = Image.new('RGB', (360, 800), color=(18, 21, 24))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((22, 426, 118, 556), radius=7, fill=(154, 81, 49))
    draw.rectangle((100, 735, 260, 782), fill=(221, 176, 40))

    assert auto_play.tower_battle_requires_precise_read('tower')

    auto_play.start_tower_battle_state('tower', image, [])

    state = auto_play.load_tower_run_state('tower')
    assert state['battle']['mode'] == 'per_action_ocr'
    assert state['battle']['max_actions_per_read'] == 1


def test_tower_discard_all_finisher_requires_precise_reads(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\n'
        'core_cards:\n'
        "  - 'Tower card choice: 重整旗鼓'\n"
    )

    assert auto_play.tower_battle_requires_precise_read('tower')


def test_tower_sacred_finisher_uses_precise_reads_only_in_kill_range(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\n'
        'core_cards:\n'
        "  - 'Tower card choice: 神圣斩击'\n"
        'battle:\n'
        '  enemy_sacred_finisher_range: false\n'
    )

    assert not auto_play.tower_battle_requires_precise_read('tower')

    state_path.write_text(
        'run_id: run-1\n'
        'core_cards:\n'
        "  - 'Tower card choice: 神圣斩击'\n"
        'battle:\n'
        '  enemy_sacred_finisher_range: true\n'
    )

    assert auto_play.tower_battle_requires_precise_read('tower')


def test_tower_waits_once_then_uses_sacred_finisher(monkeypatch):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    state = {
        'stage': '深渊楼梯',
        'profession': '战士',
        'core_cards': ['Tower card choice: 神圣斩击'],
        'battle': {
            'enemy_sacred_finisher_range': True,
            'player_hp_critical': False,
            'sacred_finisher_waits': 0,
        },
    }
    monkeypatch.setattr(auto_play, 'load_tower_run_state', lambda _game: state)
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '战士')
    end = auto_play.ButtonCandidate(
        label='结束第3回合',
        x=0.5,
        y=0.92,
        confidence=0.99,
        clickability=4.0,
        source='vision',
    )
    attack = auto_play.ButtonCandidate(
        label='Visible playable card: 普通攻击',
        x=0.2,
        y=0.53,
        confidence=0.96,
        clickability=7.4,
        source='vision',
    )

    waiting = auto_play.score_buttons(
        [attack, end],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert waiting[0].label == '结束第3回合'

    sacred = auto_play.ButtonCandidate(
        label='Visible playable card: 神圣斩击',
        x=0.5,
        y=0.53,
        confidence=0.96,
        clickability=7.4,
        source='vision',
    )
    state['battle']['sacred_finisher_waits'] = 1
    finishing = auto_play.score_buttons(
        [attack, sacred, end],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert finishing[0].label == 'Visible playable card: 神圣斩击'


def test_tower_combat_delays_discard_all_finisher_until_other_cards_are_played():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='Visible playable card: 重整旗鼓',
            x=0.20,
            y=0.59,
            confidence=0.96,
            clickability=7.4,
            source='vision',
        ),
        auto_play.ButtonCandidate(
            label='Visible playable card: 祈愿灯',
            x=0.49,
            y=0.59,
            confidence=0.96,
            clickability=7.4,
            source='vision',
        ),
        auto_play.ButtonCandidate(
            label='结束第1回合',
            x=0.50,
            y=0.92,
            confidence=0.99,
            clickability=4.0,
            source='vision',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == 'Visible playable card: 祈愿灯'


def test_tower_combat_orders_compassion_before_unnamed_discard_finisher(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\n'
        'core_cards:\n'
        "  - 'Tower card choice: 重整旗鼓'\n"
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='Visible playable card: 慈悲',
            x=0.20,
            y=0.59,
            confidence=0.96,
            clickability=7.4,
            source='vision',
        ),
        auto_play.ButtonCandidate(
            label='Visible playable card',
            x=0.49,
            y=0.59,
            confidence=0.96,
            clickability=7.4,
            source='vision',
        ),
        auto_play.ButtonCandidate(
            label='结束第2回合',
            x=0.50,
            y=0.92,
            confidence=0.99,
            clickability=4.0,
            source='vision',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == 'Visible playable card: 慈悲'


def test_tower_traveler_combat_builds_poison_before_finisher(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=0.59,
            confidence=0.96,
            clickability=7.4,
            source='vision',
        )
        for label, x in (
            ('Visible playable card: 安乐毒药', 0.20),
            ('Visible playable card: 烈性毒药', 0.49),
            ('Visible playable card: 毒药攻击', 0.78),
        )
    ]
    buttons.append(
        auto_play.ButtonCandidate(
            label='结束第1回合',
            x=0.5,
            y=0.92,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        )
    )

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == 'Visible playable card: 毒药攻击'


def test_tower_floor_counter_accepts_live_ocr_variants_only_after_progress(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text('run_id: run-1\nphase: climbing_map\nfloor: 11\n')
    image = Image.new('RGB', (360, 800), color='black')

    auto_play.update_tower_run_state(
        'tower',
        image,
        [],
        clicked_label='进人下',
        action_succeeded=False,
    )
    assert auto_play.load_tower_run_state('tower')['floor'] == 11

    auto_play.update_tower_run_state(
        'tower',
        image,
        [],
        clicked_label='进人入下一层',
        action_succeeded=True,
    )
    assert auto_play.load_tower_run_state('tower')['floor'] == 12


def test_tower_return_to_inn_completes_active_run(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text('run_id: run-1\nphase: combat\nfloor: 7\n')
    image = Image.new('RGB', (360, 800), color='black')

    auto_play.update_tower_run_state(
        'tower',
        image,
        [],
        clicked_label='返回旅馆',
        action_succeeded=True,
    )

    state = auto_play.load_tower_run_state('tower')
    assert state['phase'] == 'complete'
    assert state['floor'] == 7


def test_tower_fractional_floor_hud_self_heals_stale_run_state(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: stale-deep-run\nstage: 深渊楼梯\nphase: climbing_map\nfloor: 22\n'
    )
    image = Image.new('RGB', (360, 800), color='black')
    buttons = [
        auto_play.ButtonCandidate(
            label='当前层数2/7',
            x=0.53,
            y=0.53,
            confidence=1.0,
            clickability=1.0,
            source='ocr',
        )
    ]

    auto_play.update_tower_run_state('tower', image, buttons)

    state = auto_play.load_tower_run_state('tower')
    assert state['stage'] == '尖塔木屋'
    assert state['phase'] == 'climbing_map'
    assert state['floor'] == 2
    assert state['floor_goal'] == 7


def test_tower_first_spire_floor_clears_previous_run_navigation(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: deep-run\n'
        'stage: 尖塔木屋\n'
        'phase: initial_setup\n'
        'floor: 1\n'
        'last_room_action: 前辈的宝物\n'
        'last_room_position: [0.27, 0.69]\n'
        'awaiting_route_after_reward: true\n'
        'reroll_predecessor: true\n'
    )
    image = Image.new('RGB', (360, 800), color='black')
    buttons = [
        auto_play.ButtonCandidate(
            label='当前层数1/7',
            x=0.53,
            y=0.53,
            confidence=1.0,
            clickability=1.0,
            source='ocr',
        )
    ]

    auto_play.update_tower_run_state('tower', image, buttons)

    state = auto_play.load_tower_run_state('tower')
    assert state['run_id'] != 'deep-run'
    assert state['phase'] == 'climbing_map'
    assert state['floor'] == 1
    assert state['floor_goal'] == 7
    assert 'last_room_action' not in state
    assert 'last_room_position' not in state
    assert 'awaiting_route_after_reward' not in state
    assert 'reroll_predecessor' not in state


def test_tower_abyss_map_floor_digit_self_heals_stale_run_state(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: stale-deep-run\nstage: 深渊楼梯\n'
        'phase: climbing_map\nfloor: 15\n'
    )
    image = Image.new('RGB', (360, 800), color='black')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=1.0,
            clickability=1.0,
            source='ocr',
        )
        for label, x, y in (
            ('全服最高层数', 0.39, 0.516),
            ('当前所在层数', 0.63, 0.516),
            ('124', 0.39, 0.533),
            ('6', 0.63, 0.533),
        )
    ]

    auto_play.update_tower_run_state('tower', image, buttons)

    state = auto_play.load_tower_run_state('tower')
    assert state['stage'] == '深渊楼梯'
    assert state['floor'] == 6


def test_tower_stale_route_phase_does_not_count_treasure_confirmation(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: route_choice\nfloor: 6\n'
    )
    image = Image.new('RGB', (360, 800), color='black')
    buttons = [
        auto_play.ButtonCandidate(
            label='宝物选择',
            x=0.5,
            y=0.3,
            confidence=1.0,
            clickability=1.0,
            source='ocr',
        )
    ]

    auto_play.update_tower_run_state(
        'tower',
        image,
        buttons,
        clicked_label='确定',
        action_succeeded=True,
    )

    assert auto_play.load_tower_run_state('tower')['floor'] == 6


def test_tower_daily_moves_from_abyss_to_recruit_after_return(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'abyss', 'notes': []},
    )

    auto_play.update_tower_daily_state(
        'tower',
        [],
        clicked_label='返回旅馆',
        action_succeeded=True,
    )

    state = auto_play.load_tower_daily_state('tower')
    assert state['phase'] == 'recruit'
    assert state['notes'] == ['深渊挑战已结束，转入旅馆招募。']


def test_tower_daily_abyss_focus_restarts_after_return(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-15',
            'phase': 'abyss',
            'focus': 'abyss',
            'notes': [],
        },
    )

    auto_play.update_tower_daily_state(
        'tower',
        [],
        clicked_label='返回旅馆',
        action_succeeded=True,
    )

    state = auto_play.load_tower_daily_state('tower')
    assert state['phase'] == 'abyss_retry'
    assert state['notes'] == ['深渊专注模式：本局结束后立即重开深渊。']


def test_tower_daily_predecessor_reroll_return_stays_in_abyss(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'abyss_retry', 'notes': []},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(
        'stage: 深渊楼梯\nphase: complete\nfloor: 1\n'
        'reroll_predecessor: true\n'
    )

    auto_play.update_tower_daily_state(
        'tower',
        [],
        clicked_label='返回旅馆',
        action_succeeded=True,
    )

    state = auto_play.load_tower_daily_state('tower')
    assert state['phase'] == 'abyss_retry'
    assert state['notes'] == ['前辈职业宝物不匹配，返回旅馆后继续重开深渊。']


def test_tower_daily_recruit_prefers_free_ad_over_paid_confirmation(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'recruit_all', 'notes': []},
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=0.60,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, x in (
            ('是否消耗金萝卜获得5次招募次数', 0.5),
            ('免费(4/4)', 0.28),
            ('好的', 0.74),
            ('雇佣', 0.69),
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert [button.label for button in selection] == ['免费(4/4)']


def test_tower_recruit_capacity_modal_uses_left_cancel_and_resumes_abyss(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'recruit_all', 'notes': []},
    )
    image = Image.new('RGB', (360, 800), color=(8, 8, 8))
    pixels = image.load()
    for y in range(464, 504):
        for x in range(65, 155):
            pixels[x, y] = (35, 105, 125)
        for x in range(205, 296):
            pixels[x, y] = (150, 100, 35)

    candidates = auto_play.tower_recruit_blocking_modal_candidates(
        'tower',
        image,
    )
    selection = auto_play.tower_daily_policy_candidates('tower', candidates)

    assert [candidate.label for candidate in candidates] == [
        '取消招募容量弹窗'
    ]
    assert selection is not None
    assert selection[0].x == 0.30

    auto_play.update_tower_daily_state(
        'tower',
        candidates,
        clicked_label=selection[0].label,
        action_succeeded=True,
    )
    state = auto_play.load_tower_daily_state('tower')
    assert state['phase'] == 'abyss_retry'
    assert state['recruitment_blocked_by_capacity'] is True


def test_tower_daily_recruit_stops_when_free_ads_are_exhausted(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'recruit_all', 'notes': []},
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='免费(0/4)',
            x=0.28,
            y=0.60,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
    ]

    auto_play.update_tower_daily_state('tower', buttons)

    state = auto_play.load_tower_daily_state('tower')
    assert state['phase'] == 'complete'


def test_tower_daily_complete_state_is_stable_for_same_day(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    today = auto_play.datetime.now().astimezone().date().isoformat()
    auto_play.write_tower_daily_state(
        'tower',
        {'date': today, 'phase': 'complete', 'completed_at': 'now'},
    )

    state = auto_play.ensure_tower_daily_state('tower')

    assert state['phase'] == 'complete'
    assert state['completed_at'] == 'now'


def test_tower_daily_recruit_records_name_and_power(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-13',
            'phase': 'recruit',
            'notes': [],
            'recruited_character_name': '',
            'recruited_character_power': None,
        },
    )
    recruit_buttons = [
        auto_play.ButtonCandidate(
            label='深渊楼梯',
            x=0.5,
            y=0.13,
            confidence=1.0,
            clickability=1.8,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='雇佣',
            x=0.72,
            y=0.96,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
    ]

    auto_play.update_tower_daily_state(
        'tower',
        recruit_buttons,
        clicked_label='雇佣',
        action_succeeded=True,
    )

    state = auto_play.load_tower_daily_state('tower')
    assert state['phase'] == 'recruit_result'
    assert state['recruited_character_name'] == ''

    result_buttons = [
        auto_play.ButtonCandidate(
            label='快活的卤蛋',
            x=0.5,
            y=0.13,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='2542',
            x=0.5,
            y=0.10,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='正式加入！',
            x=0.5,
            y=0.26,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
    ]

    auto_play.update_tower_daily_state(
        'tower',
        result_buttons,
    )

    state = auto_play.load_tower_daily_state('tower')
    assert state['phase'] == 'recruit_result'
    assert state['recruited_character_name'] == '快活的卤蛋'
    assert state['recruited_character_power'] == 2542


def test_tower_daily_recruit_all_records_each_hire(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-13',
            'phase': 'recruit_all',
            'notes': [],
            'recruited_characters': [],
        },
    )
    auto_play.update_tower_daily_state(
        'tower',
        [],
        clicked_label='雇佣',
        action_succeeded=True,
    )

    buttons = [
        auto_play.ButtonCandidate(
            label='快活的卤蛋',
            x=0.5,
            y=0.13,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='2542',
            x=0.5,
            y=0.10,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='正式加入！',
            x=0.5,
            y=0.26,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
    ]

    auto_play.update_tower_daily_state('tower', buttons)

    state = auto_play.load_tower_daily_state('tower')
    assert state['phase'] == 'recruit_all_result'
    assert state['recruited_characters'] == [
        {'name': '快活的卤蛋', 'power': 2542}
    ]


def test_tower_daily_recruit_all_exhausted_completes_daily_run(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'recruit_all', 'notes': []},
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='0/15',
            x=0.82,
            y=0.31,
            confidence=0.99,
            clickability=1.0,
            source='ocr',
        )
    ]

    auto_play.update_tower_daily_state('tower', buttons)

    state = auto_play.load_tower_daily_state('tower')
    assert state['phase'] == 'complete'
    assert state['completed_at']


def test_tower_daily_prioritizes_abyss_after_spire(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'spire_running', 'notes': []},
    )

    auto_play.update_tower_daily_state(
        'tower',
        [],
        clicked_label='返回旅馆',
        action_succeeded=True,
    )

    state = auto_play.load_tower_daily_state('tower')
    assert state['phase'] == 'abyss_retry'
    assert state['notes'] == ['尖塔木屋已结束，优先再次挑战深渊楼梯。']


def test_tower_daily_spire_focus_retries_spire_after_defeat(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-13',
            'phase': 'spire_running',
            'focus': 'spire',
            'notes': [],
        },
    )

    auto_play.update_tower_daily_state(
        'tower',
        [],
        clicked_label='返回旅馆',
        action_succeeded=True,
    )

    state = auto_play.load_tower_daily_state('tower')
    assert state['phase'] == 'go_to_spire'
    assert state['character_selected'] is False
    assert state['notes'] == ['尖塔木屋挑战未通关，按尖塔专注模式重试。']


def test_tower_daily_spire_focus_completes_after_victory(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-13',
            'phase': 'spire_running',
            'focus': 'spire',
            'notes': [],
        },
    )

    auto_play.update_tower_daily_state(
        'tower',
        [],
        clicked_label='冒险胜利',
        action_succeeded=True,
    )
    auto_play.update_tower_daily_state(
        'tower',
        [],
        clicked_label='返回旅馆',
        action_succeeded=True,
    )

    state = auto_play.load_tower_daily_state('tower')
    assert state['phase'] == 'complete'
    assert state['completed_at']
    assert state['notes'] == ['尖塔木屋已通关，尖塔专注流程完成。']


def test_configure_tower_daily_focus_redirects_active_workflow(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-13',
            'phase': 'abyss_retry',
            'spire_victory': True,
        },
    )

    auto_play.configure_tower_daily_focus('tower', 'spire')

    state = auto_play.load_tower_daily_state('tower')
    assert state['focus'] == 'spire'
    assert state['phase'] == 'go_to_spire'
    assert state['character_selected'] is False
    assert 'spire_victory' not in state


def test_configure_tower_abyss_focus_redirects_recruitment(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-15', 'phase': 'recruit'},
    )

    auto_play.configure_tower_daily_focus('tower', 'abyss')

    state = auto_play.load_tower_daily_state('tower')
    assert state['focus'] == 'abyss'
    assert state['phase'] == 'abyss_retry'


def test_configure_tower_recruit_spire_focus_starts_with_one_recruit(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-14',
            'phase': 'complete',
            'recruited_character_name': '旧角色',
            'recruited_character_power': 1234,
            'character_selected': True,
            'selection_swipes': 4,
            'spire_victory': True,
            'recruitment_blocked_by_capacity': True,
        },
    )

    auto_play.configure_tower_daily_focus('tower', 'recruit_spire')

    state = auto_play.load_tower_daily_state('tower')
    assert state['focus'] == 'recruit_spire'
    assert state['phase'] == 'recruit'
    assert state['recruited_character_name'] == ''
    assert state['recruited_character_power'] is None
    assert state['character_selected'] is False
    assert state['selection_swipes'] == 0
    assert 'spire_victory' not in state
    assert 'recruitment_blocked_by_capacity' not in state


def test_tower_recruit_spire_focus_stops_when_capacity_is_full(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-14',
            'phase': 'recruit',
            'focus': 'recruit_spire',
            'notes': [],
        },
    )

    auto_play.update_tower_daily_state(
        'tower',
        [],
        clicked_label='取消招募容量弹窗',
        action_succeeded=True,
    )

    state = auto_play.load_tower_daily_state('tower')
    assert state['phase'] == 'complete'
    assert state['completed_at']
    assert state['recruitment_blocked_by_capacity'] is True


def test_tower_recruit_spire_focus_stops_when_daily_spire_attempts_are_used(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-14',
            'phase': 'go_to_spire',
            'focus': 'recruit_spire',
            'notes': [],
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='今日次数已用完',
            x=0.5,
            y=0.49,
            confidence=0.99,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='12:27:28后刷新',
            x=0.5,
            y=0.55,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        ),
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == '关闭尖塔次数提示'
    assert selection[0].x == 0.10
    assert selection[0].y == 0.965

    auto_play.update_tower_daily_state(
        'tower',
        buttons,
        clicked_label=selection[0].label,
        action_succeeded=True,
    )

    state = auto_play.load_tower_daily_state('tower')
    assert state['phase'] == 'complete'
    assert state['completed_at']
    assert state['spire_attempts_exhausted'] is True
    assert '未购买次数' in state['notes'][-1]
    assert (
        auto_play.tower_daily_completion_reason(state)
        == '已招募并挑战尖塔；今日次数已用完，未购买次数。'
    )


def test_tower_daily_uses_remaining_recruits_after_second_abyss(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'abyss_retry', 'notes': []},
    )

    auto_play.update_tower_daily_state(
        'tower',
        [],
        clicked_label='返回旅馆',
        action_succeeded=True,
    )

    state = auto_play.load_tower_daily_state('tower')
    assert state['phase'] == 'recruit_all'


def test_tower_daily_stale_recruit_phase_does_not_exit_active_abyss(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'recruit_all'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: route_choice\nfloor: 3\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        )
        for label, x, y in (
            ('选择一个楼梯', 0.5, 0.3),
            ('左侧楼梯', 0.25, 0.4),
            ('右侧楼梯', 0.75, 0.4),
            ('确定', 0.73, 0.71),
            ('返回', 0.27, 0.71),
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is None


def test_tower_stale_daily_phase_still_leaves_completed_reward_room(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'recruit_all'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: card_reward\nfloor: 15\n'
        'awaiting_route_after_reward: true\n'
        'last_room_action: 宝石牌包\n'
        'last_room_position: [0.49, 0.77]\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='Visible room icon',
            x=x,
            y=y,
            confidence=0.98,
            clickability=3.2,
            source='vision',
        )
        for x, y in ((0.49, 0.75), (0.74, 0.67))
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].x == 0.74
    assert '侧边的新房间' in selection[0].reason


def test_tower_generic_loop_leaves_completed_reward_room_by_position(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'awaiting_route_after_reward': True,
            'last_room_action': '宝石牌包',
            'last_room_position': [0.49, 0.77],
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='Visible room icon',
            x=x,
            y=y,
            confidence=0.98,
            clickability=3.2,
            source='vision',
        )
        for x, y in ((0.49, 0.75), (0.74, 0.67))
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
        recent_actions=['放弃'],
    )

    assert scored[0].x == 0.74
    assert 'Enter a new Tower room after reward' in scored[0].reason


def test_tower_next_floor_ignores_reused_previous_room_position(monkeypatch):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'awaiting_route_after_reward': False,
            'last_room_action': '宝石牌包',
            'last_room_position': [0.70, 0.69],
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='Visible next-floor stair room',
            x=0.70,
            y=0.68,
            confidence=0.98,
            clickability=9.0,
            source='vision',
        ),
        auto_play.ButtonCandidate(
            label='进入下一层',
            x=0.70,
            y=0.69,
            confidence=0.97,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='右侧道路',
            x=0.93,
            y=0.75,
            confidence=0.96,
            clickability=0.9,
            source='template',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )
    decision = auto_play.decide_next_move(
        scored,
        min_action_score=1.0,
        ambiguity_margin=0.2,
        ask_on_ambiguous=False,
        automation_config=config,
    )

    assert decision.recommended is not None
    assert decision.recommended.label == 'Visible next-floor stair room'


def test_tower_daily_spire_loadout_scrolls_then_selects_new_recruit(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    state = {
        'date': '2026-09-13',
        'phase': 'go_to_spire',
        'recruited_character_name': '快活的卤蛋',
        'recruited_character_power': 2542,
        'character_selected': False,
        'selection_swipes': 0,
    }
    auto_play.write_tower_daily_state('tower', state)
    screen_buttons = [
        auto_play.ButtonCandidate(
            label='尖塔木屋',
            x=0.5,
            y=0.1,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='开始冒险',
            x=0.5,
            y=0.95,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
    ]

    search = auto_play.tower_daily_policy_candidates('tower', screen_buttons)

    assert search is not None
    assert search[0].source == 'swipe'
    assert search[0].label == '向下查找新招募角色'

    target = auto_play.ButtonCandidate(
        label='快活的卤蛋',
        x=0.27,
        y=0.67,
        confidence=0.99,
        clickability=1.8,
        source='ocr',
    )
    selection = auto_play.tower_daily_policy_candidates(
        'tower',
        [*screen_buttons, target],
    )

    assert selection is not None
    assert selection[0].label == '选择新招募角色：快活的卤蛋'
    assert selection[0].x == target.x
    assert selection[0].y == target.y


def test_tower_daily_opens_settings_when_spire_target_is_in_deep_abyss(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'go_to_spire'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: climbing_map\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('前辈的宝物', 0.27, 0.41),
            ('职业牌包', 0.69, 0.65),
            ('当前所在层数', 0.63, 0.51),
            ('设置', 0.94, 0.05),
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == '设置'
    assert '退出当前深渊' in selection[0].reason


def test_tower_daily_synthesizes_settings_when_icon_has_no_text(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'go_to_spire'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: climbing_map\n'
    )
    room = auto_play.ButtonCandidate(
        label='职业牌包',
        x=0.69,
        y=0.65,
        confidence=0.99,
        clickability=1.8,
        source='ocr',
    )

    selection = auto_play.tower_daily_policy_candidates('tower', [room])

    assert selection is not None
    assert selection[0].label == '设置'
    assert selection[0].source == 'state'
    assert selection[0].x == 0.94
    assert selection[0].y == 0.475


def test_tower_daily_closes_deep_abyss_room_before_opening_settings(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'go_to_spire'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text(
        'run_id: run-1\nstage: 深渊楼梯\nphase: climbing_map\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, y in (
            ('拿走前辈的宝物', 0.61),
            ('我再想想', 0.69),
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == '我再想想'


def test_tower_daily_returns_to_inn_when_leaving_wrong_deep_abyss(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'go_to_spire'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text('run_id: run-1\nstage: 深渊楼梯\nphase: combat\n')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, y in (
            ('继续冒险', 0.48),
            ('返回旅馆', 0.59),
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == '返回旅馆'


def test_tower_daily_abandons_wrong_deep_abyss_after_returning_to_inn(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'go_to_spire'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text('run_id: run-1\nstage: 深渊楼梯\nphase: complete\n')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, y in (
            ('恢复冒险', 0.54),
            ('放弃冒险', 0.62),
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == '放弃冒险'


def test_tower_daily_abandons_visible_deep_resume_after_selecting_spire(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-14', 'phase': 'go_to_spire'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text(
        'run_id: run-1\nstage: 尖塔木屋\nphase: complete\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, y in (
            ('每日无尽 深澜楼梯(1)', 0.44),
            ('恢复冒险', 0.54),
            ('放弃冒险', 0.62),
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == '放弃冒险'


def test_tower_daily_opens_settings_to_reroll_wrong_predecessor(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'abyss_retry'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text(
        'run_id: run-1\nphase: combat\nreroll_predecessor: true\n'
    )
    settings = auto_play.ButtonCandidate(
        label='设置',
        x=0.94,
        y=0.47,
        confidence=0.99,
        clickability=1.8,
        source='ocr',
    )

    selection = auto_play.tower_daily_policy_candidates('tower', [settings])

    assert selection is not None
    assert selection[0].label == '设置'
    assert '重刷' in selection[0].reason


def test_tower_daily_abandons_battle_from_open_settings_before_title(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'abyss_retry'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text(
        'run_id: run-1\nphase: combat\nreroll_predecessor: true\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, y in (('设置', 0.34), ('继续冒险', 0.59), ('放弃战斗', 0.65))
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == '放弃战斗'


def test_tower_daily_closes_victory_before_reroll_navigation(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'abyss_retry'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text(
        'run_id: run-1\nphase: combat\nreroll_predecessor: true\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source=source,
        )
        for label, x, y, source in (
            ('胜利', 0.5, 0.4, 'ocr'),
            ('好的', 0.5, 0.68, 'ocr'),
            ('下方道路', 0.42, 0.91, 'template'),
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == '好的'


def test_tower_daily_closes_level_up_before_reroll_navigation(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'abyss_retry'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text(
        'run_id: run-1\nphase: combat\nreroll_predecessor: true\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source=source,
        )
        for label, x, y, source in (
            ('角色升级', 0.5, 0.3, 'ocr'),
            ('好的', 0.5, 0.75, 'ocr'),
            ('下方道路', 0.42, 0.91, 'template'),
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == '好的'


def test_tower_daily_opens_settings_from_map_to_reroll_without_combat(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'abyss_retry'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text(
        'run_id: run-1\nphase: climbing_map\nreroll_predecessor: true\n'
    )
    settings = auto_play.ButtonCandidate(
        label='设置',
        x=0.94,
        y=0.47,
        confidence=0.99,
        clickability=1.8,
        source='ocr',
    )

    selection = auto_play.tower_daily_policy_candidates('tower', [settings])

    assert selection is not None
    assert selection[0].label == '设置'
    assert '直接结束' in selection[0].reason


def test_tower_daily_follows_visible_path_before_room_guess_when_rerolling(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'abyss_retry'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text(
        'run_id: run-1\nphase: climbing_map\nreroll_predecessor: true\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='右侧道路',
            x=0.92,
            y=0.74,
            confidence=0.96,
            clickability=1.8,
            source='template',
        ),
        auto_play.ButtonCandidate(
            label='Visible combat room icon',
            x=0.19,
            y=0.66,
            confidence=0.98,
            clickability=7.0,
            source='vision',
        ),
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == '右侧道路'


def test_tower_daily_enters_next_floor_before_stale_path_when_rerolling(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'abyss_retry'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text(
        'run_id: run-1\nphase: climbing_map\nreroll_predecessor: true\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.96,
            clickability=1.8,
            source=source,
        )
        for label, x, y, source in (
            ('进入下一层', 0.26, 0.69, 'ocr'),
            ('左侧道路', 0.11, 0.71, 'template'),
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == '进入下一层'


def test_tower_daily_allows_route_choice_handler_while_seeking_reroll_battle(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'abyss_retry'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text(
        'run_id: run-1\nphase: route_choice\nreroll_predecessor: true\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='下方道路',
            x=0.66,
            y=0.91,
            confidence=0.96,
            clickability=1.8,
            source='template',
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is None


def test_tower_daily_confirms_reroll_abandonment(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'abyss_retry'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text(
        'run_id: run-1\nphase: combat\nreroll_predecessor: true\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('放弃战斗冒险将以失败告终，确认放弃战斗？', 0.5, 0.5),
            ('取消', 0.3, 0.6),
            ('好的', 0.7, 0.6),
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == '好的'


def test_tower_daily_abandons_resumable_run_before_reentering(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'abyss_retry'},
    )
    run_path = tmp_path / 'games' / 'tower' / 'active_run.yaml'
    run_path.write_text(
        'run_id: run-1\nphase: complete\nreroll_predecessor: true\n'
    )
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=0.5,
            y=y,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
        for label, y in (
            ('恢复冒险', 0.54),
            ('放弃冒险', 0.62),
        )
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == '放弃冒险'
    assert '刷新前辈宝物' in selection[0].reason


def test_tower_daily_spire_enters_victory_exit(tmp_path, monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'spire_running'},
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='冒险胜利',
            x=0.70,
            y=0.69,
            confidence=0.99,
            clickability=1.6,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='下方道路',
            x=0.32,
            y=0.91,
            confidence=0.90,
            clickability=2.0,
            source='template',
        ),
    ]

    selection = auto_play.tower_daily_policy_candidates(
        'tower',
        buttons,
    )

    assert selection is not None
    assert selection[0].label == '冒险胜利'


def test_tower_daily_self_heals_to_running_on_spire_floor_hud(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-14',
            'phase': 'go_to_spire',
            'character_selected': False,
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='当前层数1/7',
            x=0.5,
            y=0.53,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        )
    ]

    auto_play.update_tower_daily_state('tower', buttons)

    state = auto_play.load_tower_daily_state('tower')
    assert state['phase'] == 'spire_running'
    assert state['character_selected'] is True


def test_tower_daily_spire_leaves_immediately_after_victory(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'spire_running'},
    )
    leave = auto_play.ButtonCandidate(
        label='马上离开（冒险者转正）',
        x=0.5,
        y=0.62,
        confidence=0.99,
        clickability=1.6,
        source='ocr',
    )
    buttons = [
        leave,
        auto_play.ButtonCandidate(
            label='再等一等',
            x=0.5,
            y=0.69,
            confidence=0.99,
            clickability=1.6,
            source='ocr',
        ),
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == leave.label


def test_tower_daily_spire_result_returns_to_inn(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {'date': '2026-09-13', 'phase': 'spire_running'},
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='游戏胜利',
            x=0.28,
            y=0.19,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='普通攻击',
            x=0.79,
            y=0.87,
            confidence=0.99,
            clickability=1.9,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='返回旅馆',
            x=0.5,
            y=0.96,
            confidence=0.99,
            clickability=1.9,
            source='ocr',
        ),
    ]

    selection = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selection is not None
    assert selection[0].label == '返回旅馆'


def test_tower_daily_result_forces_one_full_ocr_read(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-13',
            'phase': 'spire_running',
            'last_action': '马上离开（冒险者转正）',
        },
    )

    assert auto_play.tower_daily_result_requires_ocr('tower', True)
    assert not auto_play.tower_daily_result_requires_ocr('tower', False)


def test_tower_active_spire_run_uses_daily_recruited_character(
    tmp_path,
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'local_root', lambda: tmp_path)
    auto_play.write_tower_daily_state(
        'tower',
        {
            'date': '2026-09-13',
            'phase': 'spire_running',
            'recruited_character_name': '快活的卤蛋',
        },
    )
    image = Image.new('RGB', (360, 800), color='black')
    buttons = [
        auto_play.ButtonCandidate(
            label='当前层数4/7',
            x=0.53,
            y=0.53,
            confidence=1.0,
            clickability=1.0,
            source='ocr',
        )
    ]

    auto_play.update_tower_run_state('tower', image, buttons)

    state = auto_play.load_tower_run_state('tower')
    assert state['stage'] == '尖塔木屋'
    assert state['character'] == '快活的卤蛋'


def test_tower_reward_overlay_prefers_close_over_card_title():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='恭喜获得',
            x=0.5,
            y=0.15,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='迅捷攻击',
            x=0.5,
            y=0.47,
            confidence=1.0,
            clickability=1.8,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='点击空白处关闭',
            x=0.5,
            y=0.95,
            confidence=1.0,
            clickability=0.7,
            source='ocr',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={
            'preferred': ['迅捷攻击', '点击空白处关闭'],
            'avoid': [],
            'ineffective': [],
        },
        automation_config=config,
    )

    assert scored[0].label == '点击空白处关闭'


def test_tower_card_pickup_prefers_confirm_over_selected_card():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='拾取卡牌',
            x=0.5,
            y=0.08,
            confidence=1.0,
            clickability=0.2,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='普通攻击',
            x=0.82,
            y=0.58,
            confidence=1.0,
            clickability=2.0,
            source='vision',
        ),
        auto_play.ButtonCandidate(
            label='确定',
            x=0.5,
            y=0.91,
            confidence=1.0,
            clickability=0.8,
            source='ocr',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={
            'preferred': ['普通攻击', '确定'],
            'avoid': [],
            'ineffective': [],
        },
        automation_config=config,
    )

    assert scored[0].label == '确定'


def test_tower_end_turn_is_never_learned_as_ineffective():
    auto_play = load_auto_play_module()
    verification = auto_play.StateVerification(
        status='unchanged',
        reason='slow victory animation',
        attempts=4,
        threshold=0.995,
        similarities=[1.0, 1.0, 1.0, 1.0],
        progress_threshold=0.985,
        progress_similarities=[1.0, 1.0, 1.0, 1.0],
        progress_region='lower_progress_region',
    )
    button = auto_play.ButtonCandidate(
        label='结束第1回合',
        x=0.5,
        y=0.92,
        confidence=1.0,
        clickability=2.0,
        source='ocr',
    )

    assert not auto_play.should_remember_ineffective_button(
        button,
        verification,
        '## Preferred Buttons\n\n## Ineffective Buttons\n',
        automation_config(auto_play, 'tower'),
    )


def test_tower_fast_batch_uses_only_one_follow_up():
    auto_play = load_auto_play_module()
    buttons = [
        auto_play.ButtonCandidate(
            label=f'Visible playable card {index}',
            x=x,
            y=0.59,
            confidence=0.96,
            clickability=7.4,
            source='vision',
        )
        for index, x in enumerate((0.196, 0.49, 0.78), start=1)
    ]

    follow_up = auto_play.tower_fast_batch_follow_up(buttons)

    assert follow_up is not None
    assert follow_up.x == 0.196
    assert follow_up.y == 0.59
    assert follow_up.label == 'Visible playable card batch follow-up'


def test_tower_immediate_fusion_is_hard_priority():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    fusion = auto_play.ButtonCandidate(
        label='马上融合',
        x=0.2,
        y=0.5,
        confidence=0.8,
        clickability=1.0,
        source='ocr',
    )
    reward = auto_play.ButtonCandidate(
        label='不灭宝物',
        x=0.8,
        y=0.5,
        confidence=1.0,
        clickability=2.0,
        source='ocr',
    )

    scored = auto_play.score_buttons(
        [reward, fusion],
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '马上融合'


def test_tower_prefers_trainer_task_over_magic_shop_route():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=0.69,
            confidence=0.98,
            clickability=1.6,
            source='ocr',
        )
        for label, x in (('魔术商店', 0.27), ('训练师任务', 0.73))
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '训练师任务'


def test_tower_leaves_persisted_completed_shop_when_recent_history_expired(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'last_room_action': '魔术商店'},
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='上方道路',
            x=0.49,
            y=0.64,
            confidence=0.99,
            clickability=7.0,
            source='vision',
        ),
        auto_play.ButtonCandidate(
            label='魔术商店',
            x=0.27,
            y=0.69,
            confidence=0.99,
            clickability=1.6,
            source='ocr',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
        recent_actions=['确定', '放弃', '返回'],
    )
    decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.65,
        ambiguity_margin=0.2,
        ask_on_ambiguous=False,
        automation_config=config,
    )

    assert decision.recommended.label == '上方道路'
    assert 'Leave recently completed Tower room' in decision.recommended.reason


def test_tower_map_avoids_arrow_attached_to_completed_shop(monkeypatch):
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'stage': '深渊楼梯',
            'phase': 'climbing_map',
            'floor': 20,
            'last_room_action': '金币商店',
            'completed_shop_keys': ['20:金币商店'],
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='金币商店',
            x=0.272,
            y=0.688,
            confidence=0.99,
            clickability=1.6,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='左侧道路',
            x=0.192,
            y=0.733,
            confidence=0.99,
            clickability=7.0,
            source='vision',
        ),
        auto_play.ButtonCandidate(
            label='上方道路',
            x=0.510,
            y=0.700,
            confidence=0.86,
            clickability=1.0,
            source='template',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '上方道路'
    left = next(button for button in scored if button.label == '左侧道路')
    assert 'attached to a completed Tower shop' in left.reason


def test_tower_prebattle_does_not_treat_enemy_name_as_map_room():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='战斗',
            x=0.715,
            y=0.948,
            confidence=0.99,
            clickability=5.0,
            source='vision',
        ),
        auto_play.ButtonCandidate(
            label='护盾·金币哥布林',
            x=0.50,
            y=0.214,
            confidence=0.97,
            clickability=1.8,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='即将发起战斗',
            x=0.49,
            y=0.10,
            confidence=0.99,
            clickability=1.8,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='下方道路',
            x=0.44,
            y=0.91,
            confidence=0.90,
            clickability=0.8,
            source='template',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '战斗'
    enemy = next(
        button for button in scored if button.label == '护盾·金币哥布林'
    )
    assert enemy.score < scored[0].score


def test_tower_prefers_mystery_shop_when_only_shop_routes_remain():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=0.69,
            confidence=0.98,
            clickability=1.6,
            source='ocr',
        )
        for label, x in (('金币商店', 0.70), ('神秘商店', 0.27))
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '神秘商店'


def test_tower_map_with_change_rooms_can_still_choose_enhancement_room():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.6,
            source='ocr',
        )
        for label, x, y in (
            ('BOSS战补给', 0.26, 0.70),
            ('强化法阵', 0.70, 0.70),
            ('遗忘法阵', 0.49, 0.77),
            ('变化法阵', 0.27, 0.85),
            ('变化法阵', 0.71, 0.85),
        )
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={
            'preferred': ['强化法阵'],
            'avoid': ['遗忘法阵'],
            'ineffective': [],
        },
        automation_config=config,
    )

    assert scored[0].label == '强化法阵'


def test_tower_prefers_boss_supply_over_change_rooms():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.6,
            source='ocr',
        )
        for label, x, y in (
            ('BOSS战补给', 0.26, 0.70),
            ('变化法阵', 0.27, 0.85),
            ('变化法阵', 0.71, 0.85),
        )
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={
            'preferred': ['BOSS战补给'],
            'avoid': [],
            'ineffective': [],
        },
        automation_config=config,
    )

    assert scored[0].label == 'BOSS战补给'


def test_tower_sold_out_shop_prefers_return():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('生命商店', 0.5, 0.34),
            ('商品已售馨', 0.5, 0.60),
            ('点击【刷新】补货！', 0.5, 0.63),
            ('返回', 0.27, 0.88),
        )
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': ['返回']},
        automation_config=config,
    )

    assert scored[0].label == '返回'


def test_tower_magic_shop_uses_cheapest_change_array():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=2.0,
            source='ocr',
        )
        for label, x, y in (
            ('魔术商店', 0.5, 0.34),
            ('变化法阵', 0.5, 0.68),
            ('确定', 0.72, 0.88),
            ('返回', 0.27, 0.88),
        )
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '变化法阵'


def test_tower_magic_shop_confirms_default_selected_free_array():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=2.0,
            source='ocr',
        )
        for label, x, y in (
            ('魔术商店', 0.5, 0.34),
            ('免费1次', 0.13, 0.27),
            ('变化法阵', 0.2, 0.51),
            ('变化法阵', 0.5, 0.51),
            ('变化法阵', 0.8, 0.51),
            ('变化法阵', 0.2, 0.69),
            ('变化法阵', 0.5, 0.69),
            ('变化法阵', 0.8, 0.69),
            ('确定', 0.72, 0.88),
            ('返回', 0.27, 0.88),
        )
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '确定'


def test_tower_card_change_selects_junk_then_confirms(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'stage': '深渊楼梯',
            'profession': '旅行者',
        },
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=2.0,
            source='ocr',
        )
        for label, x, y in (
            ('卡牌变化', 0.5, 0.12),
            ('慈悲', 0.5, 0.42),
            ('变化', 0.72, 0.84),
            ('返回', 0.28, 0.84),
        )
    ]

    select = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
        recent_actions=['变化法阵'],
    )
    change = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
        recent_actions=['变化法阵', '慈悲'],
    )

    assert select[0].label == '慈悲'
    assert change[0].label == '变化'


def test_tower_card_forgetting_selects_junk_then_confirms(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'stage': '深渊楼梯',
            'profession': '旅行者',
        },
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=2.0,
            source='ocr',
        )
        for label, x, y in (
            ('卡牌遗忘', 0.5, 0.12),
            ('慈悲', 0.5, 0.42),
            ('许愿！', 0.5, 0.47),
            ('无限宝石', 0.5, 0.52),
            ('遗忘', 0.72, 0.84),
            ('返回', 0.28, 0.84),
        )
    ]

    select = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
        recent_actions=['遗忘法阵'],
    )
    forget = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
        recent_actions=['遗忘法阵', '慈悲'],
    )

    assert select[0].label == '许愿！'
    assert forget[0].label == '遗忘'


def test_tower_card_forgetting_confirms_when_detail_header_is_missing(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'stage': '深渊楼梯', 'profession': '法师'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=0.84,
            confidence=0.98,
            clickability=2.0,
            source='ocr',
        )
        for label, x in (('遗忘', 0.72), ('返回', 0.28))
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
        recent_actions=['遗忘法阵', 'Tower cull choice: 虚弱'],
    )

    assert scored[0].label == '遗忘'


def test_tower_card_forgetting_grid_culls_mage_junk_and_protects_cycle(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'stage': '深渊楼梯', 'profession': '法师'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=2.0,
            source='ocr',
        )
        for label, x, y in (
            ('卡牌遗忘', 0.5, 0.12),
            ('虚弱II', 0.21, 0.27),
            ('快速思考II', 0.21, 0.57),
            ('小雷虫', 0.79, 0.57),
            ('闪电晶石II', 0.50, 0.72),
            ('返回', 0.5, 0.92),
        )
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={
            'preferred': ['快速思考II', '小雷虫', '闪电晶石II'],
            'avoid': [],
            'ineffective': [],
        },
        automation_config=config,
        recent_actions=['遗忘法阵'],
    )

    assert scored[0].label == '虚弱II'
    assert auto_play.tower_card_cull_bonus('tower', '快速思考II') == 0.0
    assert auto_play.tower_card_cull_bonus('tower', '小雷虫') == 0.0
    assert auto_play.tower_card_cull_bonus('tower', '寒冷晶石') == 0.0
    assert auto_play.tower_card_cull_bonus('tower', '雷龙') == 0.0


def test_tower_card_forgetting_culls_warrior_starters_and_protects_weakness_cycle(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'stage': '深渊楼梯', 'profession': '战士'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=2.0,
            source='ocr',
        )
        for label, x, y in (
            ('卡牌遗忘', 0.5, 0.12),
            ('普通攻击', 0.21, 0.27),
            ('举盾', 0.79, 0.27),
            ('弱点打击！', 0.50, 0.42),
            ('迅捷！', 0.50, 0.57),
            ('攻击宝石', 0.79, 0.72),
            ('返回', 0.5, 0.92),
        )
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={
            'preferred': ['弱点打击！', '迅捷！', '攻击宝石'],
            'avoid': [],
            'ineffective': [],
        },
        automation_config=config,
        recent_actions=['遗忘法阵'],
    )

    assert scored[0].label == '举盾'
    assert auto_play.tower_card_cull_bonus('tower', '普通攻击') > 0.0
    assert auto_play.tower_card_cull_bonus('tower', '弱点打击！') == 0.0
    assert auto_play.tower_card_cull_bonus('tower', '迅捷！') == 0.0
    assert auto_play.tower_card_cull_bonus('tower', '攻击宝石') == 0.0


def test_tower_stairs_choose_card_forgetting_route():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=2.0,
            source='ocr',
        )
        for label, x, y in (
            ('选择一个楼梯', 0.5, 0.30),
            ('左侧楼梯', 0.26, 0.39),
            ('信息点', 0.25, 0.44),
            ('右侧楼梯', 0.75, 0.39),
            ('卡牌遗忘', 0.82, 0.44),
            ('确定', 0.73, 0.71),
        )
    ]

    candidate = auto_play.tower_stair_choice_candidate(config, buttons)

    assert candidate is not None
    assert candidate.label == '右侧楼梯'


def test_tower_traveler_mystery_shop_buys_cycle_consumable(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'stage': '深渊楼梯',
            'profession': '旅行者',
        },
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        )
        for label, x, y in (
            ('神秘商店', 0.5, 0.34),
            ('过期药水', 0.2, 0.69),
            ('宝石药水', 0.5, 0.69),
            ('唤回药水', 0.8, 0.69),
            ('确定', 0.72, 0.88),
            ('返回', 0.27, 0.88),
        )
    ]
    memory = {'preferred': [], 'avoid': [], 'ineffective': []}

    select = auto_play.score_buttons(
        buttons,
        memory=memory,
        automation_config=config,
        recent_actions=[],
    )
    confirm = auto_play.score_buttons(
        buttons,
        memory=memory,
        automation_config=config,
        recent_actions=['唤回药水'],
    )

    assert select[0].label == '唤回药水'
    assert confirm[0].label == '确定'


def test_tower_coin_pouch_shop_prefers_return_over_repeat_purchase():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        )
        for label, x, y in (
            ('钱袋商店', 0.5, 0.34),
            ('金币钱袋', 0.5, 0.51),
            ('确定', 0.72, 0.88),
            ('返回', 0.27, 0.88),
        )
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '返回'


def test_tower_coin_shop_fusion_attempt_then_confirm_then_exit():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=2.0,
            source='ocr',
        )
        for label, x, y in (
            ('金币商店', 0.5, 0.34),
            ('马上融合', 0.87, 0.57),
            ('确定', 0.72, 0.88),
            ('返回', 0.27, 0.88),
        )
    ]
    memory = {'preferred': [], 'avoid': [], 'ineffective': []}

    select = auto_play.score_buttons(
        buttons,
        memory=memory,
        automation_config=config,
        recent_actions=[],
    )
    confirm = auto_play.score_buttons(
        buttons,
        memory=memory,
        automation_config=config,
        recent_actions=['马上融合'],
    )
    leave = auto_play.score_buttons(
        buttons,
        memory=memory,
        automation_config=config,
        recent_actions=['马上融合', '确定'],
    )

    assert select[0].label == '马上融合'
    assert confirm[0].label == '确定'
    assert leave[0].label == '返回'
    assert 'Tower shop fusion' in select[0].reason
    assert 'Tower shop fusion' in confirm[0].reason


def test_tower_card_change_uses_abandon_to_exit_over_stale_back_template():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='卡牌变化',
            x=0.5,
            y=0.12,
            confidence=0.99,
            clickability=1.9,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='放弃',
            x=0.5,
            y=0.92,
            confidence=0.99,
            clickability=1.9,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='返回',
            x=0.78,
            y=0.96,
            confidence=0.86,
            clickability=0.5,
            source='template',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '放弃'


def test_tower_card_change_uses_back_when_abandon_is_ocr_as_back():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='卡牌变化',
            x=0.5,
            y=0.12,
            confidence=0.99,
            clickability=1.9,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='迅捷攻击',
            x=0.5,
            y=0.42,
            confidence=0.99,
            clickability=1.9,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='变化',
            x=0.72,
            y=0.84,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='返回',
            x=0.28,
            y=0.84,
            confidence=0.99,
            clickability=1.9,
            source='ocr',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={
            'preferred': ['迅捷攻击'],
            'avoid': [],
            'ineffective': [],
        },
        automation_config=config,
    )

    assert scored[0].label == '返回'


def test_tower_trainer_prefers_level_up_dodge_task(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: None)
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='训练师任务',
            x=0.5,
            y=0.09,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='猪手本能 见习冒险者升级时：闪避+1',
            x=0.3,
            y=0.61,
            confidence=0.95,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='游盗车厢 战斗开始时加入随机道具牌',
            x=0.3,
            y=0.71,
            confidence=0.95,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='毒性思考 每使用1张卡牌获得1层毒',
            x=0.3,
            y=0.82,
            confidence=0.95,
            clickability=1.5,
            source='ocr',
        ),
        *[
            auto_play.ButtonCandidate(
                label='选择',
                x=0.82,
                y=y,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            )
            for y in (0.62, 0.72, 0.825)
        ],
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '选择'
    assert scored[0].y == 0.62


def test_tower_electric_mage_trainer_prefers_immortal_heart(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '法师')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'predecessor_treasure': '电虫药水'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='训练师任务',
            x=0.5,
            y=0.09,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        *[
            auto_play.ButtonCandidate(
                label=label,
                x=0.3,
                y=y,
                confidence=0.96,
                clickability=1.6,
                source='ocr',
            )
            for label, y in (
                ('战斗胜利3次', 0.574),
                ('火纹', 0.601),
                ('冒险中，直接获得4张新卡牌', 0.679),
                ('骑士之力', 0.704),
                ('见习冒险者获得宝物时：生命上限+8', 0.733),
                ('冒险中，直接获得1张3级卡牌', 0.781),
                ('不朽之心', 0.808),
                ('战斗中，每减少5点生命，获得1层再生', 0.836),
            )
        ],
        *[
            auto_play.ButtonCandidate(
                label='选择',
                x=0.82,
                y=y,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            )
            for y in (0.617, 0.72, 0.825)
        ],
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '选择'
    assert scored[0].y == 0.825


def test_tower_electric_mage_avoids_lone_warrior_attack_penalty(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '法师')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'predecessor_treasure': '电虫药水'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='训练师任务',
            x=0.5,
            y=0.09,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='获得4个水晶 生死对决',
            x=0.3,
            y=0.61,
            confidence=0.96,
            clickability=1.6,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='直接获得2张防御牌 独孤求败 敌方物攻增加100点',
            x=0.3,
            y=0.71,
            confidence=0.96,
            clickability=1.6,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='获得6个水晶 灵巧身法',
            x=0.3,
            y=0.82,
            confidence=0.96,
            clickability=1.6,
            source='ocr',
        ),
        *[
            auto_play.ButtonCandidate(
                label='选择',
                x=0.82,
                y=y,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            )
            for y in (0.62, 0.72, 0.825)
        ],
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '选择'
    assert scored[0].y != 0.72


def test_tower_trainer_never_disables_future_encounters(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '法师')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'predecessor_treasure': '电虫药水'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='训练师任务',
            x=0.5,
            y=0.09,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='本次冒险不想遇到该训练师',
            x=0.77,
            y=0.5425,
            confidence=0.92,
            clickability=1.7,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='冒险中，直接获得5张新卡牌 金币子弹',
            x=0.3,
            y=0.60,
            confidence=0.96,
            clickability=1.6,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='冒险中，直接获得2张3级卡牌 双枪',
            x=0.3,
            y=0.70,
            confidence=0.96,
            clickability=1.6,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='完成2层冒险 牛牌气 卡牌使用后不会被移除',
            x=0.3,
            y=0.81,
            confidence=0.96,
            clickability=1.6,
            source='ocr',
        ),
        *[
            auto_play.ButtonCandidate(
                label='选择',
                x=0.82,
                y=y,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            )
            for y in (0.617, 0.72, 0.825)
        ],
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )
    decision = auto_play.decide_next_move(
        scored,
        min_action_score=0.5,
        ambiguity_margin=0.25,
        ask_on_ambiguous=False,
        automation_config=config,
    )

    assert auto_play.tower_deep_map_room_bonus(
        '本次冒险不想遇到该训练师'
    ) == -20.0
    assert decision.recommended.label == '选择'
    assert decision.recommended.y == 0.825


def test_tower_electric_mage_prefers_energy_conversion_over_mutant_bloodline(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '法师')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'predecessor_treasure': '电虫药水'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='训练师任务',
            x=0.5,
            y=0.09,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        *[
            auto_play.ButtonCandidate(
                label=label,
                x=0.3,
                y=y,
                confidence=0.96,
                clickability=1.6,
                source='ocr',
            )
            for label, y in (
                ('击败1只精英怪', 0.574),
                ('变异血统', 0.601),
                ('战斗中增加物攻时：增加5点生命上限', 0.629),
                ('获得100个金币', 0.678),
                ('能量转换', 0.704),
                ('每2点法力转换为1点护盾', 0.726),
                ('回合开始时每3点护盾转换为1点法力', 0.738),
                ('直接获得3张防御牌', 0.782),
                ('身体强化', 0.808),
                ('第1个回合开始时：获得10点护盾', 0.836),
            )
        ],
        *[
            auto_play.ButtonCandidate(
                label='选择',
                x=0.82,
                y=y,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            )
            for y in (0.617, 0.72, 0.825)
        ],
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '选择'
    assert scored[0].y == 0.72


def test_tower_traveler_trainer_prefers_bull_temper(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='训练师任务',
            x=0.5,
            y=0.09,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='牛脾气 移除牌不再移除',
            x=0.3,
            y=0.61,
            confidence=0.95,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='毒性思考 每使用1张卡牌获得1层毒',
            x=0.3,
            y=0.71,
            confidence=0.95,
            clickability=1.5,
            source='ocr',
        ),
        *[
            auto_play.ButtonCandidate(
                label='选择',
                x=0.82,
                y=y,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            )
            for y in (0.62, 0.72)
        ],
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '选择'
    assert scored[0].y == 0.62


def test_tower_traveler_trainer_prefers_plant_essence_over_bull_temper(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'predecessor_treasure': '毒龙匕首'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='训练师任务',
            x=0.5,
            y=0.09,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='牛脾气 移除牌不再移除',
            x=0.3,
            y=0.61,
            confidence=0.95,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='植物精华 中毒层数不会在回合结束时衰减',
            x=0.3,
            y=0.71,
            confidence=0.95,
            clickability=1.5,
            source='ocr',
        ),
        *[
            auto_play.ButtonCandidate(
                label='选择',
                x=0.82,
                y=y,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            )
            for y in (0.62, 0.72)
        ],
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '选择'
    assert scored[0].y == 0.72


def test_tower_hunter_trainer_prefers_quick_cast_over_bull_temper(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '猎人')
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='训练师任务',
            x=0.5,
            y=0.09,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='牛脾气 移除牌不再移除',
            x=0.3,
            y=0.61,
            confidence=0.95,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='快速施法 战斗开始时触发瞬发牌',
            x=0.3,
            y=0.71,
            confidence=0.95,
            clickability=1.5,
            source='ocr',
        ),
        *[
            auto_play.ButtonCandidate(
                label='选择',
                x=0.82,
                y=y,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            )
            for y in (0.62, 0.72)
        ],
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '选择'
    assert scored[0].y == 0.72


def test_tower_traveler_trainer_prefers_crystal_meditation_over_element_sense(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='训练师任务',
            x=0.5,
            y=0.09,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='晶体冥想 每装备1张宝石牌获得专注',
            x=0.3,
            y=0.71,
            confidence=0.95,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='元素感应 加入随机元素宝石',
            x=0.3,
            y=0.82,
            confidence=0.95,
            clickability=1.5,
            source='ocr',
        ),
        *[
            auto_play.ButtonCandidate(
                label='选择',
                x=0.82,
                y=y,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            )
            for y in (0.72, 0.825)
        ],
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '选择'
    assert scored[0].y == 0.72


def test_tower_traveler_trainer_says_goodbye_without_build_synergy(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {'predecessor_treasure': '花喇叭'},
    )
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='训练师任务',
            x=0.5,
            y=0.09,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='告别',
            x=0.78,
            y=0.515,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='神奇口袋 将5张贩售机加入道具口袋',
            x=0.3,
            y=0.81,
            confidence=0.95,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='直接获得2张防御牌',
            x=0.3,
            y=0.78,
            confidence=0.95,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='选择',
            x=0.82,
            y=0.825,
            confidence=0.99,
            clickability=2.0,
            source='ocr',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '告别'


def test_tower_traveler_trainer_avoids_five_card_condition(monkeypatch):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(auto_play, 'tower_run_profession', lambda _game: '旅行者')
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='训练师任务',
            x=0.5,
            y=0.09,
            confidence=1.0,
            clickability=2.0,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='战斗胜利3次 生死对决',
            x=0.3,
            y=0.61,
            confidence=0.95,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='完成2层冒险 独孤求败 敌方物攻增加100点',
            x=0.3,
            y=0.71,
            confidence=0.95,
            clickability=1.5,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='直接获得5张新卡牌 灵巧身法',
            x=0.3,
            y=0.82,
            confidence=0.95,
            clickability=1.5,
            source='ocr',
        ),
        *[
            auto_play.ButtonCandidate(
                label='选择',
                x=0.82,
                y=y,
                confidence=0.99,
                clickability=2.0,
                source='ocr',
            )
            for y in (0.62, 0.72, 0.825)
        ],
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '选择'
    assert scored[0].y == 0.62


def test_tower_card_upgrade_prefers_draw_engine_and_never_header():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('卡牌强化', 0.5, 0.12),
            ('医疗人偶', 0.5, 0.56),
            ('杂念', 0.21, 0.72),
            ('以物易物I', 0.79, 0.56),
            ('返回', 0.5, 0.92),
        )
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '以物易物I'
    assert scored[-1].label == '卡牌强化'


def test_tower_card_fusion_panel_gets_local_confirm_candidate():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label=label,
            x=x,
            y=y,
            confidence=0.98,
            clickability=1.8,
            source='ocr',
        )
        for label, x, y in (
            ('涂毒小刀', 0.28, 0.42),
            ('涂毒小刀II', 0.73, 0.42),
            ('消耗2张相同的牌进行融合，并且获得水晶', 0.49, 0.77),
            ('返回', 0.28, 0.84),
            ('融合', 0.72, 0.84),
        )
    ]

    candidates = auto_play.tower_card_fusion_candidates(config, buttons)

    assert len(candidates) == 1
    assert candidates[0].label == '融合'
    assert candidates[0].source == 'vision'


def test_tower_leaves_a_room_after_its_event_was_recently_used():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='神秘交易',
            x=0.27,
            y=0.69,
            confidence=0.98,
            clickability=1.65,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='左侧道路',
            x=0.10,
            y=0.75,
            confidence=0.94,
            clickability=1.13,
            source='template',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
        recent_actions=['神秘交易', '拿走前辈的宝物'],
    )

    assert scored[0].label == '左侧道路'


def test_tower_talking_stairs_takes_abyss_dragon_blood():
    auto_play = load_auto_play_module()
    config = automation_config(auto_play, 'tower')
    buttons = [
        auto_play.ButtonCandidate(
            label='说话的楼梯',
            x=0.5,
            y=0.35,
            confidence=1.0,
            clickability=1.8,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='告别楼梯，拿走深渊龙血',
            x=0.5,
            y=0.62,
            confidence=0.96,
            clickability=1.6,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='拿走前辈的宝物',
            x=0.45,
            y=0.58,
            confidence=0.85,
            clickability=1.2,
            source='template',
        ),
    ]

    scored = auto_play.score_buttons(
        buttons,
        memory={'preferred': [], 'avoid': [], 'ineffective': []},
        automation_config=config,
    )

    assert scored[0].label == '告别楼梯，拿走深渊龙血'


def test_tower_daily_policy_takes_talking_stairs_dragon_blood_before_stale_room(
    monkeypatch,
):
    auto_play = load_auto_play_module()
    monkeypatch.setattr(
        auto_play,
        'load_tower_daily_state',
        lambda _game: {'phase': 'abyss'},
    )
    monkeypatch.setattr(
        auto_play,
        'load_tower_run_state',
        lambda _game: {
            'stage': '深渊楼梯',
            'phase': 'climbing_map',
            'floor': 20,
        },
    )
    buttons = [
        auto_play.ButtonCandidate(
            label='说话的楼梯',
            x=0.5,
            y=0.35,
            confidence=1.0,
            clickability=1.8,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='告别楼梯，拿走深渊龙血',
            x=0.5,
            y=0.62,
            confidence=0.96,
            clickability=1.6,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='和楼梯再呆一会儿',
            x=0.5,
            y=0.69,
            confidence=0.98,
            clickability=1.6,
            source='ocr',
        ),
        auto_play.ButtonCandidate(
            label='拿走前辈的宝物',
            x=0.45,
            y=0.58,
            confidence=0.85,
            clickability=1.2,
            source='template',
        ),
    ]

    selected = auto_play.tower_daily_policy_candidates('tower', buttons)

    assert selected is not None
    assert selected[0].label == '告别楼梯，拿走深渊龙血'
    assert selected[0].clickability == 25.0

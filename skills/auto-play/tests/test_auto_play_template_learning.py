import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

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


def test_ad_revive_cancel_beats_stale_card_templates_without_prompt_ocr():
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

    assert scored[0].label == 'Cancel'
    assert scored[-1].label == '观看'


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


def test_recruit_beats_adventure_when_no_adventurer_is_available():
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

    assert scored[0].label == '招募'


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


def test_tower_treasure_panel_selects_real_card_before_confirming():
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

    choice = auto_play.tower_treasure_choice_candidate(
        config,
        [back, confirm, stale_card],
    )

    assert choice is not None
    assert choice.label == 'Right treasure choice'
    assert not auto_play.is_inspectable_item_candidate(
        back,
        fallback_labels=set(),
        avoid_labels=set(),
        ineffective_labels=set(),
        automation_config=config,
    )


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


def test_tower_map_room_detector_prefers_concrete_room_over_arrows():
    auto_play = load_auto_play_module()
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


def test_tower_current_room_detector_beats_stale_lower_route():
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

    assert [button.label for button in candidates] == ['Visible current room icon']
    assert scored[0].label == 'Visible current room icon'


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


def test_inspect_item_choices_selects_best_item_then_recommends_confirm(
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

    assert clicks == ['Royal Training', 'Quick Spark', 'Royal Training']
    assert [item.candidate.label for item in inspections] == [
        'Royal Training',
        'Quick Spark',
    ]
    assert decision is not None
    assert decision.recommended.label == 'Confirm'
    assert decision.choices[0].label == 'Royal Training'
    assert artifact_paths['item_inspections'].exists()
    knowledge = (tmp_path / 'games' / 'tower' / 'game_info.md').read_text()
    assert '### item' in knowledge
    assert '| 1 | Royal Training |' in knowledge
    assert 'Permanent attack +1' in knowledge
    assert knowledge.index('Royal Training') < knowledge.index('Quick Spark')


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

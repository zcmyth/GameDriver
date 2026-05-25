import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def load_image_analyzer_module():
    path = Path(__file__).resolve().parents[1] / 'scripts'
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    spec = importlib.util.spec_from_file_location(
        'image_analyzer_script', path / 'image_analyzer.py'
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class EmptyReader:
    def predict(self, _image):
        return []


def build_analyzer(analyzer_cls, template_dir, threshold=0.8):
    analyzer = object.__new__(analyzer_cls)
    analyzer.reader = EmptyReader()
    analyzer.noise_text_patterns = []
    analyzer.template_dirs = [template_dir]
    analyzer.template_match_threshold = threshold
    analyzer.template_configs = {}
    analyzer.navigation_template_labels = {
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
    analyzer.navigation_template_keywords = (
        ' arrow',
        ' path',
        ' route',
        ' road',
    )
    analyzer.navigation_template_glyphs = ('↑', '↓', '←', '→')
    return analyzer


def test_template_images_are_reported_as_clickable_locations(tmp_path):
    image_analyzer = load_image_analyzer_module()

    screenshot = Image.new('RGB', (120, 120), color='black')
    draw = ImageDraw.Draw(screenshot)
    draw.rectangle((30, 50, 70, 86), fill='white')
    draw.rectangle((42, 60, 58, 76), fill='black')
    draw.line((30, 50, 70, 86), fill='gray', width=2)

    templates_dir = tmp_path / 'images'
    templates_dir.mkdir()
    screenshot.crop((30, 50, 70, 86)).save(templates_dir / 'fight-button--fixture.png')

    analyzer = build_analyzer(image_analyzer.PaddleOCRAnalyzer, templates_dir)

    locations = analyzer.extract_text_locations(screenshot, confidence_threshold=0.9)

    match = next(item for item in locations if item['source'] == 'template')
    assert match['text'] == 'fight button'
    assert 0.40 <= match['x'] <= 0.45
    assert 0.55 <= match['y'] <= 0.60
    assert match['confidence'] >= 0.8
    assert match['score'] > match['confidence']
    assert match['bbox']['x1'] < match['x'] < match['bbox']['x2']
    assert match['bbox']['y1'] < match['y'] < match['bbox']['y2']


def test_visual_score_rewards_brighter_matching_crop(tmp_path):
    image_analyzer = load_image_analyzer_module()
    analyzer = build_analyzer(image_analyzer.PaddleOCRAnalyzer, tmp_path)

    dim = Image.new('RGB', (32, 32), color=(50, 50, 50))
    bright = Image.new('RGB', (32, 32), color=(180, 180, 180))

    dim_score = analyzer._visual_clickability_score(image_analyzer.np.array(dim))
    bright_score = analyzer._visual_clickability_score(image_analyzer.np.array(bright))

    assert bright_score > dim_score


def test_template_click_center_uses_highlighted_component(tmp_path):
    image_analyzer = load_image_analyzer_module()

    screenshot = Image.new('RGB', (120, 160), color=(20, 24, 26))
    draw = ImageDraw.Draw(screenshot)
    draw.rectangle((78, 28, 100, 52), fill=(90, 60, 35))
    draw.ellipse((70, 92, 112, 134), fill=(40, 120, 120), outline=(210, 255, 255))
    draw.polygon((88, 104, 88, 122, 104, 113), fill=(245, 255, 255))

    templates_dir = tmp_path / 'images'
    templates_dir.mkdir()
    screenshot.crop((62, 24, 116, 140)).save(templates_dir / 'right-road.png')

    analyzer = build_analyzer(image_analyzer.PaddleOCRAnalyzer, templates_dir)

    locations = analyzer.extract_text_locations(screenshot, confidence_threshold=0.9)

    match = next(item for item in locations if item['source'] == 'template')
    bbox_center_y = (match['bbox']['y1'] + match['bbox']['y2']) / 2
    assert match['y'] > bbox_center_y
    assert 0.65 <= match['y'] <= 0.78


def test_stat_delta_text_is_not_clickable_ocr_text(tmp_path):
    image_analyzer = load_image_analyzer_module()
    analyzer = build_analyzer(image_analyzer.PaddleOCRAnalyzer, tmp_path)
    analyzer.noise_text_patterns = image_analyzer.NOISE_TEXT_PATTERNS

    assert analyzer._looks_like_noise_text('±2')
    assert analyzer._looks_like_noise_text('+4')
    assert analyzer._looks_like_noise_text('-5')
    assert analyzer._looks_like_noise_text('QQ')
    assert analyzer._looks_like_noise_text('QQ0')
    assert analyzer._looks_like_noise_text('BEA')
    assert analyzer._looks_like_noise_text('x1')
    assert analyzer._looks_like_noise_text('i2')
    assert analyzer._looks_like_noise_text('(%)')
    assert analyzer._looks_like_noise_text('CM')
    assert analyzer._looks_like_noise_text('50 >> 52')
    assert analyzer._looks_like_noise_text('36/50]')
    assert analyzer._looks_like_noise_text('[6')
    assert analyzer._looks_like_noise_text('Lv.1')
    assert analyzer._looks_like_noise_text('>>')
    assert not analyzer._looks_like_noise_text('END')
    assert not analyzer._looks_like_noise_text('OK')


def test_template_matching_preserves_color_distinctions(tmp_path):
    image_analyzer = load_image_analyzer_module()

    screenshot = Image.new('RGB', (160, 80), color='black')
    draw = ImageDraw.Draw(screenshot)
    draw.rectangle((20, 20, 60, 60), fill=(100, 0, 0))
    draw.rectangle((100, 20, 140, 60), fill=(0, 0, 255))
    draw.line((20, 20, 60, 60), fill='white', width=2)
    draw.line((100, 20, 140, 60), fill='white', width=2)

    templates_dir = tmp_path / 'images'
    templates_dir.mkdir()
    screenshot.crop((100, 20, 140, 60)).save(templates_dir / 'blue-room.png')

    analyzer = build_analyzer(image_analyzer.PaddleOCRAnalyzer, templates_dir)

    locations = analyzer.extract_text_locations(screenshot, confidence_threshold=0.9)

    match = next(item for item in locations if item['source'] == 'template')
    assert match['text'] == 'blue room'
    assert 0.70 <= match['x'] <= 0.80


def test_navigation_templates_get_lower_match_threshold(tmp_path):
    image_analyzer = load_image_analyzer_module()
    analyzer = build_analyzer(image_analyzer.PaddleOCRAnalyzer, tmp_path)

    analyzer.navigation_template_labels.add('右侧道路')
    arrow_threshold = analyzer._template_match_threshold_for_label('右侧道路')
    card_threshold = analyzer._template_match_threshold_for_label('弱点打击')

    assert arrow_threshold < analyzer.template_match_threshold
    assert arrow_threshold <= 0.74
    assert card_threshold == analyzer.template_match_threshold


def test_template_config_can_override_match_threshold(tmp_path):
    image_analyzer = load_image_analyzer_module()
    analyzer = build_analyzer(image_analyzer.PaddleOCRAnalyzer, tmp_path, threshold=0.8)
    analyzer.template_configs = {
        'battle active skill': {
            'match_threshold': 0.38,
        }
    }

    assert analyzer._template_match_threshold_for_label('battle active skill') == 0.38


def test_template_config_roi_limits_search_area(tmp_path):
    image_analyzer = load_image_analyzer_module()

    screenshot = Image.new('RGB', (160, 100), color='black')
    draw = ImageDraw.Draw(screenshot)
    draw.rectangle((10, 30, 40, 60), fill='white')
    draw.line((10, 30, 40, 60), fill='gray', width=3)
    draw.rectangle((115, 30, 145, 60), fill='white')
    draw.line((115, 30, 145, 60), fill='gray', width=3)

    templates_dir = tmp_path / 'images'
    templates_dir.mkdir()
    screenshot.crop((10, 30, 40, 60)).save(templates_dir / 'battle-active-skill.png')

    analyzer = build_analyzer(image_analyzer.PaddleOCRAnalyzer, templates_dir)
    analyzer.template_configs = {
        'battle active skill': {
            'match_threshold': 0.8,
            'search_roi': [0.6, 0.0, 1.0, 1.0],
        }
    }

    locations = analyzer.extract_text_locations(screenshot, confidence_threshold=0.9)

    match = next(item for item in locations if item['source'] == 'template')
    assert match['text'] == 'battle active skill'
    assert 0.78 <= match['x'] <= 0.86

from PIL import Image, ImageDraw

from game_driver.image_analyzer import PaddleOCRAnalyzer


class EmptyReader:
    def predict(self, _image):
        return []


def build_analyzer(template_dir, threshold=0.8):
    analyzer = object.__new__(PaddleOCRAnalyzer)
    analyzer.reader = EmptyReader()
    analyzer.noise_text_patterns = []
    analyzer.template_dirs = [template_dir]
    analyzer.template_match_threshold = threshold
    return analyzer


def test_template_images_are_reported_as_clickable_locations(tmp_path):
    screenshot = Image.new('RGB', (120, 120), color='black')
    draw = ImageDraw.Draw(screenshot)
    draw.rectangle((30, 50, 70, 86), fill='white')
    draw.rectangle((42, 60, 58, 76), fill='black')
    draw.line((30, 50, 70, 86), fill='gray', width=2)

    templates_dir = tmp_path / 'images'
    templates_dir.mkdir()
    screenshot.crop((30, 50, 70, 86)).save(templates_dir / 'fight-button--fixture.png')

    analyzer = build_analyzer(templates_dir)

    locations = analyzer.extract_text_locations(screenshot, confidence_threshold=0.9)

    match = next(item for item in locations if item['source'] == 'template')
    assert match['text'] == 'fight button'
    assert 0.40 <= match['x'] <= 0.45
    assert 0.55 <= match['y'] <= 0.60
    assert match['confidence'] >= 0.8
    assert match['bbox']['x1'] < match['x'] < match['bbox']['x2']
    assert match['bbox']['y1'] < match['y'] < match['bbox']['y2']

from pathlib import Path

from PIL import Image, ImageDraw

from game_driver.template_matcher import TemplateMatcher


def _make_test_images(tmp_path: Path):
    screenshot = Image.new('RGB', (200, 200), color='black')
    draw = ImageDraw.Draw(screenshot)

    # Draw a distinctive icon-like pattern to avoid ambiguous template matches.
    draw.rectangle((60, 80, 100, 120), fill='white')
    draw.rectangle((72, 92, 88, 108), fill='black')

    template = screenshot.crop((60, 80, 100, 120))

    screenshot_path = tmp_path / 'screen.png'
    template_path = tmp_path / 'btn.png'
    screenshot.save(screenshot_path)
    template.save(template_path)
    return screenshot, template, template_path


def test_template_match_from_path(tmp_path):
    screenshot, _template, template_path = _make_test_images(tmp_path)
    matcher = TemplateMatcher()

    match = matcher.match(screenshot, template_path, threshold=0.8)

    assert match is not None
    assert 0.25 <= match['x'] <= 0.55
    assert 0.35 <= match['y'] <= 0.75


def test_template_match_from_registered_name(tmp_path):
    screenshot, _template, template_path = _make_test_images(tmp_path)
    matcher = TemplateMatcher()
    matcher.register_template('button', template_path)

    match = matcher.match(screenshot, 'button', threshold=0.8)

    assert match is not None
    assert match['confidence'] >= 0.8


def test_register_template_image_supports_in_memory_templates(tmp_path):
    screenshot, template, _template_path = _make_test_images(tmp_path)
    matcher = TemplateMatcher()
    matcher.register_template_image('button', template)

    match = matcher.match(screenshot, 'button', threshold=0.8)

    assert match is not None
    assert match['confidence'] >= 0.8


def test_find_all_returns_ranked_matches(tmp_path):
    screenshot = Image.new('RGB', (240, 120), color='black')
    draw = ImageDraw.Draw(screenshot)
    draw.rectangle((20, 20, 60, 60), fill='white')
    draw.rectangle((160, 20, 200, 60), fill='white')

    template = screenshot.crop((20, 20, 60, 60))

    matcher = TemplateMatcher()
    matcher.register_template_image('box', template)

    matches = matcher.find_all(screenshot, 'box', threshold=0.95)

    assert len(matches) >= 2
    assert matches[0]['confidence'] >= matches[1]['confidence']

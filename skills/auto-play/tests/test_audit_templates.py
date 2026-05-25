import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def load_audit_module():
    path = Path(__file__).resolve().parents[1] / 'scripts'
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    spec = importlib.util.spec_from_file_location(
        'audit_templates_script', path / 'audit_templates.py'
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_duplicate_decisions_keep_higher_quality_same_label(tmp_path):
    audit = load_audit_module()
    images_dir = tmp_path / 'images'
    images_dir.mkdir()

    crisp = Image.new('RGB', (60, 60), color='black')
    draw = ImageDraw.Draw(crisp)
    draw.rectangle((8, 8, 52, 52), fill='white')
    draw.line((8, 8, 52, 52), fill='black', width=3)
    crisp.save(images_dir / 'fight.png')

    padded = Image.new('RGB', (120, 120), color='black')
    padded.paste(crisp, (30, 30))
    padded.save(images_dir / 'fight--02.png')

    templates = [
        audit.inspect_template(images_dir / 'fight.png'),
        audit.inspect_template(images_dir / 'fight--02.png'),
    ]

    removals, reviews = audit.duplicate_decisions(
        templates,
        same_label_threshold=0.80,
        cross_label_threshold=0.95,
        dedupe_cross_label=False,
    )

    assert reviews == []
    assert len(removals) == 1
    assert removals[0].keep.path.name == 'fight.png'
    assert removals[0].remove.path.name == 'fight--02.png'


def test_llm_crop_actions_apply_normalized_bbox(tmp_path):
    audit = load_audit_module()
    images_dir = tmp_path / 'images'
    images_dir.mkdir()
    image_path = images_dir / 'card.png'
    Image.new('RGB', (100, 200), color='white').save(image_path)
    crops_path = tmp_path / 'crops.yaml'
    crops_path.write_text(
        """
crops:
  - path: card.png
    template_bbox:
      x1: 0.1
      y1: 0.2
      x2: 0.6
      y2: 0.7
"""
    )

    actions = audit.apply_llm_crops(crops_path, images_dir=images_dir, apply=True)

    assert len(actions) == 1
    assert Image.open(image_path).size == (50, 100)


def test_suspicious_reasons_allow_focused_card_and_text_hint():
    audit = load_audit_module()

    card = Image.new('RGB', (90, 160), color=(12, 18, 24))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((2, 2, 87, 157), radius=4, fill=(55, 142, 170))
    draw.rectangle((8, 105, 82, 135), fill=(230, 220, 170))
    draw.text((28, 113), 'card', fill='black')
    card_mask = audit.active_pixels(card)

    hint = Image.new('RGB', (82, 30), color=(8, 8, 8))
    draw = ImageDraw.Draw(hint)
    draw.text((10, 10), 'close', fill=(92, 92, 92))
    hint_mask = audit.active_pixels(hint)

    assert audit.suspicious_reasons(card, card_mask) == ()
    assert audit.suspicious_reasons(hint, hint_mask) == ()

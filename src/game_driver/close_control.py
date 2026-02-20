import re


DEFAULT_TEXT_PATTERNS = (
    re.compile(r'^x$'),
    re.compile(r'^×$'),
    re.compile(r'^close$'),
    re.compile(r'^skip$'),
    re.compile(r'^cancel$'),
)


def is_corner_close_candidate(item):
    x = float(item.get('x', 0.0))
    y = float(item.get('y', 1.0))
    return (x >= 0.84 and y <= 0.23) or (x <= 0.16 and y <= 0.23)


def try_click_close_control(
    engine,
    *,
    icon_templates=(),
    text_patterns=DEFAULT_TEXT_PATTERNS,
    min_confidence=0.82,
    glyph_min_confidence=0.9,
):
    textual_hits = []
    for item in engine.text_locations:
        if item.get('confidence', 0) < min_confidence:
            continue
        text = str(item.get('text', '')).strip().lower()
        if any(pattern.search(text) for pattern in text_patterns):
            textual_hits.append(item)

    for hit in textual_hits:
        if is_corner_close_candidate(hit):
            engine.click(hit['x'], hit['y'], wait=False)
            return True, 'close_text_corner'

    if textual_hits:
        hit = sorted(textual_hits, key=lambda x: x.get('confidence', 0), reverse=True)[0]
        engine.click(hit['x'], hit['y'], wait=False)
        return True, 'close_text'

    for item in engine.text_locations:
        if item.get('confidence', 0) < glyph_min_confidence:
            continue
        text = str(item.get('text', '')).strip().lower()
        if len(text) > 2:
            continue
        if text in {'x', '×', '+'} and is_corner_close_candidate(item):
            engine.click(item['x'], item['y'], wait=False)
            return True, 'close_glyph_corner'

    for template in icon_templates:
        try:
            if engine.try_click_template(template, threshold=0.88):
                return True, str(template)
        except (KeyError, FileNotFoundError, ValueError):
            continue

    engine.click(0.92, 0.08, False)
    engine.click(0.50, 0.10, False)
    return True, 'close_safe_tap'

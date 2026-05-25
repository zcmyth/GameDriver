import re
from abc import ABC, abstractmethod
from pathlib import Path

import cv2
import numpy as np
from paddleocr import PaddleOCR
from PIL import ImageDraw

PROMPT = """
Extract text with center coordinates and confidence.
   Return the results as a JSON array in this exact format:
   [{"text": "example text", "x": 200, "y": 300, "confidence": 0.9}].
   Try grouping text based on the UI component boundaries.
   Order button text to the top of the list.
   Ignore text that is grayed out and cannot be clicked.
   The coordinates should be in the very center of those text and UI
   component boundaries.
"""


NOISE_TEXT_PATTERNS = [
    re.compile(r'^@\s*\d{2,}$'),
    re.compile(r'^\d{1,2}\s*-\s*\d{1,2}$'),
    re.compile(r'^[±+\-]\s*\d+([.]\d+)?%?[;；]?$'),
    re.compile(r'^q{2,}\d*$', re.I),
    re.compile(r'^\d+[./:]?\d*[kmb]?$'),
    re.compile(r'^lv[.\s]*\d+$', re.I),
    re.compile(r'^[+\-]?\d+[./:]\d+$'),
    re.compile(r'^\d+\s*>{1,2}\s*\d+$'),
    re.compile(r'^[\[(]?\s*\d+\s*/\s*\d+\s*[\])]?$'),
    re.compile(r'^[\[(]\s*\d+\s*[\])]?$'),
    re.compile(r'^[x×]\s*\d+$', re.I),
    re.compile(r'^[a-z]\s*\d+$', re.I),
    re.compile(r'^[()\[\]{}%.,:;!?+\-*/\\|_~<>]+$'),
    re.compile(r'^season\s*\d+', re.I),
]
ACTION_SHORT_WORDS = {'end', 'go', 'ok'}
NAVIGATION_TEMPLATE_LABELS = {
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
NAVIGATION_TEMPLATE_KEYWORDS = (
    ' arrow',
    ' path',
    ' route',
    ' road',
)
NAVIGATION_TEMPLATE_GLYPHS = ('↑', '↓', '←', '→')


def cached_paddle_model_dir(model_name: str) -> Path | None:
    model_dir = Path.home() / '.paddlex' / 'official_models' / model_name
    if (model_dir / 'inference.yml').exists() and (
        model_dir / 'inference.pdiparams'
    ).exists():
        return model_dir
    return None


def draw_text_locations(image, text_locations):
    overlay_image = image.copy()
    draw = ImageDraw.Draw(overlay_image)

    for i, item in enumerate(text_locations):
        text = item['text']
        confidence = item['confidence']

        # Draw center point
        center_x = int(item['x'] * image.width)
        center_y = int(item['y'] * image.height)
        radius = 4
        draw.ellipse(
            [
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
            ],
            fill='blue',
            outline='white',
            width=2,
        )

        # Draw text with background rectangle
        text_content = f'{i + 1}: {text}({confidence:.2f})'
        text_x = center_x + radius + 7
        text_y = center_y - radius - 2

        # Get text size for background rectangle
        bbox = draw.textbbox((text_x, text_y), text_content)

        # Draw background rectangle
        draw.rectangle(
            [bbox[0] - 3, bbox[1] - 3, bbox[2] + 3, bbox[3] + 3],
            fill='white',
            outline='black',
            width=1,
        )

        # Draw text on top
        draw.text((text_x, text_y), text_content, fill='black')

    return overlay_image


class ImageAnalyzer(ABC):
    @abstractmethod
    def extract_text_locations(self, image, confidence_threshold=0.5):
        pass


class PaddleOCRAnalyzer(ImageAnalyzer):
    def __init__(
        self,
        template_dirs: list[str | Path] | None = None,
        template_match_threshold: float = 0.82,
        template_configs: dict | None = None,
        noise_text_patterns: list[str | re.Pattern] | None = None,
        navigation_template_labels: list[str] | None = None,
        navigation_template_keywords: list[str] | None = None,
        navigation_template_glyphs: list[str] | None = None,
    ):
        det_model_name = 'PP-OCRv5_mobile_det'
        rec_model_name = 'en_PP-OCRv5_mobile_rec'
        ocr_kwargs = {
            'lang': 'en',
            'use_doc_orientation_classify': False,
            'use_doc_unwarping': False,
            'use_textline_orientation': False,
        }
        det_model_dir = cached_paddle_model_dir(det_model_name)
        rec_model_dir = cached_paddle_model_dir(rec_model_name)
        if det_model_dir is not None:
            ocr_kwargs['text_detection_model_name'] = det_model_name
            ocr_kwargs['text_detection_model_dir'] = str(det_model_dir)
        else:
            ocr_kwargs['text_detection_model_name'] = det_model_name
        if rec_model_dir is not None:
            ocr_kwargs['text_recognition_model_name'] = rec_model_name
            ocr_kwargs['text_recognition_model_dir'] = str(rec_model_dir)
        else:
            ocr_kwargs['text_recognition_model_name'] = rec_model_name
        self.reader = PaddleOCR(**ocr_kwargs)
        self.noise_text_patterns = [*NOISE_TEXT_PATTERNS]
        for pattern in noise_text_patterns or []:
            if hasattr(pattern, 'search'):
                self.noise_text_patterns.append(pattern)
                continue
            try:
                self.noise_text_patterns.append(re.compile(str(pattern), re.I))
            except re.error:
                continue
        self.template_dirs = [Path(path) for path in template_dirs or []]
        self.template_match_threshold = template_match_threshold
        self.template_configs = self._normalized_template_configs(
            template_configs or {}
        )
        self.navigation_template_labels = {
            re.sub(r'\s+', ' ', label.strip().lower())
            for label in [
                *NAVIGATION_TEMPLATE_LABELS,
                *(navigation_template_labels or []),
            ]
            if label.strip()
        }
        self.navigation_template_keywords = tuple(
            keyword.strip().lower()
            for keyword in [
                *NAVIGATION_TEMPLATE_KEYWORDS,
                *(navigation_template_keywords or []),
            ]
            if keyword.strip()
        )
        self.navigation_template_glyphs = tuple(
            glyph.strip()
            for glyph in [
                *NAVIGATION_TEMPLATE_GLYPHS,
                *(navigation_template_glyphs or []),
            ]
            if glyph.strip()
        )

    def _bbox_slice(self, img_array, x_coords, y_coords):
        h, w = img_array.shape[:2]
        x1 = max(0, min(w - 1, int(np.floor(min(x_coords)))))
        x2 = max(0, min(w, int(np.ceil(max(x_coords)))))
        y1 = max(0, min(h - 1, int(np.floor(min(y_coords)))))
        y2 = max(0, min(h, int(np.ceil(max(y_coords)))))
        if x2 <= x1 or y2 <= y1:
            return None
        return img_array[y1:y2, x1:x2]

    def _visual_clickability_score(self, crop):
        if crop is None or crop.size == 0:
            return 0.0

        gray, sat = self._gray_and_saturation(crop)
        brightness = float(np.mean(gray) / 255.0)
        highlight = float(np.percentile(gray, 90) / 255.0)
        contrast = float(np.std(gray) / 255.0)
        saturation = float(np.mean(sat))

        # Bright/glowing UI controls are often the enabled route while dimmer
        # copies of the same icon remain visible but unavailable.
        score = (
            (1.6 * contrast)
            + (1.1 * saturation)
            + (0.7 * brightness)
            + (0.9 * highlight)
        )
        return float(min(2.0, score))

    @staticmethod
    def _gray_and_saturation(crop):
        pixels = crop.astype(np.float32)
        if pixels.ndim == 2:
            gray = pixels
            sat = np.zeros_like(gray)
        else:
            r = pixels[..., 0]
            g = pixels[..., 1]
            b = pixels[..., 2]
            maxc = np.maximum(np.maximum(r, g), b)
            minc = np.minimum(np.minimum(r, g), b)
            gray = 0.299 * r + 0.587 * g + 0.114 * b
            sat = (maxc - minc) / np.maximum(maxc, 1.0)
        return gray, sat

    def _visual_click_center(self, crop, default_x, default_y):
        if crop is None or crop.size == 0:
            return default_x, default_y

        gray, sat = self._gray_and_saturation(crop)
        if gray.size == 0:
            return default_x, default_y

        bright_threshold = max(120.0, float(np.percentile(gray, 88)))
        sat_threshold = max(0.18, float(np.percentile(sat, 82)))
        mask = ((gray >= bright_threshold) | (sat >= sat_threshold)).astype(np.uint8)
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            np.ones((3, 3), dtype=np.uint8),
        )
        labels_count, labels, stats, centroids = cv2.connectedComponentsWithStats(
            mask,
            connectivity=8,
        )
        if labels_count <= 1:
            return default_x, default_y

        min_area = max(6, int(gray.size * 0.01))
        components = [
            index
            for index in range(1, labels_count)
            if stats[index, cv2.CC_STAT_AREA] >= min_area
        ]
        if not components:
            return default_x, default_y

        center_x = (crop.shape[1] - 1) / 2.0
        center_y = (crop.shape[0] - 1) / 2.0
        best = max(
            components,
            key=lambda index: (
                stats[index, cv2.CC_STAT_AREA],
                -abs(float(centroids[index][0]) - center_x),
                -abs(float(centroids[index][1]) - center_y),
            ),
        )
        return float(centroids[best][0]), float(centroids[best][1])

    @staticmethod
    def _template_label(path):
        label = path.stem.split('--', 1)[0]
        return label.replace('-', ' ').strip()

    @staticmethod
    def _normalized_template_label(value):
        return re.sub(r'\s+', ' ', str(value).strip().lower())

    def _normalized_template_configs(self, template_configs):
        templates = template_configs.get('templates', template_configs)
        if not isinstance(templates, dict):
            return {}
        normalized = {}
        for label, options in templates.items():
            if not isinstance(options, dict):
                continue
            normalized[self._normalized_template_label(label)] = options
        return normalized

    def _template_config_for_label(self, label):
        return self.template_configs.get(self._normalized_template_label(label), {})

    def _is_navigation_template_label(self, label):
        normalized = re.sub(r'\s+', ' ', label.strip().lower())
        if normalized in self.navigation_template_labels:
            return True
        if any(glyph in normalized for glyph in self.navigation_template_glyphs):
            return True
        return any(
            keyword in normalized for keyword in self.navigation_template_keywords
        )

    def _template_match_threshold_for_label(self, label):
        config = self._template_config_for_label(label)
        configured = config.get('match_threshold', config.get('threshold'))
        if configured is not None:
            try:
                return max(0.0, min(1.0, float(configured)))
            except (TypeError, ValueError):
                pass
        if self._is_navigation_template_label(label):
            return max(0.72, self.template_match_threshold - 0.08)
        return self.template_match_threshold

    def _template_search_roi_for_label(self, label, width, height):
        config = self._template_config_for_label(label)
        roi = config.get('search_roi', config.get('roi'))
        if isinstance(roi, str):
            roi = [part.strip() for part in re.split(r'[,| ]+', roi) if part.strip()]
        if isinstance(roi, (list, tuple)) and len(roi) == 4:
            try:
                left, top, right, bottom = (float(value) for value in roi)
            except (TypeError, ValueError):
                return 0, 0, width, height
            x1 = max(0, min(width - 1, int(round(left * width))))
            y1 = max(0, min(height - 1, int(round(top * height))))
            x2 = max(x1 + 1, min(width, int(round(right * width))))
            y2 = max(y1 + 1, min(height, int(round(bottom * height))))
            return x1, y1, x2, y2
        return 0, 0, width, height

    def _template_paths(self):
        for directory in self.template_dirs:
            if not directory.exists():
                continue
            yield from sorted(directory.glob('*.png'))

    def _template_locations(self, img_array, width, height):
        if not self.template_dirs:
            return []

        if img_array.ndim == 2:
            screenshot = img_array
            template_read_flag = cv2.IMREAD_GRAYSCALE
        else:
            screenshot = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            template_read_flag = cv2.IMREAD_COLOR

        locations = []
        for template_path in self._template_paths():
            label = self._template_label(template_path)
            template = cv2.imread(str(template_path), template_read_flag)
            if template is None:
                continue

            template_height, template_width = template.shape[:2]
            if (
                template_width < 4
                or template_height < 4
                or template_width > width
                or template_height > height
            ):
                continue

            roi_x1, roi_y1, roi_x2, roi_y2 = self._template_search_roi_for_label(
                label,
                width,
                height,
            )
            search_area = screenshot[roi_y1:roi_y2, roi_x1:roi_x2]
            if (
                search_area.shape[1] < template_width
                or search_area.shape[0] < template_height
            ):
                continue

            matches = cv2.matchTemplate(
                search_area,
                template,
                cv2.TM_CCOEFF_NORMED,
            )
            _, confidence, _, top_left = cv2.minMaxLoc(matches)
            if confidence < self._template_match_threshold_for_label(label):
                continue

            x1, y1 = top_left
            x1 += roi_x1
            y1 += roi_y1
            x2 = x1 + template_width
            y2 = y1 + template_height
            crop = self._bbox_slice(img_array, [x1, x2], [y1, y2])
            clickability = self._visual_clickability_score(crop)
            default_click_x = template_width / 2
            default_click_y = template_height / 2
            click_x, click_y = self._visual_click_center(
                crop,
                default_click_x,
                default_click_y,
            )
            locations.append(
                {
                    'text': label,
                    'x': (x1 + click_x) / width,
                    'y': (y1 + click_y) / height,
                    'bbox': {
                        'x1': x1 / width,
                        'y1': y1 / height,
                        'x2': x2 / width,
                        'y2': y2 / height,
                    },
                    'confidence': float(confidence),
                    'char_size': float(template_width * template_height),
                    'clickability': clickability,
                    'score': float(confidence + clickability),
                    'source': 'template',
                    'template_path': str(template_path),
                }
            )
        return locations

    def _looks_like_noise_text(self, text):
        raw = text.strip()
        norm = raw.lower()
        if not norm:
            return True
        if len(norm) <= 1:
            return True
        if re.fullmatch(r'[A-Z]{2,3}', raw) and norm not in ACTION_SHORT_WORDS:
            return True
        return any(p.search(norm) for p in self.noise_text_patterns)

    @staticmethod
    def _dedupe_similar_locations(results, min_dist=0.03):
        deduped = []
        for item in sorted(results, key=lambda x: x['confidence'], reverse=True):
            keep = True
            for existing in deduped:
                same_text = (
                    item['text'].strip().lower() == existing['text'].strip().lower()
                )
                close_x = abs(item['x'] - existing['x']) <= min_dist
                close_y = abs(item['y'] - existing['y']) <= min_dist
                if same_text and close_x and close_y:
                    keep = False
                    break
            if keep:
                deduped.append(item)
        return deduped

    def extract_text_locations(self, image, confidence_threshold=0.8):
        width, height = image.size

        # Convert PIL image to numpy array
        img_array = np.array(image)

        # Use PaddleOCR to detect text
        # PaddleOCR 3.3.0 returns OCRResult with dt_polys, rec_texts, rec_scores
        results_raw = self.reader.predict(img_array)

        results = []

        if results_raw and results_raw[0]:
            ocr_result = results_raw[0]
            bboxes = ocr_result['dt_polys']
            texts = ocr_result['rec_texts']
            confidences = ocr_result['rec_scores']

            for bbox, text, confidence in zip(bboxes, texts, confidences):
                if confidence <= confidence_threshold:
                    continue

                if self._looks_like_noise_text(text):
                    continue

                # Calculate center from bounding box
                # bbox format: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                x_coords, y_coords = zip(*bbox)
                center_x = float(sum(x_coords) / len(x_coords))
                center_y = float(sum(y_coords) / len(y_coords))

                crop = self._bbox_slice(img_array, x_coords, y_coords)
                clickability = self._visual_clickability_score(crop)

                # Filter likely disabled / greyed-out text.
                if clickability < 0.10:
                    continue

                # Calculate character size for sorting
                bbox_width = float(max(x_coords) - min(x_coords))
                bbox_height = float(max(y_coords) - min(y_coords))
                bbox_area = bbox_width * bbox_height
                char_count = len(text.strip())
                char_size = bbox_area / char_count if char_count > 0 else 0.0

                results.append(
                    {
                        'text': text,
                        'x': center_x / width,
                        'y': center_y / height,
                        'bbox': {
                            'x1': float(min(x_coords)) / width,
                            'y1': float(min(y_coords)) / height,
                            'x2': float(max(x_coords)) / width,
                            'y2': float(max(y_coords)) / height,
                        },
                        'confidence': float(confidence),
                        'char_size': char_size,
                        'clickability': clickability,
                        'score': float(confidence + clickability),
                        'source': 'ocr',
                    }
                )

        results.extend(self._template_locations(img_array, width, height))

        # Sort with clickable-looking candidates first.
        results.sort(
            key=lambda x: (x['clickability'], x['confidence'], x['char_size']),
            reverse=True,
        )

        # Remove internal-only fields from final results
        for result in results:
            result.pop('char_size', None)

        # Remove near-duplicate OCR hits that often happen on stylized UI text.
        return self._dedupe_similar_locations(results)


def create_analyzer(
    template_dirs: list[str | Path] | None = None,
    template_match_threshold: float = 0.82,
    template_configs: dict | None = None,
    noise_text_patterns: list[str | re.Pattern] | None = None,
    navigation_template_labels: list[str] | None = None,
    navigation_template_keywords: list[str] | None = None,
    navigation_template_glyphs: list[str] | None = None,
):
    return PaddleOCRAnalyzer(
        template_dirs=template_dirs,
        template_match_threshold=template_match_threshold,
        template_configs=template_configs,
        noise_text_patterns=noise_text_patterns,
        navigation_template_labels=navigation_template_labels,
        navigation_template_keywords=navigation_template_keywords,
        navigation_template_glyphs=navigation_template_glyphs,
    )

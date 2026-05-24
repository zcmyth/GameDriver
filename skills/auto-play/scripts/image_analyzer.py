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
    ):
        self.reader = PaddleOCR(
            lang='en',
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_recognition_model_name='en_PP-OCRv5_mobile_rec',
            text_detection_model_name='PP-OCRv5_mobile_det',
        )
        self.noise_text_patterns = [
            re.compile(r'^\d+[./:]?\d*[kmb]?$'),
            re.compile(r'^[+\-]?\d+[./:]\d+$'),
            re.compile(r'^season\s*\d+', re.I),
        ]
        self.template_dirs = [Path(path) for path in template_dirs or []]
        self.template_match_threshold = template_match_threshold

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

        brightness = float(np.mean(gray) / 255.0)
        contrast = float(np.std(gray) / 255.0)
        saturation = float(np.mean(sat))

        # Greys + low-contrast regions are usually disabled labels.
        score = (1.8 * contrast) + (1.2 * saturation) + (0.2 * brightness)
        return score

    @staticmethod
    def _template_label(path):
        label = path.stem.split('--', 1)[0]
        return label.replace('-', ' ').strip()

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
        else:
            screenshot = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        locations = []
        for template_path in self._template_paths():
            template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
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

            matches = cv2.matchTemplate(
                screenshot,
                template,
                cv2.TM_CCOEFF_NORMED,
            )
            _, confidence, _, top_left = cv2.minMaxLoc(matches)
            if confidence < self.template_match_threshold:
                continue

            x1, y1 = top_left
            x2 = x1 + template_width
            y2 = y1 + template_height
            crop = self._bbox_slice(img_array, [x1, x2], [y1, y2])
            locations.append(
                {
                    'text': self._template_label(template_path),
                    'x': (x1 + (template_width / 2)) / width,
                    'y': (y1 + (template_height / 2)) / height,
                    'bbox': {
                        'x1': x1 / width,
                        'y1': y1 / height,
                        'x2': x2 / width,
                        'y2': y2 / height,
                    },
                    'confidence': float(confidence),
                    'char_size': float(template_width * template_height),
                    'clickability': self._visual_clickability_score(crop),
                    'source': 'template',
                    'template_path': str(template_path),
                }
            )
        return locations

    def _looks_like_noise_text(self, text):
        norm = text.strip().lower()
        if not norm:
            return True
        if len(norm) <= 1:
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
):
    return PaddleOCRAnalyzer(
        template_dirs=template_dirs,
        template_match_threshold=template_match_threshold,
    )

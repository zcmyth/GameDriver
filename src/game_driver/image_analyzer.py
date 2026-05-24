import re
from abc import ABC, abstractmethod

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
    def __init__(self):
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

    def _normalized_crop(self, img_array, x, y, half_width, half_height):
        h, w = img_array.shape[:2]
        center_x = x * w
        center_y = y * h
        return self._bbox_slice(
            img_array,
            [center_x - (half_width * w), center_x + (half_width * w)],
            [center_y - (half_height * h), center_y + (half_height * h)],
        )

    @staticmethod
    def _is_near_existing_result(results, x, y, min_dist=0.055):
        return any(
            abs(item['x'] - x) <= min_dist and abs(item['y'] - y) <= min_dist
            for item in results
        )

    def _visual_action_hints(self, img_array, width, height, results):
        if height <= width:
            return []

        hotspots = [
            ('Adventure', 0.500, 0.925, 0.18, 0.045),
            ('Dismiss Reward', 0.500, 0.925, 0.18, 0.045),
            ('Next Room', 0.500, 0.925, 0.18, 0.045),
            ('Enter Adventure', 0.500, 0.817, 0.18, 0.045),
            ('Resume Adventure', 0.500, 0.548, 0.20, 0.050),
            ('Pick Up Weapon', 0.500, 0.616, 0.18, 0.050),
            ('Take Treasure', 0.500, 0.618, 0.18, 0.050),
            ('Confirm', 0.735, 0.698, 0.14, 0.055),
            ('Confirm Selected Card', 0.735, 0.698, 0.14, 0.055),
            ('Merge Weapon', 0.762, 0.838, 0.14, 0.050),
            ('Merge Card', 0.762, 0.838, 0.14, 0.050),
            ('Battle Focus', 0.770, 0.432, 0.16, 0.085),
            ('Next Room', 0.492, 0.586, 0.07, 0.045),
            ('Map Left Arrow', 0.108, 0.708, 0.08, 0.055),
            ('Chest', 0.276, 0.646, 0.11, 0.075),
            ('Professional Backpack', 0.500, 0.715, 0.12, 0.080),
            ('Normal Sword', 0.728, 0.646, 0.11, 0.075),
            ('Scroll Room', 0.805, 0.641, 0.12, 0.080),
            ('Scroll Room', 0.806, 0.666, 0.12, 0.080),
            ('Move Right', 0.850, 0.265, 0.12, 0.080),
            ('Obtained Loot', 0.887, 0.526, 0.10, 0.065),
            ('visual bottom action', 0.500, 0.925, 0.18, 0.045),
            ('visual primary button', 0.500, 0.817, 0.18, 0.045),
            ('visual middle button', 0.500, 0.548, 0.20, 0.050),
            ('visual card action', 0.500, 0.616, 0.18, 0.050),
            ('visual card confirm', 0.735, 0.698, 0.14, 0.055),
            ('visual upgrade action', 0.762, 0.838, 0.14, 0.050),
            ('visual right card', 0.770, 0.432, 0.16, 0.085),
            ('visual map connector', 0.492, 0.586, 0.07, 0.045),
            ('visual map left arrow', 0.108, 0.708, 0.08, 0.055),
            ('visual left room', 0.276, 0.646, 0.11, 0.075),
            ('visual center room', 0.500, 0.715, 0.12, 0.080),
            ('visual right room', 0.728, 0.646, 0.11, 0.075),
            ('visual upper right room', 0.805, 0.641, 0.12, 0.080),
            ('visual lower right room', 0.806, 0.666, 0.12, 0.080),
            ('visual right path', 0.850, 0.265, 0.12, 0.080),
            ('visual loot button', 0.887, 0.526, 0.10, 0.065),
        ]

        hints = []
        for label, x, y, half_width, half_height in hotspots:
            if self._is_near_existing_result(results, x, y):
                continue
            crop = self._normalized_crop(img_array, x, y, half_width, half_height)
            clickability = self._visual_clickability_score(crop)
            hints.append(
                {
                    'text': label,
                    'x': x,
                    'y': y,
                    'confidence': 0.62,
                    'char_size': (width * half_width * height * half_height) / 6,
                    'clickability': max(0.20, clickability),
                }
            )
        return hints

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

        # PaddleOCR returns empty list if no text detected
        if not results_raw or not results_raw[0]:
            return results

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
                    'confidence': float(confidence),
                    'char_size': char_size,
                    'clickability': clickability,
                }
            )

        results.extend(self._visual_action_hints(img_array, width, height, results))

        # Sort with clickable-looking candidates first.
        results.sort(
            key=lambda x: (x['clickability'], x['confidence'], x['char_size']),
            reverse=True,
        )

        # Remove internal-only fields from final results
        for result in results:
            del result['char_size']

        # Remove near-duplicate OCR hits that often happen on stylized UI text.
        return self._dedupe_similar_locations(results)


def create_analyzer():
    return PaddleOCRAnalyzer()

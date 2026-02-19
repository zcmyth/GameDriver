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

    @staticmethod
    def _dedupe_similar_locations(results, min_dist=0.03):
        deduped = []
        for item in sorted(results, key=lambda x: x['confidence'], reverse=True):
            keep = True
            for existing in deduped:
                same_text = (
                    item['text'].strip().lower()
                    == existing['text'].strip().lower()
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
            if confidence > confidence_threshold:
                # Calculate center from bounding box
                # bbox format: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                x_coords, y_coords = zip(*bbox)
                center_x = sum(x_coords) / len(x_coords)
                center_y = sum(y_coords) / len(y_coords)

                # Calculate character size for sorting
                bbox_width = max(x_coords) - min(x_coords)
                bbox_height = max(y_coords) - min(y_coords)
                bbox_area = bbox_width * bbox_height
                char_count = len(text.strip())
                char_size = bbox_area / char_count if char_count > 0 else 0

                results.append(
                    {
                        'text': text,
                        'x': center_x / width,
                        'y': center_y / height,
                        'confidence': confidence,
                        'char_size': char_size,
                    }
                )

        # Sort by character size (largest first)
        results.sort(key=lambda x: x['char_size'], reverse=True)

        # Remove char_size from final results
        for result in results:
            del result['char_size']

        # Remove near-duplicate OCR hits that often happen on stylized UI text.
        return self._dedupe_similar_locations(results)


def create_analyzer():
    return PaddleOCRAnalyzer()

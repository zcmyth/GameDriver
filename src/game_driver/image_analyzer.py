from abc import ABC, abstractmethod

import cv2
import easyocr
import numpy as np
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


class EasyOCRAnalyzer(ImageAnalyzer):
    def __init__(self):
        self.reader = easyocr.Reader(['en'])

    def extract_text_locations(self, image, confidence_threshold=0.3):
        width, height = image.size

        # Convert PIL image to numpy array
        img_array = np.array(image)

        # Use EasyOCR to detect text
        results_raw = self.reader.readtext(img_array)

        results = []
        for bbox, text, confidence in results_raw:
            if confidence > confidence_threshold:
                # Calculate center from bounding box
                x_coords = [point[0] for point in bbox]
                y_coords = [point[1] for point in bbox]
                center_x = sum(x_coords) / len(x_coords)
                center_y = sum(y_coords) / len(y_coords)

                # Check if text is greyed out
                try:
                    if self._is_greyed_out(img_array, bbox):
                        continue
                except Exception:
                    # ignore errors in greyed-out detection
                    pass

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

        return results

    def _is_greyed_out(self, img_array, bbox):
        # Extract text region
        x_coords = [point[0] for point in bbox]
        y_coords = [point[1] for point in bbox]
        x1, y1 = int(min(x_coords)), int(min(y_coords))
        x2, y2 = int(max(x_coords)), int(max(y_coords))

        # Crop text region
        text_region = img_array[y1:y2, x1:x2]

        # Convert to grayscale
        gray = cv2.cvtColor(text_region, cv2.COLOR_RGB2GRAY)

        # Calculate contrast (standard deviation)
        contrast = np.std(gray)

        # Low contrast indicates greyed out text
        return contrast < 30


def create_analyzer():
    return EasyOCRAnalyzer()

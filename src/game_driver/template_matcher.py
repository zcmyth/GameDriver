from pathlib import Path

import cv2
import numpy as np


class TemplateMatcher:
    def __init__(self):
        self._templates = {}

    def _template_record(self, path, template):
        return {
            'path': Path(path) if path is not None else None,
            'image': template,
            'width': template.shape[1],
            'height': template.shape[0],
        }

    def register_template(self, name, template_path):
        path = Path(template_path)
        if not path.exists():
            raise FileNotFoundError(f'Template not found: {path}')

        template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            raise ValueError(f'Failed to load template image: {path}')

        self._templates[name] = self._template_record(path, template)

    def register_template_image(self, name, template_image):
        template = np.array(template_image)
        if len(template.shape) == 3:
            template = cv2.cvtColor(template, cv2.COLOR_RGB2GRAY)
        if len(template.shape) != 2:
            raise ValueError('Template image must be a grayscale or RGB image.')
        self._templates[name] = self._template_record(None, template)

    def _resolve_template(self, name_or_path):
        if name_or_path in self._templates:
            return self._templates[name_or_path]

        path = Path(name_or_path)
        if path.exists():
            template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if template is None:
                raise ValueError(f'Failed to load template image: {path}')
            return self._template_record(path, template)

        raise KeyError(
            f'Unknown template "{name_or_path}". Register it or pass a valid path.'
        )

    def _to_grayscale(self, screenshot):
        screenshot_np = np.array(screenshot)
        if len(screenshot_np.shape) == 2:
            return screenshot_np
        return cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)

    def match(
        self,
        screenshot,
        name_or_path,
        threshold=0.88,
        method=cv2.TM_CCOEFF_NORMED,
    ):
        template_data = self._resolve_template(name_or_path)

        screenshot_gray = self._to_grayscale(screenshot)
        result = cv2.matchTemplate(
            screenshot_gray,
            template_data['image'],
            method,
        )
        _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val < threshold:
            return None

        top_left_x, top_left_y = max_loc
        center_x = top_left_x + template_data['width'] / 2
        center_y = top_left_y + template_data['height'] / 2

        height, width = screenshot_gray.shape
        return {
            'x': center_x / width,
            'y': center_y / height,
            'confidence': float(max_val),
            'template': (
                str(template_data['path'])
                if template_data['path'] is not None
                else str(name_or_path)
            ),
        }

    def find_all(self, screenshot, name_or_path, threshold=0.88):
        template_data = self._resolve_template(name_or_path)
        screenshot_gray = self._to_grayscale(screenshot)

        result = cv2.matchTemplate(
            screenshot_gray,
            template_data['image'],
            cv2.TM_CCOEFF_NORMED,
        )

        y_idx, x_idx = np.where(result >= threshold)
        height, width = screenshot_gray.shape
        matches = []

        for y, x in zip(y_idx, x_idx):
            center_x = x + template_data['width'] / 2
            center_y = y + template_data['height'] / 2
            matches.append(
                {
                    'x': center_x / width,
                    'y': center_y / height,
                    'confidence': float(result[y, x]),
                    'template': (
                        str(template_data['path'])
                        if template_data['path'] is not None
                        else str(name_or_path)
                    ),
                }
            )

        matches.sort(key=lambda x: x['confidence'], reverse=True)
        return matches

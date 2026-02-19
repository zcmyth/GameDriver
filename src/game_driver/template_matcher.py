import re
from pathlib import Path

import cv2
import numpy as np


_DIMENSION_SUFFIX = re.compile(r'^(?P<name>.+?)__(?P<width>\d+)x(?P<height>\d+)$')


class TemplateMatcher:
    def __init__(self):
        self._templates = {}

    def _template_record(self, path, template, source_width=None, source_height=None):
        return {
            'path': Path(path) if path is not None else None,
            'image': template,
            'width': template.shape[1],
            'height': template.shape[0],
            'source_width': source_width,
            'source_height': source_height,
        }

    def _parse_name_with_dimensions(self, raw_name):
        match = _DIMENSION_SUFFIX.match(raw_name)
        if not match:
            return raw_name, None, None
        return (
            match.group('name'),
            int(match.group('width')),
            int(match.group('height')),
        )

    def register_template(self, name, template_path):
        path = Path(template_path)
        if not path.exists():
            raise FileNotFoundError(f'Template not found: {path}')

        template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            raise ValueError(f'Failed to load template image: {path}')

        clean_name, source_width, source_height = self._parse_name_with_dimensions(
            str(name)
        )
        self._templates[clean_name] = self._template_record(
            path,
            template,
            source_width=source_width,
            source_height=source_height,
        )

    def register_from_folder(self, folder_path):
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            raise FileNotFoundError(f'Template folder not found: {folder}')

        count = 0
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}:
                continue
            raw_name = path.stem
            self.register_template(raw_name, path)
            count += 1
        return count

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

    def _scaled_template(self, template_data, screenshot_gray):
        source_width = template_data.get('source_width')
        source_height = template_data.get('source_height')
        if not source_width or not source_height:
            return template_data['image']

        current_height, current_width = screenshot_gray.shape
        scale_x = current_width / source_width
        scale_y = current_height / source_height

        scaled_w = max(1, int(round(template_data['width'] * scale_x)))
        scaled_h = max(1, int(round(template_data['height'] * scale_y)))

        return cv2.resize(
            template_data['image'],
            (scaled_w, scaled_h),
            interpolation=cv2.INTER_AREA,
        )

    def match(
        self,
        screenshot,
        name_or_path,
        threshold=0.88,
        method=cv2.TM_CCOEFF_NORMED,
    ):
        template_data = self._resolve_template(name_or_path)

        screenshot_gray = self._to_grayscale(screenshot)
        template_image = self._scaled_template(template_data, screenshot_gray)
        template_height, template_width = template_image.shape

        if (
            template_height > screenshot_gray.shape[0]
            or template_width > screenshot_gray.shape[1]
        ):
            return None

        result = cv2.matchTemplate(
            screenshot_gray,
            template_image,
            method,
        )
        _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val < threshold:
            return None

        top_left_x, top_left_y = max_loc
        center_x = top_left_x + template_width / 2
        center_y = top_left_y + template_height / 2

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

        template_image = self._scaled_template(template_data, screenshot_gray)
        template_height, template_width = template_image.shape

        if (
            template_height > screenshot_gray.shape[0]
            or template_width > screenshot_gray.shape[1]
        ):
            return []

        result = cv2.matchTemplate(
            screenshot_gray,
            template_image,
            cv2.TM_CCOEFF_NORMED,
        )

        y_idx, x_idx = np.where(result >= threshold)
        height, width = screenshot_gray.shape
        matches = []

        for y, x in zip(y_idx, x_idx):
            center_x = x + template_width / 2
            center_y = y + template_height / 2
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

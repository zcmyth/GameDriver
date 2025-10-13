import time

from game_driver.device import Device
from game_driver.image_analyzer import create_analyzer, draw_text_locations


class GameEngine:
    def __init__(self):
        self.device = Device()
        self.analyzer = create_analyzer()
        self.refresh()

    def refresh(self):
        self._screenshot = self.device.screenshot()
        self._locations = self.analyzer.extract_text_locations(self._screenshot)

    def contains(self, text):
        return len(self.get_matched_locations(text))

    def get_matched_locations(self, text):
        result = []
        for location in self._locations:
            if text in location['text'].lower():
                result.append(location)
        return result

    def try_click_text(self, text):
        clicked = False
        for location in self.get_matched_locations(text):
            self.click(location['x'], location['y'], False)
            clicked = True
        if clicked:
            self.wait()
        return clicked

    def click_text(self, text, retry=5):
        for _ in range(retry):
            if self.try_click_text(text):
                return True
            self.refresh()
        return False

    def click_first_text(self, text_list):
        for text in text_list:
            if self.try_click_text(text):
                return True, text
        return False, None

    def click(self, x, y, wait=True):
        self.device.click(x, y)
        if wait:
            self.wait()

    def debug(self):
        return draw_text_locations(self._screenshot, self._locations)

    def wait(self, seconds=1):
        time.sleep(seconds)
        self.refresh()

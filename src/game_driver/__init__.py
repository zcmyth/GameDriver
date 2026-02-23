"""Game Driver - Automated game interaction via OCR and device control."""

# Expose main public classes for convenient imports
from game_driver.game_engine import GameEngine, ImageClickError
from game_driver.v2.state import ClickableTarget, GameStateV2, ScreenshotState
from game_driver.targeting import TargetSpec
from game_driver.template_matcher import TemplateMatcher

# Define public API (shows up in autocomplete)
__all__ = [
    'GameEngine',
    'ImageClickError',
    'TemplateMatcher',
    'TargetSpec',
    'GameStateV2',
    'ScreenshotState',
    'ClickableTarget',
]

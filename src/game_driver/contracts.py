"""Boundary contracts between core engine runtime and game scripts.

Stage-1 goal: codify the minimum surface area that a game strategy may depend on.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


TextLocation = dict[str, object]


@runtime_checkable
class EngineRuntime(Protocol):
    """Minimal contract consumed by game scripts.

    This intentionally excludes direct device/analyzer/template internals.
    """

    @property
    def text_locations(self) -> Sequence[TextLocation]: ...

    def contains(self, text, exact: bool = False, min_confidence: float = 0.0) -> bool: ...

    def get_matched_locations(
        self,
        text,
        exact: bool = False,
        min_confidence: float = 0.0,
    ) -> list[TextLocation]: ...

    def click_text(
        self,
        text,
        retry: int = 5,
        exact: bool = False,
        min_confidence: float = 0.0,
    ) -> bool: ...

    def try_click_text(
        self,
        text,
        exact: bool = False,
        min_confidence: float = 0.0,
    ) -> bool: ...

    def click_first_text(
        self,
        text_list,
        exact: bool = False,
        min_confidence: float = 0.0,
    ) -> tuple[bool, str | None]: ...

    def try_click_template(self, name_or_path, threshold: float = 0.88, **kwargs) -> bool: ...

    def click(self, x, y, wait: bool = True) -> None: ...

    def wait(self, seconds: float = 1) -> None: ...

    def debug(self): ...

    def recent_signatures(self, count: int | None = None) -> list[str]: ...

    def is_stuck(self, repeat_threshold: int = 8) -> bool: ...

    def is_cycle_stuck(self, cycle_len: int = 2, min_cycles: int = 3) -> bool: ...

    def metrics(self) -> dict[str, object]: ...

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

    Contract notes:
    - `click_*` methods raise/return according to their naming:
      - `click_*`: best-effort action API (may retry internally)
      - `try_click_*`: single-attempt, no-throw convenience returning bool
    - `wait(seconds)` is a passive delay primitive (sleep-like), not an event waiter.
    - `min_confidence` remains explicit in Stage-1 for compatibility with existing
      strategy thresholds; threshold policy centralization is tracked as follow-up.
    """

    @property
    def text_locations(self) -> Sequence[TextLocation]:
        """Read-only snapshot of OCR text locations for current frame."""
        ...

    def contains(self, text, exact: bool = False, min_confidence: float = 0.0) -> bool:
        """Return whether current frame contains matching text."""
        ...

    def get_matched_locations(
        self,
        text,
        exact: bool = False,
        min_confidence: float = 0.0,
    ) -> list[TextLocation]:
        """Return matched OCR items in the current frame."""
        ...

    def click_text(
        self,
        text,
        retry: int = 5,
        exact: bool = False,
        min_confidence: float = 0.0,
    ) -> bool:
        """Click matching text with internal retries up to `retry`."""
        ...

    def try_click_text(
        self,
        text,
        exact: bool = False,
        min_confidence: float = 0.0,
    ) -> bool:
        """Attempt a single-pass text click and return success boolean."""
        ...

    def click_first_text(
        self,
        text_list,
        exact: bool = False,
        min_confidence: float = 0.0,
    ) -> tuple[bool, str | None]:
        """Click first matched candidate from ordered `text_list`."""
        ...

    def try_click_template(self, name_or_path, threshold: float = 0.88, **kwargs) -> bool:
        """Attempt a single-pass template/image click and return success."""
        ...

    def click(self, x, y, wait: bool = True) -> None:
        """Execute a coordinate click.

        If `wait` is true, engine applies the default post-click delay.
        """
        ...

    def wait(self, seconds: float = 1) -> None:
        """Passive delay primitive (sleep semantics)."""
        ...

    def debug(self):
        """Emit debug artifacts/logging for current runtime state."""
        ...

    def recent_signatures(self, count: int | None = None) -> list[str]:
        """Return recent state signatures for diagnostics."""
        ...

    def is_stuck(self, repeat_threshold: int = 8) -> bool:
        """Return true if repeated same-signature state exceeds threshold."""
        ...

    def is_cycle_stuck(self, cycle_len: int = 2, min_cycles: int = 3) -> bool:
        """Return true when engine alternates through a short repeating cycle."""
        ...

    def metrics(self) -> dict[str, object]:
        """Return runtime counters/diagnostic metrics snapshot."""
        ...

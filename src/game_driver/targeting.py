from __future__ import annotations

from dataclasses import dataclass


IMAGE_PREFIX = 'image:'


@dataclass(frozen=True)
class TargetSpec:
    """Canonical target descriptor for script-facing click APIs."""

    kind: str
    value: str
    exact: bool = False
    min_confidence: float = 0.0
    threshold: float = 0.88

    @classmethod
    def text(
        cls,
        value: str,
        *,
        exact: bool = False,
        min_confidence: float = 0.0,
    ) -> 'TargetSpec':
        return cls(
            kind='text',
            value=str(value),
            exact=exact,
            min_confidence=min_confidence,
        )

    @classmethod
    def image(
        cls,
        value: str,
        *,
        threshold: float = 0.88,
    ) -> 'TargetSpec':
        return cls(kind='image', value=str(value), threshold=threshold)

    @classmethod
    def from_target(cls, target: object) -> 'TargetSpec':
        if isinstance(target, TargetSpec):
            return target
        if isinstance(target, str) and target.startswith(IMAGE_PREFIX):
            image_name = target[len(IMAGE_PREFIX) :].strip()
            if not image_name:
                raise ValueError('Image target cannot be empty. Use image:<name>.')
            return cls.image(image_name)
        return cls.text(str(target))

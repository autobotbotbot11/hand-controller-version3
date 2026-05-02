from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LandmarkPoint:
    x: float
    y: float
    z: float


@dataclass(frozen=True, slots=True)
class DetectedHand:
    label: str
    score: float
    landmarks: tuple[LandmarkPoint, ...]

    def landmark(self, index: int) -> LandmarkPoint:
        return self.landmarks[index]


@dataclass(frozen=True, slots=True)
class VisionResult:
    hands: tuple[DetectedHand, ...]
    frame_width: int
    frame_height: int


@dataclass(frozen=True, slots=True)
class SelectedHands:
    primary: DetectedHand | None
    secondary: DetectedHand | None
    left: DetectedHand | None
    right: DetectedHand | None

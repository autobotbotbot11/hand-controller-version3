from __future__ import annotations

from typing import Iterable

from .models import DetectedHand, LandmarkPoint, VisionResult


class HandTracker:
    """MediaPipe Hands wrapper that returns structured hand data."""

    def __init__(
        self,
        max_num_hands: int = 2,
        min_detection_confidence: float = 0.7,
        min_tracking_confidence: float = 0.7,
    ):
        import mediapipe as mp

        self._cv2 = None
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    @property
    def connections(self) -> Iterable[tuple[int, int]]:
        return self.mp_hands.HAND_CONNECTIONS

    def track_bgr_frame(self, frame_bgr) -> VisionResult:
        if self._cv2 is None:
            import cv2

            self._cv2 = cv2

        frame_height, frame_width = frame_bgr.shape[:2]
        rgb_frame = self._cv2.cvtColor(frame_bgr, self._cv2.COLOR_BGR2RGB)
        result = self.hands.process(rgb_frame)
        hands = self.extract_hands(result)
        return VisionResult(
            hands=hands,
            frame_width=frame_width,
            frame_height=frame_height,
        )

    def extract_hands(self, result) -> tuple[DetectedHand, ...]:
        detected: list[DetectedHand] = []
        if result.multi_hand_landmarks and result.multi_handedness:
            for landmarks, handedness in zip(result.multi_hand_landmarks, result.multi_handedness):
                label = handedness.classification[0].label
                score = float(handedness.classification[0].score)
                points = tuple(
                    LandmarkPoint(
                        x=float(point.x),
                        y=float(point.y),
                        z=float(point.z),
                    )
                    for point in landmarks.landmark
                )
                detected.append(
                    DetectedHand(
                        label=label,
                        score=score,
                        landmarks=points,
                    )
                )
        return tuple(detected)

    def close(self) -> None:
        if self.hands is not None:
            self.hands.close()

    def __enter__(self) -> "HandTracker":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

from __future__ import annotations

from dataclasses import dataclass
import math
import time

from ..config.settings import HandSelectorConfig
from .models import DetectedHand, SelectedHands


def _bbox_area_px(hand: DetectedHand, frame_width: int, frame_height: int) -> float:
    xs = [point.x * frame_width for point in hand.landmarks]
    ys = [point.y * frame_height for point in hand.landmarks]
    return float(max(1.0, max(xs) - min(xs)) * max(1.0, max(ys) - min(ys)))


def _center_px(hand: DetectedHand, frame_width: int, frame_height: int) -> tuple[float, float]:
    anchor = hand.landmark(5)
    return anchor.x * frame_width, anchor.y * frame_height


class HandSelector:
    """Pick a stable primary hand while preserving left/right references."""

    def __init__(self, settings: HandSelectorConfig | None = None):
        self.settings = settings or HandSelectorConfig()
        self._last_primary_center_px: tuple[float, float] | None = None
        self._last_seen_time: float = 0.0

    def select(self, hands: tuple[DetectedHand, ...], frame_width: int, frame_height: int) -> SelectedHands:
        now = time.time()

        if not hands:
            if now - self._last_seen_time > self.settings.lost_grace_seconds:
                self._last_primary_center_px = None
            return SelectedHands(primary=None, secondary=None, left=None, right=None)

        scored = [
            (_bbox_area_px(hand, frame_width, frame_height), hand)
            for hand in hands
        ]
        scored.sort(key=lambda item: item[0], reverse=True)

        best_score, best_hand = scored[0]
        chosen = best_hand

        if self._last_primary_center_px is not None:
            best_dist = math.inf
            best_match: tuple[float, DetectedHand] | None = None

            for score, hand in scored:
                cx, cy = _center_px(hand, frame_width, frame_height)
                dist = math.hypot(cx - self._last_primary_center_px[0], cy - self._last_primary_center_px[1])
                if dist < best_dist:
                    best_dist = dist
                    best_match = (score, hand)

            if best_match is not None and best_dist <= self.settings.centroid_switch_px:
                match_score, match_hand = best_match
                if match_score >= best_score * (1.0 - self.settings.switch_margin):
                    chosen = match_hand

        self._last_primary_center_px = _center_px(chosen, frame_width, frame_height)
        self._last_seen_time = now

        secondary = None
        for _, hand in scored:
            if hand is not chosen:
                secondary = hand
                break

        left = None
        right = None
        for _, hand in scored:
            label = hand.label.lower()
            if label == "left" and left is None:
                left = hand
            elif label == "right" and right is None:
                right = hand

        return SelectedHands(primary=chosen, secondary=secondary, left=left, right=right)

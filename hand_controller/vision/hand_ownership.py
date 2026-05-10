from __future__ import annotations

from dataclasses import dataclass
import math

from ..config.settings import HandOwnershipConfig
from .models import DetectedHand


PALM_ANCHOR_IDX = 9


@dataclass(frozen=True, slots=True)
class OwnershipGuide:
    visible: bool = False
    text: str = ""
    progress: float = 0.0
    zone: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    locked_count: int = 0
    max_count: int = 0


@dataclass(frozen=True, slots=True)
class HandOwnershipUpdate:
    trusted_hands: tuple[DetectedHand, ...]
    active_count: int
    locked_count: int
    max_count: int
    new_locks: int
    guide: OwnershipGuide
    status: str


@dataclass(slots=True)
class _TrustedSlot:
    slot_id: int
    label: str
    center_x: float
    center_y: float
    last_seen: float


@dataclass(slots=True)
class _PendingCandidate:
    label: str
    center_x: float
    center_y: float
    started_at: float
    last_seen: float


def _anchor_px(hand: DetectedHand, frame_width: int, frame_height: int) -> tuple[float, float]:
    anchor = hand.landmark(PALM_ANCHOR_IDX)
    return anchor.x * frame_width, anchor.y * frame_height


class HandOwnershipTracker:
    def __init__(self, settings: HandOwnershipConfig | None = None) -> None:
        self.settings = settings or HandOwnershipConfig()
        self._slots: list[_TrustedSlot] = []
        self._pending: dict[str, _PendingCandidate] = {}
        self._next_slot_id = 1

    def reset(self) -> None:
        self._slots.clear()
        self._pending.clear()

    def _zone(self) -> tuple[float, float, float, float]:
        x1 = max(0.0, min(1.0, self.settings.zone_x1_ratio))
        y1 = max(0.0, min(1.0, self.settings.zone_y1_ratio))
        x2 = max(0.0, min(1.0, self.settings.zone_x2_ratio))
        y2 = max(0.0, min(1.0, self.settings.zone_y2_ratio))
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)

    def _inside_zone(self, hand: DetectedHand, frame_width: int, frame_height: int) -> bool:
        x1, y1, x2, y2 = self._zone()
        cx, cy = _anchor_px(hand, frame_width, frame_height)
        return (x1 * frame_width) <= cx <= (x2 * frame_width) and (
            y1 * frame_height
        ) <= cy <= (y2 * frame_height)

    def _safe_to_lock(self, hand: DetectedHand, press_safe_by_label: dict[str, bool]) -> bool:
        if not self.settings.require_press_safe_for_lock:
            return True
        return bool(press_safe_by_label.get(hand.label, False))

    def _match_existing_slots(
        self,
        *,
        hands: tuple[DetectedHand, ...],
        frame_width: int,
        frame_height: int,
        now: float,
    ) -> tuple[list[DetectedHand], list[DetectedHand]]:
        available = list(hands)
        trusted: list[DetectedHand] = []
        kept_slots: list[_TrustedSlot] = []

        for slot in self._slots:
            best_index: int | None = None
            best_distance = math.inf

            for index, hand in enumerate(available):
                if hand.label != slot.label:
                    continue
                cx, cy = _anchor_px(hand, frame_width, frame_height)
                distance = math.hypot(cx - slot.center_x, cy - slot.center_y)
                if distance < best_distance:
                    best_distance = distance
                    best_index = index

            if best_index is not None and best_distance <= self.settings.max_travel_px:
                hand = available.pop(best_index)
                cx, cy = _anchor_px(hand, frame_width, frame_height)
                slot.center_x = cx
                slot.center_y = cy
                slot.last_seen = now
                kept_slots.append(slot)
                trusted.append(hand)
            elif (now - slot.last_seen) <= self.settings.reacquire_grace_seconds:
                kept_slots.append(slot)

        self._slots = kept_slots
        return trusted, available

    def _update_pending_candidates(
        self,
        *,
        candidates: list[DetectedHand],
        frame_width: int,
        frame_height: int,
        now: float,
    ) -> dict[str, float]:
        active_labels = {hand.label for hand in candidates}
        for label in list(self._pending):
            if label not in active_labels:
                self._pending.pop(label, None)

        progress_by_label: dict[str, float] = {}
        for hand in candidates:
            cx, cy = _anchor_px(hand, frame_width, frame_height)
            pending = self._pending.get(hand.label)
            if pending is None or math.hypot(cx - pending.center_x, cy - pending.center_y) > self.settings.pending_match_px:
                pending = _PendingCandidate(
                    label=hand.label,
                    center_x=cx,
                    center_y=cy,
                    started_at=now,
                    last_seen=now,
                )
                self._pending[hand.label] = pending
            else:
                pending.center_x = cx
                pending.center_y = cy
                pending.last_seen = now

            hold_seconds = max(0.01, self.settings.calibration_hold_seconds)
            progress_by_label[hand.label] = max(0.0, min(1.0, (now - pending.started_at) / hold_seconds))

        return progress_by_label

    def _add_new_locks(
        self,
        *,
        candidates: list[DetectedHand],
        progress_by_label: dict[str, float],
        trusted: list[DetectedHand],
        frame_width: int,
        frame_height: int,
        now: float,
    ) -> int:
        open_slots = max(0, max(1, self.settings.max_trusted_hands) - len(self._slots))
        if open_slots <= 0:
            return 0

        new_locks = 0
        for hand in candidates:
            if new_locks >= open_slots:
                break
            if progress_by_label.get(hand.label, 0.0) < 1.0:
                continue
            cx, cy = _anchor_px(hand, frame_width, frame_height)
            self._slots.append(
                _TrustedSlot(
                    slot_id=self._next_slot_id,
                    label=hand.label,
                    center_x=cx,
                    center_y=cy,
                    last_seen=now,
                )
            )
            self._next_slot_id += 1
            trusted.append(hand)
            self._pending.pop(hand.label, None)
            new_locks += 1

        return new_locks

    def update(
        self,
        *,
        hands: tuple[DetectedHand, ...],
        frame_width: int,
        frame_height: int,
        press_safe_by_label: dict[str, bool],
        allow_additional_hands: bool,
        now: float,
    ) -> HandOwnershipUpdate:
        max_count = max(1, self.settings.max_trusted_hands)
        if not self.settings.enabled:
            return HandOwnershipUpdate(
                trusted_hands=hands,
                active_count=len(hands),
                locked_count=len(hands),
                max_count=max_count,
                new_locks=0,
                guide=OwnershipGuide(visible=False, zone=self._zone(), locked_count=len(hands), max_count=max_count),
                status=f"ownership=off active={len(hands)}",
            )

        trusted, available = self._match_existing_slots(
            hands=hands,
            frame_width=frame_width,
            frame_height=frame_height,
            now=now,
        )

        can_add_hands = len(self._slots) == 0 or allow_additional_hands
        slots_available = len(self._slots) < max_count
        candidates: list[DetectedHand] = []
        if can_add_hands and slots_available:
            candidates = [
                hand
                for hand in available
                if self._inside_zone(hand, frame_width, frame_height)
                and self._safe_to_lock(hand, press_safe_by_label)
            ]
            progress_by_label = self._update_pending_candidates(
                candidates=candidates,
                frame_width=frame_width,
                frame_height=frame_height,
                now=now,
            )
            new_locks = self._add_new_locks(
                candidates=candidates,
                progress_by_label=progress_by_label,
                trusted=trusted,
                frame_width=frame_width,
                frame_height=frame_height,
                now=now,
            )
        else:
            self._pending.clear()
            progress_by_label = {}
            new_locks = 0

        can_show_add_prompt = len(self._slots) == 0 or allow_additional_hands
        guide_visible = can_show_add_prompt and len(self._slots) < max_count
        progress = max(progress_by_label.values(), default=0.0)
        if progress > 0.0:
            guide_text = "Hold still"
        elif len(self._slots) == 0:
            guide_text = "Place hand here"
        else:
            guide_text = "Place other hand here"

        guide = OwnershipGuide(
            visible=guide_visible,
            text=guide_text if guide_visible else "",
            progress=progress if guide_visible else 0.0,
            zone=self._zone(),
            locked_count=len(self._slots),
            max_count=max_count,
        )
        status = (
            f"ownership=on active={len(trusted)} "
            f"locked={len(self._slots)}/{max_count} "
            f"guide={'on' if guide.visible else 'off'}"
        )
        return HandOwnershipUpdate(
            trusted_hands=tuple(trusted),
            active_count=len(trusted),
            locked_count=len(self._slots),
            max_count=max_count,
            new_locks=new_locks,
            guide=guide,
            status=status,
        )

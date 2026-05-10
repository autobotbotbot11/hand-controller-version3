from __future__ import annotations

import time
from dataclasses import dataclass

from ..config.settings import AppConfig
from ..controllers import (
    KeyboardController,
    KeyboardOverlayToggleController,
    MouseController,
    execute_actions,
)
from ..controllers.actions import Action, Click, DoubleClick, Hotkey, KeyPress, MouseDown, MouseUp
from ..controllers.keyboard_controller import KeyboardUpdate
from ..gestures import (
    HandPinchDetector,
    HandPinchState,
    HandViewSafety,
    MouseClickGestureState,
    MouseClickDetector,
    analyze_hand_view_safety,
    is_palm_facing_thumb_pinky,
)
from ..ml import MLPrediction, MLPredictor, MLControlAdapter
from ..ml.labels import ML_LABEL_HOLD, canonicalize_label
from ..runtime.state import RuntimeState
from .diagnostics import log_diagnostic
from ..vision.hand_selector import HandSelector
from ..vision.hand_ownership import HandOwnershipTracker, OwnershipGuide
from ..vision.models import DetectedHand, SelectedHands, VisionResult


THUMB_TIP_IDX = 4
INDEX_TIP_IDX = 8
MAPPING_RESET_COOLDOWN_SECONDS = 0.4
MAPPING_RESET_FEEDBACK = "Cursor Reset"
CLUTCH_REPOSITION_HINT = "Thumb + pinky: reset cursor"
SECOND_HAND_HINT = "Move other hand to center to add it"
HELPER_HINT_SECONDS = 5.0


def _mouse_pointer_norm(hand) -> tuple[float, float]:
    thumb = hand.landmark(THUMB_TIP_IDX)
    index = hand.landmark(INDEX_TIP_IDX)
    return (thumb.x + index.x) / 2.0, (thumb.y + index.y) / 2.0


def _hovered_keyboard_label(keyboard_update: KeyboardUpdate, hand_label: str | None) -> str | None:
    if hand_label is None:
        return None
    for label, hovered in keyboard_update.hovered_key_by_hand:
        if label == hand_label:
            return hovered
    return None


def _hand_by_label(hands: tuple[DetectedHand, ...], label: str | None) -> DetectedHand | None:
    if label is None:
        return None
    for hand in hands:
        if hand.label == label:
            return hand
    return None


def _selected_with_primary(
    selected: SelectedHands,
    hands: tuple[DetectedHand, ...],
    primary: DetectedHand | None,
) -> SelectedHands:
    if primary is None:
        return SelectedHands(
            primary=None,
            secondary=None,
            left=selected.left,
            right=selected.right,
        )

    secondary = next((hand for hand in hands if hand is not primary), None)
    return SelectedHands(
        primary=primary,
        secondary=secondary,
        left=selected.left,
        right=selected.right,
    )


@dataclass(frozen=True, slots=True)
class ControlFrameResult:
    runtime_state: RuntimeState
    vision: VisionResult
    trusted_hands: tuple[DetectedHand, ...]
    selected: SelectedHands
    click_state: MouseClickGestureState
    keyboard_update: KeyboardUpdate
    movement_status: str
    movement_enabled: bool
    click_freeze: bool
    ml_prediction: MLPrediction
    ml_status: str
    ml_available: bool
    ml_reason: str | None
    keyboard_toggle_status: str
    drag_active: bool
    pre_hold_right_suppressed: bool
    press_gestures_safe: bool
    press_safety_status: str
    gesture_command_text: str
    helper_hint_text: str
    ownership_guide: OwnershipGuide
    ownership_status: str


class LiveControlEngine:
    def __init__(self, config: AppConfig, *, screen_width: int, screen_height: int) -> None:
        self.config = config
        self.screen_width = screen_width
        self.screen_height = screen_height

        self.mouse_controller = MouseController(
            screen_w=screen_width,
            screen_h=screen_height,
            motion_settings=config.mouse_motion,
            click_settings=config.mouse_click,
        )
        self.click_detector = MouseClickDetector(config.mouse_click)
        self.pinch_detector = HandPinchDetector(config.keyboard)
        self.keyboard_controller = KeyboardController(config.keyboard)
        self.keyboard_overlay_toggle_controller = KeyboardOverlayToggleController(config.keyboard)
        self.runtime_state = RuntimeState()
        self.selector = HandSelector(config.selector)
        self.ownership_tracker = HandOwnershipTracker(config.ownership)
        self.ml_predictor, self.ml_reason = MLPredictor.try_create(config.ml)
        self.ml_adapter = MLControlAdapter(config.ml)
        self._gesture_feedback_text = ""
        self._gesture_feedback_until = 0.0
        self._helper_hint_text = ""
        self._helper_hint_until = 0.0
        self._second_hand_hint_shown = False
        self._press_safety_by_hand: dict[str, bool] = {}
        self._diag_last_ml_label: str | None = None
        self._diag_last_hold_active: bool | None = None
        self._diag_last_control_enabled: bool | None = None
        self._diag_last_owner_trace = ""
        self._diag_last_owner_trace_time = 0.0
        self._last_mapping_reset_time = -1e9
        self._mouse_owner_label: str | None = None
        self._hold_owner_label: str | None = None
        self._hold_owner_enabled = ML_LABEL_HOLD in {
            canonicalize_label(label) for label in config.ml.accepted_action_labels
        }

        if self.ml_predictor is None:
            log_diagnostic(f"ml=unavailable reason={self.ml_reason}")
        else:
            log_diagnostic(
                "ml=loaded "
                f"model={self.ml_predictor.model_path} "
                f"scaler={self.ml_predictor.scaler_path} "
                f"label_encoder={self.ml_predictor.encoder_path}"
            )

    def _set_gesture_feedback(self, text: str, now: float) -> None:
        if not text:
            return
        self._gesture_feedback_text = text
        self._gesture_feedback_until = now + self.config.keyboard.gesture_command_hold_seconds

    def _set_helper_hint(self, text: str, now: float) -> None:
        if not text:
            return
        self._helper_hint_text = text
        self._helper_hint_until = now + HELPER_HINT_SECONDS

    def _clear_helper_hint(self) -> None:
        self._helper_hint_text = ""
        self._helper_hint_until = 0.0

    def _clear_helper_hint_if_text(self, text: str) -> None:
        if self._helper_hint_text == text:
            self._clear_helper_hint()

    def _helper_hint(self, now: float) -> str:
        if now <= self._helper_hint_until:
            return self._helper_hint_text
        return ""

    def _update_second_hand_hint(
        self,
        *,
        keyboard_visible: bool,
        ownership_guide_visible: bool,
        locked_hand_count: int,
        max_hand_count: int,
        now: float,
    ) -> None:
        if not keyboard_visible or max_hand_count < 2:
            self._second_hand_hint_shown = False
            self._clear_helper_hint_if_text(SECOND_HAND_HINT)
            return

        if locked_hand_count >= 2:
            self._second_hand_hint_shown = False
            self._clear_helper_hint_if_text(SECOND_HAND_HINT)
            return

        if locked_hand_count == 0:
            self._second_hand_hint_shown = False
            self._clear_helper_hint_if_text(SECOND_HAND_HINT)
            return

        if ownership_guide_visible:
            self._second_hand_hint_shown = True
            self._clear_helper_hint_if_text(SECOND_HAND_HINT)
            return

        if not self._second_hand_hint_shown:
            self._set_helper_hint(SECOND_HAND_HINT, now)
            self._second_hand_hint_shown = True

    def _label_for_action(self, action: Action, *, click_status: str | None = None) -> str:
        if isinstance(action, Click):
            if click_status == "Mouse | double click" and action.button == "left":
                return "Double Click"
            return "Left Click" if action.button == "left" else "Right Click"
        if isinstance(action, DoubleClick):
            return "Double Click"
        if isinstance(action, MouseDown) and action.button == "left":
            return "Drag Start"
        if isinstance(action, MouseUp) and action.button == "left":
            return "Drop"
        if isinstance(action, Hotkey):
            if action.keys == ("ctrl", "z"):
                return "Undo"
            if action.keys == ("ctrl", "y"):
                return "Redo"
            return " + ".join(part.upper() for part in action.keys)
        if isinstance(action, KeyPress):
            named = {
                "space": "Space",
                "enter": "Enter",
                "backspace": "Backspace",
                "tab": "Tab",
                "esc": "Esc",
            }
            if action.key in named:
                return named[action.key]
            if len(action.key) == 1:
                return action.key.upper()
            return action.key.title()
        return ""

    def _gesture_feedback(
        self,
        *,
        actions: list[Action],
        click_status: str | None,
        keyboard_toggle_status: str,
        ml_status: str,
        now: float,
    ) -> str:
        text = ""
        if "toggled" in keyboard_toggle_status:
            text = "Keyboard On" if self.runtime_state.keyboard_visible else "Keyboard Off"
        elif "toggled" in ml_status:
            text = "Control On" if self.runtime_state.control_enabled else "Control Off"
        else:
            for action in reversed(actions):
                text = self._label_for_action(action, click_status=click_status)
                if text:
                    break

        if text:
            self._set_gesture_feedback(text, now)
        if now <= self._gesture_feedback_until:
            return self._gesture_feedback_text
        return ""

    def _should_pre_hold_suppress_right_click(self, prediction: MLPrediction) -> bool:
        if not self.config.ml.pre_hold_right_click_suppression:
            return False
        if not prediction.available:
            return False
        if not self.runtime_state.control_enabled or self.runtime_state.hold_active:
            return False
        if prediction.raw_label != ML_LABEL_HOLD:
            return False
        return (prediction.p1 or 0.0) >= self.config.ml.pre_hold_min_p1

    def _is_hold_owner_candidate(self, prediction: MLPrediction) -> bool:
        if not self._hold_owner_enabled:
            return False
        if not self.runtime_state.control_enabled:
            return False
        if not prediction.available:
            return False
        if prediction.label != ML_LABEL_HOLD:
            return False
        return (prediction.p1 or 0.0) >= self.config.ml.pre_hold_min_p1

    def _predict_trusted_hands(
        self,
        trusted_hands: tuple[DetectedHand, ...],
    ) -> dict[str, MLPrediction]:
        if self.ml_predictor is None:
            return {}
        return {hand.label: self.ml_predictor.predict(hand) for hand in trusted_hands}

    def _ml_prediction_for_hand(
        self,
        *,
        hand: DetectedHand | None,
        predictions_by_label: dict[str, MLPrediction],
    ) -> MLPrediction:
        if self.ml_predictor is None:
            return MLPrediction(available=False, reason=self.ml_reason)
        if hand is None:
            return MLPrediction(available=True)
        prediction = predictions_by_label.get(hand.label)
        if prediction is not None:
            return prediction
        return self.ml_predictor.predict(hand)

    def _current_hold_candidate(
        self,
        *,
        selected: SelectedHands,
        trusted_hands: tuple[DetectedHand, ...],
        predictions_by_label: dict[str, MLPrediction],
    ) -> DetectedHand | None:
        hold_labels = {
            label for label, prediction in predictions_by_label.items()
            if self._is_hold_owner_candidate(prediction)
        }
        if not hold_labels:
            return None

        selected_label = selected.primary.label if selected.primary is not None else None
        priority_labels = (
            self._hold_owner_label,
            self.runtime_state.active_hand_label,
            selected_label,
        )
        for label in priority_labels:
            if label in hold_labels:
                return _hand_by_label(trusted_hands, label)

        for hand in trusted_hands:
            if hand.label in hold_labels:
                return hand
        return None

    def _hold_candidate_labels(
        self,
        predictions_by_label: dict[str, MLPrediction],
    ) -> tuple[str, ...]:
        return tuple(
            label for label, prediction in predictions_by_label.items()
            if self._is_hold_owner_candidate(prediction)
        )

    def _prediction_debug_text(self, predictions_by_label: dict[str, MLPrediction]) -> str:
        parts: list[str] = []
        for label, prediction in predictions_by_label.items():
            p1 = f"{prediction.p1:.2f}" if prediction.p1 is not None else "-"
            margin = f"{prediction.margin:.2f}" if prediction.margin is not None else "-"
            parts.append(f"{label}:{prediction.raw_label}/{prediction.label}/{p1}/{margin}")
        return ";".join(parts) if parts else "-"

    def _log_owner_trace(
        self,
        *,
        now: float,
        trusted_hands: tuple[DetectedHand, ...],
        raw_selected_label: str | None,
        active_hand: DetectedHand | None,
        predictions_by_label: dict[str, MLPrediction],
        ml_status: str,
        mouse_status: str,
    ) -> None:
        hold_candidates = self._hold_candidate_labels(predictions_by_label)
        should_trace = (
            len(trusted_hands) >= 2
            or bool(hold_candidates)
            or self.runtime_state.hold_active
            or self._hold_owner_label is not None
        )
        if not should_trace:
            return

        trusted = ",".join(hand.label for hand in trusted_hands) or "-"
        trace = (
            "owner_trace "
            f"trusted={trusted} "
            f"raw_selected={raw_selected_label or '-'} "
            f"active={active_hand.label if active_hand is not None else '-'} "
            f"mouse_owner={self._mouse_owner_label or '-'} "
            f"owner={self._hold_owner_label or '-'} "
            f"hold_active={'yes' if self.runtime_state.hold_active else 'no'} "
            f"hold_candidates={','.join(hold_candidates) or '-'} "
            f"preds={self._prediction_debug_text(predictions_by_label)} "
            f"ml_status={ml_status} "
            f"mouse={mouse_status}"
        )
        if trace == self._diag_last_owner_trace and (now - self._diag_last_owner_trace_time) < 0.50:
            return
        self._diag_last_owner_trace = trace
        self._diag_last_owner_trace_time = now
        log_diagnostic(trace)

    def _resolve_active_hand(
        self,
        *,
        selected: SelectedHands,
        trusted_hands: tuple[DetectedHand, ...],
        predictions_by_label: dict[str, MLPrediction],
    ) -> tuple[SelectedHands, DetectedHand | None]:
        owner_hand = _hand_by_label(trusted_hands, self._hold_owner_label)
        if self.runtime_state.hold_active and owner_hand is None and self._hold_owner_label is not None:
            return _selected_with_primary(selected, trusted_hands, None), None
        if self.runtime_state.hold_active and owner_hand is not None:
            selected = _selected_with_primary(selected, trusted_hands, owner_hand)
            return selected, owner_hand

        hold_candidate = self._current_hold_candidate(
            selected=selected,
            trusted_hands=trusted_hands,
            predictions_by_label=predictions_by_label,
        )
        if hold_candidate is not None:
            self._mouse_owner_label = hold_candidate.label
            selected = _selected_with_primary(selected, trusted_hands, hold_candidate)
            return selected, hold_candidate

        mouse_owner = _hand_by_label(trusted_hands, self._mouse_owner_label)
        if mouse_owner is not None:
            selected = _selected_with_primary(selected, trusted_hands, mouse_owner)
            return selected, mouse_owner

        if self._mouse_owner_label is not None:
            self._mouse_owner_label = None

        if selected.primary is not None:
            self._mouse_owner_label = selected.primary.label
        return selected, selected.primary

    def _update_hold_owner_latch(
        self,
        *,
        active_hand: DetectedHand | None,
        prediction: MLPrediction,
    ) -> None:
        if not self.runtime_state.control_enabled:
            self._hold_owner_label = None
            self._mouse_owner_label = None
            return
        if self.runtime_state.hold_active:
            if self._hold_owner_label is None and active_hand is not None:
                self._hold_owner_label = active_hand.label
            if active_hand is not None:
                self._mouse_owner_label = active_hand.label
            return
        if self._is_hold_owner_candidate(prediction) and active_hand is not None:
            self._hold_owner_label = active_hand.label
            self._mouse_owner_label = active_hand.label
            return
        self._hold_owner_label = None

    def _should_reset_mapping(
        self,
        *,
        active_pinch_state: HandPinchState | None,
        press_gestures_safe: bool,
        now: float,
    ) -> bool:
        if not self.runtime_state.control_enabled:
            return False
        if not press_gestures_safe:
            return False
        if self.runtime_state.hold_active:
            return False
        if self.mouse_controller.state.drag_active:
            return False
        if active_pinch_state is None:
            return False
        if not active_pinch_state.pinky.down:
            return False
        if active_pinch_state.index.pressed or active_pinch_state.middle.pressed:
            return False
        if (now - self._last_mapping_reset_time) < MAPPING_RESET_COOLDOWN_SECONDS:
            return False
        self._last_mapping_reset_time = now
        return True

    def _analyze_hand_safety(
        self,
        hands,
    ) -> dict[str, HandViewSafety]:
        safety_by_label: dict[str, HandViewSafety] = {}
        visible_labels: set[str] = set()

        for hand in hands:
            visible_labels.add(hand.label)
            previously_safe = bool(self._press_safety_by_hand.get(hand.label, False))
            safety = analyze_hand_view_safety(
                hand,
                mirrored_input=self.config.tracker.mirror_input,
                previously_safe=previously_safe,
            )
            safety_by_label[hand.label] = safety
            self._press_safety_by_hand[hand.label] = safety.press_safe

        for label in list(self._press_safety_by_hand):
            if label not in visible_labels:
                self._press_safety_by_hand.pop(label, None)

        return safety_by_label

    def process_frame(
        self,
        vision: VisionResult,
        *,
        layout_width: int,
        layout_height: int,
        now: float | None = None,
    ) -> ControlFrameResult:
        now = time.time() if now is None else now

        hand_safety_by_label = self._analyze_hand_safety(vision.hands)
        ownership_update = self.ownership_tracker.update(
            hands=vision.hands,
            frame_width=vision.frame_width,
            frame_height=vision.frame_height,
            press_safe_by_label={
                label: safety.press_safe for label, safety in hand_safety_by_label.items()
            },
            allow_additional_hands=(
                self.runtime_state.control_enabled
                and self.runtime_state.keyboard_visible
                and self.config.keyboard.virtual_keyboard_enabled
            ),
            now=now,
        )
        trusted_hands = ownership_update.trusted_hands
        selected = self.selector.select(trusted_hands, vision.frame_width, vision.frame_height)
        raw_selected_label = selected.primary.label if selected.primary is not None else None
        ml_predictions_by_label = self._predict_trusted_hands(trusted_hands)
        selected, active_hand = self._resolve_active_hand(
            selected=selected,
            trusted_hands=trusted_hands,
            predictions_by_label=ml_predictions_by_label,
        )
        active_hand_safety = hand_safety_by_label.get(active_hand.label) if active_hand is not None else None
        palm_facing = (
            active_hand_safety.ordering_ok
            if active_hand_safety is not None
            else (
                is_palm_facing_thumb_pinky(active_hand, mirrored_input=self.config.tracker.mirror_input)
                if active_hand is not None
                else False
            )
        )
        press_gestures_safe = active_hand_safety.press_safe if active_hand_safety is not None else False
        press_safety_status = active_hand_safety.status if active_hand_safety is not None else "presssafe=no hand"
        self.runtime_state.active_hand_label = active_hand.label if active_hand is not None else None
        self.runtime_state.palm_facing = palm_facing

        pinch_states = self.pinch_detector.analyze(
            hands=trusted_hands,
            frame_width=vision.frame_width,
            frame_height=vision.frame_height,
            activation_allowed_by_hand={
                label: safety.press_safe and ownership_update.new_locks == 0
                for label, safety in hand_safety_by_label.items()
            },
        )
        if ownership_update.new_locks:
            self._set_gesture_feedback("Hand Locked", now)
        active_pinch_state = pinch_states.get(active_hand.label) if active_hand is not None else None

        ml_prediction = self._ml_prediction_for_hand(
            hand=active_hand,
            predictions_by_label=ml_predictions_by_label,
        )
        ml_update = self.ml_adapter.update(ml_prediction, self.runtime_state, now)
        self._update_hold_owner_latch(
            active_hand=active_hand,
            prediction=ml_prediction,
        )
        if not self.runtime_state.control_enabled:
            self._clear_helper_hint()

        keyboard_toggle_update = self.keyboard_overlay_toggle_controller.update(
            state=self.runtime_state,
            active_hand=active_hand,
            palm_facing=palm_facing,
            pinch_state=active_pinch_state,
            now=now,
        )

        click_state = MouseClickGestureState()
        keyboard_update = KeyboardUpdate(
            layout=self.keyboard_controller.layout_for_frame(layout_width, layout_height),
            status="keyboard idle",
        )
        movement_status = "idle"
        movement_enabled = False
        click_freeze = False
        pre_hold_right_suppressed = self._should_pre_hold_suppress_right_click(ml_prediction)
        action_queue: list[Action] = []
        action_queue.extend(ml_update.actions)
        feedback_actions = list(ml_update.actions)
        click_feedback_status: str | None = None

        keyboard_visible = (
            self.runtime_state.control_enabled
            and self.runtime_state.keyboard_visible
            and self.config.keyboard.virtual_keyboard_enabled
        )
        if keyboard_visible:
            keyboard_update = self.keyboard_controller.update(
                hands=trusted_hands,
                pinch_states=pinch_states,
                frame_width=layout_width,
                frame_height=layout_height,
                now=now,
            )
            action_queue.extend(keyboard_update.actions)
            feedback_actions.extend(keyboard_update.actions)
        else:
            keyboard_update = KeyboardUpdate(
                layout=self.keyboard_controller.layout_for_frame(layout_width, layout_height),
                status=(
                    "keyboard disabled"
                    if not self.config.keyboard.virtual_keyboard_enabled
                    else "keyboard hidden"
                    if self.runtime_state.control_enabled
                    else "keyboard control off"
                ),
            )

        self._update_second_hand_hint(
            keyboard_visible=keyboard_visible,
            ownership_guide_visible=ownership_update.guide.visible,
            locked_hand_count=ownership_update.locked_count,
            max_hand_count=ownership_update.max_count,
            now=now,
        )

        active_keyboard_hover = (
            _hovered_keyboard_label(
                keyboard_update,
                active_hand.label if active_hand is not None else None,
            )
            if keyboard_visible
            else None
        )
        reset_mapping = self._should_reset_mapping(
            active_pinch_state=active_pinch_state,
            press_gestures_safe=press_gestures_safe,
            now=now,
        )
        if reset_mapping:
            self._set_gesture_feedback(MAPPING_RESET_FEEDBACK, now)
            self._clear_helper_hint()

        click_enabled = (
            self.runtime_state.control_enabled
            and not self.runtime_state.hold_active
            and not reset_mapping
            and active_keyboard_hover is None
        )
        if click_enabled:
            click_state = self.click_detector.analyze(
                active_hand=active_hand,
                frame_width=vision.frame_width,
                frame_height=vision.frame_height,
                activation_allowed=press_gestures_safe,
            )
        else:
            self.click_detector.reset()

        pointer_norm = _mouse_pointer_norm(active_hand) if active_hand is not None else None
        movement_enabled = (
            active_hand is not None
            and palm_facing
            and self.runtime_state.control_enabled
            and not self.runtime_state.hold_active
        )
        self.runtime_state.movement_frozen = not movement_enabled

        mouse_actions, mouse_status = self.mouse_controller.update(
            pointer_norm=pointer_norm,
            control_enabled=self.runtime_state.control_enabled,
            movement_allowed=movement_enabled,
            click_enabled=click_enabled,
            clutch_active=self.runtime_state.hold_active,
            reset_mapping=reset_mapping,
            press_activation_allowed=press_gestures_safe,
            right_click_allowed=not pre_hold_right_suppressed,
            click_state=click_state,
            now=now,
        )
        action_queue.extend(mouse_actions)
        feedback_actions.extend(mouse_actions)
        movement_status = f"keyboard overlay | {mouse_status}" if keyboard_visible else mouse_status
        click_feedback_status = mouse_status
        if "hand repositioned" in mouse_status:
            self._set_helper_hint(CLUTCH_REPOSITION_HINT, now)
        click_freeze = click_enabled and (
            click_state.right_pressed
            or (click_state.left_pressed and not self.mouse_controller.state.drag_active)
        )
        self._log_owner_trace(
            now=now,
            trusted_hands=trusted_hands,
            raw_selected_label=raw_selected_label,
            active_hand=active_hand,
            predictions_by_label=ml_predictions_by_label,
            ml_status=ml_update.status,
            mouse_status=mouse_status,
        )

        execute_actions(action_queue)

        if self.runtime_state.latest_ml_label != self._diag_last_ml_label:
            log_diagnostic(
                "ml_label_change "
                f"stable={self.runtime_state.latest_ml_label} "
                f"raw={ml_prediction.raw_label} "
                f"p1={ml_prediction.p1 if ml_prediction.p1 is not None else 'None'} "
                f"margin={ml_prediction.margin if ml_prediction.margin is not None else 'None'} "
                f"status={ml_update.status}"
            )
            self._diag_last_ml_label = self.runtime_state.latest_ml_label

        if self.runtime_state.hold_active != self._diag_last_hold_active:
            log_diagnostic(
                "hold_change "
                f"hold_active={self.runtime_state.hold_active} "
                f"stable={self.runtime_state.latest_ml_label} "
                f"raw={ml_prediction.raw_label}"
            )
            self._diag_last_hold_active = self.runtime_state.hold_active

        if self.runtime_state.control_enabled != self._diag_last_control_enabled:
            log_diagnostic(
                "control_change "
                f"control_enabled={self.runtime_state.control_enabled} "
                f"stable={self.runtime_state.latest_ml_label}"
            )
            self._diag_last_control_enabled = self.runtime_state.control_enabled

        if self.runtime_state.hold_active:
            press_actions = [
                action for action in action_queue if isinstance(action, (Click, DoubleClick, MouseDown, MouseUp))
            ]
            if press_actions:
                names = ",".join(type(action).__name__ for action in press_actions)
                log_diagnostic(
                    "hold_conflict "
                    f"actions={names} "
                    f"stable={self.runtime_state.latest_ml_label} "
                    f"raw={ml_prediction.raw_label}"
                )

        gesture_command_text = self._gesture_feedback(
            actions=feedback_actions,
            click_status=click_feedback_status,
            keyboard_toggle_status=keyboard_toggle_update.status,
            ml_status=ml_update.status,
            now=now,
        )
        helper_hint_text = self._helper_hint(now)

        return ControlFrameResult(
            runtime_state=self.runtime_state,
            vision=vision,
            trusted_hands=trusted_hands,
            selected=selected,
            click_state=click_state,
            keyboard_update=keyboard_update,
            movement_status=movement_status,
            movement_enabled=movement_enabled,
            click_freeze=click_freeze,
            ml_prediction=ml_prediction,
            ml_status=ml_update.status,
            ml_available=self.ml_predictor is not None,
            ml_reason=self.ml_reason,
            keyboard_toggle_status=keyboard_toggle_update.status,
            drag_active=self.mouse_controller.state.drag_active,
            pre_hold_right_suppressed=pre_hold_right_suppressed,
            press_gestures_safe=press_gestures_safe,
            press_safety_status=press_safety_status,
            gesture_command_text=gesture_command_text,
            helper_hint_text=helper_hint_text,
            ownership_guide=ownership_update.guide,
            ownership_status=ownership_update.status,
        )

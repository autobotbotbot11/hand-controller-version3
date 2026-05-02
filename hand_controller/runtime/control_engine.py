from __future__ import annotations

import time
from dataclasses import dataclass

from ..config.settings import AppConfig
from ..controllers import (
    KeyboardController,
    KeyboardModeToggleController,
    MouseController,
    execute_actions,
)
from ..controllers.actions import Action, Click, DoubleClick, Hotkey, KeyPress, MouseDown, MouseUp
from ..controllers.keyboard_controller import KeyboardUpdate
from ..gestures import (
    HandPinchDetector,
    HandViewSafety,
    MouseClickGestureState,
    MouseClickDetector,
    analyze_hand_view_safety,
    is_palm_facing_thumb_pinky,
)
from ..ml import MLPrediction, MLPredictor, MLControlAdapter
from ..ml.labels import ML_LABEL_HOLD
from ..runtime.state import Mode, RuntimeState
from .diagnostics import log_diagnostic
from ..vision.hand_selector import HandSelector
from ..vision.models import SelectedHands, VisionResult


MOVEMENT_ANCHOR_IDX = 5


def _movement_anchor_norm(hand) -> tuple[float, float]:
    point = hand.landmark(MOVEMENT_ANCHOR_IDX)
    return point.x, point.y


def _hovered_keyboard_label(keyboard_update: KeyboardUpdate, hand_label: str | None) -> str | None:
    if hand_label is None:
        return None
    for label, hovered in keyboard_update.hovered_key_by_hand:
        if label == hand_label:
            return hovered
    return None


@dataclass(frozen=True, slots=True)
class ControlFrameResult:
    runtime_state: RuntimeState
    vision: VisionResult
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
    mode_toggle_status: str
    drag_active: bool
    pre_hold_right_suppressed: bool
    press_gestures_safe: bool
    press_safety_status: str
    gesture_command_text: str


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
        self.mode_toggle_controller = KeyboardModeToggleController(config.keyboard)
        self.runtime_state = RuntimeState()
        self.selector = HandSelector(config.selector)
        self.ml_predictor, self.ml_reason = MLPredictor.try_create(config.ml)
        self.ml_adapter = MLControlAdapter(config.ml)
        self._last_mode = self.runtime_state.mode
        self._gesture_feedback_text = ""
        self._gesture_feedback_until = 0.0
        self._press_safety_by_hand: dict[str, bool] = {}
        self._diag_last_ml_label: str | None = None
        self._diag_last_hold_active: bool | None = None
        self._diag_last_control_enabled: bool | None = None

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

    def _label_for_action(self, action: Action, *, click_status: str | None = None) -> str:
        if isinstance(action, Click):
            if click_status == "Mouse | double click" and action.button == "left":
                return "Double Click"
            return "Left Click" if action.button == "left" else "Right Click"
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
        mode_toggle_status: str,
        ml_status: str,
        now: float,
    ) -> str:
        text = ""
        if "toggled" in mode_toggle_status:
            text = "Keyboard Mode" if self.runtime_state.mode == Mode.KEYBOARD else "Mouse Mode"
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

    def _handle_mode_transition(self, now: float) -> tuple[list[Action], str | None]:
        actions: list[Action] = []
        status: str | None = None

        if self.runtime_state.mode == self._last_mode:
            return actions, status

        self.click_detector.reset()
        self.keyboard_controller.reset()
        mouse_actions, mouse_status = self.mouse_controller.update(
            anchor_norm=None,
            control_enabled=self.runtime_state.control_enabled,
            movement_allowed=False,
            click_enabled=False,
            right_click_allowed=False,
            click_state=MouseClickGestureState(),
            now=now,
        )
        actions.extend(mouse_actions)
        if mouse_actions:
            status = mouse_status

        self._last_mode = self.runtime_state.mode
        return actions, status

    def _should_pre_hold_suppress_right_click(self, prediction: MLPrediction) -> bool:
        if not self.config.ml.pre_hold_right_click_suppression:
            return False
        if not prediction.available:
            return False
        if self.runtime_state.mode != Mode.MOUSE:
            return False
        if not self.runtime_state.control_enabled or self.runtime_state.hold_active:
            return False
        if prediction.raw_label != ML_LABEL_HOLD:
            return False
        return (prediction.p1 or 0.0) >= self.config.ml.pre_hold_min_p1

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

        selected = self.selector.select(vision.hands, vision.frame_width, vision.frame_height)
        active_hand = selected.primary
        hand_safety_by_label = self._analyze_hand_safety(vision.hands)
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
            hands=vision.hands,
            frame_width=vision.frame_width,
            frame_height=vision.frame_height,
            activation_allowed_by_hand={
                label: safety.press_safe for label, safety in hand_safety_by_label.items()
            },
        )
        active_pinch_state = pinch_states.get(active_hand.label) if active_hand is not None else None

        if self.ml_predictor is not None:
            ml_prediction = self.ml_predictor.predict(active_hand)
        else:
            ml_prediction = MLPrediction(available=False, reason=self.ml_reason)
        ml_update = self.ml_adapter.update(ml_prediction, self.runtime_state, now)

        mode_toggle_update = self.mode_toggle_controller.update(
            state=self.runtime_state,
            active_hand=active_hand,
            palm_facing=palm_facing,
            pinch_state=active_pinch_state,
            now=now,
        )

        if self.runtime_state.mode != Mode.MOUSE:
            self.runtime_state.hold_active = False

        transition_actions, transition_status = self._handle_mode_transition(now)

        click_state = MouseClickGestureState()
        keyboard_update = KeyboardUpdate(
            layout=self.keyboard_controller.layout_for_frame(layout_width, layout_height),
            status="keyboard idle",
        )
        movement_status = transition_status or "idle"
        movement_enabled = False
        click_freeze = False
        pre_hold_right_suppressed = self._should_pre_hold_suppress_right_click(ml_prediction)
        action_queue = list(transition_actions)
        action_queue.extend(ml_update.actions)
        feedback_actions = list(ml_update.actions)
        click_feedback_status: str | None = None

        if self.runtime_state.mode == Mode.MOUSE:
            click_enabled = self.runtime_state.control_enabled and not self.runtime_state.hold_active
            if click_enabled:
                click_state = self.click_detector.analyze(
                    active_hand=active_hand,
                    frame_width=vision.frame_width,
                    frame_height=vision.frame_height,
                    activation_allowed=press_gestures_safe,
                )
            else:
                self.click_detector.reset()

            anchor_norm = _movement_anchor_norm(active_hand) if active_hand is not None else None
            movement_enabled = (
                active_hand is not None
                and palm_facing
                and self.runtime_state.control_enabled
                and not self.runtime_state.hold_active
            )
            self.runtime_state.movement_frozen = not movement_enabled

            mouse_actions, mouse_status = self.mouse_controller.update(
                anchor_norm=anchor_norm,
                control_enabled=self.runtime_state.control_enabled,
                movement_allowed=movement_enabled,
                click_enabled=click_enabled,
                press_activation_allowed=press_gestures_safe,
                right_click_allowed=not pre_hold_right_suppressed,
                click_state=click_state,
                now=now,
            )
            action_queue.extend(mouse_actions)
            feedback_actions.extend(mouse_actions)
            movement_status = transition_status or mouse_status
            click_feedback_status = mouse_status
            click_freeze = click_enabled and (
                click_state.right_pressed
                or (click_state.left_pressed and not self.mouse_controller.state.drag_active)
            )
        else:
            self.runtime_state.movement_frozen = True

            if self.runtime_state.control_enabled and self.config.keyboard.virtual_keyboard_enabled:
                keyboard_update = self.keyboard_controller.update(
                    hands=vision.hands,
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
                    status="keyboard disabled" if not self.config.keyboard.virtual_keyboard_enabled else "keyboard control off",
                )

            active_keyboard_hover = _hovered_keyboard_label(
                keyboard_update,
                active_hand.label if active_hand is not None else None,
            )
            keyboard_hybrid_enabled = (
                self.runtime_state.control_enabled
                and self.config.keyboard.virtual_keyboard_enabled
                and active_hand is not None
            )
            keyboard_mouse_movement_allowed = (
                keyboard_hybrid_enabled
                and ml_update.stable_label == ML_LABEL_HOLD
            )
            keyboard_mouse_click_enabled = (
                keyboard_hybrid_enabled
                and active_keyboard_hover is None
                and not keyboard_mouse_movement_allowed
            )

            if keyboard_mouse_click_enabled:
                click_state = self.click_detector.analyze(
                    active_hand=active_hand,
                    frame_width=vision.frame_width,
                    frame_height=vision.frame_height,
                    activation_allowed=press_gestures_safe,
                )
            else:
                self.click_detector.reset()

            anchor_norm = (
                _movement_anchor_norm(active_hand)
                if active_hand is not None and (keyboard_mouse_movement_allowed or keyboard_mouse_click_enabled)
                else None
            )
            mouse_actions, mouse_status = self.mouse_controller.update(
                anchor_norm=anchor_norm,
                control_enabled=self.runtime_state.control_enabled,
                movement_allowed=keyboard_mouse_movement_allowed,
                click_enabled=keyboard_mouse_click_enabled,
                press_activation_allowed=press_gestures_safe,
                right_click_allowed=True,
                click_state=click_state,
                now=now,
            )
            action_queue.extend(mouse_actions)
            feedback_actions.extend(mouse_actions)
            movement_enabled = keyboard_mouse_movement_allowed
            self.runtime_state.movement_frozen = not movement_enabled
            click_feedback_status = mouse_status
            click_freeze = keyboard_mouse_click_enabled and (
                click_state.right_pressed
                or (click_state.left_pressed and not self.mouse_controller.state.drag_active)
            )
            if transition_status is not None:
                movement_status = transition_status
            elif keyboard_mouse_movement_allowed or mouse_actions:
                movement_status = f"keyboard hybrid | {mouse_status}"
            else:
                movement_status = "keyboard mode"

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
            mode_toggle_status=mode_toggle_update.status,
            ml_status=ml_update.status,
            now=now,
        )

        return ControlFrameResult(
            runtime_state=self.runtime_state,
            vision=vision,
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
            mode_toggle_status=mode_toggle_update.status,
            drag_active=self.mouse_controller.state.drag_active,
            pre_hold_right_suppressed=pre_hold_right_suppressed,
            press_gestures_safe=press_gestures_safe,
            press_safety_status=press_safety_status,
            gesture_command_text=gesture_command_text,
        )

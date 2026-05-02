from __future__ import annotations

import time
import threading
import traceback
from typing import TYPE_CHECKING

import cv2

from ..config.settings import AppConfig
from ..controllers.keyboard_controller import KeyboardUpdate
from ..gestures import MouseClickGestureState
from ..ml import MLPrediction, MLPredictor
from ..runtime.control_engine import LiveControlEngine
from ..runtime.diagnostics import diagnostics_enabled, diagnostics_log_path, log_diagnostic
from ..runtime.state import Mode, RuntimeState
from ..ui.payloads import OverlayKeyRect, OverlayPayload, OverlayPointer
from ..vision.camera import Camera
from ..vision.hand_tracker import HandTracker
from ..vision.models import SelectedHands, VisionResult

if TYPE_CHECKING:
    from ..ui.main_window import MainWindow
    from ..ui.signals import OverlaySignalBus


_UI_LIVE_WARMUP_LOCK = threading.Lock()
_UI_LIVE_WARMUP_STARTED = False


def _screen_xy(x_norm: float, y_norm: float, screen_width: int, screen_height: int) -> tuple[int, int]:
    return int(x_norm * screen_width), int(y_norm * screen_height)


def _build_skeleton_lines(
    vision: VisionResult,
    tracker: HandTracker,
    screen_width: int,
    screen_height: int,
) -> tuple[tuple[int, int, int, int], ...]:
    lines: list[tuple[int, int, int, int]] = []
    for hand in vision.hands:
        for start_idx, end_idx in tracker.connections:
            start = hand.landmark(start_idx)
            end = hand.landmark(end_idx)
            x1, y1 = _screen_xy(start.x, start.y, screen_width, screen_height)
            x2, y2 = _screen_xy(end.x, end.y, screen_width, screen_height)
            lines.append((x1, y1, x2, y2))
    return tuple(lines)


def _build_keyboard_keys(keyboard_update: KeyboardUpdate) -> tuple[OverlayKeyRect, ...]:
    return tuple(
        OverlayKeyRect(
            label=key.label,
            x1=key.x1,
            y1=key.y1,
            x2=key.x2,
            y2=key.y2,
        )
        for key in keyboard_update.layout
    )


def _build_pointer_payload(keyboard_update: KeyboardUpdate) -> tuple[OverlayPointer, ...]:
    return tuple(
        OverlayPointer(
            x=pointer.x,
            y=pointer.y,
            hand_label="L" if pointer.hand_label == "Left" else "R" if pointer.hand_label == "Right" else pointer.hand_label,
            thumb_x=pointer.thumb_x,
            thumb_y=pointer.thumb_y,
            index_x=pointer.index_x,
            index_y=pointer.index_y,
        )
        for pointer in keyboard_update.pointers
    )


def _build_selfie_frame(frame_bgr, *, width: int, height: int) -> object | None:
    try:
        return cv2.resize(frame_bgr, (width, height))
    except Exception:
        return None


def _build_debug_tags(
    *,
    selected: SelectedHands,
    runtime_state: RuntimeState,
    movement_enabled: bool,
    click_state: MouseClickGestureState,
    drag_active: bool,
    ml_prediction: MLPrediction,
    ml_status: str,
    mode_toggle_status: str,
    ml_available: bool,
    ml_reason: str | None,
    pre_hold_right_suppressed: bool,
    press_gestures_safe: bool,
    press_safety_status: str,
) -> tuple[str, ...]:
    active_label = selected.primary.label if selected.primary is not None else "-"
    ml_line = "  ".join(
        [
            f"active={active_label}",
            f"ml={'on' if ml_available else 'off'}",
            f"raw={ml_prediction.raw_label}",
            f"stable={runtime_state.latest_ml_label}",
            f"p1={ml_prediction.p1:.2f}" if ml_prediction.p1 is not None else "p1=-",
            f"margin={ml_prediction.margin:.2f}" if ml_prediction.margin is not None else "margin=-",
            f"ml_status={ml_status}",
        ]
    )
    mouse_line = "  ".join(
        [
            f"hold={'yes' if runtime_state.hold_active else 'no'}",
            f"presssafe={'yes' if press_gestures_safe else 'no'}",
            f"prehold_r={'on' if pre_hold_right_suppressed else 'off'}",
            f"movement={'on' if movement_enabled else 'off'}",
            f"drag={'yes' if drag_active else 'no'}",
            f"click_idx={'down' if click_state.left_pressed else 'up'}",
            f"click_mid={'down' if click_state.right_pressed else 'up'}",
            mode_toggle_status,
        ]
    )
    tags = [ml_line, mouse_line, press_safety_status]
    if not ml_available and ml_reason:
        tags.append(f"ml_reason={ml_reason}")
    return tuple(tags)


def _build_overlay_payload(
    *,
    runtime_state: RuntimeState,
    keyboard_update: KeyboardUpdate,
    skeleton_lines: tuple[tuple[int, int, int, int], ...],
    selfie_frame,
    mouse_status: str,
    movement_enabled: bool,
    gesture_command_text: str,
    debug_tags: tuple[str, ...],
) -> OverlayPayload:
    keyboard_visible = runtime_state.control_enabled and runtime_state.mode == Mode.KEYBOARD
    return OverlayPayload(
        mode=runtime_state.mode.value,
        control_enabled=runtime_state.control_enabled,
        keyboard_visible=keyboard_visible,
        keyboard_dimmed=keyboard_visible and movement_enabled,
        keyboard_keys=_build_keyboard_keys(keyboard_update) if keyboard_visible else (),
        highlight_labels=keyboard_update.highlight_labels if keyboard_visible else frozenset(),
        finger_points=_build_pointer_payload(keyboard_update) if keyboard_visible else (),
        skeleton_lines=skeleton_lines,
        mouse_status=mouse_status,
        keyboard_status=keyboard_update.status if keyboard_visible else "",
        profile_label="live-overlay",
        footer_hint="Live overlay path | close the control panel window to stop",
        selfie_frame=selfie_frame,
        gesture_command_text=gesture_command_text,
        debug_tags=debug_tags,
    )


def run_ui_live_worker(
    overlay_bus,
    stop_event,
    config: AppConfig,
    screen_width: int,
    screen_height: int,
) -> None:
    try:
        log_diagnostic("worker=start")
        engine = LiveControlEngine(config, screen_width=screen_width, screen_height=screen_height)

        with Camera(
            index=config.camera.index,
            width=config.camera.width,
            height=config.camera.height,
        ) as camera, HandTracker(
            max_num_hands=config.tracker.max_num_hands,
            min_detection_confidence=config.tracker.min_detection_confidence,
            min_tracking_confidence=config.tracker.min_tracking_confidence,
        ) as tracker:
            if not camera.is_opened():
                raise RuntimeError("Unable to open the configured camera.")

            while not stop_event.is_set():
                ok, frame_bgr = camera.read()
                if not ok:
                    continue

                if config.tracker.mirror_input:
                    frame_bgr = cv2.flip(frame_bgr, 1)

                vision = tracker.track_bgr_frame(frame_bgr)
                now = time.time()
                frame_result = engine.process_frame(
                    vision,
                    layout_width=screen_width,
                    layout_height=screen_height,
                    now=now,
                )

                payload = _build_overlay_payload(
                    runtime_state=frame_result.runtime_state,
                    keyboard_update=frame_result.keyboard_update,
                    skeleton_lines=_build_skeleton_lines(frame_result.vision, tracker, screen_width, screen_height),
                    selfie_frame=_build_selfie_frame(
                        frame_bgr,
                        width=config.keyboard.selfie_width_px,
                        height=config.keyboard.selfie_height_px,
                    ),
                    mouse_status=frame_result.movement_status,
                    movement_enabled=frame_result.movement_enabled,
                    gesture_command_text=frame_result.gesture_command_text,
                    debug_tags=_build_debug_tags(
                        selected=frame_result.selected,
                        runtime_state=frame_result.runtime_state,
                        movement_enabled=frame_result.movement_enabled,
                        click_state=frame_result.click_state,
                        drag_active=frame_result.drag_active,
                        ml_prediction=frame_result.ml_prediction,
                        ml_status=frame_result.ml_status,
                        mode_toggle_status=frame_result.mode_toggle_status,
                        ml_available=frame_result.ml_available,
                        ml_reason=frame_result.ml_reason,
                        pre_hold_right_suppressed=frame_result.pre_hold_right_suppressed,
                        press_gestures_safe=frame_result.press_gestures_safe,
                        press_safety_status=frame_result.press_safety_status,
                    ),
                )
                try:
                    overlay_bus.update_overlay.emit(payload)
                except Exception:
                    return
    except Exception as exc:
        error_payload = OverlayPayload(
            mode="error",
            control_enabled=False,
            keyboard_visible=False,
            mouse_status="worker failed",
            keyboard_status="",
            profile_label="live-overlay",
            footer_hint="See terminal traceback. Close the control panel window to stop.",
            debug_tags=(
                f"worker_error={exc}",
                traceback.format_exc(limit=3).replace("\n", " | "),
            ),
        )
        try:
            log_diagnostic(f"worker=error detail={exc}")
            overlay_bus.update_overlay.emit(error_payload)
        except Exception:
            pass
        raise


def _prewarm_ui_live_components(config: AppConfig) -> None:
    try:
        MLPredictor.try_create(config.ml)
    except Exception:
        pass

    try:
        tracker = HandTracker(
            max_num_hands=config.tracker.max_num_hands,
            min_detection_confidence=config.tracker.min_detection_confidence,
            min_tracking_confidence=config.tracker.min_tracking_confidence,
        )
    except Exception:
        return

    try:
        tracker.close()
    except Exception:
        pass


def _start_ui_live_warmup(config: AppConfig) -> None:
    global _UI_LIVE_WARMUP_STARTED
    with _UI_LIVE_WARMUP_LOCK:
        if _UI_LIVE_WARMUP_STARTED:
            return
        _UI_LIVE_WARMUP_STARTED = True

    thread = threading.Thread(
        target=_prewarm_ui_live_components,
        args=(config,),
        name="ui-live-prewarm",
        daemon=True,
    )
    thread.start()


def run_ui_live_control(config: AppConfig) -> None:
    log_diagnostic(
        "ui_live=start "
        f"tuning={config.tuning_path or 'defaults'} "
        f"camera={config.camera.width}x{config.camera.height}@{config.camera.index} "
        f"theme={config.general.theme} "
        f"log={diagnostics_log_path()}"
    )
    try:
        import mediapipe  # noqa: F401
    except Exception as exc:
        log_diagnostic(f"ui_live=mediapipe_import_fail detail={exc}")
        raise RuntimeError(
            "MediaPipe failed to initialize before the Qt UI startup. On this Windows setup, mediapipe must load before PyQt5."
        ) from exc

    try:
        from PyQt5.QtWidgets import QApplication
        from ..ui.main_window import MainWindow
    except ModuleNotFoundError as exc:
        log_diagnostic(f"ui_live=pyqt_import_fail detail={exc}")
        raise RuntimeError(
            "PyQt5 is required for --ui-live. Install requirements.txt first."
        ) from exc

    app = QApplication.instance() or QApplication([])
    window = MainWindow(
        config=config,
        worker_fn=run_ui_live_worker,
        ui_mode_label="Live Control",
        start_button_label="LAUNCH",
        stop_button_label="STOP",
        info_text=(
            ""
        ),
    )
    _start_ui_live_warmup(config)
    window.show()
    if diagnostics_enabled():
        log_diagnostic("ui_live=window_shown")
    app.exec_()
    log_diagnostic("ui_live=exit")

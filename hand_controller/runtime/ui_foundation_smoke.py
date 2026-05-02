from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

from ..config.settings import AppConfig
from ..controllers.keyboard_controller import KeyboardController
from ..ui.payloads import OverlayKeyRect, OverlayPayload, OverlayPointer

if TYPE_CHECKING:
    from ..ui.main_window import MainWindow
    from ..ui.signals import OverlaySignalBus


def _build_overlay_keys(config: AppConfig, screen_width: int, screen_height: int) -> tuple[OverlayKeyRect, ...]:
    controller = KeyboardController(config.keyboard)
    layout = controller.layout_for_frame(screen_width, screen_height)
    return tuple(
        OverlayKeyRect(
            label=key.label,
            x1=key.x1,
            y1=key.y1,
            x2=key.x2,
            y2=key.y2,
        )
        for key in layout
    )


def _build_mock_payload(
    *,
    keyboard_keys: tuple[OverlayKeyRect, ...],
    elapsed: float,
) -> OverlayPayload:
    keyboard_visible = True
    mode = "keyboard" if elapsed % 6.0 < 3.8 else "mouse"
    keyboard_visible = mode == "keyboard"

    highlight_labels: frozenset[str] = frozenset()
    pointers: tuple[OverlayPointer, ...] = ()

    if keyboard_visible and keyboard_keys:
        active_index = int((elapsed * 2.0) % len(keyboard_keys))
        active_key = keyboard_keys[active_index]
        highlight_labels = frozenset({active_key.label})
        px = (active_key.x1 + active_key.x2) // 2
        py = (active_key.y1 + active_key.y2) // 2
        pointers = (
            OverlayPointer(x=px, y=py, hand_label="R"),
        )

    oscillation = int(20 * math.sin(elapsed * 1.6))
    skeleton_lines = (
        (980, 180 + oscillation, 1030, 260 + oscillation),
        (1030, 260 + oscillation, 1095, 320 + oscillation),
        (1030, 260 + oscillation, 980, 340 + oscillation),
        (1030, 260 + oscillation, 1115, 255 + oscillation),
        (1030, 260 + oscillation, 1125, 185 + oscillation),
    )

    keyboard_status = "ui smoke | hover + pinch typing path will connect here"
    mouse_status = "ui smoke | mouse overlay path placeholder"

    return OverlayPayload(
        mode=mode,
        control_enabled=True,
        keyboard_visible=keyboard_visible,
        keyboard_keys=keyboard_keys,
        highlight_labels=highlight_labels,
        finger_points=pointers,
        skeleton_lines=skeleton_lines,
        mouse_status=mouse_status,
        keyboard_status=keyboard_status,
        profile_label="ui-foundation",
        footer_hint="UI foundation smoke | close the control panel to stop",
        debug_tags=(
            "transparent overlay + signal bus + worker thread active",
        ),
    )


def run_ui_foundation_worker(
    overlay_bus,
    stop_event,
    config: AppConfig,
    screen_width: int,
    screen_height: int,
) -> None:
    keyboard_keys = _build_overlay_keys(config, screen_width, screen_height)
    started_at = time.time()

    while not stop_event.is_set():
        elapsed = time.time() - started_at
        payload = _build_mock_payload(
            keyboard_keys=keyboard_keys,
            elapsed=elapsed,
        )
        try:
            overlay_bus.update_overlay.emit(payload)
        except Exception:
            return
        time.sleep(1.0 / 30.0)


def run_ui_foundation_smoke(config: AppConfig) -> None:
    try:
        from PyQt5.QtWidgets import QApplication
        from ..ui.main_window import MainWindow
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PyQt5 is required for --ui-smoke. Install requirements.txt first."
        ) from exc

    app = QApplication.instance() or QApplication([])
    window = MainWindow(
        config=config,
        worker_fn=run_ui_foundation_worker,
        ui_mode_label="Overlay Preview",
        start_button_label="LAUNCH",
        stop_button_label="STOP",
        info_text=(
            "This preview checks the control panel and transparent overlay flow.\n"
            "It uses mock overlay content instead of the live camera runtime."
        ),
    )
    window.show()
    app.exec_()

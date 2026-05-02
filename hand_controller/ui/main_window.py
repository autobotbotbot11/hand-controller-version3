from __future__ import annotations

import json
import math
import sys
import threading
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from PyQt5.QtCore import QPointF, QRectF, QSize, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPalette, QPen, QPixmap, QPolygonF, QRadialGradient
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QStackedWidget,
    QToolTip,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..config.settings import AppConfig, RUNTIME_APP_DIR, RUNTIME_BUNDLE_ROOT, build_factory_default_config
from ..vision.camera import CameraSource, detect_available_cameras, probe_camera_index
from .overlay_window import OverlayWindow
from .quick_toolbar_window import QuickToolbarWindow
from .selfie_window import SelfieWindow
from .signals import OverlaySignalBus

if sys.platform == "win32":
    import winreg


WorkerFn = Callable[[OverlaySignalBus, threading.Event, AppConfig, int, int], None]

PAGE_ORDER = ["GENERAL", "CAMERA", "DISPLAY", "KEYBOARD", "MOUSE"]
SELFIE_POSITIONS = [
    ("Top Left", "top_left"),
    ("Top Right", "top_right"),
    ("Bottom Left", "bottom_left"),
    ("Bottom Right", "bottom_right"),
    ("Custom", "custom"),
]
GESTURE_COMMAND_POSITIONS = [("Top", "top"), ("Center", "center"), ("Bottom", "bottom")]
HELP_TEXT = {
    "mouse_sensitivity": "Adjusts how strongly hand movement affects cursor movement.",
    "mouse_smoothness": "Adds more smoothing to reduce mouse jitter.",
    "mouse_dead_zone": "Ignores very small hand movement near the resting position.",
    "tap_sensitivity": "Controls how close thumb and index finger must be to count as a keyboard tap.",
    "tap_cooldown": "Minimum delay before another keyboard tap is accepted.",
    "keyboard_enable": "Turns the virtual keyboard feature on or off.",
    "camera_enable": "Turns camera input on or off.",
    "camera_source": "Selects which detected camera index the app should use. Hardware names are shown when Windows exposes them reliably.",
    "show_hand_skeleton": "Shows or hides hand skeleton lines on the overlay.",
    "hand_skeleton_thickness": "Adjusts skeleton line thickness.",
    "show_live_selfie": "Shows or hides the live selfie preview on the overlay.",
    "selfie_position": "Chooses where the selfie preview appears on screen. Dragging the selfie sets a custom position.",
    "selfie_size": "Adjusts the size of the live selfie preview.",
    "show_gesture_command": "Shows or hides text feedback for recognized gestures.",
    "gesture_command_position": "Chooses where the gesture feedback text appears on screen.",
    "minimize_after_launch": "Minimizes the window to the taskbar after launch.",
}

LIGHT_THEME = {
    "sidebar_bg": "#1e2433",
    "sidebar_border": "#2c3347",
    "content_bg": "#f4f1eb",
    "page_bg": "#f4f1eb",
    "frame_bg": "#f4f1eb",
    "card_bg": "#fffffff8",
    "card_border": "#e2ddd6",
    "text_primary": "#1a1a24",
    "text_secondary": "#6b6860",
    "value_text": "#8a857d",
    "outline_bg": "#ffffff",
    "outline_border": "#d9d5ce",
    "outline_text": "#5a5650",
    "outline_hover_bg": "#f7f3ee",
    "outline_hover_border": "#cdc6bc",
    "outline_hover_text": "#444038",
    "danger_border": "#d63030",
    "danger_text": "#b52020",
    "danger_hover_bg": "#fff3f1",
    "danger_hover_border": "#cb4242",
    "danger_hover_text": "#a81c1c",
    "combo_bg": "#ffffff",
    "combo_border": "#d9d5ce",
    "combo_text": "#2c2a26",
    "combo_arrow": "#3d7a60",
    "combo_popup_bg": "#ffffff",
    "combo_popup_border": "#d9d5ce",
    "combo_popup_text": "#2c2a26",
    "combo_popup_sel_bg": "#e8f2ed",
    "combo_popup_sel_text": "#1a1a24",
    "slider_groove": "#dedad4",
    "slider_fill": "#5db890",
    "slider_handle": "#ffffff",
    "slider_handle_border": "#d0c8bc",
    "accent": "#3d7a60",
    "accent2": "#5db890",
    "help_border": "#3d7a60",
    "help_text": "#3d7a60",
    "help_bg": "#e8f2ed",
    "help_hover_bg": "#c8e4d8",
    "tooltip_bg": "#ffffff",
    "tooltip_border": "#d9d5ce",
    "tooltip_text": "#1a1a24",
    "nav_active_bg": "#2e3a50",
    "nav_indicator": "#eef0f5",
    "nav_text_active": "#eef0f5",
    "nav_text_inactive": "#8891a8",
    "launch_fill": "#ececef",
    "launch_text": "#ffffff",
    "stop_fill": "#f8eaea",
    "stop_text": "#b52020",
    "close_fill": "#2e3a50",
    "close_text": "#c5cdd8",
    "toggle_off_track": "#d5d0c8",
    "toggle_off_border": "#c2bdb5",
    "toggle_off_knob": "#ffffff",
    "status_dot_on": "#3d9e6c",
    "status_dot_off": "#9ea8b8",
    "dialog_bg": "#f9f6f0",
    "dialog_border": "#d9d5ce",
    "df_bg": "#f2ede4",
    "df_orbs": [
        {"color": "#7a9e8a", "alpha": 0.13, "r_frac": 0.70},
        {"color": "#5a7a8e", "alpha": 0.10, "r_frac": 0.62},
        {"color": "#9aaa88", "alpha": 0.09, "r_frac": 0.78},
    ],
    "df_line": "#3d7a60",
    "df_line_alpha": 0.028,
    "df_line_spacing": 28,
}

DARK_THEME = {
    "sidebar_bg": "#18181c",
    "sidebar_border": "#28282e",
    "content_bg": "#111115",
    "page_bg": "#111115",
    "frame_bg": "#111115",
    "card_bg": "#1c1c22ee",
    "card_border": "#28282e",
    "text_primary": "#f0f0f6",
    "text_secondary": "#6a6a78",
    "value_text": "#6a6a78",
    "outline_bg": "#1c1c22",
    "outline_border": "#30303a",
    "outline_text": "#8d8d9a",
    "outline_hover_bg": "#23232b",
    "outline_hover_border": "#40404c",
    "outline_hover_text": "#b7b7c8",
    "danger_border": "#9b2828",
    "danger_text": "#ff5555",
    "danger_hover_bg": "#251a1b",
    "danger_hover_border": "#ba3838",
    "danger_hover_text": "#ff7676",
    "combo_bg": "#1c1c22",
    "combo_border": "#30303a",
    "combo_text": "#9898a8",
    "combo_arrow": "#9898a8",
    "combo_popup_bg": "#1c1c22",
    "combo_popup_border": "#30303a",
    "combo_popup_text": "#d0d0e0",
    "combo_popup_sel_bg": "#2a2a38",
    "combo_popup_sel_text": "#f0f0f6",
    "slider_groove": "#26262e",
    "slider_fill": "#6272ff",
    "slider_handle": "#e0e0e8",
    "slider_handle_border": "#d0d0d4",
    "accent": "#6272ff",
    "accent2": "#a78bfa",
    "help_border": "#9898b8",
    "help_text": "#9898b8",
    "help_bg": "#2a2a36",
    "help_hover_bg": "#383848",
    "tooltip_bg": "#242430",
    "tooltip_border": "#383848",
    "tooltip_text": "#f0f0f6",
    "nav_active_bg": "#22222c",
    "nav_indicator": "#f1f2ff",
    "nav_text_active": "#f0f0f6",
    "nav_text_inactive": "#55556a",
    "launch_fill": "#ffffff",
    "launch_text": "#111111",
    "stop_fill": "#2e1e1e",
    "stop_text": "#ff8888",
    "close_fill": "#222228",
    "close_text": "#aaaabc",
    "toggle_off_track": "#26262e",
    "toggle_off_border": "#30303a",
    "toggle_off_knob": "#d0d0e0",
    "status_dot_on": "#22c55e",
    "status_dot_off": "#4b5563",
    "dialog_bg": "#18181f",
    "dialog_border": "#30303a",
    "df_bg": "#0d0d12",
    "df_orbs": [
        {"color": "#3a3f8f", "alpha": 0.18, "r_frac": 0.72},
        {"color": "#5c3f8a", "alpha": 0.13, "r_frac": 0.60},
        {"color": "#1a2a6e", "alpha": 0.12, "r_frac": 0.80},
    ],
    "df_line": "#6272ff",
    "df_line_alpha": 0.030,
    "df_line_spacing": 28,
}


def _theme_for(widget: QWidget) -> dict[str, str]:
    window = widget.window()
    mode = getattr(window, "_resolved_theme_mode", "light")
    return DARK_THEME if mode == "dark" else LIGHT_THEME


def _windows_system_theme_mode() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if int(value) == 1 else "dark"
    except Exception:
        return None


class DepthFieldBackground(QWidget):
    TICK_MS = 40

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._t = 0.0
        self._orb_params = [
            {"fx": 0.00031, "fy": 0.00019, "px": 0.0, "py": 1.1},
            {"fx": 0.00023, "fy": 0.00037, "px": 2.1, "py": 0.4},
            {"fx": 0.00017, "fy": 0.00027, "px": 4.3, "py": 3.0},
        ]
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(self.TICK_MS)
        self._timer = timer

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.update()

    def _tick(self) -> None:
        self._t += self.TICK_MS
        self.update()

    def _orb_centre(self, idx: int, width: float, height: float) -> tuple[float, float]:
        orb = self._orb_params[idx]
        t = self._t
        cx = width * 0.5 + width * 0.30 * math.sin(orb["fx"] * t + orb["px"])
        cy = height * 0.5 + height * 0.28 * math.cos(orb["fy"] * t + orb["py"])
        return cx, cy

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = _theme_for(self)
        width = float(self.width())
        height = float(self.height())

        painter.fillRect(self.rect(), QColor(colors["df_bg"]))
        painter.setPen(Qt.NoPen)

        for idx, orb_def in enumerate(colors["df_orbs"]):
            cx, cy = self._orb_centre(idx, width, height)
            radius = min(width, height) * orb_def["r_frac"] * 1.10
            base = QColor(orb_def["color"])
            grad = QRadialGradient(QPointF(cx, cy), radius)
            inner = QColor(base)
            inner.setAlphaF(min(1.0, orb_def["alpha"] * 1.08))
            mid = QColor(base)
            mid.setAlphaF(orb_def["alpha"] * 0.52)
            edge = QColor(base)
            edge.setAlphaF(0.0)
            grad.setColorAt(0.0, inner)
            grad.setColorAt(0.68, mid)
            grad.setColorAt(1.0, edge)
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QPointF(cx, cy), radius, radius)

        spacing = colors["df_line_spacing"]
        line_color = QColor(colors["df_line"])
        line_color.setAlphaF(colors["df_line_alpha"])
        painter.setPen(QPen(line_color, 0.5))
        painter.setBrush(Qt.NoBrush)
        int_width = int(width)
        int_height = int(height)

        x = -int_height
        while x < int_width + int_height:
            painter.drawLine(QPointF(float(x), 0.0), QPointF(float(x + int_height), float(int_height)))
            x += spacing

        x = -int_height
        while x < int_width + int_height:
            painter.drawLine(QPointF(float(x + int_height), 0.0), QPointF(float(x), float(int_height)))
            x += spacing


class ContentFrame(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("contentFrame")
        self._bg: DepthFieldBackground | None = None

    def attach_bg(self, bg: DepthFieldBackground) -> None:
        self._bg = bg
        bg.setGeometry(0, 0, self.width(), self.height())
        bg.lower()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._bg is not None:
            self._bg.setGeometry(0, 0, self.width(), self.height())


class StatusDot(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(10, 10)
        self._running = False
        self._opacity = 1.0
        self._rising = False
        timer = QTimer(self)
        timer.timeout.connect(self._pulse)
        timer.start(30)
        self._timer = timer

    def set_running(self, running: bool) -> None:
        self._running = running
        self._opacity = 1.0
        self.update()

    def _pulse(self) -> None:
        if not self._running:
            return
        if self._rising:
            self._opacity = min(1.0, self._opacity + 0.03)
            self._rising = self._opacity < 1.0
        else:
            self._opacity = max(0.3, self._opacity - 0.03)
            self._rising = self._opacity <= 0.3
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = _theme_for(self)
        color = QColor(colors["status_dot_on"] if self._running else colors["status_dot_off"])
        color.setAlphaF(self._opacity if self._running else 1.0)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(1, 1, 8, 8)


class SidebarPillButton(QPushButton):
    def __init__(self, text: str, *, icon_kind: str, launch: bool) -> None:
        super().__init__(text)
        self.icon_kind = icon_kind
        self.launch = launch
        self._glow = 0.0
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setMinimumHeight(58 if launch else 40)
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(16)
        self._timer = timer

    def _tick(self) -> None:
        target = 1.0 if self.underMouse() else 0.0
        delta = target - self._glow
        self._glow = target if abs(delta) < 0.04 else self._glow + delta * 0.14
        if abs(delta) > 0.001:
            self.update()

    def set_icon_kind(self, icon_kind: str) -> None:
        self.icon_kind = icon_kind
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(160, 58 if self.launch else 40)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = _theme_for(self)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = 18 if self.launch else 8

        if self.launch and self.icon_kind == "play":
            fill = QColor(colors["launch_fill"])
            text_color = QColor(colors["launch_text"])
        elif self.launch and self.icon_kind == "stop":
            fill = QColor(colors["stop_fill"])
            text_color = QColor(colors["stop_text"])
        else:
            fill = QColor(colors["close_fill"])
            text_color = QColor(colors["close_text"])
        if self.isDown():
            fill = fill.darker(104)

        painter.setPen(Qt.NoPen)
        if self.launch and self.icon_kind == "play":
            gradient = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
            gradient.setColorAt(0, QColor(colors["accent"]))
            gradient.setColorAt(1, QColor(colors["accent2"]))
            painter.setBrush(QBrush(gradient))
        else:
            painter.setBrush(QBrush(fill))
        painter.drawRoundedRect(rect, radius, radius)

        if self._glow > 0.01:
            glow = QColor("#ffffff") if (self.launch and self.icon_kind == "play") else QColor(colors["accent"])
            glow.setAlphaF(self._glow * (0.08 if self.launch else 0.10))
            painter.setBrush(QBrush(glow))
            painter.drawRoundedRect(rect, radius, radius)

        icon_center_x = 26 if self.launch else 18
        icon_center_y = rect.center().y()

        painter.setBrush(QBrush(text_color))
        painter.setPen(QPen(text_color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))

        if self.icon_kind == "play":
            triangle = QPolygonF(
                [
                    QPointF(icon_center_x - 6, icon_center_y - 9),
                    QPointF(icon_center_x - 6, icon_center_y + 9),
                    QPointF(icon_center_x + 9, icon_center_y),
                ]
            )
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(triangle)
        elif self.icon_kind == "stop":
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(QRectF(icon_center_x - 7, icon_center_y - 7, 14, 14), 3, 3)
        elif self.icon_kind == "close":
            painter.drawLine(QPointF(icon_center_x - 6, icon_center_y - 6), QPointF(icon_center_x + 6, icon_center_y + 6))
            painter.drawLine(QPointF(icon_center_x + 6, icon_center_y - 6), QPointF(icon_center_x - 6, icon_center_y + 6))

        text_x = 52 if self.launch else 38
        painter.setPen(text_color)
        painter.setFont(QFont("Segoe UI", 10 if self.launch else 9, QFont.Bold))
        painter.drawText(QRectF(text_x, 0, rect.width() - text_x - 14, rect.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())


class ToggleSwitch(QCheckBox):
    def __init__(self) -> None:
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(42, 22)
        self._knob_x = 2.0
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(16)
        self._timer = timer

    def _tick(self) -> None:
        track_height = self.height() - 2
        knob_size = track_height - 4
        target = (self.width() - 2 - knob_size - 2) if self.isChecked() else 2.0
        delta = target - self._knob_x
        self._knob_x = target if abs(delta) < 0.5 else self._knob_x + delta * 0.22
        if abs(delta) > 0.001:
            self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(42, 22)

    def hitButton(self, pos) -> bool:  # noqa: N802
        return self.rect().contains(pos)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = _theme_for(self)

        track_rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        track_height = track_rect.height()
        knob_size = track_height - 4
        travel = track_rect.width() - knob_size - 4
        progress = max(0.0, min(1.0, (self._knob_x - 2.0) / travel)) if travel > 0 else 0.0

        if progress > 0.01:
            gradient = QLinearGradient(track_rect.left(), 0, track_rect.right(), 0)
            off_color = QColor(colors["toggle_off_track"])
            on_color = QColor(colors["accent"])
            on_color_2 = QColor(colors["accent2"])

            def blend(a: QColor, b: QColor, amount: float) -> QColor:
                return QColor(
                    int(a.red() * (1 - amount) + b.red() * amount),
                    int(a.green() * (1 - amount) + b.green() * amount),
                    int(a.blue() * (1 - amount) + b.blue() * amount),
                )

            start = blend(off_color, on_color, progress * 0.85)
            end = blend(off_color, on_color_2, progress)
            gradient.setColorAt(0, start)
            gradient.setColorAt(1, end)
            track_brush = QBrush(gradient)
            border_color = blend(off_color, on_color, progress)
        else:
            track_brush = QBrush(QColor(colors["toggle_off_track"]))
            border_color = QColor(colors["toggle_off_border"])

        knob_color = QColor("#d9d9dc" if self.isChecked() else colors["toggle_off_knob"])

        painter.setPen(QPen(border_color, 1))
        painter.setBrush(track_brush)
        painter.drawRoundedRect(track_rect, track_rect.height() / 2.0, track_rect.height() / 2.0)

        knob_rect = QRectF(self._knob_x, track_rect.top() + 2, knob_size, knob_size)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(knob_color))
        painter.drawEllipse(knob_rect)


class NavButton(QPushButton):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self._active = False
        self._hover_amount = 0.0
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setCheckable(True)
        self.setFixedHeight(38)
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(16)
        self._timer = timer

    def _tick(self) -> None:
        target = 1.0 if (self.underMouse() or self._active) else 0.0
        step = 0.08
        delta = target - self._hover_amount
        self._hover_amount = target if abs(delta) < step else self._hover_amount + (step if delta > 0 else -step)
        if abs(delta) > 0.001:
            self.update()

    def set_active(self, active: bool) -> None:
        self._active = active
        self.setChecked(active)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = _theme_for(self)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self._hover_amount > 0.001:
            pill_rect = QRectF(rect.left() + 5, rect.top() + 1, rect.width() - 5, rect.height() - 2)
            pill_color = QColor(colors["nav_active_bg"])
            pill_color.setAlphaF(self._hover_amount * (1.0 if self._active else 0.55))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(pill_color))
            painter.drawRoundedRect(pill_rect, 8, 8)

        if self._active:
            indicator_rect = QRectF(pill_rect.left() + 2, rect.top() + 11, 2, rect.height() - 22)
            indicator_gradient = QLinearGradient(0, indicator_rect.top(), 0, indicator_rect.bottom())
            indicator_gradient.setColorAt(0, QColor(colors["accent"]))
            indicator_gradient.setColorAt(1, QColor(colors["accent2"]))
            painter.setBrush(QBrush(indicator_gradient))
            painter.drawRoundedRect(indicator_rect, 1.0, 1.0)

        painter.setPen(QColor(colors["nav_text_active"] if self._active else colors["nav_text_inactive"]))
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold if self._active else QFont.DemiBold))
        painter.drawText(
            QRectF(rect.left() + 18, rect.top(), rect.width() - 18, rect.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.text(),
        )


class HelpBadge(QWidget):
    def __init__(self, tip: str) -> None:
        super().__init__()
        self._hovered = False
        self._tip = tip
        self.setFixedSize(18, 18)
        self.setCursor(Qt.ArrowCursor)
        self.setToolTip(tip)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self.update()
        QToolTip.showText(
            self.mapToGlobal(self.rect().bottomRight()),
            self._tip,
            self,
            self.rect(),
        )
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self.update()
        QToolTip.hideText()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = _theme_for(self)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(colors["help_hover_bg"] if self._hovered else colors["help_bg"])))
        painter.drawEllipse(QRectF(1, 1, 16, 16))
        painter.setPen(QColor(colors["accent"] if self._hovered else colors["help_text"]))
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.drawText(QRectF(0, 0, 18, 18), Qt.AlignCenter, "?")


class ResetConfirmDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._mode = getattr(parent, "_resolved_theme_mode", "light")
        self.setFixedSize(310, 148)
        self._build()
        self._apply_theme()
        parent_geometry = parent.geometry()
        self.move(parent_geometry.center() - self.rect().center())

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QWidget()
        card.setObjectName("rcCard")
        root.addWidget(card)

        content = QVBoxLayout(card)
        content.setContentsMargins(24, 22, 24, 20)
        content.setSpacing(8)

        title = QLabel("Reset to Default?")
        title.setObjectName("rcTitle")
        content.addWidget(title)

        subtitle = QLabel("All settings will return to their original values.")
        subtitle.setObjectName("rcSub")
        subtitle.setWordWrap(True)
        content.addWidget(subtitle)

        content.addStretch(1)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        back_button = QPushButton("Back")
        back_button.setObjectName("rcBack")
        back_button.setFixedHeight(34)
        back_button.setCursor(Qt.PointingHandCursor)
        back_button.clicked.connect(self.reject)

        apply_button = QPushButton("Apply Reset")
        apply_button.setObjectName("rcApply")
        apply_button.setFixedHeight(34)
        apply_button.setCursor(Qt.PointingHandCursor)
        apply_button.clicked.connect(self.accept)

        button_row.addWidget(back_button)
        button_row.addWidget(apply_button)
        content.addLayout(button_row)

    def _apply_theme(self) -> None:
        colors = DARK_THEME if self._mode == "dark" else LIGHT_THEME
        self.setStyleSheet(
            f"""
            QWidget#rcCard {{
                background: {colors["dialog_bg"]};
                border: 1px solid {colors["dialog_border"]};
                border-radius: 14px;
            }}
            QLabel#rcTitle {{
                font-family: "Segoe UI";
                font-size: 14px;
                font-weight: 800;
                color: {colors["text_primary"]};
                background: transparent;
            }}
            QLabel#rcSub {{
                font-family: "Segoe UI";
                font-size: 11px;
                color: {colors["text_secondary"]};
                background: transparent;
            }}
            QPushButton#rcBack {{
                font-family: "Segoe UI";
                font-size: 11px;
                font-weight: 700;
                background: {colors["outline_bg"]};
                border: 1px solid {colors["outline_border"]};
                border-radius: 8px;
                color: {colors["outline_text"]};
                padding: 0 14px;
            }}
            QPushButton#rcBack:hover {{
                border-color: {colors["accent"]};
                color: {colors["accent"]};
            }}
            QPushButton#rcApply {{
                font-family: "Segoe UI";
                font-size: 11px;
                font-weight: 700;
                border: none;
                border-radius: 8px;
                color: #ffffff;
                padding: 0 14px;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {colors["danger_border"]},
                    stop:1 {colors["danger_text"]}
                );
            }}
            """
        )


class ThemedComboBox(QComboBox):
    def __init__(self) -> None:
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(24)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = _theme_for(self)

        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.setPen(QPen(QColor(colors["combo_border"]), 1))
        painter.setBrush(QBrush(QColor(colors["combo_bg"])))
        painter.drawRoundedRect(rect, 6, 6)

        painter.setPen(QColor(colors["combo_text"]))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(QRectF(9, 0, self.width() - 30, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.currentText())

        arrow_pen = QPen(QColor(colors["combo_arrow"]), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(arrow_pen)
        painter.setBrush(Qt.NoBrush)
        ax = self.width() - 17
        ay = self.height() / 2 - 3
        painter.drawPolyline(QPolygonF([QPointF(ax, ay), QPointF(ax + 5, ay + 5), QPointF(ax + 10, ay)]))

    def showPopup(self) -> None:  # noqa: N802
        colors = _theme_for(self)
        self.setStyleSheet(
            f"""
            QComboBox QAbstractItemView {{
                background-color: {colors["combo_popup_bg"]};
                border: 1px solid {colors["combo_popup_border"]};
                border-radius: 6px;
                color: {colors["combo_popup_text"]};
                selection-background-color: {colors["combo_popup_sel_bg"]};
                selection-color: {colors["combo_popup_sel_text"]};
                padding: 2px;
                outline: none;
                font-family: "Segoe UI";
                font-size: 10px;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 26px;
                padding-left: 8px;
                border-radius: 4px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {colors["combo_popup_sel_bg"]};
                color: {colors["combo_popup_sel_text"]};
            }}
            QScrollBar:vertical {{
                background: {colors["combo_popup_bg"]};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {colors["combo_popup_border"]};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            """
        )
        super().showPopup()

    def hidePopup(self) -> None:  # noqa: N802
        super().hidePopup()
        self.setStyleSheet("")


class MiniActionButton(QPushButton):
    def __init__(self, text: str, *, danger: bool = False) -> None:
        super().__init__(text)
        self._danger = danger
        self._hovered = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setFixedHeight(28)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = _theme_for(self)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)

        if self._danger:
            fill = QColor(colors["danger_hover_bg"] if self._hovered or self.isDown() else colors["outline_bg"])
            border = QColor(colors["danger_hover_border"] if self._hovered or self.isDown() else colors["danger_border"])
            text = QColor(colors["danger_hover_text"] if self._hovered or self.isDown() else colors["danger_text"])
        else:
            fill = QColor(colors["outline_hover_bg"] if self._hovered or self.isDown() else colors["outline_bg"])
            border = QColor(colors["outline_hover_border"] if self._hovered or self.isDown() else colors["outline_border"])
            text = QColor(colors["outline_hover_text"] if self._hovered or self.isDown() else colors["outline_text"])

        painter.setPen(QPen(border, 1.0))
        painter.setBrush(QBrush(fill))
        painter.drawRoundedRect(rect, 5, 5)

        painter.setPen(text)
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold if self._danger else QFont.DemiBold))
        painter.drawText(rect, Qt.AlignCenter, self.text())


class ThinSlider(QWidget):
    valueChanged = pyqtSignal(int)

    def __init__(self, lo: int, hi: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lo = lo
        self._hi = hi
        self._val = lo
        self._hovered = False
        self._dragging = False
        self.setFixedHeight(22)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def value(self) -> int:
        return self._val

    def setValue(self, value: int) -> None:  # noqa: N802
        clamped = max(self._lo, min(self._hi, int(value)))
        if clamped == self._val:
            return
        self._val = clamped
        self.update()
        if not self.signalsBlocked():
            self.valueChanged.emit(clamped)

    def _groove_rect(self) -> QRectF:
        h = self.height()
        return QRectF(8, h / 2 - 2.5, self.width() - 16, 5)

    def _handle_x(self) -> float:
        groove = self._groove_rect()
        fraction = (self._val - self._lo) / max(1, self._hi - self._lo)
        return groove.left() + fraction * groove.width()

    def _set_from_x(self, x: float) -> None:
        groove = self._groove_rect()
        fraction = max(0.0, min(1.0, (x - groove.left()) / groove.width()))
        self.setValue(round(self._lo + fraction * (self._hi - self._lo)))

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._set_from_x(event.x())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._dragging:
            self._set_from_x(event.x())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._dragging = False
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = _theme_for(self)
        groove = self._groove_rect()
        cx = self._handle_x()
        h = self.height()

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(colors["slider_groove"])))
        painter.drawRoundedRect(groove, 2, 2)

        if cx > groove.left() + 1:
            fill = QRectF(groove.left(), groove.top(), cx - groove.left(), groove.height())
            gradient = QLinearGradient(fill.left(), 0, fill.right(), 0)
            gradient.setColorAt(0, QColor(colors["accent"]))
            gradient.setColorAt(1, QColor(colors["accent2"]))
            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(fill, 2, 2)

        radius = 8.0 if (self._hovered or self._dragging) else 6.0
        painter.setBrush(QBrush(QColor(colors["accent2"] if (self._hovered or self._dragging) else colors["accent"])))
        painter.drawEllipse(QPointF(cx, h / 2), radius, radius)


class CameraRefreshThread(QThread):
    refreshed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, *, width: int, height: int, max_index: int = 5) -> None:
        super().__init__()
        self._width = width
        self._height = height
        self._max_index = max_index

    def run(self) -> None:  # noqa: D401
        try:
            sources = detect_available_cameras(
                max_index=self._max_index,
                width=self._width,
                height=self._height,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.refreshed.emit(sources)


class LaunchPreflightThread(QThread):
    prepared = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, *, preferred_index: int, width: int, height: int, max_index: int = 5) -> None:
        super().__init__()
        self._preferred_index = preferred_index
        self._width = width
        self._height = height
        self._max_index = max_index

    def run(self) -> None:  # noqa: D401
        try:
            probe_ok = probe_camera_index(
                index=self._preferred_index,
                width=self._width,
                height=self._height,
            )
            sources = [] if probe_ok else detect_available_cameras(
                max_index=self._max_index,
                width=self._width,
                height=self._height,
                include_placeholder=False,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.prepared.emit(
            {
                'preferred_index': self._preferred_index,
                'probe_ok': probe_ok,
                'available_sources': sources,
            }
        )


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        config: AppConfig,
        worker_fn: WorkerFn,
        ui_mode_label: str = "Control Panel",
        info_text: str | None = None,
        start_button_label: str = "LAUNCH",
        stop_button_label: str = "STOP",
    ) -> None:
        super().__init__()
        self.base_config = config
        self.working_config = config
        self.worker_fn = worker_fn
        self.ui_mode_label = ui_mode_label
        self.info_text = info_text
        self.start_button_label = start_button_label
        self.stop_button_label = stop_button_label

        self.overlay: OverlayWindow | None = None
        self.selfie_window: SelfieWindow | None = None
        self.quick_toolbar: QuickToolbarWindow | None = None
        self.overlay_bus: OverlaySignalBus | None = None
        self.worker_thread: threading.Thread | None = None
        self.stop_event: threading.Event | None = None
        self.running = False
        self._resolved_theme_mode = "light"
        self._df_bg: DepthFieldBackground | None = None

        self.page_stack: QStackedWidget | None = None
        self.nav_buttons: dict[str, QPushButton] = {}
        self.controls: dict[str, QWidget] = {}
        self.value_labels: dict[str, QLabel] = {}
        self.camera_info_label: QLabel | None = None
        self._camera_refresh_thread: CameraRefreshThread | None = None
        self._launch_preflight_thread: LaunchPreflightThread | None = None
        self._launch_pending = False
        self._launch_preflight_should_minimize = False
        self._launch_pending_minimized = False
        self.camera_sources = self._detect_camera_sources()
        self._status_dot: StatusDot | None = None

        self._init_ui()
        self._sync_widgets_from_config()

    def _init_ui(self) -> None:
        self.setWindowTitle("Hand Controller")
        self.resize(980, 720)
        self.setMinimumSize(860, 620)

        central = QWidget()
        root = QHBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        central.setLayout(root)
        self.setCentralWidget(central)

        sidebar = QFrame()
        sidebar.setObjectName("sidebarFrame")
        sidebar.setFixedWidth(188)
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(14, 22, 14, 14)
        sidebar_layout.setSpacing(10)
        sidebar.setLayout(sidebar_layout)

        logo = self._build_logo_widget()
        logo.setObjectName("logoLabel")
        sidebar_layout.addWidget(logo)

        sidebar_layout.addWidget(self._section_header("PROGRAM"))
        launch_row = QHBoxLayout()
        launch_row.setContentsMargins(0, 0, 0, 0)
        launch_row.setSpacing(8)
        self._status_dot = StatusDot()
        self.controls["launch"] = self._pill_button(self.start_button_label.upper(), launch=True)
        self.controls["launch"].clicked.connect(self.toggle_worker)
        launch_row.addWidget(self._status_dot, 0, Qt.AlignVCenter)
        launch_row.addWidget(self.controls["launch"], 1)
        sidebar_layout.addLayout(launch_row)

        sidebar_layout.addSpacing(22)
        sidebar_layout.addWidget(self._section_header("NAVIGATE"))
        nav_group = QButtonGroup(self)
        nav_group.setExclusive(True)
        for page in PAGE_ORDER:
            button = NavButton(page)
            button.clicked.connect(lambda checked=False, name=page: self._set_active_page(name))
            nav_group.addButton(button)
            sidebar_layout.addWidget(button)
            self.nav_buttons[page] = button

        sidebar_layout.addStretch(1)
        self.controls["close"] = self._pill_button("CLOSE", launch=False)
        self.controls["close"].clicked.connect(self.close)
        sidebar_layout.addWidget(self.controls["close"])

        content = ContentFrame()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(12, 18, 18, 16)
        content_layout.setSpacing(0)
        content.setLayout(content_layout)
        self._df_bg = DepthFieldBackground(content)
        content.attach_bg(self._df_bg)

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("pageStack")
        self.page_stack.addWidget(self._page_general())
        self.page_stack.addWidget(self._page_camera())
        self.page_stack.addWidget(self._page_display())
        self.page_stack.addWidget(self._page_keyboard())
        self.page_stack.addWidget(self._page_mouse())
        content_layout.addWidget(self.page_stack)

        root.addWidget(sidebar)
        root.addWidget(content, 1)

        self._apply_window_theme(self.working_config.general.theme)

        self._set_active_page("GENERAL")

    def _resolve_theme_mode(self, theme_value: str | None) -> str:
        normalized = (theme_value or "").strip().lower()
        if normalized == "dark":
            return "dark"
        if normalized == "light":
            return "light"
        system_mode = _windows_system_theme_mode()
        if system_mode is not None:
            return system_mode
        app_palette = self.palette()
        return "dark" if app_palette.color(QPalette.Window).lightness() < 128 else "light"

    def _apply_window_theme(self, theme_value: str | None) -> None:
        self._resolved_theme_mode = self._resolve_theme_mode(theme_value)
        colors = DARK_THEME if self._resolved_theme_mode == "dark" else LIGHT_THEME
        content_background = (
            "transparent"
            if self._resolved_theme_mode == "dark"
            else colors["content_bg"]
        )
        card_background = colors["card_bg"]
        page_surface = "transparent" if self._resolved_theme_mode == "dark" else colors["page_bg"]
        self.setStyleSheet(
            f"""
            QWidget {{ background: {colors["page_bg"]}; color: {colors["text_primary"]}; font-family: "Segoe UI"; }}
            QFrame {{ background: {colors["frame_bg"]}; }}
            QFrame#sidebarFrame {{ background: {colors["sidebar_bg"]}; border-right: 1px solid {colors["sidebar_border"]}; }}
            QFrame#contentFrame {{ background: {content_background}; }}
            QStackedWidget#pageStack {{ background: transparent; }}
            QWidget#pageShell, QWidget#scrollInner, QWidget#rowWrapper {{ background: transparent; }}
            QLabel#logoLabel {{ margin-bottom: 10px; background: transparent; }}
            QLabel#sectionHeader {{ font-size: 9px; font-weight: 800; letter-spacing: 1.4px; color: {colors["text_secondary"]}; background: transparent; }}
            QLabel#pageTitle {{ font-size: 22px; font-weight: 800; margin: 0 0 2px 2px; color: {colors["text_primary"]}; background: transparent; }}
            QLabel#pageSubtitle {{ font-size: 12px; color: {colors["text_secondary"]}; background: transparent; margin-bottom: 10px; }}
            QLabel#fieldLabel {{ font-size: 13px; font-weight: 700; color: {colors["text_primary"]}; background: transparent; }}
            QLabel#valueLabel {{ font-size: 11px; color: {colors["value_text"]}; background: transparent; }}
            QLabel#noteLabel {{ font-size: 11px; color: {colors["text_secondary"]}; background: transparent; padding-top: 2px; }}
            QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {{ border: none; background: {page_surface}; }}
            QFrame#card {{ border: 1px solid {colors["card_border"]}; border-radius: 24px; background: {card_background}; }}
            QToolTip {{ background: {colors["tooltip_bg"]}; color: {colors["tooltip_text"]}; border: 1px solid {colors["tooltip_border"]}; padding: 5px 6px; }}
            """
        )
        if self._df_bg is not None:
            self._df_bg.setVisible(self._resolved_theme_mode == "dark")
            self._df_bg.update()
        for widget in self.findChildren(QWidget):
            widget.update()

    def _section_header(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionHeader")
        return label

    def _build_logo_widget(self) -> QLabel:
        label = QLabel()
        candidates = [
            RUNTIME_BUNDLE_ROOT / "assets" / "touch-logo.png",
            RUNTIME_BUNDLE_ROOT / "assets" / "logo.png",
            RUNTIME_APP_DIR / "assets" / "touch-logo.png",
            RUNTIME_APP_DIR / "assets" / "logo.png",
            RUNTIME_APP_DIR / "touch-logo.png",
            RUNTIME_APP_DIR / "logo.png",
        ]
        logo_path = next((path for path in candidates if path.exists()), None)
        if logo_path is not None:
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                label.setPixmap(
                    pixmap.scaled(
                        132,
                        64,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
                return label

        label.setText(
            '<span style="font-size:44px; font-weight:800; color:#407af6;">TOU</span>'
            '<span style="font-size:44px; font-weight:800; color:#57d6d0;">CH</span>'
        )
        label.setTextFormat(Qt.RichText)
        return label

    def _pill_button(self, text: str, *, launch: bool) -> QPushButton:
        button = SidebarPillButton(
            text,
            icon_kind="play" if launch else "close",
            launch=launch,
        )
        return button

    def _make_page(self, title: str, subtitle: str, card: QWidget) -> QWidget:
        page = QWidget()
        page.setObjectName("pageShell")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        page.setLayout(layout)

        scroll = QScrollArea()
        scroll.setObjectName("pageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        inner = QWidget()
        inner.setObjectName("scrollInner")
        inner_layout = QVBoxLayout()
        inner_layout.setContentsMargins(0, 0, 0, 20)
        inner_layout.setSpacing(8)
        inner.setLayout(inner_layout)

        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("pageSubtitle")
        inner_layout.addWidget(title_label)
        inner_layout.addWidget(subtitle_label)
        inner_layout.addWidget(card, 0, Qt.AlignTop)
        inner_layout.addStretch(1)

        scroll.setWidget(inner)
        layout.addWidget(scroll)
        return page

    def _card(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumWidth(620)
        card.setMaximumWidth(760)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(18)
        card.setLayout(layout)
        return card, layout

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _value(self) -> QLabel:
        label = QLabel("")
        label.setObjectName("valueLabel")
        return label

    def _note(self, text: str = "") -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setObjectName("noteLabel")
        return label

    def _help(self, key: str) -> QToolButton:
        return HelpBadge(HELP_TEXT[key])

    def _switch(self, key: str) -> QCheckBox:
        box = ToggleSwitch()
        self.controls[key] = box
        return box

    def _combo(self, key: str, width: int = 150) -> QComboBox:
        combo = ThemedComboBox()
        combo.setFixedWidth(width)
        self.controls[key] = combo
        return combo

    def _slider(self, key: str, minimum: int, maximum: int) -> QSlider:
        slider = ThinSlider(minimum, maximum)
        self.controls[key] = slider
        return slider

    def _outline(self, key: str, text: str, *, danger: bool = False, width: int = 86) -> QPushButton:
        button = MiniActionButton(text, danger=danger)
        button.setFixedWidth(width)
        self.controls[key] = button
        return button

    def _row(self, layout: QVBoxLayout, text: str, control: QWidget, *, help_key: str | None = None, value_label: QLabel | None = None, slider: bool = False) -> None:
        wrapper = QWidget()
        wrapper.setObjectName("rowWrapper")
        wrapper_layout = QVBoxLayout()
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(6)
        wrapper.setLayout(wrapper_layout)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        top.addWidget(self._label(text))
        if help_key:
            top.addWidget(self._help(help_key))
        top.addStretch(1)
        if value_label is not None:
            top.addWidget(value_label)
        elif not slider:
            top.addWidget(control)
        wrapper_layout.addLayout(top)

        if slider:
            wrapper_layout.addWidget(control)
        layout.addWidget(wrapper)

    def _page_general(self) -> QWidget:
        card, layout = self._card()
        lang = self._combo("language", width=104)
        lang.addItems(["English"])
        lang.currentTextChanged.connect(lambda text: self._update_general(language=text))
        self._row(layout, "Language", lang)

        theme = self._combo("theme", width=134)
        theme.addItems(["System Default", "Light", "Dark"])
        theme.currentTextChanged.connect(self._theme_changed)
        self._row(layout, "Theme", theme)

        manual = self._outline("manual", "OPEN", width=58)
        manual.clicked.connect(lambda: QMessageBox.information(self, "User Manual", "Placeholder pa lang ito."))
        self._row(layout, "User Manual", manual)

        minimize_after_launch = self._switch("minimize_after_launch")
        minimize_after_launch.toggled.connect(lambda checked: self._update_general(minimize_after_launch=checked))
        self._row(layout, "Minimize After Launch", minimize_after_launch, help_key="minimize_after_launch")

        reset = self._outline("reset", "Reset", danger=True, width=58)
        reset.clicked.connect(self._reset_to_factory_defaults)
        self._row(layout, "Reset to Default", reset)
        return self._make_page("General", "App preferences & defaults", card)

    def _page_camera(self) -> QWidget:
        card, layout = self._card()
        camera_enable = self._switch("camera_enable")
        camera_enable.toggled.connect(lambda checked: self._update_camera(enabled=checked))
        self._row(layout, "Enable Camera", camera_enable, help_key="camera_enable")

        source = self._combo("camera_source", width=258)
        refresh = self._outline("camera_refresh", "Refresh", width=72)
        refresh.clicked.connect(self._refresh_camera_sources)
        source_row = QWidget()
        source_row_layout = QHBoxLayout()
        source_row_layout.setContentsMargins(0, 0, 0, 0)
        source_row_layout.setSpacing(8)
        source_row.setLayout(source_row_layout)
        source_row_layout.addWidget(source, 1)
        source_row_layout.addWidget(refresh, 0)
        for camera_source in self.camera_sources:
            source.addItem(camera_source.label, camera_source.index)
        source.currentIndexChanged.connect(self._camera_source_changed)
        self._row(layout, "Camera Source", source_row, help_key="camera_source")
        self.camera_info_label = self._note()
        layout.addWidget(self.camera_info_label)
        self._update_camera_source_feedback()
        return self._make_page("Camera", "Input device configuration", card)

    def _page_display(self) -> QWidget:
        card, layout = self._card()
        skeleton = self._switch("show_hand_skeleton")
        skeleton.toggled.connect(lambda checked: self._update_keyboard(show_skeleton=checked))
        self._row(layout, "Show Hand Skeleton", skeleton, help_key="show_hand_skeleton")

        skeleton_value = self._value()
        self.value_labels["skeleton"] = skeleton_value
        skeleton_slider = self._slider("skeleton_thickness", 1, 10)
        skeleton_slider.valueChanged.connect(self._display_skeleton_thickness_changed)
        self._row(layout, "Hand Skeleton Thickness", skeleton_slider, help_key="hand_skeleton_thickness", value_label=skeleton_value, slider=True)

        selfie = self._switch("show_live_selfie")
        selfie.toggled.connect(lambda checked: self._update_keyboard(show_selfie=checked))
        self._row(layout, "Show Live Selfie", selfie, help_key="show_live_selfie")

        selfie_position = self._combo("selfie_position")
        for label, value in SELFIE_POSITIONS:
            selfie_position.addItem(label, value)
        selfie_position.currentIndexChanged.connect(self._selfie_position_changed)
        self._row(layout, "Selfie Position", selfie_position, help_key="selfie_position")

        selfie_size_value = self._value()
        self.value_labels["selfie"] = selfie_size_value
        selfie_size = self._slider("selfie_size", 50, 160)
        selfie_size.valueChanged.connect(self._display_selfie_size_changed)
        self._row(layout, "Selfie Size", selfie_size, help_key="selfie_size", value_label=selfie_size_value, slider=True)

        gesture = self._switch("show_gesture_command")
        gesture.toggled.connect(lambda checked: self._update_keyboard(show_gesture_command=checked))
        self._row(layout, "Show Gesture Command", gesture, help_key="show_gesture_command")

        gesture_position = self._combo("gesture_command_position")
        for label, value in GESTURE_COMMAND_POSITIONS:
            gesture_position.addItem(label, value)
        gesture_position.currentIndexChanged.connect(self._gesture_command_position_changed)
        self._row(layout, "Gesture Command Position", gesture_position, help_key="gesture_command_position")
        return self._make_page("Display", "Overlay appearance settings", card)

    def _page_keyboard(self) -> QWidget:
        card, layout = self._card()
        tap_sens_value = self._value()
        self.value_labels["tap_sensitivity"] = tap_sens_value
        tap_sens = self._slider("tap_sensitivity", 10, 80)
        tap_sens.valueChanged.connect(self._keyboard_tap_sensitivity_changed)
        self._row(layout, "Tap Sensitivity", tap_sens, help_key="tap_sensitivity", value_label=tap_sens_value, slider=True)

        tap_cooldown_value = self._value()
        self.value_labels["tap_cooldown"] = tap_cooldown_value
        tap_cooldown = self._slider("tap_cooldown", 0, 600)
        tap_cooldown.valueChanged.connect(self._keyboard_tap_cooldown_changed)
        self._row(layout, "Tap Cooldown", tap_cooldown, help_key="tap_cooldown", value_label=tap_cooldown_value, slider=True)

        keyboard_enable = self._switch("keyboard_enable")
        keyboard_enable.toggled.connect(lambda checked: self._update_keyboard(virtual_keyboard_enabled=checked))
        self._row(layout, "Enable Virtual Keyboard Control", keyboard_enable, help_key="keyboard_enable")
        return self._make_page("Keyboard", "Virtual keyboard tap settings", card)

    def _page_mouse(self) -> QWidget:
        card, layout = self._card()
        sensitivity_value = self._value()
        self.value_labels["mouse_sensitivity"] = sensitivity_value
        sensitivity = self._slider("mouse_sensitivity", 30, 200)
        sensitivity.valueChanged.connect(self._mouse_sensitivity_changed)
        self._row(layout, "Sensitivity", sensitivity, help_key="mouse_sensitivity", value_label=sensitivity_value, slider=True)

        smooth_value = self._value()
        self.value_labels["mouse_smoothness"] = smooth_value
        smooth = self._slider("mouse_smoothness", 10, 90)
        smooth.valueChanged.connect(self._mouse_smoothness_changed)
        self._row(layout, "Smoothness", smooth, help_key="mouse_smoothness", value_label=smooth_value, slider=True)

        dead_value = self._value()
        self.value_labels["mouse_dead_zone"] = dead_value
        dead_zone = self._slider("mouse_dead_zone", 0, 100)
        dead_zone.valueChanged.connect(self._mouse_dead_zone_changed)
        self._row(layout, "Dead Zone", dead_zone, help_key="mouse_dead_zone", value_label=dead_value, slider=True)
        return self._make_page("Mouse", "Cursor movement & feel", card)

    def _set_active_page(self, page: str) -> None:
        if self.page_stack is None:
            return
        index = PAGE_ORDER.index(page)
        self.page_stack.setCurrentIndex(index)
        for name, button in self.nav_buttons.items():
            active = name == page
            if isinstance(button, NavButton):
                button.set_active(active)
            else:
                button.setChecked(active)

    def _update_launch_button(self) -> None:
        button = self.controls["launch"]
        if self.running:
            button.setText(self.stop_button_label.upper())
        elif self._launch_pending:
            button.setText("STARTING...")
        else:
            button.setText(self.start_button_label.upper())
        if isinstance(button, SidebarPillButton):
            button.set_icon_kind("stop" if self.running else "play")
        if self._status_dot is not None:
            self._status_dot.set_running(self.running)
        button.setEnabled(not self._launch_pending)
        button.setProperty("running", "true" if self.running else "false")
        button.style().unpolish(button)
        button.style().polish(button)
        button.update()

    def _detect_camera_sources(self) -> list[CameraSource]:
        return detect_available_cameras(
            max_index=5,
            width=self.working_config.camera.width,
            height=self.working_config.camera.height,
        )

    def _apply_camera_source_list(self, sources: list[CameraSource], *, preferred_index: int | None = None) -> None:
        combo = self.controls.get("camera_source")
        if not isinstance(combo, QComboBox):
            return

        self.camera_sources = sources
        target_index = self.working_config.camera.index if preferred_index is None else preferred_index
        combo.blockSignals(True)
        combo.clear()
        for camera_source in self.camera_sources:
            combo.addItem(camera_source.label, camera_source.index)
        idx = combo.findData(target_index)
        if idx < 0:
            idx = 0
        combo.setCurrentIndex(max(0, idx))
        current_value = combo.itemData(combo.currentIndex())
        combo.blockSignals(False)
        if current_value is not None:
            self._update_camera(index=int(current_value))
        self._update_camera_source_feedback()

    def _refresh_camera_sources(self) -> None:
        if self._camera_refresh_thread is not None and self._camera_refresh_thread.isRunning():
            return

        self._set_camera_refresh_state(True)
        thread = CameraRefreshThread(
            width=self.working_config.camera.width,
            height=self.working_config.camera.height,
            max_index=5,
        )
        thread.refreshed.connect(self._camera_refresh_finished)
        thread.failed.connect(self._camera_refresh_failed)
        thread.finished.connect(self._camera_refresh_cleanup)
        self._camera_refresh_thread = thread
        thread.start()

    def _set_camera_refresh_state(self, refreshing: bool) -> None:
        refresh_button = self.controls.get("camera_refresh")
        combo = self.controls.get("camera_source")
        if isinstance(refresh_button, QPushButton):
            refresh_button.setEnabled(not refreshing)
        if not isinstance(combo, QComboBox):
            return
        combo.setEnabled(not refreshing)
        if refreshing and self.camera_info_label is not None:
            self.camera_info_label.setText("Scanning camera sources...")

    def _set_camera_source_controls_enabled(self, enabled: bool, *, info_text: str | None = None) -> None:
        refresh_button = self.controls.get("camera_refresh")
        combo = self.controls.get("camera_source")
        if isinstance(refresh_button, QPushButton):
            refresh_button.setEnabled(enabled)
        if isinstance(combo, QComboBox):
            combo.setEnabled(enabled)
        if info_text is not None and self.camera_info_label is not None:
            self.camera_info_label.setText(info_text)

    @pyqtSlot(object)
    def _camera_refresh_finished(self, sources: object) -> None:
        if not isinstance(sources, list):
            self._camera_refresh_failed("Camera refresh returned an invalid result.")
            return

        selected_index = self.working_config.camera.index
        camera_sources = [source for source in sources if isinstance(source, CameraSource)]
        self._apply_camera_source_list(camera_sources, preferred_index=selected_index)
        self._set_camera_refresh_state(False)

    @pyqtSlot(str)
    def _camera_refresh_failed(self, error_text: str) -> None:
        self._set_camera_refresh_state(False)
        if self.camera_info_label is not None:
            self.camera_info_label.setText(
                f"Camera scan failed. Using the last known source list. Details: {error_text}"
            )

    @pyqtSlot()
    def _camera_refresh_cleanup(self) -> None:
        thread = self._camera_refresh_thread
        self._camera_refresh_thread = None
        if thread is not None:
            thread.deleteLater()

    def _update_camera_source_feedback(self) -> None:
        if self.camera_info_label is None:
            return
        count = len(self.camera_sources)
        uses_device_names = any(source.device_name for source in self.camera_sources)
        if count <= 1:
            if uses_device_names:
                camera_name = next((source.device_name for source in self.camera_sources if source.device_name), "default camera")
                text = f"Detected 1 camera source. Using {camera_name}. Click Refresh after connecting another webcam."
            else:
                text = "Detected 1 camera source. Click Refresh after connecting another webcam."
        elif uses_device_names:
            text = (
                f"Detected {count} camera sources. Labels use best-effort Windows device names, "
                "with the camera index shown for consistency."
            )
        else:
            text = (
                f"Detected {count} camera sources. This setup exposes camera indices more reliably than hardware names, "
                "so the labels stay generic."
            )
        self.camera_info_label.setText(text)

    def _selected_camera_source(self) -> CameraSource | None:
        current_index = self.working_config.camera.index
        return next((source for source in self.camera_sources if source.index == current_index), None)

    def _resolve_camera_preflight_result(
        self,
        *,
        preferred_index: int,
        available_sources: list[CameraSource],
        show_dialogs: bool,
        keep_previous_index: int | None = None,
    ) -> AppConfig | None:
        if not available_sources:
            if show_dialogs:
                QMessageBox.warning(
                    self,
                    "No Camera Detected",
                    "No usable camera source was detected. Connect or enable a camera first, then try again.",
                )
            elif self.camera_info_label is not None:
                self.camera_info_label.setText("No usable camera source was detected. Keeping the current camera.")
            self._apply_camera_source_list(self._detect_camera_sources(), preferred_index=keep_previous_index or preferred_index)
            return None

        available_indices = {source.index for source in available_sources}
        if preferred_index not in available_indices:
            fallback = next((source for source in available_sources if source.index == 0), available_sources[0])
            self._apply_camera_source_list(available_sources, preferred_index=fallback.index)
            if show_dialogs:
                QMessageBox.information(
                    self,
                    "Camera Fallback",
                    f"The previously selected camera is no longer available. The app will use {fallback.label} instead.",
                )
            elif self.camera_info_label is not None:
                if keep_previous_index is not None and fallback.index == keep_previous_index:
                    self.camera_info_label.setText(
                        f"The selected camera is no longer available. Keeping {fallback.label}."
                    )
                else:
                    self.camera_info_label.setText(
                        f"The selected camera is no longer available. Switching to {fallback.label}."
                    )
            return self.working_config

        self._apply_camera_source_list(available_sources, preferred_index=preferred_index)
        return self.working_config

    def _launch_camera_preflight(
        self,
        *,
        preferred_index: int,
        show_dialogs: bool,
        keep_previous_index: int | None = None,
    ) -> AppConfig | None:
        launch_config = self.working_config
        if probe_camera_index(
            index=preferred_index,
            width=launch_config.camera.width,
            height=launch_config.camera.height,
        ):
            return launch_config

        available_sources = detect_available_cameras(
            max_index=5,
            width=launch_config.camera.width,
            height=launch_config.camera.height,
            include_placeholder=False,
        )
        return self._resolve_camera_preflight_result(
            preferred_index=preferred_index,
            available_sources=available_sources,
            show_dialogs=show_dialogs,
            keep_previous_index=keep_previous_index,
        )

    def _block(self, key: str, block: bool) -> None:
        widget = self.controls.get(key)
        if widget is not None:
            widget.blockSignals(block)

    def _sync_widgets_from_config(self) -> None:
        keys = [
            "language", "theme", "minimize_after_launch", "camera_enable", "camera_source",
            "show_hand_skeleton", "skeleton_thickness", "show_live_selfie", "selfie_position",
            "selfie_size", "show_gesture_command", "gesture_command_position",
            "tap_sensitivity", "tap_cooldown", "keyboard_enable",
            "mouse_sensitivity", "mouse_smoothness", "mouse_dead_zone",
        ]
        for key in keys:
            self._block(key, True)
        try:
            cast = self.working_config
            self.controls["language"].setCurrentText(cast.general.language)
            self.controls["theme"].setCurrentText(cast.general.theme)
            self.controls["minimize_after_launch"].setChecked(cast.general.minimize_after_launch)
            self.controls["camera_enable"].setChecked(cast.camera.enabled)
            idx = self.controls["camera_source"].findData(cast.camera.index)
            if idx < 0:
                label = "Default Webcam (Index 0)" if cast.camera.index == 0 else f"Camera {cast.camera.index} (Index {cast.camera.index})"
                self.controls["camera_source"].addItem(label, cast.camera.index)
                idx = self.controls["camera_source"].findData(cast.camera.index)
            self.controls["camera_source"].setCurrentIndex(max(0, idx))
            self.controls["show_hand_skeleton"].setChecked(cast.keyboard.show_skeleton)
            self.controls["skeleton_thickness"].setValue(int(cast.keyboard.skeleton_stroke_px))
            self.controls["show_live_selfie"].setChecked(cast.keyboard.show_selfie)
            idx = self.controls["selfie_position"].findData(cast.keyboard.selfie_position)
            self.controls["selfie_position"].setCurrentIndex(max(0, idx))
            self.controls["selfie_size"].setValue(max(50, min(160, int(round((cast.keyboard.selfie_width_px / 320.0) * 100)))))
            self.controls["show_gesture_command"].setChecked(cast.keyboard.show_gesture_command)
            idx = self.controls["gesture_command_position"].findData(cast.keyboard.gesture_command_position)
            self.controls["gesture_command_position"].setCurrentIndex(max(0, idx))
            self.controls["tap_sensitivity"].setValue(int(round(cast.keyboard.index_pinch_threshold_px)))
            self.controls["tap_cooldown"].setValue(int(round(cast.keyboard.tap_cooldown_seconds * 1000)))
            self.controls["keyboard_enable"].setChecked(cast.keyboard.virtual_keyboard_enabled)
            self.controls["mouse_sensitivity"].setValue(int(round(cast.mouse_motion.sensitivity * 100)))
            self.controls["mouse_smoothness"].setValue(int(round(cast.mouse_motion.ema_alpha * 100)))
            self.controls["mouse_dead_zone"].setValue(int(round(cast.mouse_motion.wake_threshold_px * 10)))
        finally:
            for key in keys:
                self._block(key, False)

        self._display_skeleton_thickness_changed(self.controls["skeleton_thickness"].value())
        self._display_selfie_size_changed(self.controls["selfie_size"].value())
        self._keyboard_tap_sensitivity_changed(self.controls["tap_sensitivity"].value())
        self._keyboard_tap_cooldown_changed(self.controls["tap_cooldown"].value())
        self._mouse_sensitivity_changed(self.controls["mouse_sensitivity"].value())
        self._mouse_smoothness_changed(self.controls["mouse_smoothness"].value())
        self._mouse_dead_zone_changed(self.controls["mouse_dead_zone"].value())
        self._update_camera_source_feedback()
        self._apply_window_theme(cast.general.theme)
        self._push_live_overlay_settings()
        self._update_launch_button()

    def _update_general(self, **kwargs) -> None:
        self.working_config = replace(self.working_config, general=replace(self.working_config.general, **kwargs))

    def _update_camera(self, **kwargs) -> None:
        self.working_config = replace(self.working_config, camera=replace(self.working_config.camera, **kwargs))

    def _update_keyboard(self, **kwargs) -> None:
        self.working_config = replace(self.working_config, keyboard=replace(self.working_config.keyboard, **kwargs))
        self._push_live_overlay_settings()

    def _persist_keyboard_fields(self, field_names: tuple[str, ...]) -> None:
        tuning_path = Path(self.working_config.tuning_path) if self.working_config.tuning_path else RUNTIME_APP_DIR / "tuning.local.json"
        try:
            data = json.loads(tuning_path.read_text(encoding="utf-8")) if tuning_path.exists() else {}
            if not isinstance(data, dict):
                data = {}
            keyboard_data = data.get("keyboard", {})
            if not isinstance(keyboard_data, dict):
                keyboard_data = {}
            for field_name in field_names:
                keyboard_data[field_name] = getattr(self.working_config.keyboard, field_name)
            data["keyboard"] = keyboard_data
            tuning_path.parent.mkdir(parents=True, exist_ok=True)
            tuning_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass

    @pyqtSlot(float, float)
    def _selfie_position_dragged(self, x_ratio: float, y_ratio: float) -> None:
        self._update_keyboard(
            selfie_position="custom",
            selfie_custom_x_ratio=float(x_ratio),
            selfie_custom_y_ratio=float(y_ratio),
        )
        control = self.controls.get("selfie_position")
        if isinstance(control, QComboBox):
            self._block("selfie_position", True)
            try:
                idx = control.findData("custom")
                if idx >= 0:
                    control.setCurrentIndex(idx)
            finally:
                self._block("selfie_position", False)
        self._persist_keyboard_fields(
            (
                "selfie_position",
                "selfie_custom_x_ratio",
                "selfie_custom_y_ratio",
            )
        )

    def _set_combo_by_data(self, key: str, value: object) -> None:
        control = self.controls.get(key)
        if not isinstance(control, QComboBox):
            return
        self._block(key, True)
        try:
            idx = control.findData(value)
            if idx >= 0:
                control.setCurrentIndex(idx)
        finally:
            self._block(key, False)

    def _set_selfie_size_slider_from_width(self, width_px: int) -> None:
        control = self.controls.get("selfie_size")
        if not isinstance(control, QSlider):
            return
        value = max(50, min(160, int(round((width_px / 320.0) * 100))))
        self._block("selfie_size", True)
        try:
            control.setValue(value)
            self.value_labels["selfie"].setText(f"{value}%")
        finally:
            self._block("selfie_size", False)

    @pyqtSlot()
    def _selfie_hide_requested(self) -> None:
        self._update_keyboard(show_selfie=False)
        self._set_checked_control("show_live_selfie", False)

    @pyqtSlot(int, int, float, float)
    def _selfie_size_changed(self, width_px: int, height_px: int, x_ratio: float, y_ratio: float) -> None:
        self._update_keyboard(
            selfie_width_px=int(width_px),
            selfie_height_px=int(height_px),
            selfie_position="custom",
            selfie_custom_x_ratio=float(x_ratio),
            selfie_custom_y_ratio=float(y_ratio),
        )
        self._set_combo_by_data("selfie_position", "custom")
        self._set_selfie_size_slider_from_width(width_px)
        self._persist_keyboard_fields(
            (
                "selfie_width_px",
                "selfie_height_px",
                "selfie_position",
                "selfie_custom_x_ratio",
                "selfie_custom_y_ratio",
            )
        )

    def _set_checked_control(self, key: str, checked: bool) -> None:
        control = self.controls.get(key)
        if not isinstance(control, QCheckBox):
            return
        self._block(key, True)
        try:
            control.setChecked(checked)
        finally:
            self._block(key, False)

    @pyqtSlot(bool)
    def _quick_toolbar_selfie_toggled(self, checked: bool) -> None:
        self._update_keyboard(show_selfie=checked)
        self._set_checked_control("show_live_selfie", checked)

    @pyqtSlot(bool)
    def _quick_toolbar_skeleton_toggled(self, checked: bool) -> None:
        self._update_keyboard(show_skeleton=checked)
        self._set_checked_control("show_hand_skeleton", checked)

    @pyqtSlot(str, float)
    def _quick_toolbar_position_changed(self, edge: str, offset_ratio: float) -> None:
        self._update_keyboard(
            quick_toolbar_edge=str(edge),
            quick_toolbar_offset_ratio=float(offset_ratio),
        )
        self._persist_keyboard_fields(
            (
                "quick_toolbar_edge",
                "quick_toolbar_offset_ratio",
            )
        )

    @pyqtSlot()
    def _show_from_quick_toolbar(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _update_mouse_motion(self, **kwargs) -> None:
        self.working_config = replace(self.working_config, mouse_motion=replace(self.working_config.mouse_motion, **kwargs))

    def _push_live_overlay_settings(self) -> None:
        if not self.running or self.overlay_bus is None:
            return
        try:
            self.overlay_bus.update_overlay_settings.emit(self.working_config.keyboard)
        except Exception:
            pass

    def _camera_source_changed(self, index: int) -> None:
        previous_index = self.working_config.camera.index
        value = self.controls["camera_source"].itemData(index)
        if value is not None:
            self._update_camera(index=int(value))
        self._update_camera_source_feedback()
        if self.running and value is not None and int(value) != previous_index:
            self._switch_running_camera(previous_index=previous_index, requested_index=int(value))

    def _switch_running_camera(self, *, previous_index: int, requested_index: int) -> None:
        if not self.running:
            return
        self._set_camera_source_controls_enabled(False, info_text="Switching camera...")
        prepared_config = self._launch_camera_preflight(
            preferred_index=requested_index,
            show_dialogs=False,
            keep_previous_index=previous_index,
        )
        target_index = self.working_config.camera.index
        if prepared_config is None or target_index == previous_index:
            self._set_camera_source_controls_enabled(True)
            self._update_camera_source_feedback()
            return

        self.stop_worker()
        self._launch_worker(prepared_config, minimize_on_start=False)
        source = self._selected_camera_source()
        if self.camera_info_label is not None:
            self.camera_info_label.setText(
                f"Switched to {(source.label if source is not None else f'camera index {target_index}')} while running."
            )
        self._set_camera_source_controls_enabled(True)

    def _theme_changed(self, value: str) -> None:
        self._update_general(theme=value)
        self._apply_window_theme(value)

    def _display_skeleton_thickness_changed(self, value: int) -> None:
        self.value_labels["skeleton"].setText(f"{value}px")
        self._update_keyboard(skeleton_stroke_px=value)

    def _display_selfie_size_changed(self, value: int) -> None:
        self.value_labels["selfie"].setText(f"{value}%")
        self._update_keyboard(selfie_width_px=int(round(320 * value / 100.0)), selfie_height_px=int(round(240 * value / 100.0)))

    def _selfie_position_changed(self, index: int) -> None:
        value = self.controls["selfie_position"].itemData(index)
        if value is not None:
            self._update_keyboard(selfie_position=str(value))

    def _gesture_command_position_changed(self, index: int) -> None:
        value = self.controls["gesture_command_position"].itemData(index)
        if value is not None:
            self._update_keyboard(gesture_command_position=str(value))

    def _keyboard_tap_sensitivity_changed(self, value: int) -> None:
        self.value_labels["tap_sensitivity"].setText(f"{value}px")
        self._update_keyboard(index_pinch_threshold_px=float(value))

    def _keyboard_tap_cooldown_changed(self, value: int) -> None:
        self.value_labels["tap_cooldown"].setText(f"{value} ms")
        self._update_keyboard(tap_cooldown_seconds=float(value) / 1000.0)

    def _mouse_sensitivity_changed(self, value: int) -> None:
        self.value_labels["mouse_sensitivity"].setText(f"{value / 100.0:.2f}x")
        self._update_mouse_motion(sensitivity=float(value) / 100.0)

    def _mouse_smoothness_changed(self, value: int) -> None:
        self.value_labels["mouse_smoothness"].setText(f"{value / 100.0:.2f}")
        self._update_mouse_motion(ema_alpha=float(value) / 100.0)

    def _mouse_dead_zone_changed(self, value: int) -> None:
        dead_zone = float(value) / 10.0
        self.value_labels["mouse_dead_zone"].setText(f"{dead_zone:.1f}px")
        self._update_mouse_motion(wake_threshold_px=dead_zone, sleep_threshold_px=max(0.0, round(dead_zone * 0.4, 2)))

    def _reset_to_factory_defaults(self) -> None:
        dialog = ResetConfirmDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        defaults = build_factory_default_config()
        self.working_config = replace(defaults, tuning_path=self.working_config.tuning_path)
        self._sync_widgets_from_config()

    def _set_launch_pending(self, pending: bool, *, info_text: str | None = None) -> None:
        self._launch_pending = pending
        if pending:
            self._set_camera_source_controls_enabled(False, info_text=info_text or "Checking selected camera...")
        else:
            self._set_camera_source_controls_enabled(True)
            self._update_camera_source_feedback()
        self._update_launch_button()

    def _restore_from_pending_launch_minimize(self) -> None:
        if not self._launch_pending_minimized:
            return
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self._launch_pending_minimized = False

    def _show_prelaunch_overlay(self) -> None:
        if self.overlay is not None:
            return
        self.overlay = OverlayWindow(self.working_config.keyboard)

    def _close_prelaunch_overlay(self) -> None:
        if self.running or self.overlay_bus is not None:
            return
        if self.overlay is not None:
            self.overlay.close()
            self.overlay = None

    def _ensure_selfie_window(self, settings) -> None:
        if self.selfie_window is None:
            self.selfie_window = SelfieWindow(settings)
            self.selfie_window.position_changed.connect(self._selfie_position_dragged)
            self.selfie_window.hide_requested.connect(self._selfie_hide_requested)
            self.selfie_window.size_changed.connect(self._selfie_size_changed)
        else:
            self.selfie_window.apply_settings(settings)

    def _ensure_quick_toolbar(self, settings) -> None:
        if self.quick_toolbar is None:
            self.quick_toolbar = QuickToolbarWindow(settings)
            self.quick_toolbar.selfie_toggled.connect(self._quick_toolbar_selfie_toggled)
            self.quick_toolbar.skeleton_toggled.connect(self._quick_toolbar_skeleton_toggled)
            self.quick_toolbar.position_changed.connect(self._quick_toolbar_position_changed)
            self.quick_toolbar.open_main_requested.connect(self._show_from_quick_toolbar)
        else:
            self.quick_toolbar.apply_settings(settings)
            self.quick_toolbar.show()

    def _start_launch_preflight(self, *, preferred_index: int) -> None:
        if self._launch_preflight_thread is not None and self._launch_preflight_thread.isRunning():
            return
        self._launch_preflight_should_minimize = bool(self.working_config.general.minimize_after_launch)
        self._set_launch_pending(True, info_text="Checking selected camera...")
        self._show_prelaunch_overlay()
        if self._launch_preflight_should_minimize:
            self.showMinimized()
            self._launch_pending_minimized = True
        thread = LaunchPreflightThread(
            preferred_index=preferred_index,
            width=self.working_config.camera.width,
            height=self.working_config.camera.height,
            max_index=5,
        )
        thread.prepared.connect(self._launch_preflight_finished)
        thread.failed.connect(self._launch_preflight_failed)
        thread.finished.connect(self._launch_preflight_cleanup)
        self._launch_preflight_thread = thread
        thread.start()

    @pyqtSlot(object)
    def _launch_preflight_finished(self, payload: object) -> None:
        if not isinstance(payload, dict):
            self._launch_preflight_failed("Launch preflight returned an invalid result.")
            return

        self._set_launch_pending(False)

        preferred_index = int(payload.get("preferred_index", self.working_config.camera.index))
        if bool(payload.get("probe_ok", False)):
            prepared_config = self.working_config
            minimize_on_start = self._launch_preflight_should_minimize and not self._launch_pending_minimized
        else:
            self._close_prelaunch_overlay()
            self._restore_from_pending_launch_minimize()
            raw_sources = payload.get("available_sources", [])
            available_sources = raw_sources if isinstance(raw_sources, list) else []
            prepared_config = self._resolve_camera_preflight_result(
                preferred_index=preferred_index,
                available_sources=available_sources,
                show_dialogs=True,
            )
            minimize_on_start = self._launch_preflight_should_minimize

        if prepared_config is None:
            self._close_prelaunch_overlay()
            self._launch_preflight_should_minimize = False
            return
        self._launch_worker(prepared_config, minimize_on_start=minimize_on_start)
        self._launch_preflight_should_minimize = False
        self._launch_pending_minimized = False

    @pyqtSlot(str)
    def _launch_preflight_failed(self, message: str) -> None:
        self._set_launch_pending(False)
        self._close_prelaunch_overlay()
        self._restore_from_pending_launch_minimize()
        self._launch_preflight_should_minimize = False
        QMessageBox.warning(self, "Camera Check Failed", message or "Unable to verify the selected camera before launch.")

    @pyqtSlot()
    def _launch_preflight_cleanup(self) -> None:
        self._launch_preflight_thread = None

    @pyqtSlot()
    def toggle_worker(self) -> None:
        if self._launch_pending:
            return
        if self.running:
            self.stop_worker()
        else:
            self.start_worker()

    def _launch_worker(self, launch_config: AppConfig, *, minimize_on_start: bool) -> None:
        if self.overlay is None:
            self.overlay = OverlayWindow(launch_config.keyboard)
        else:
            self.overlay.apply_settings(launch_config.keyboard)
        self._ensure_selfie_window(launch_config.keyboard)
        self._ensure_quick_toolbar(launch_config.keyboard)
        self.overlay_bus = OverlaySignalBus()
        self.overlay_bus.update_overlay.connect(self.overlay.apply_payload)
        self.overlay_bus.update_overlay_settings.connect(self.overlay.apply_settings)
        if self.selfie_window is not None:
            self.overlay_bus.update_overlay.connect(self.selfie_window.apply_payload)
            self.overlay_bus.update_overlay_settings.connect(self.selfie_window.apply_settings)
        if self.quick_toolbar is not None:
            self.overlay_bus.update_overlay_settings.connect(self.quick_toolbar.apply_settings)
        self.stop_event = threading.Event()
        self.worker_thread = threading.Thread(
            target=self.worker_fn,
            args=(self.overlay_bus, self.stop_event, launch_config, max(1, self.overlay.width()), max(1, self.overlay.height())),
            daemon=True,
        )
        self.worker_thread.start()
        self.running = True
        self._update_launch_button()
        if minimize_on_start:
            self.showMinimized()

    def start_worker(self) -> None:
        if self.running or self._launch_pending:
            return
        launch_config = self.working_config
        if not launch_config.camera.enabled:
            QMessageBox.warning(self, "Camera Disabled", "Enable Camera first before launching the app.")
            return
        self._start_launch_preflight(preferred_index=launch_config.camera.index)

    def stop_worker(self) -> None:
        if not self.running:
            return
        if self.stop_event is not None:
            self.stop_event.set()
        if self.worker_thread is not None and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.0)
        if self.overlay_bus is not None and self.overlay is not None:
            try:
                self.overlay_bus.update_overlay.disconnect(self.overlay.apply_payload)
            except Exception:
                pass
            try:
                self.overlay_bus.update_overlay_settings.disconnect(self.overlay.apply_settings)
            except Exception:
                pass
        if self.overlay_bus is not None and self.selfie_window is not None:
            try:
                self.overlay_bus.update_overlay.disconnect(self.selfie_window.apply_payload)
            except Exception:
                pass
            try:
                self.overlay_bus.update_overlay_settings.disconnect(self.selfie_window.apply_settings)
            except Exception:
                pass
        if self.overlay_bus is not None and self.quick_toolbar is not None:
            try:
                self.overlay_bus.update_overlay_settings.disconnect(self.quick_toolbar.apply_settings)
            except Exception:
                pass
        if self.overlay is not None:
            self.overlay.close()
            self.overlay = None
        if self.selfie_window is not None:
            self.selfie_window.close()
            self.selfie_window = None
        if self.quick_toolbar is not None:
            self.quick_toolbar.close()
            self.quick_toolbar = None
        self.overlay_bus = None
        self.worker_thread = None
        self.stop_event = None
        self.running = False
        self._update_launch_button()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._camera_refresh_thread is not None and self._camera_refresh_thread.isRunning():
            self._camera_refresh_thread.wait(1500)
        if self._launch_preflight_thread is not None and self._launch_preflight_thread.isRunning():
            self._launch_preflight_thread.wait(5000)
        self.stop_worker()
        event.accept()

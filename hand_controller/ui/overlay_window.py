from __future__ import annotations

from PyQt5.QtCore import QRect, Qt, pyqtSlot
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QApplication, QWidget

from ..config.settings import KeyboardConfig
from .payloads import OverlayPayload


class OverlayWindow(QWidget):
    def __init__(self, settings: KeyboardConfig | None = None) -> None:
        super().__init__()
        self.settings = settings or KeyboardConfig()
        self.payload = OverlayPayload()
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle("Hand Controller Overlay")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        screen = QApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.geometry())
        self.showFullScreen()

    @pyqtSlot(object)
    def apply_payload(self, payload: object) -> None:
        if not isinstance(payload, OverlayPayload):
            return
        self.payload = payload
        self.update()

    @pyqtSlot(object)
    def apply_settings(self, settings: object) -> None:
        if not isinstance(settings, KeyboardConfig):
            return
        self.settings = settings
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.payload.keyboard_visible:
            self._draw_keyboard(painter)
        if self.settings.show_skeleton:
            self._draw_skeleton(painter)
        if self.settings.show_pointers:
            self._draw_pointers(painter)
        self._draw_gesture_command(painter)

    def _draw_keyboard(self, painter: QPainter) -> None:
        painter.setFont(QFont("Arial", self.settings.key_label_font_px))
        dimmed = self.payload.keyboard_dimmed
        for key in self.payload.keyboard_keys:
            highlighted = key.label in self.payload.highlight_labels
            if dimmed:
                fill = QColor(0, 0, 0, 70) if not highlighted else QColor(0, 120, 220, 95)
                border = QColor(255, 255, 255, 105) if highlighted else QColor(185, 185, 185, 75)
                text = QColor(255, 255, 255, 120)
            else:
                fill = QColor(0, 0, 0, 155) if not highlighted else QColor(0, 120, 220, 185)
                border = QColor(255, 255, 255, 210) if highlighted else QColor(185, 185, 185, 180)
                text = QColor(255, 255, 255, 230)

            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(border, self.settings.key_border_px if not highlighted else self.settings.key_hover_border_px))
            rect = QRect(key.x1, key.y1, key.x2 - key.x1, key.y2 - key.y1)
            painter.drawRect(rect)

            label = "SPC" if key.label == "SPACE" else key.label
            painter.setPen(text)
            painter.drawText(rect, Qt.AlignCenter, label)

    def _draw_skeleton(self, painter: QPainter) -> None:
        painter.setPen(QPen(QColor(0, 200, 255, 180), self.settings.skeleton_stroke_px))
        for x1, y1, x2, y2 in self.payload.skeleton_lines:
            painter.drawLine(x1, y1, x2, y2)

    def _draw_pointers(self, painter: QPainter) -> None:
        radius = self.settings.pointer_radius_px
        painter.setFont(QFont("Arial", self.settings.pointer_label_font_px, QFont.Bold))
        for pointer in self.payload.finger_points:
            if (
                pointer.thumb_x is not None
                and pointer.thumb_y is not None
                and pointer.index_x is not None
                and pointer.index_y is not None
            ):
                painter.setPen(QPen(QColor(255, 255, 255, 185), 1))
                painter.drawLine(pointer.thumb_x, pointer.thumb_y, pointer.index_x, pointer.index_y)

            painter.setPen(QPen(QColor(0, 255, 255, 235), self.settings.pointer_stroke_px))
            painter.setBrush(QBrush(QColor(0, 255, 255, 155)))
            painter.drawEllipse(pointer.x - radius, pointer.y - radius, radius * 2, radius * 2)
            if pointer.hand_label:
                painter.setPen(QColor(255, 255, 255, 230))
                painter.drawText(pointer.x + radius + 3, pointer.y - max(4, radius // 2), pointer.hand_label)

    def _draw_gesture_command(self, painter: QPainter) -> None:
        if not self.settings.show_gesture_command or not self.payload.gesture_command_text:
            return

        painter.setFont(QFont("Arial", max(16, self.settings.header_font_px + 2), QFont.Bold))
        metrics = painter.fontMetrics()
        text = self.payload.gesture_command_text
        text_width = metrics.horizontalAdvance(text)
        width = text_width + 32
        height = metrics.height() + 20
        x = (self.width() - width) // 2

        position = self.settings.gesture_command_position
        if position == "center":
            y = (self.height() - height) // 2
        elif position == "bottom":
            y = self.height() - height - 56
        else:
            y = 68

        rect = QRect(x, y, width, height)
        painter.setBrush(QBrush(QColor(0, 0, 0, 175)))
        painter.setPen(QPen(QColor(255, 255, 255, 0), 0))
        painter.drawRoundedRect(rect, 14, 14)
        painter.setPen(QColor(255, 255, 255, 235))
        painter.drawText(rect, Qt.AlignCenter, text)

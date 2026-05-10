from __future__ import annotations

import math

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
        self._draw_ownership_guide(painter)
        if self.settings.show_skeleton:
            self._draw_skeleton(painter)
        if self.settings.show_pointers:
            self._draw_pointers(painter)
        self._draw_helper_hint(painter)
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
        trusted_pen = QPen(QColor(0, 200, 255, 180), self.settings.skeleton_stroke_px)
        untrusted_pen = QPen(QColor(190, 190, 190, 105), self.settings.skeleton_stroke_px)
        for line in self.payload.skeleton_lines:
            painter.setPen(trusted_pen if line.trusted else untrusted_pen)
            painter.drawLine(line.x1, line.y1, line.x2, line.y2)

    def _draw_ownership_guide(self, painter: QPainter) -> None:
        guide = self.payload.ownership_guide
        if not guide.visible:
            return

        x1 = max(0, min(self.width(), guide.x1))
        y1 = max(0, min(self.height(), guide.y1))
        x2 = max(0, min(self.width(), guide.x2))
        y2 = max(0, min(self.height(), guide.y2))
        left, right = min(x1, x2), max(x1, x2)
        top, bottom = min(y1, y2), max(y1, y2)
        rect = QRect(left, top, max(1, right - left), max(1, bottom - top))

        active = guide.progress > 0.0
        border = QColor(255, 255, 255, 120) if not active else QColor(80, 210, 255, 170)
        painter.setBrush(QBrush(QColor(0, 0, 0, 42)))
        painter.setPen(QPen(border, 2))
        painter.drawRoundedRect(rect, 14, 14)

        painter.setFont(QFont("Arial", max(13, self.settings.status_font_px), QFont.Normal))
        metrics = painter.fontMetrics()
        text = guide.text
        text_height = metrics.height() + 10
        text_y = top - text_height - 8
        if text_y < 20:
            text_y = top + 10
        text_rect = QRect(left, text_y, rect.width(), text_height)
        painter.setPen(QColor(255, 255, 255, 215))
        painter.drawText(text_rect, Qt.AlignCenter, text)

        progress = max(0.0, min(1.0, guide.progress))
        if progress > 0.0:
            bar_margin = 18
            bar_height = 4
            bar_x = left + bar_margin
            bar_y = bottom - bar_margin
            bar_w = max(1, rect.width() - bar_margin * 2)
            painter.setPen(QPen(QColor(255, 255, 255, 45), 1))
            painter.setBrush(QBrush(QColor(255, 255, 255, 45)))
            painter.drawRoundedRect(QRect(bar_x, bar_y, bar_w, bar_height), 2, 2)
            painter.setPen(QPen(QColor(80, 210, 255, 170), 1))
            painter.setBrush(QBrush(QColor(80, 210, 255, 170)))
            painter.drawRoundedRect(QRect(bar_x, bar_y, int(round(bar_w * progress)), bar_height), 2, 2)

    def _draw_line_with_midpoint_gap(
        self,
        painter: QPainter,
        *,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        midpoint_x: int,
        midpoint_y: int,
        half_gap_px: int,
    ) -> None:
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length <= half_gap_px * 2:
            return

        unit_x = dx / length
        unit_y = dy / length
        left_x = int(round(midpoint_x - unit_x * half_gap_px))
        left_y = int(round(midpoint_y - unit_y * half_gap_px))
        right_x = int(round(midpoint_x + unit_x * half_gap_px))
        right_y = int(round(midpoint_y + unit_y * half_gap_px))

        painter.drawLine(x1, y1, left_x, left_y)
        painter.drawLine(right_x, right_y, x2, y2)

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
                if pointer.show_dot:
                    painter.drawLine(pointer.thumb_x, pointer.thumb_y, pointer.index_x, pointer.index_y)
                else:
                    self._draw_line_with_midpoint_gap(
                        painter,
                        x1=pointer.thumb_x,
                        y1=pointer.thumb_y,
                        x2=pointer.index_x,
                        y2=pointer.index_y,
                        midpoint_x=pointer.x,
                        midpoint_y=pointer.y,
                        half_gap_px=max(24, radius * 3),
                    )

            if not pointer.show_dot:
                continue

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

    def _draw_helper_hint(self, painter: QPainter) -> None:
        if not self.payload.helper_hint_text:
            return

        painter.setFont(QFont("Arial", max(13, self.settings.status_font_px), QFont.Normal))
        metrics = painter.fontMetrics()
        text = self.payload.helper_hint_text
        max_width = max(160, self.width() - 48)
        display_text = metrics.elidedText(text, Qt.ElideRight, max_width - 28)
        text_width = metrics.horizontalAdvance(display_text)
        width = text_width + 28
        height = metrics.height() + 14
        x = (self.width() - width) // 2

        if self.payload.keyboard_visible and self.payload.keyboard_keys:
            keyboard_top = min(key.y1 for key in self.payload.keyboard_keys)
            y = max(56, keyboard_top - height - 14)
        else:
            y = self.height() - height - 96

        rect = QRect(x, y, width, height)
        painter.setBrush(QBrush(QColor(0, 0, 0, 125)))
        painter.setPen(QPen(QColor(255, 255, 255, 55), 1))
        painter.drawRoundedRect(rect, 10, 10)
        painter.setPen(QColor(255, 255, 255, 215))
        painter.drawText(rect, Qt.AlignCenter, display_text)

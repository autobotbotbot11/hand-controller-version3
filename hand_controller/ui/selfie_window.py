from __future__ import annotations

from typing import Literal

from PyQt5.QtCore import QPoint, QRect, QRectF, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QBrush, QColor, QImage, QMouseEvent, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QApplication, QWidget

from ..config.settings import KeyboardConfig
from .payloads import OverlayPayload


class SelfieWindow(QWidget):
    position_changed = pyqtSignal(float, float)
    hide_requested = pyqtSignal()
    size_changed = pyqtSignal(int, int, float, float)

    MIN_WIDTH = 160
    MAX_WIDTH = 512
    ASPECT_RATIO = 4.0 / 3.0
    CLOSE_SIZE = 24
    RESIZE_SIZE = 28

    def __init__(self, settings: KeyboardConfig | None = None) -> None:
        super().__init__()
        self.settings = settings or KeyboardConfig()
        self.payload = OverlayPayload()
        self._drag_offset: QPoint | None = None
        self._resize_corner: Literal["top_left", "top_right", "bottom_left", "bottom_right"] | None = None
        self._hovered = False
        self._init_ui()
        self._apply_geometry_from_settings()
        self._apply_visibility()

    def _init_ui(self) -> None:
        self.setWindowTitle("Hand Controller Selfie")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.OpenHandCursor)
        self.setMouseTracking(True)

    def _available_geometry(self) -> QRect:
        screen = QApplication.primaryScreen()
        if screen is None:
            return QRect(0, 0, 1280, 720)
        return screen.availableGeometry()

    def _clamped_top_left(self, point: QPoint) -> QPoint:
        available = self._available_geometry()
        min_x = available.left()
        min_y = available.top()
        max_x = available.left() + max(0, available.width() - self.width())
        max_y = available.top() + max(0, available.height() - self.height())
        return QPoint(
            max(min_x, min(point.x(), max_x)),
            max(min_y, min(point.y(), max_y)),
        )

    def _target_size_from_settings(self) -> tuple[int, int]:
        width = max(self.MIN_WIDTH, min(self.MAX_WIDTH, int(self.settings.selfie_width_px)))
        height = int(round(width / self.ASPECT_RATIO))
        return width, height

    def _corner_top_left(self, available: QRect) -> QPoint:
        margin = 20
        width, height = self._target_size_from_settings()
        x = available.left() + margin
        y = available.top() + margin
        if self.settings.selfie_position == "top_right":
            x = available.left() + available.width() - width - margin
        elif self.settings.selfie_position == "bottom_left":
            y = available.top() + available.height() - height - margin
        elif self.settings.selfie_position == "bottom_right":
            x = available.left() + available.width() - width - margin
            y = available.top() + available.height() - height - margin
        return QPoint(x, y)

    def _custom_top_left(self, available: QRect) -> QPoint | None:
        if self.settings.selfie_position != "custom":
            return None
        if self.settings.selfie_custom_x_ratio is None or self.settings.selfie_custom_y_ratio is None:
            return None

        width, height = self._target_size_from_settings()
        max_x = max(0, available.width() - width)
        max_y = max(0, available.height() - height)
        x_ratio = max(0.0, min(1.0, float(self.settings.selfie_custom_x_ratio)))
        y_ratio = max(0.0, min(1.0, float(self.settings.selfie_custom_y_ratio)))
        return QPoint(
            available.left() + int(round(max_x * x_ratio)),
            available.top() + int(round(max_y * y_ratio)),
        )

    def _apply_geometry_from_settings(self) -> None:
        width, height = self._target_size_from_settings()
        self.resize(width, height)
        available = self._available_geometry()
        top_left = self._custom_top_left(available) or self._corner_top_left(available)
        self.move(self._clamped_top_left(top_left))

    def _apply_visibility(self) -> None:
        if self.settings.show_selfie:
            if not self.isVisible():
                self.show()
                self.raise_()
        else:
            self.hide()

    def _current_position_ratio(self) -> tuple[float, float]:
        available = self._available_geometry()
        max_x = max(1, available.width() - self.width())
        max_y = max(1, available.height() - self.height())
        x_ratio = (self.x() - available.left()) / max_x
        y_ratio = (self.y() - available.top()) / max_y
        return (
            max(0.0, min(1.0, x_ratio)),
            max(0.0, min(1.0, y_ratio)),
        )

    def _close_rect(self) -> QRect:
        margin = 8
        return QRect((self.width() - self.CLOSE_SIZE) // 2, margin, self.CLOSE_SIZE, self.CLOSE_SIZE)

    def _resize_rects(self) -> dict[str, QRect]:
        size = self.RESIZE_SIZE
        return {
            "top_left": QRect(0, 0, size, size),
            "top_right": QRect(self.width() - size, 0, size, size),
            "bottom_left": QRect(0, self.height() - size, size, size),
            "bottom_right": QRect(self.width() - size, self.height() - size, size, size),
        }

    def _resize_corner_at(self, pos: QPoint) -> Literal["top_left", "top_right", "bottom_left", "bottom_right"] | None:
        for corner, rect in self._resize_rects().items():
            if rect.contains(pos):
                return corner  # type: ignore[return-value]
        return None

    def _update_cursor(self, pos: QPoint) -> None:
        corner = self._resize_corner_at(pos)
        if self._resize_corner is not None:
            if self._resize_corner in {"top_left", "bottom_right"}:
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self.setCursor(Qt.SizeBDiagCursor)
        elif self._drag_offset is not None:
            self.setCursor(Qt.ClosedHandCursor)
        elif corner in {"top_left", "bottom_right"}:
            self.setCursor(Qt.SizeFDiagCursor)
        elif corner in {"top_right", "bottom_left"}:
            self.setCursor(Qt.SizeBDiagCursor)
        elif self._close_rect().contains(pos):
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.OpenHandCursor)

    def _resize_from_global_pos(self, global_pos: QPoint) -> None:
        if self._resize_corner is None:
            return
        available = self._available_geometry()
        frame = self.frameGeometry()
        max_width = self.MAX_WIDTH
        width = self.width()
        height = self.height()
        top_left = frame.topLeft()

        if self._resize_corner == "bottom_right":
            anchor = frame.topLeft()
            raw_width = max(
                global_pos.x() - anchor.x(),
                int(round((global_pos.y() - anchor.y()) * self.ASPECT_RATIO)),
            )
            available_width = available.right() - anchor.x() + 1
            available_height = available.bottom() - anchor.y() + 1
            max_width = int(min(self.MAX_WIDTH, available_width, available_height * self.ASPECT_RATIO))
            min_width = min(self.MIN_WIDTH, max_width)
            width = max(min_width, min(max_width, raw_width))
            height = int(round(width / self.ASPECT_RATIO))
            top_left = anchor
        elif self._resize_corner == "bottom_left":
            anchor = frame.topRight()
            raw_width = max(
                anchor.x() - global_pos.x() + 1,
                int(round((global_pos.y() - anchor.y()) * self.ASPECT_RATIO)),
            )
            available_width = anchor.x() - available.left() + 1
            available_height = available.bottom() - anchor.y() + 1
            max_width = int(min(self.MAX_WIDTH, available_width, available_height * self.ASPECT_RATIO))
            min_width = min(self.MIN_WIDTH, max_width)
            width = max(min_width, min(max_width, raw_width))
            height = int(round(width / self.ASPECT_RATIO))
            top_left = QPoint(anchor.x() - width + 1, anchor.y())
        elif self._resize_corner == "top_right":
            anchor = frame.bottomLeft()
            raw_width = max(
                global_pos.x() - anchor.x(),
                int(round((anchor.y() - global_pos.y() + 1) * self.ASPECT_RATIO)),
            )
            available_width = available.right() - anchor.x() + 1
            available_height = anchor.y() - available.top() + 1
            max_width = int(min(self.MAX_WIDTH, available_width, available_height * self.ASPECT_RATIO))
            min_width = min(self.MIN_WIDTH, max_width)
            width = max(min_width, min(max_width, raw_width))
            height = int(round(width / self.ASPECT_RATIO))
            top_left = QPoint(anchor.x(), anchor.y() - height + 1)
        else:
            anchor = frame.bottomRight()
            raw_width = max(
                anchor.x() - global_pos.x() + 1,
                int(round((anchor.y() - global_pos.y() + 1) * self.ASPECT_RATIO)),
            )
            available_width = anchor.x() - available.left() + 1
            available_height = anchor.y() - available.top() + 1
            max_width = int(min(self.MAX_WIDTH, available_width, available_height * self.ASPECT_RATIO))
            min_width = min(self.MIN_WIDTH, max_width)
            width = max(min_width, min(max_width, raw_width))
            height = int(round(width / self.ASPECT_RATIO))
            top_left = QPoint(anchor.x() - width + 1, anchor.y() - height + 1)

        self.setGeometry(QRect(top_left, QRect(0, 0, width, height).size()))
        self.update()

    @pyqtSlot(object)
    def apply_payload(self, payload: object) -> None:
        if not isinstance(payload, OverlayPayload):
            return
        self.payload = payload
        self._apply_visibility()
        self.update()

    @pyqtSlot(object)
    def apply_settings(self, settings: object) -> None:
        if not isinstance(settings, KeyboardConfig):
            return
        self.settings = settings
        self._apply_geometry_from_settings()
        self._apply_visibility()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        if self._close_rect().contains(event.pos()):
            self.hide_requested.emit()
            event.accept()
            return
        resize_corner = self._resize_corner_at(event.pos())
        if resize_corner is not None:
            self._resize_corner = resize_corner
            self._update_cursor(event.pos())
            event.accept()
            return
        self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
        self.setCursor(Qt.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._resize_corner is not None:
            self._resize_from_global_pos(event.globalPos())
            event.accept()
            return
        if self._drag_offset is None:
            self._update_cursor(event.pos())
            super().mouseMoveEvent(event)
            return
        self.move(self._clamped_top_left(event.globalPos() - self._drag_offset))
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self._resize_corner is not None:
            self._resize_corner = None
            self._update_cursor(event.pos())
            x_ratio, y_ratio = self._current_position_ratio()
            self.size_changed.emit(self.width(), self.height(), x_ratio, y_ratio)
            event.accept()
            return
        if event.button() != Qt.LeftButton or self._drag_offset is None:
            super().mouseReleaseEvent(event)
            return
        self._drag_offset = None
        self._update_cursor(event.pos())
        self.position_changed.emit(*self._current_position_ratio())
        event.accept()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        if self._resize_corner is None and self._drag_offset is None:
            self.setCursor(Qt.OpenHandCursor)
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        target = self.rect()
        panel_path = QPainterPath()
        panel_path.addRoundedRect(QRectF(target), 18, 18)
        border = QColor(255, 255, 255, 145 if self._hovered else 90)
        painter.setPen(QPen(border, 1))
        painter.setBrush(QBrush(QColor(0, 0, 0, 230)))
        painter.drawPath(panel_path)

        frame = self.payload.selfie_frame
        if frame is not None:
            try:
                import cv2
            except ModuleNotFoundError:
                frame = None

        if frame is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
            inset = target.adjusted(3, 3, -3, -3)
            clip_path = QPainterPath()
            clip_path.addRoundedRect(QRectF(inset), 15, 15)
            painter.save()
            painter.setClipPath(clip_path)
            painter.drawImage(inset, qimg)
            painter.restore()
        else:
            self._draw_placeholder(painter, target)

        if self._hovered or self._resize_corner is not None or self._drag_offset is not None:
            self._draw_hover_controls(painter)

    def _draw_placeholder(self, painter: QPainter, target: QRect) -> None:
        painter.save()
        painter.setPen(QPen(QColor(255, 255, 255, 235), 2))
        painter.setBrush(Qt.NoBrush)

        icon_w = min(72, max(40, target.width() // 3))
        icon_h = int(icon_w * 0.7)
        body = QRectF(
            target.center().x() - icon_w / 2,
            target.center().y() - icon_h / 2,
            icon_w,
            icon_h,
        )
        painter.drawRoundedRect(body, 8, 8)

        lens_size = min(icon_h * 0.45, icon_w * 0.34)
        lens = QRectF(
            target.center().x() - lens_size / 2,
            target.center().y() - lens_size / 2,
            lens_size,
            lens_size,
        )
        painter.drawEllipse(lens)

        top = QRectF(body.left() + icon_w * 0.18, body.top() - 10, icon_w * 0.36, 10)
        painter.drawRoundedRect(top, 5, 5)
        painter.restore()

    def _draw_hover_controls(self, painter: QPainter) -> None:
        painter.save()

        hide_rect = QRectF(self._close_rect())
        painter.setPen(QPen(QColor(255, 255, 255, 185), 1))
        painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
        painter.drawEllipse(hide_rect)

        cx = hide_rect.center().x()
        cy = hide_rect.center().y()
        eye = QRectF(cx - 7, cy - 4, 14, 8)
        painter.setPen(QPen(QColor(255, 255, 255, 225), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(eye)
        painter.drawEllipse(QPoint(int(cx), int(cy)), 2, 2)
        painter.setPen(QPen(QColor(255, 255, 255, 235), 2, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPoint(int(cx - 8), int(cy + 8)), QPoint(int(cx + 8), int(cy - 8)))

        painter.setPen(QPen(QColor(255, 255, 255, 180), 2, Qt.SolidLine, Qt.RoundCap))
        self._draw_corner_grip(painter, "top_left")
        self._draw_corner_grip(painter, "top_right")
        self._draw_corner_grip(painter, "bottom_left")
        self._draw_corner_grip(painter, "bottom_right")

        painter.restore()

    def _draw_corner_grip(self, painter: QPainter, corner: str) -> None:
        margin = 9
        lengths = (8, 14)
        if corner == "top_left":
            x = margin
            y = margin
            for length in lengths:
                painter.drawLine(QPoint(x, y + length), QPoint(x, y))
                painter.drawLine(QPoint(x, y), QPoint(x + length, y))
        elif corner == "top_right":
            x = self.width() - margin
            y = margin
            for length in lengths:
                painter.drawLine(QPoint(x - length, y), QPoint(x, y))
                painter.drawLine(QPoint(x, y), QPoint(x, y + length))
        elif corner == "bottom_left":
            x = margin
            y = self.height() - margin
            for length in lengths:
                painter.drawLine(QPoint(x, y - length), QPoint(x, y))
                painter.drawLine(QPoint(x, y), QPoint(x + length, y))
        else:
            x = self.width() - margin
            y = self.height() - margin
            for length in lengths:
                painter.drawLine(QPoint(x - length, y), QPoint(x, y))
                painter.drawLine(QPoint(x, y), QPoint(x, y - length))

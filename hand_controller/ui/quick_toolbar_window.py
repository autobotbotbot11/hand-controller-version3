from __future__ import annotations

from typing import Literal

from PyQt5.QtCore import QPoint, QRect, QRectF, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QApplication, QWidget

from ..config.settings import KeyboardConfig


class QuickToolButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, icon_kind: str, tooltip: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.icon_kind = icon_kind
        self.active = True
        self.setFixedSize(34, 34)
        self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)

    def set_active(self, active: bool) -> None:
        if self.active == active:
            return
        self.active = active
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        bg = QColor(42, 42, 52, 178) if self.active else QColor(24, 24, 30, 118)
        border = QColor(185, 190, 255, 150) if self.active else QColor(120, 120, 135, 92)
        ink = QColor(246, 247, 255, 232) if self.active else QColor(150, 150, 166, 205)

        painter.setBrush(QBrush(bg))
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(rect, 8, 8)
        painter.setPen(QPen(ink, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)

        if self.icon_kind == "camera":
            painter.drawRoundedRect(QRectF(9, 12, 16, 11), 2, 2)
            painter.drawRoundedRect(QRectF(12, 9, 8, 4), 2, 2)
            painter.drawEllipse(QPoint(17, 18), 4, 4)
        elif self.icon_kind == "skeleton":
            points = [QPoint(17, 8), QPoint(11, 16), QPoint(23, 16), QPoint(9, 25), QPoint(25, 25)]
            painter.drawLine(points[0], points[1])
            painter.drawLine(points[0], points[2])
            painter.drawLine(points[1], points[3])
            painter.drawLine(points[2], points[4])
            painter.setBrush(QBrush(ink))
            painter.setPen(Qt.NoPen)
            for point in points:
                painter.drawEllipse(point, 2, 2)
        elif self.icon_kind == "panel":
            painter.drawRoundedRect(QRectF(9, 10, 16, 14), 2, 2)
            painter.drawLine(QPoint(14, 14), QPoint(22, 14))
            painter.drawLine(QPoint(14, 19), QPoint(20, 19))
        elif self.icon_kind == "dots":
            painter.setBrush(QBrush(ink))
            painter.setPen(Qt.NoPen)
            for y in (12, 17, 22):
                painter.drawEllipse(QPoint(17, y), 2, 2)

        if not self.active:
            painter.setPen(QPen(QColor(255, 255, 255, 145), 2, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPoint(10, 25), QPoint(25, 10))


class QuickToolbarWindow(QWidget):
    selfie_toggled = pyqtSignal(bool)
    skeleton_toggled = pyqtSignal(bool)
    open_main_requested = pyqtSignal()
    position_changed = pyqtSignal(str, float)

    COLLAPSED_SIZE = (36, 52)
    EXPANDED_SIZE = (46, 168)
    VALID_EDGES = {"left", "right", "top", "bottom"}

    def __init__(self, settings: KeyboardConfig | None = None) -> None:
        super().__init__()
        self.settings = settings or KeyboardConfig()
        self.edge: Literal["left", "right", "top", "bottom"] = self._normalized_edge(self.settings.quick_toolbar_edge)
        self.offset_ratio = self._normalized_offset(self.settings.quick_toolbar_offset_ratio)
        self.expanded = False
        self._drag_offset: QPoint | None = None
        self._press_global: QPoint | None = None
        self._drag_started = False
        self._init_ui()
        self._apply_geometry()
        self._sync_button_state()
        self.show()

    def _init_ui(self) -> None:
        self.setWindowTitle("Hand Controller Quick Tools")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.OpenHandCursor)

        self.handle_button = QuickToolButton("dots", "Quick tools", self)
        self.selfie_button = QuickToolButton("camera", "Show or hide selfie", self)
        self.skeleton_button = QuickToolButton("skeleton", "Show or hide hand skeleton", self)
        self.panel_button = QuickToolButton("panel", "Open control panel", self)

        self.handle_button.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.selfie_button.clicked.connect(self._toggle_selfie)
        self.skeleton_button.clicked.connect(self._toggle_skeleton)
        self.panel_button.clicked.connect(self.open_main_requested.emit)

    def _normalized_edge(self, edge: object) -> Literal["left", "right", "top", "bottom"]:
        value = str(edge or "right").strip().lower()
        if value in self.VALID_EDGES:
            return value  # type: ignore[return-value]
        return "right"

    def _normalized_offset(self, offset: object) -> float:
        try:
            value = float(offset)
        except (TypeError, ValueError):
            value = 0.5
        return max(0.0, min(1.0, value))

    def _available_geometry(self) -> QRect:
        screen = QApplication.primaryScreen()
        if screen is None:
            return QRect(0, 0, 1280, 720)
        return screen.availableGeometry()

    def _is_horizontal(self) -> bool:
        return self.edge in {"top", "bottom"}

    def _target_size(self) -> tuple[int, int]:
        width, height = self.EXPANDED_SIZE if self.expanded else self.COLLAPSED_SIZE
        if self._is_horizontal():
            return height, width
        return width, height

    def _apply_geometry(self) -> None:
        width, height = self._target_size()
        available = self._available_geometry()

        if self.edge == "left":
            x = available.left()
            y = available.top() + int(round((available.height() - height) * self.offset_ratio))
        elif self.edge == "right":
            x = available.right() - width + 1
            y = available.top() + int(round((available.height() - height) * self.offset_ratio))
        elif self.edge == "top":
            x = available.left() + int(round((available.width() - width) * self.offset_ratio))
            y = available.top()
        else:
            x = available.left() + int(round((available.width() - width) * self.offset_ratio))
            y = available.bottom() - height + 1

        x = max(available.left(), min(x, available.right() - width + 1))
        y = max(available.top(), min(y, available.bottom() - height + 1))
        self.setGeometry(x, y, width, height)
        self._layout_buttons()

    def _layout_buttons(self) -> None:
        if self._is_horizontal():
            y = (self.height() - 34) // 2
            self.handle_button.move(9, y)
            if not self.expanded:
                self.selfie_button.hide()
                self.skeleton_button.hide()
                self.panel_button.hide()
                return
            self.selfie_button.move(48, y)
            self.skeleton_button.move(87, y)
            self.panel_button.move(126, y)
        else:
            x = (self.width() - 34) // 2
            self.handle_button.move(x, 9)
            if not self.expanded:
                self.selfie_button.hide()
                self.skeleton_button.hide()
                self.panel_button.hide()
                return
            self.selfie_button.move(x, 48)
            self.skeleton_button.move(x, 87)
            self.panel_button.move(x, 126)

        self.selfie_button.show()
        self.skeleton_button.show()
        self.panel_button.show()

    def _sync_button_state(self) -> None:
        self.selfie_button.set_active(self.settings.show_selfie)
        self.skeleton_button.set_active(self.settings.show_skeleton)

    def _update_offset_from_current_geometry(self) -> None:
        available = self._available_geometry()
        if self._is_horizontal():
            span = max(1, available.width() - self.width())
            self.offset_ratio = max(0.0, min(1.0, (self.x() - available.left()) / span))
        else:
            span = max(1, available.height() - self.height())
            self.offset_ratio = max(0.0, min(1.0, (self.y() - available.top()) / span))

    def _nearest_edge(self) -> Literal["left", "right", "top", "bottom"]:
        available = self._available_geometry()
        center = self.frameGeometry().center()
        distances = {
            "left": abs(center.x() - available.left()),
            "right": abs(available.right() - center.x()),
            "top": abs(center.y() - available.top()),
            "bottom": abs(available.bottom() - center.y()),
        }
        return min(distances, key=distances.get)  # type: ignore[return-value]

    def _snap_to_nearest_edge(self) -> None:
        self.edge = self._nearest_edge()
        self._update_offset_from_current_geometry()
        self._apply_geometry()
        self.position_changed.emit(self.edge, self.offset_ratio)

    def _toggle_expanded(self) -> None:
        self._update_offset_from_current_geometry()
        self.expanded = not self.expanded
        self._apply_geometry()
        self.update()

    def _toggle_selfie(self) -> None:
        self.selfie_toggled.emit(not self.settings.show_selfie)

    def _toggle_skeleton(self) -> None:
        self.skeleton_toggled.emit(not self.settings.show_skeleton)

    @pyqtSlot(object)
    def apply_settings(self, settings: object) -> None:
        if not isinstance(settings, KeyboardConfig):
            return
        previous_edge = self.edge
        previous_offset = self.offset_ratio
        self.settings = settings
        self.edge = self._normalized_edge(settings.quick_toolbar_edge)
        self.offset_ratio = self._normalized_offset(settings.quick_toolbar_offset_ratio)
        if self.edge != previous_edge or self.offset_ratio != previous_offset:
            self._apply_geometry()
        self._sync_button_state()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
        self._press_global = event.globalPos()
        self._drag_started = False
        self.setCursor(Qt.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_offset is None:
            super().mouseMoveEvent(event)
            return
        if self._press_global is not None and (event.globalPos() - self._press_global).manhattanLength() > 4:
            self._drag_started = True
        available = self._available_geometry()
        target = event.globalPos() - self._drag_offset
        x = max(available.left(), min(target.x(), available.right() - self.width() + 1))
        y = max(available.top(), min(target.y(), available.bottom() - self.height() + 1))
        self.move(x, y)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton or self._drag_offset is None:
            super().mouseReleaseEvent(event)
            return
        self._drag_offset = None
        self._press_global = None
        self.setCursor(Qt.OpenHandCursor)
        if self._drag_started:
            self._snap_to_nearest_edge()
        else:
            self._toggle_expanded()
        self._drag_started = False
        event.accept()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        alpha = 150 if self.expanded or self.underMouse() else 92
        border_alpha = 110 if self.expanded or self.underMouse() else 58
        painter.setPen(QPen(QColor(255, 255, 255, border_alpha), 1))
        painter.setBrush(QBrush(QColor(12, 12, 18, alpha)))
        painter.drawPath(path)

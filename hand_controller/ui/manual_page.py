from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .manual_content import ManualEntry


class ManualImageView(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._frame_name = ""
        self.setObjectName("manualImageView")
        self.setMinimumHeight(250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        self.setLayout(layout)

        self.image_label = QLabel()
        self.image_label.setObjectName("manualImageLabel")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setWordWrap(True)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.image_label)

    def set_frame(self, image_path: Path | None, frame_name: str) -> None:
        self._frame_name = frame_name
        self._pixmap = QPixmap(str(image_path)) if image_path is not None else QPixmap()
        self._refresh()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        if not self._pixmap.isNull():
            size = self.image_label.size()
            if size.width() <= 0 or size.height() <= 0:
                return
            scaled = self._pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)
            self.image_label.setText("")
            self.image_label.setToolTip("")
            return

        self.image_label.setPixmap(QPixmap())
        self.image_label.setToolTip(self._frame_name)
        if self._frame_name:
            self.image_label.setText("Visual guide coming soon")
        else:
            self.image_label.setText("Visual guide coming soon")


class ManualPage(QWidget):
    FRAME_INTERVAL_MS = 1200

    def __init__(
        self,
        *,
        entries: Sequence[ManualEntry],
        asset_dirs: Sequence[Path],
        colors: Mapping[str, object],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.entries = tuple(entries)
        self.asset_dirs = tuple(asset_dirs)
        self.colors = colors
        self.groups = tuple(dict.fromkeys(entry.group for entry in self.entries))
        self.current_group = self.groups[0] if self.groups else ""
        self.current_entry_index = 0
        self.current_frame_index = 0
        self.group_buttons: dict[str, QPushButton] = {}
        self.entry_buttons: dict[int, QPushButton] = {}

        self.frame_timer = QTimer(self)
        self.frame_timer.setInterval(self.FRAME_INTERVAL_MS)
        self.frame_timer.timeout.connect(self._advance_frame)

        self._init_ui()
        self.apply_theme(colors)
        if self.entries:
            self._show_group(self.current_group)

    def _color(self, key: str, fallback: str) -> str:
        return str(self.colors.get(key, fallback))

    def _init_ui(self) -> None:
        self.setObjectName("manualPage")
        self.setMinimumWidth(640)
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        self.setLayout(root)

        title = QLabel("User Manual")
        title.setObjectName("manualPageTitle")
        subtitle = QLabel("Quick reference for the current hand-control gestures and runtime behavior.")
        subtitle.setObjectName("manualPageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        group_scroll = QScrollArea()
        group_scroll.setObjectName("manualTabScroll")
        group_scroll.setWidgetResizable(True)
        group_scroll.setFrameShape(QFrame.NoFrame)
        group_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        group_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        group_shell = QWidget()
        group_shell.setObjectName("manualTabShell")
        group_layout = QHBoxLayout()
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(8)
        group_shell.setLayout(group_layout)
        for group in self.groups:
            button = QPushButton(group)
            button.setObjectName("manualGroupButton")
            button.setProperty("active", "false")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, value=group: self._show_group(value))
            self.group_buttons[group] = button
            group_layout.addWidget(button)
        group_layout.addStretch(1)
        group_scroll.setWidget(group_shell)
        group_scroll.setFixedHeight(38)
        root.addWidget(group_scroll)

        entry_scroll = QScrollArea()
        entry_scroll.setObjectName("manualEntryScroll")
        entry_scroll.setWidgetResizable(True)
        entry_scroll.setFrameShape(QFrame.NoFrame)
        entry_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        entry_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        entry_shell = QWidget()
        entry_shell.setObjectName("manualEntryShell")
        self.entry_layout = QHBoxLayout()
        self.entry_layout.setContentsMargins(0, 0, 0, 0)
        self.entry_layout.setSpacing(8)
        entry_shell.setLayout(self.entry_layout)
        entry_scroll.setWidget(entry_shell)
        entry_scroll.setFixedHeight(44)
        root.addWidget(entry_scroll)

        panel = QFrame()
        panel.setObjectName("manualPanel")
        panel_layout = QHBoxLayout()
        panel_layout.setContentsMargins(16, 16, 16, 16)
        panel_layout.setSpacing(16)
        panel.setLayout(panel_layout)
        root.addWidget(panel, 1)

        visual_col = QVBoxLayout()
        visual_col.setContentsMargins(0, 0, 0, 0)
        visual_col.setSpacing(8)
        panel_layout.addLayout(visual_col, 5)

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        self.group_badge = QLabel("")
        self.group_badge.setObjectName("manualBadge")
        self.entry_counter = QLabel("")
        self.entry_counter.setObjectName("manualCounter")
        meta_row.addWidget(self.group_badge)
        meta_row.addStretch(1)
        meta_row.addWidget(self.entry_counter)
        visual_col.addLayout(meta_row)

        self.image_view = ManualImageView()
        visual_col.addWidget(self.image_view, 1)

        self.frame_counter = QLabel("")
        self.frame_counter.setObjectName("manualFrameCounter")
        self.frame_counter.setAlignment(Qt.AlignCenter)
        visual_col.addWidget(self.frame_counter)

        info = QFrame()
        info.setObjectName("manualInfo")
        info.setMinimumWidth(240)
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(16, 14, 16, 14)
        info_layout.setSpacing(10)
        info.setLayout(info_layout)
        panel_layout.addWidget(info, 3)

        self.entry_title = QLabel("")
        self.entry_title.setObjectName("manualEntryTitle")
        self.entry_title.setWordWrap(True)
        self.entry_body = QLabel("")
        self.entry_body.setObjectName("manualEntryBody")
        self.entry_body.setWordWrap(True)
        self.entry_body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        info_layout.addWidget(self.entry_title)
        info_layout.addWidget(self.entry_body)
        info_layout.addStretch(1)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        self.previous_button = QPushButton("Previous")
        self.previous_button.setObjectName("manualActionButton")
        self.previous_button.clicked.connect(lambda: self._show_entry(self.current_entry_index - 1))
        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("manualActionButton")
        self.next_button.clicked.connect(lambda: self._show_entry(self.current_entry_index + 1))
        actions.addWidget(self.previous_button)
        actions.addWidget(self.next_button)
        info_layout.addLayout(actions)

    def apply_theme(self, colors: Mapping[str, object]) -> None:
        self.colors = colors
        self.setStyleSheet(
            f"""
            QWidget#manualPage, QWidget#manualTabShell, QWidget#manualEntryShell {{
                background: transparent;
            }}
            QLabel#manualPageTitle {{
                color: {self._color("text_primary", "#f0f0f6")};
                font-size: 22px;
                font-weight: 800;
                background: transparent;
            }}
            QLabel#manualPageSubtitle {{
                color: {self._color("text_secondary", "#6a6a78")};
                font-size: 12px;
                background: transparent;
            }}
            QScrollArea#manualTabScroll, QScrollArea#manualEntryScroll {{
                border: none;
                background: transparent;
            }}
            QPushButton#manualGroupButton {{
                min-height: 30px;
                padding: 0 14px;
                border-radius: 8px;
                border: 1px solid {self._color("outline_border", "#30303a")};
                background: {self._color("outline_bg", "#1c1c22")};
                color: {self._color("outline_text", "#8d8d9a")};
                font-weight: 800;
            }}
            QPushButton#manualGroupButton:hover {{
                border-color: {self._color("accent", "#6272ff")};
                color: {self._color("accent", "#6272ff")};
            }}
            QPushButton#manualGroupButton[active="true"] {{
                border-color: {self._color("accent", "#6272ff")};
                background: {self._color("nav_active_bg", "#22222c")};
                color: {self._color("nav_text_active", "#f0f0f6")};
            }}
            QPushButton#manualEntryButton {{
                min-height: 30px;
                padding: 0 12px;
                border-radius: 8px;
                border: 1px solid {self._color("card_border", "#30303a")};
                background: transparent;
                color: {self._color("text_secondary", "#6a6a78")};
                font-weight: 700;
            }}
            QPushButton#manualEntryButton:hover {{
                background: {self._color("outline_hover_bg", "#23232b")};
                color: {self._color("outline_hover_text", "#b7b7c8")};
            }}
            QPushButton#manualEntryButton[active="true"] {{
                background: {self._color("outline_bg", "#1c1c22")};
                border-color: {self._color("accent", "#6272ff")};
                color: {self._color("text_primary", "#f0f0f6")};
            }}
            QFrame#manualPanel {{
                background: {self._color("card_bg", "#1c1c22")};
                border: 1px solid {self._color("card_border", "#30303a")};
                border-radius: 18px;
            }}
            QLabel#manualBadge, QLabel#manualCounter, QLabel#manualFrameCounter {{
                color: {self._color("text_secondary", "#6a6a78")};
                font-size: 10px;
                font-weight: 800;
                background: transparent;
            }}
            QFrame#manualImageView {{
                background: {self._color("frame_bg", "#111115")};
                border: 1px solid {self._color("card_border", "#30303a")};
                border-radius: 12px;
            }}
            QLabel#manualImageLabel {{
                color: {self._color("text_secondary", "#6a6a78")};
                font-size: 12px;
                font-weight: 700;
                background: transparent;
            }}
            QFrame#manualInfo {{
                background: {self._color("outline_bg", "#1c1c22")};
                border: 1px solid {self._color("outline_border", "#30303a")};
                border-radius: 12px;
            }}
            QLabel#manualEntryTitle {{
                color: {self._color("text_primary", "#f0f0f6")};
                font-size: 18px;
                font-weight: 800;
                background: transparent;
            }}
            QLabel#manualEntryBody {{
                color: {self._color("text_secondary", "#b6b6c8")};
                font-size: 12px;
                line-height: 1.45;
                background: transparent;
            }}
            QPushButton#manualActionButton {{
                min-height: 30px;
                padding: 0 12px;
                border-radius: 7px;
                border: 1px solid {self._color("outline_border", "#30303a")};
                background: {self._color("outline_bg", "#1c1c22")};
                color: {self._color("outline_text", "#8d8d9a")};
                font-weight: 700;
            }}
            QPushButton#manualActionButton:hover {{
                border-color: {self._color("accent", "#6272ff")};
                color: {self._color("accent", "#6272ff")};
            }}
            QPushButton#manualActionButton:disabled {{
                color: {self._color("text_secondary", "#6a6a78")};
            }}
            """
        )
        self._refresh_active_styles()

    def _show_group(self, group: str) -> None:
        if group not in self.groups:
            return
        self.current_group = group
        self._rebuild_entry_buttons()
        first_index = next((index for index, entry in enumerate(self.entries) if entry.group == group), 0)
        self._show_entry(first_index)
        self._refresh_active_styles()

    def _rebuild_entry_buttons(self) -> None:
        while self.entry_layout.count():
            item = self.entry_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.entry_buttons.clear()
        for index, entry in enumerate(self.entries):
            if entry.group != self.current_group:
                continue
            button = QPushButton(entry.title)
            button.setObjectName("manualEntryButton")
            button.setProperty("active", "false")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, idx=index: self._show_entry(idx))
            self.entry_buttons[index] = button
            self.entry_layout.addWidget(button)
        self.entry_layout.addStretch(1)

    def _show_entry(self, index: int) -> None:
        if not self.entries:
            return
        index = max(0, min(len(self.entries) - 1, index))
        entry = self.entries[index]
        if entry.group != self.current_group:
            self.current_group = entry.group
            self._rebuild_entry_buttons()

        self.current_entry_index = index
        self.current_frame_index = 0
        self.group_badge.setText(entry.group.upper())
        self.entry_counter.setText(f"{index + 1:02d} / {len(self.entries):02d}")
        self.entry_title.setText(entry.title)
        self.entry_body.setText(self._format_entry_body(entry))
        self.previous_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < len(self.entries) - 1)

        self._show_current_frame()
        if len(entry.frames) > 1:
            self.frame_timer.start()
        else:
            self.frame_timer.stop()
        self._refresh_active_styles()

    def _format_entry_body(self, entry: ManualEntry) -> str:
        parts = [entry.summary]
        if entry.steps:
            parts.append("")
            parts.extend(f"- {step}" for step in entry.steps)
        return "\n".join(parts)

    def _show_current_frame(self) -> None:
        entry = self.entries[self.current_entry_index]
        if not entry.frames:
            self.frame_counter.setText("No image assigned")
            self.image_view.set_frame(None, "")
            return

        frame_count = len(entry.frames)
        self.current_frame_index %= frame_count
        frame_name = entry.frames[self.current_frame_index]
        self.frame_counter.setText(f"Frame {self.current_frame_index + 1} / {frame_count}")
        self.image_view.set_frame(self._resolve_frame_path(frame_name), frame_name)

    def _advance_frame(self) -> None:
        entry = self.entries[self.current_entry_index]
        if len(entry.frames) <= 1:
            self.frame_timer.stop()
            return
        self.current_frame_index = (self.current_frame_index + 1) % len(entry.frames)
        self._show_current_frame()

    def _resolve_frame_path(self, frame_name: str) -> Path | None:
        for root in self.asset_dirs:
            candidate = root / frame_name
            if candidate.exists():
                return candidate
        return None

    def _refresh_active_styles(self) -> None:
        for group, button in self.group_buttons.items():
            button.setProperty("active", "true" if group == self.current_group else "false")
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

        for index, button in self.entry_buttons.items():
            button.setProperty("active", "true" if index == self.current_entry_index else "false")
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

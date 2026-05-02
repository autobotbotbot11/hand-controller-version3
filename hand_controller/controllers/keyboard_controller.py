from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import time

from ..config.settings import KeyboardConfig
from ..gestures.hand_pinches import HandPinchState
from ..vision.models import DetectedHand
from .actions import Action, Hotkey, KeyPress


THUMB_TIP_IDX = 4
INDEX_TIP_IDX = 8
PAGE_ALPHA = "alpha"
PAGE_SYMBOLS = "symbols"


@dataclass(frozen=True, slots=True)
class KeyboardKeySpec:
    token: str
    label: str
    action_kind: str
    action_value: str | tuple[str, ...] | None
    width_units: float = 1.0
    shift_action_kind: str | None = None
    shift_action_value: str | tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class KeyboardKeyRect:
    token: str
    label: str
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True, slots=True)
class KeyboardPointer:
    x: int
    y: int
    hand_label: str
    thumb_x: int | None = None
    thumb_y: int | None = None
    index_x: int | None = None
    index_y: int | None = None


@dataclass(slots=True)
class KeyboardState:
    shift_one_shot: bool = False
    caps_lock: bool = False
    current_page: str = PAGE_ALPHA
    last_tap_at: float = -1e9


@dataclass(frozen=True, slots=True)
class KeyboardUpdate:
    actions: tuple[Action, ...] = ()
    layout: tuple[KeyboardKeyRect, ...] = ()
    highlight_labels: frozenset[str] = frozenset()
    pointers: tuple[KeyboardPointer, ...] = ()
    hovered_key_by_hand: tuple[tuple[str, str | None], ...] = ()
    shift_armed: bool = False
    caps_lock: bool = False
    page: str = PAGE_ALPHA
    status: str = "keyboard idle"


def _build_default_specs() -> dict[str, KeyboardKeySpec]:
    specs: dict[str, KeyboardKeySpec] = {
        "ESC": KeyboardKeySpec("ESC", "ESC", "key", "esc", width_units=1.20),
        "TAB": KeyboardKeySpec("TAB", "TAB", "key", "tab", width_units=1.40),
        "BACKSPACE": KeyboardKeySpec("BACKSPACE", "BKSP", "key", "backspace", width_units=1.90),
        "ENTER": KeyboardKeySpec("ENTER", "ENTER", "key", "enter", width_units=1.80),
        "SHIFT": KeyboardKeySpec("SHIFT", "SHIFT", "shift_one_shot", None, width_units=1.80),
        "CAPS": KeyboardKeySpec("CAPS", "CAPS", "caps_lock", None, width_units=1.60),
        "PAGE_SYMBOLS": KeyboardKeySpec("PAGE_SYMBOLS", "123", "page", PAGE_SYMBOLS, width_units=1.50),
        "PAGE_ALPHA": KeyboardKeySpec("PAGE_ALPHA", "ABC", "page", PAGE_ALPHA, width_units=1.50),
        "SPACE": KeyboardKeySpec("SPACE", "SPACE", "key", "space", width_units=4.60),
        "SEMICOLON": KeyboardKeySpec(
            "SEMICOLON",
            ";",
            "key",
            ";",
            shift_action_kind="hotkey",
            shift_action_value=("shift", ";"),
        ),
        "COLON": KeyboardKeySpec("COLON", ":", "hotkey", ("shift", ";")),
        "APOSTROPHE": KeyboardKeySpec(
            "APOSTROPHE",
            "'",
            "key",
            "'",
            shift_action_kind="hotkey",
            shift_action_value=("shift", "'"),
        ),
        "DOUBLE_QUOTE": KeyboardKeySpec("DOUBLE_QUOTE", '"', "hotkey", ("shift", "'")),
        "COMMA": KeyboardKeySpec(
            "COMMA",
            ",",
            "key",
            ",",
            shift_action_kind="hotkey",
            shift_action_value=("shift", ","),
        ),
        "PERIOD": KeyboardKeySpec(
            "PERIOD",
            ".",
            "key",
            ".",
            shift_action_kind="hotkey",
            shift_action_value=("shift", "."),
        ),
        "SLASH": KeyboardKeySpec(
            "SLASH",
            "/",
            "key",
            "/",
            shift_action_kind="hotkey",
            shift_action_value=("shift", "/"),
        ),
        "BACKSLASH": KeyboardKeySpec(
            "BACKSLASH",
            "\\",
            "key",
            "\\",
            shift_action_kind="hotkey",
            shift_action_value=("shift", "\\"),
        ),
        "MINUS": KeyboardKeySpec(
            "MINUS",
            "-",
            "key",
            "-",
            shift_action_kind="hotkey",
            shift_action_value=("shift", "-"),
        ),
        "UNDERSCORE": KeyboardKeySpec("UNDERSCORE", "_", "hotkey", ("shift", "-")),
        "QUESTION": KeyboardKeySpec("QUESTION", "?", "hotkey", ("shift", "/")),
        "EXCLAMATION": KeyboardKeySpec("EXCLAMATION", "!", "hotkey", ("shift", "1")),
        "LPAREN": KeyboardKeySpec("LPAREN", "(", "hotkey", ("shift", "9")),
        "RPAREN": KeyboardKeySpec("RPAREN", ")", "hotkey", ("shift", "0")),
    }

    for digit in "1234567890":
        specs[digit] = KeyboardKeySpec(
            digit,
            digit,
            "key",
            digit,
        )

    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        key_name = letter.lower()
        specs[letter] = KeyboardKeySpec(
            letter,
            letter,
            "key",
            key_name,
            shift_action_kind="hotkey",
            shift_action_value=("shift", key_name),
        )

    return specs


KEY_SPECS = _build_default_specs()


def _normalize_layout_rows(rows: Sequence[Sequence[str]] | Sequence[str]) -> tuple[tuple[str, ...], ...]:
    normalized_rows: list[tuple[str, ...]] = []
    for row in rows or ():
        if isinstance(row, str):
            tokens = tuple(part.strip().upper() for part in row.split() if part.strip())
        else:
            tokens = tuple(str(part).strip().upper() for part in row if str(part).strip())
        if tokens:
            normalized_rows.append(tokens)
    if not normalized_rows:
        raise ValueError("Keyboard layout must contain at least one non-empty row.")
    return tuple(normalized_rows)


def _resolve_width_units(settings: KeyboardConfig) -> dict[str, float]:
    resolved = {token: spec.width_units for token, spec in KEY_SPECS.items()}
    overrides = settings.key_width_units or {}
    if isinstance(overrides, Mapping):
        for token, width in overrides.items():
            resolved[str(token).strip().upper()] = float(width)
    return resolved


def _create_action(kind: str | None, value: str | tuple[str, ...] | None) -> Action | None:
    if kind is None or value is None:
        return None
    if kind == "key":
        return KeyPress(str(value))
    if kind == "hotkey":
        if isinstance(value, tuple):
            return Hotkey(value)
        if isinstance(value, list):
            return Hotkey(tuple(str(part) for part in value))
        raise ValueError(f"Hotkey action expects a tuple/list, got {type(value)!r}")
    return None


def _is_letter_token(token: str) -> bool:
    return len(token) == 1 and token.isalpha()


def create_keyboard_layout(
    frame_width: int,
    frame_height: int,
    settings: KeyboardConfig,
    *,
    rows: Sequence[Sequence[str]] | Sequence[str] | None = None,
) -> tuple[KeyboardKeyRect, ...]:
    normalized_rows = _normalize_layout_rows(rows if rows is not None else settings.layout_rows)
    width_units = _resolve_width_units(settings)

    for row in normalized_rows:
        for token in row:
            if token not in KEY_SPECS:
                raise ValueError(f"Unknown keyboard layout token: {token}")

    keyboard_height = int(frame_height * settings.height_ratio)
    keyboard_top = frame_height - keyboard_height - settings.bottom_margin_px
    keyboard_left = settings.side_margin_px
    keyboard_right = frame_width - settings.side_margin_px
    keyboard_width = max(1, keyboard_right - keyboard_left)
    gap_x = settings.key_gap_px
    gap_y = settings.row_gap_px

    unit_width = min(
        (keyboard_width - gap_x * max(0, len(row) - 1)) / max(1.0, sum(width_units[token] for token in row))
        for row in normalized_rows
    )
    row_height = (keyboard_height - gap_y * max(0, len(normalized_rows) - 1)) / len(normalized_rows)

    keys: list[KeyboardKeyRect] = []
    for row_index, row in enumerate(normalized_rows):
        y1 = int(round(keyboard_top + row_index * (row_height + gap_y)))
        y2 = int(round(y1 + row_height))

        row_width = sum(width_units[token] * unit_width for token in row) + gap_x * max(0, len(row) - 1)
        cursor_x = keyboard_left + (keyboard_width - row_width) / 2.0

        for token in row:
            spec = KEY_SPECS[token]
            width_px = max(1, int(round(width_units[token] * unit_width)))
            x1 = int(round(cursor_x))
            x2 = int(round(cursor_x + width_px))
            keys.append(
                KeyboardKeyRect(
                    token=token,
                    label=spec.label,
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                )
            )
            cursor_x += width_px + gap_x

    return tuple(keys)


def get_key_at_point(keys: tuple[KeyboardKeyRect, ...], x: int, y: int) -> KeyboardKeyRect | None:
    for key in keys:
        if key.x1 <= x <= key.x2 and key.y1 <= y <= key.y2:
            return key
    return None


def _landmark_px(hand: DetectedHand, index: int, frame_width: int, frame_height: int) -> tuple[int, int]:
    point = hand.landmark(index)
    return int(point.x * frame_width), int(point.y * frame_height)


class KeyboardController:
    def __init__(self, settings: KeyboardConfig | None = None) -> None:
        self.settings = settings or KeyboardConfig()
        self.state = KeyboardState()
        self._layout_cache: dict[tuple[int, int, str], tuple[KeyboardKeyRect, ...]] = {}

    def reset(self) -> None:
        self.state.shift_one_shot = False
        self.state.caps_lock = False
        self.state.current_page = PAGE_ALPHA
        self.state.last_tap_at = -1e9

    def _rows_for_current_page(self) -> tuple[tuple[str, ...], ...]:
        if self.state.current_page == PAGE_SYMBOLS:
            return _normalize_layout_rows(self.settings.symbol_layout_rows)
        return _normalize_layout_rows(self.settings.layout_rows)

    def _should_uppercase_letters(self) -> bool:
        return self.state.caps_lock != self.state.shift_one_shot

    def _display_label(self, token: str) -> str:
        spec = KEY_SPECS[token]
        if self.state.current_page == PAGE_ALPHA and _is_letter_token(token):
            return token if self._should_uppercase_letters() else token.lower()
        return spec.label

    def _render_layout(self, base_layout: tuple[KeyboardKeyRect, ...]) -> tuple[KeyboardKeyRect, ...]:
        return tuple(
            KeyboardKeyRect(
                token=key.token,
                label=self._display_label(key.token),
                x1=key.x1,
                y1=key.y1,
                x2=key.x2,
                y2=key.y2,
            )
            for key in base_layout
        )

    def layout_for_frame(self, frame_width: int, frame_height: int) -> tuple[KeyboardKeyRect, ...]:
        cache_key = (frame_width, frame_height, self.state.current_page)
        cached = self._layout_cache.get(cache_key)
        if cached is not None:
            return self._render_layout(cached)

        layout = create_keyboard_layout(
            frame_width,
            frame_height,
            self.settings,
            rows=self._rows_for_current_page(),
        )
        self._layout_cache[cache_key] = layout
        return self._render_layout(layout)

    def _activate_special_token(self, token: str) -> None:
        if token == "SHIFT":
            self.state.shift_one_shot = not self.state.shift_one_shot
        elif token == "CAPS":
            self.state.caps_lock = not self.state.caps_lock
            self.state.shift_one_shot = False
        elif token == "PAGE_SYMBOLS":
            self.state.current_page = PAGE_SYMBOLS
            self.state.shift_one_shot = False
        elif token == "PAGE_ALPHA":
            self.state.current_page = PAGE_ALPHA
            self.state.shift_one_shot = False

    def _resolve_key_action(self, spec: KeyboardKeySpec) -> Action | None:
        use_shift_variant = False
        if self.state.current_page == PAGE_ALPHA and _is_letter_token(spec.token):
            use_shift_variant = self._should_uppercase_letters()

        if use_shift_variant and spec.shift_action_kind is not None:
            return _create_action(spec.shift_action_kind, spec.shift_action_value)
        return _create_action(spec.action_kind, spec.action_value)

    def update(
        self,
        *,
        hands: tuple[DetectedHand, ...],
        pinch_states: dict[str, HandPinchState],
        frame_width: int,
        frame_height: int,
        now: float | None = None,
    ) -> KeyboardUpdate:
        now = time.time() if now is None else now
        layout = self.layout_for_frame(frame_width, frame_height)
        actions: list[Action] = []
        highlights: set[str] = set()
        pointers: list[KeyboardPointer] = []
        hovered_by_hand: dict[str, str | None] = {"Left": None, "Right": None}

        for hand in hands:
            hand_label = hand.label
            thumb_x, thumb_y = _landmark_px(hand, THUMB_TIP_IDX, frame_width, frame_height)
            index_x, index_y = _landmark_px(hand, INDEX_TIP_IDX, frame_width, frame_height)
            px = int(round((thumb_x + index_x) / 2.0))
            py = int(round((thumb_y + index_y) / 2.0))
            pointers.append(
                KeyboardPointer(
                    x=px,
                    y=py,
                    hand_label=hand_label,
                    thumb_x=thumb_x,
                    thumb_y=thumb_y,
                    index_x=index_x,
                    index_y=index_y,
                )
            )

            key = get_key_at_point(layout, px, py)
            if key is None:
                continue

            hovered_by_hand[hand_label] = key.label
            highlights.add(key.label)
            pinch_state = pinch_states.get(hand_label)
            if pinch_state is None:
                continue
            if pinch_state.middle.down:
                actions.append(KeyPress("backspace"))
                continue
            if not pinch_state.index.down:
                continue
            if (now - self.state.last_tap_at) < self.settings.tap_cooldown_seconds:
                continue

            spec = KEY_SPECS[key.token]
            if spec.action_kind in {"shift_one_shot", "caps_lock", "page"}:
                self._activate_special_token(key.token)
                self.state.last_tap_at = now
                layout = self.layout_for_frame(frame_width, frame_height)
                continue

            action = self._resolve_key_action(spec)
            if action is not None:
                actions.append(action)
                self.state.last_tap_at = now
            self.state.shift_one_shot = False

        if self.state.shift_one_shot:
            highlights.add("SHIFT")
        if self.state.caps_lock and self.state.current_page == PAGE_ALPHA:
            highlights.add("CAPS")

        hovered_pairs = tuple(sorted(hovered_by_hand.items()))
        hovered_summary = " ".join(f"{hand}:{label or '-'}" for hand, label in hovered_pairs)
        status = (
            f"keyboard page={self.state.current_page} "
            f"shift={'on' if self.state.shift_one_shot else 'off'} "
            f"caps={'on' if self.state.caps_lock else 'off'} "
            f"hover={hovered_summary}"
        )

        return KeyboardUpdate(
            actions=tuple(actions),
            layout=layout,
            highlight_labels=frozenset(highlights),
            pointers=tuple(pointers),
            hovered_key_by_hand=hovered_pairs,
            shift_armed=self.state.shift_one_shot,
            caps_lock=self.state.caps_lock,
            page=self.state.current_page,
            status=status,
        )

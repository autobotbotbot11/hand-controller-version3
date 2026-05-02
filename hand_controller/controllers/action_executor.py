from __future__ import annotations

from typing import Iterable

from .actions import Action, Click, DoubleClick, Hotkey, KeyPress, MouseDown, MouseUp, MoveRelative


def get_screen_size() -> tuple[int, int]:
    try:
        import pyautogui
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pyautogui is required for --mouse-smoke. Install Phase 4 dependencies first."
        ) from exc

    pyautogui.FAILSAFE = False
    size = pyautogui.size()
    return int(size.width), int(size.height)


def execute_actions(actions: Iterable[Action]) -> None:
    try:
        import pyautogui
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pyautogui is required for --mouse-smoke. Install Phase 4 dependencies first."
        ) from exc

    pyautogui.FAILSAFE = False

    for action in actions:
        if isinstance(action, MoveRelative):
            pyautogui.moveRel(action.dx, action.dy, _pause=False)
        elif isinstance(action, DoubleClick):
            pyautogui.click(button=action.button, clicks=2, interval=0.12, _pause=False)
        elif isinstance(action, MouseDown):
            pyautogui.mouseDown(button=action.button, _pause=False)
        elif isinstance(action, MouseUp):
            pyautogui.mouseUp(button=action.button, _pause=False)
        elif isinstance(action, Hotkey):
            pyautogui.hotkey(*action.keys, _pause=False)
        elif isinstance(action, KeyPress):
            pyautogui.press(action.key, _pause=False)
        elif isinstance(action, Click):
            pyautogui.mouseDown(button=action.button, _pause=False)
            pyautogui.mouseUp(button=action.button, _pause=False)

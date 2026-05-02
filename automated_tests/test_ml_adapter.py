from __future__ import annotations

from bootstrap import ensure_repo_root_on_path
from common import PlainTestSuite

ensure_repo_root_on_path()

from hand_controller.config.settings import MLConfig
from hand_controller.controllers.actions import Hotkey
from hand_controller.ml.adapter import MLControlAdapter
from hand_controller.ml.predictor import MLPrediction
from hand_controller.runtime.state import Mode, RuntimeState


def prediction(label: str, *, available: bool = True, reason: str | None = None) -> MLPrediction:
    return MLPrediction(
        raw_label=label,
        label=label if available else "idle",
        p1=0.9 if available else None,
        margin=0.4 if available else None,
        available=available,
        reason=reason,
    )


def run() -> object:
    suite = PlainTestSuite("ML Adapter")
    config = MLConfig(confirm_frames=2, toggle_hold_seconds=0.30, toggle_cooldown=0.80, shortcut_cooldown=0.60)

    adapter = MLControlAdapter(config)
    state = RuntimeState()
    unavailable = adapter.update(prediction("idle", available=False, reason="missing model"), state, now=0.0)
    suite.check_equal("unavailable prediction reports the reason", unavailable.status, "missing model", input_data='MLPrediction available = False and reason = "missing model"')

    adapter = MLControlAdapter(config)
    state = RuntimeState(mode=Mode.MOUSE)
    adapter.update(prediction("undo"), state, now=1.0)
    undo_update = adapter.update(prediction("undo"), state, now=1.1)
    suite.check_equal("confirmed undo emits one Ctrl+Z hotkey", undo_update.actions, (Hotkey(keys=("ctrl", "z")),), input_data='Two consecutive predictions with label = "undo" while mode = mouse')
    undo_repeat = adapter.update(prediction("undo"), state, now=1.2)
    suite.check_equal("held undo does not repeat immediately", undo_repeat.actions, (), input_data='Third consecutive "undo" prediction immediately after shortcut trigger')

    adapter = MLControlAdapter(config)
    state = RuntimeState(mode=Mode.MOUSE)
    adapter.update(prediction("hold"), state, now=1.0)
    hold_update = adapter.update(prediction("hold"), state, now=1.1)
    suite.check_true("confirmed hold activates clutch in mouse mode", hold_update.hold_active, input_data='Two consecutive predictions with label = "hold" while mode = mouse')

    adapter = MLControlAdapter(config)
    state = RuntimeState(mode=Mode.KEYBOARD)
    adapter.update(prediction("hold"), state, now=1.0)
    hold_keyboard = adapter.update(prediction("hold"), state, now=1.1)
    suite.check_false("hold does not stay active in keyboard mode", hold_keyboard.hold_active, input_data='Two consecutive predictions with label = "hold" while mode = keyboard')

    adapter = MLControlAdapter(config)
    state = RuntimeState(mode=Mode.MOUSE, control_enabled=True)
    adapter.update(prediction("toggle"), state, now=1.0)
    toggle_armed = adapter.update(prediction("toggle"), state, now=1.1)
    suite.check_equal("toggle is armed before hold time completes", state.control_enabled, True, input_data='Toggle prediction held for only 0.1 seconds, below configured hold threshold')
    toggled = adapter.update(prediction("toggle"), state, now=1.5)
    suite.check_false("toggle hold flips control_enabled once threshold is met", state.control_enabled, input_data='Toggle prediction held long enough to exceed configured hold threshold')
    suite.check_true("toggle status mentions toggled", "toggled" in toggled.status, input_data='Status text returned after successful toggle event')

    adapter.update(prediction("idle"), state, now=1.6)
    adapter.update(prediction("toggle"), state, now=1.7)
    cooldown_update = adapter.update(prediction("toggle"), state, now=1.8)
    adapter.update(prediction("toggle"), state, now=2.0)
    suite.check_false("toggle cooldown blocks immediate second flip", state.control_enabled, input_data='Second toggle attempt happens inside cooldown window after a recent successful toggle')
    suite.check_true("cooldown status stays on toggle path", cooldown_update.status.startswith("toggle"), input_data='Status text returned during cooldown-limited toggle attempt')

    adapter.update(prediction("idle"), state, now=2.4)
    adapter.update(prediction("toggle"), state, now=2.6)
    adapter.update(prediction("toggle"), state, now=3.0)
    adapter.update(prediction("toggle"), state, now=3.4)
    suite.check_true("toggle can fire again after cooldown window", state.control_enabled, input_data='Fresh toggle sequence begins after cooldown has already passed')

    return suite.summary()


if __name__ == "__main__":
    run()

from __future__ import annotations

from bootstrap import ensure_repo_root_on_path
from common import PlainTestSuite
from fixtures import make_hand, make_pinch_state

ensure_repo_root_on_path()

from hand_controller.controllers.actions import Hotkey, KeyPress
from hand_controller.controllers.keyboard_controller import KeyboardController


FRAME_WIDTH = 1200
FRAME_HEIGHT = 700


def hand_over_key(controller: KeyboardController, token: str, *, label: str = "Right"):
    layout = controller.layout_for_frame(FRAME_WIDTH, FRAME_HEIGHT)
    key = next(item for item in layout if item.token == token)
    center_x = ((key.x1 + key.x2) / 2.0) / FRAME_WIDTH
    center_y = ((key.y1 + key.y2) / 2.0) / FRAME_HEIGHT
    return make_hand(label=label, overrides={8: (center_x, center_y, 0.0)})


def run() -> object:
    suite = PlainTestSuite("Keyboard Controller")

    controller = KeyboardController()
    layout = controller.layout_for_frame(FRAME_WIDTH, FRAME_HEIGHT)
    tokens = {key.token for key in layout}
    suite.check_true("default layout contains ESC", "ESC" in tokens, input_data="default keyboard layout for a 1200x700 frame")
    suite.check_true("default layout contains SPACE", "SPACE" in tokens, input_data="default keyboard layout for a 1200x700 frame")

    controller = KeyboardController()
    hand_a = hand_over_key(controller, "A")
    update = controller.update(
        hands=(hand_a,),
        pinch_states={"Right": make_pinch_state(hand_label="Right", index_down=True)},
        frame_width=FRAME_WIDTH,
        frame_height=FRAME_HEIGHT,
        now=1.0,
    )
    suite.check_equal("plain letter press emits one action", len(update.actions), 1, input_data='Right hand index finger centered on key "A" with index pinch down')
    suite.check_equal("plain letter press types lowercase a", update.actions[0], KeyPress("a"), input_data='Right hand index finger centered on key "A" with index pinch down')

    controller = KeyboardController()
    shift_hand = hand_over_key(controller, "SHIFT")
    update_shift = controller.update(
        hands=(shift_hand,),
        pinch_states={"Right": make_pinch_state(hand_label="Right", index_down=True)},
        frame_width=FRAME_WIDTH,
        frame_height=FRAME_HEIGHT,
        now=1.0,
    )
    suite.check_true("shift key arms one-shot shift", update_shift.shift_armed, input_data='Right hand index finger centered on key "SHIFT" with index pinch down')
    hand_a = hand_over_key(controller, "A")
    update_shift_a = controller.update(
        hands=(hand_a,),
        pinch_states={"Right": make_pinch_state(hand_label="Right", index_down=True)},
        frame_width=FRAME_WIDTH,
        frame_height=FRAME_HEIGHT,
        now=2.0,
    )
    suite.check_equal("shifted letter uses hotkey action", update_shift_a.actions[0], Hotkey(("shift", "a")), input_data='After SHIFT is armed, Right hand index finger is centered on key "A" with index pinch down')
    suite.check_false("one-shot shift resets after the letter press", controller.state.shift_one_shot, input_data='State of controller after shifted letter "A" is pressed once')

    controller = KeyboardController()
    caps_hand = hand_over_key(controller, "CAPS")
    controller.update(
        hands=(caps_hand,),
        pinch_states={"Right": make_pinch_state(hand_label="Right", index_down=True)},
        frame_width=FRAME_WIDTH,
        frame_height=FRAME_HEIGHT,
        now=1.0,
    )
    hand_a = hand_over_key(controller, "A")
    update_caps_a = controller.update(
        hands=(hand_a,),
        pinch_states={"Right": make_pinch_state(hand_label="Right", index_down=True)},
        frame_width=FRAME_WIDTH,
        frame_height=FRAME_HEIGHT,
        now=2.0,
    )
    suite.check_equal("caps lock keeps uppercase behavior", update_caps_a.actions[0], Hotkey(("shift", "a")), input_data='After CAPS is toggled, Right hand index finger is centered on key "A" with index pinch down')

    controller = KeyboardController()
    page_symbols_hand = hand_over_key(controller, "PAGE_SYMBOLS")
    update_page = controller.update(
        hands=(page_symbols_hand,),
        pinch_states={"Right": make_pinch_state(hand_label="Right", index_down=True)},
        frame_width=FRAME_WIDTH,
        frame_height=FRAME_HEIGHT,
        now=1.0,
    )
    suite.check_equal("page switch changes controller state to symbols", update_page.page, "symbols", input_data='Right hand index finger centered on key "PAGE_SYMBOLS" with index pinch down')
    hand_one = hand_over_key(controller, "1")
    update_one = controller.update(
        hands=(hand_one,),
        pinch_states={"Right": make_pinch_state(hand_label="Right", index_down=True)},
        frame_width=FRAME_WIDTH,
        frame_height=FRAME_HEIGHT,
        now=2.0,
    )
    suite.check_equal("number key on symbols page types numeric keypress", update_one.actions[0], KeyPress("1"), input_data='Symbols page active, Right hand index finger centered on key "1" with index pinch down')

    controller = KeyboardController()
    backspace_update = controller.update(
        hands=(),
        pinch_states={"Right": make_pinch_state(hand_label="Right", middle_down=True)},
        frame_width=FRAME_WIDTH,
        frame_height=FRAME_HEIGHT,
        now=1.0,
    )
    suite.check_equal("middle pinch sends backspace", backspace_update.actions[0], KeyPress("backspace"), input_data="no hovered key, but pinch_states contains Right.middle.down = True")

    return suite.summary()


if __name__ == "__main__":
    run()

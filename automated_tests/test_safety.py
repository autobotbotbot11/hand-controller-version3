from __future__ import annotations

from bootstrap import ensure_repo_root_on_path
from common import PlainTestSuite
from fixtures import make_hand

ensure_repo_root_on_path()

from hand_controller.gestures.safety import analyze_hand_view_safety


def run() -> object:
    suite = PlainTestSuite("Hand Safety")

    safe_right = make_hand(label="Right")
    safe_result = analyze_hand_view_safety(safe_right, mirrored_input=True)
    suite.check_true(
        "right-hand palm-facing is ordering-safe",
        safe_result.ordering_ok,
        input_data="default mirrored Right hand fixture with palm-facing thumb/pinky ordering",
    )
    suite.check_true(
        "wide palm is press-safe",
        safe_result.press_safe,
        input_data="default mirrored Right hand fixture with normal palm width",
    )

    wrong_order = make_hand(
        label="Right",
        overrides={
            4: (0.86, 0.52, 0.0),
            20: (0.22, 0.34, 0.0),
        },
    )
    wrong_order_result = analyze_hand_view_safety(wrong_order, mirrored_input=True)
    suite.check_false(
        "wrong thumb-pinky ordering is not palm-facing",
        wrong_order_result.ordering_ok,
        input_data="Right hand fixture where thumb x is moved opposite to expected mirrored ordering",
    )
    suite.check_false(
        "wrong thumb-pinky ordering blocks press safety",
        wrong_order_result.press_safe,
        input_data="Right hand fixture with wrong thumb/pinky ordering",
    )

    narrow_palm = make_hand(
        label="Right",
        overrides={
            5: (0.47, 0.55, 0.0),
            17: (0.53, 0.58, 0.0),
        },
    )
    narrow_result = analyze_hand_view_safety(narrow_palm, mirrored_input=True)
    suite.check_false(
        "narrow palm ratio is not press-safe",
        narrow_result.press_safe,
        input_data="Right hand fixture with index MCP and pinky MCP placed unusually close together",
    )

    # For the mirrored left-hand branch, thumb must appear to the right of the pinky.
    safe_left = make_hand(
        label="Left",
        overrides={
            4: (0.82, 0.52, 0.0),
            17: (0.26, 0.58, 0.0),
            18: (0.22, 0.50, 0.0),
            19: (0.19, 0.42, 0.0),
            20: (0.16, 0.34, 0.0),
        },
    )
    safe_left_result = analyze_hand_view_safety(safe_left, mirrored_input=True)
    suite.check_true(
        "left-hand mirrored ordering is handled",
        safe_left_result.ordering_ok,
        input_data="mirrored Left hand fixture with thumb positioned to the right of the pinky",
    )
    suite.check_true(
        "left-hand wide palm can still be press-safe",
        safe_left_result.press_safe,
        input_data="mirrored Left hand fixture with safe palm width and ordering",
    )

    return suite.summary()


if __name__ == "__main__":
    run()

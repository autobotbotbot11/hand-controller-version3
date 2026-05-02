from __future__ import annotations

import time

from bootstrap import ensure_repo_root_on_path
from common import PlainTestSuite
from fixtures import make_box_hand

ensure_repo_root_on_path()

from hand_controller.config.settings import HandSelectorConfig
from hand_controller.vision.hand_selector import HandSelector


FRAME_WIDTH = 1000
FRAME_HEIGHT = 800


def run() -> object:
    suite = PlainTestSuite("Hand Selector")

    selector = HandSelector(HandSelectorConfig())
    empty_selection = selector.select((), FRAME_WIDTH, FRAME_HEIGHT)
    suite.check_equal(
        "no hands means no primary hand",
        empty_selection.primary,
        None,
        input_data="hands = empty tuple",
    )

    left_large = make_box_hand(label="Left", center_x=0.35, center_y=0.50, spread_x=0.32, spread_y=0.34)
    right_small = make_box_hand(label="Right", center_x=0.68, center_y=0.50, spread_x=0.18, spread_y=0.20)
    first_selection = selector.select((left_large, right_small), FRAME_WIDTH, FRAME_HEIGHT)
    shared_input = "two visible hands: larger Left hand and smaller Right hand"
    suite.check_equal("largest bounding box becomes primary first", first_selection.primary, left_large, input_data=shared_input)
    suite.check_equal("left hand reference is preserved", first_selection.left, left_large, input_data=shared_input)
    suite.check_equal("right hand reference is preserved", first_selection.right, right_small, input_data=shared_input)
    suite.check_equal("secondary hand is filled", first_selection.secondary, right_small, input_data=shared_input)

    left_nearby = make_box_hand(label="Left", center_x=0.36, center_y=0.50, spread_x=0.30, spread_y=0.32)
    right_slightly_larger = make_box_hand(label="Right", center_x=0.72, center_y=0.50, spread_x=0.33, spread_y=0.35)
    second_selection = selector.select((left_nearby, right_slightly_larger), FRAME_WIDTH, FRAME_HEIGHT)
    suite.check_equal(
        "selector keeps the nearby previous primary when size difference stays inside switch margin",
        second_selection.primary,
        left_nearby,
        input_data="second frame with previous Left hand still nearby while Right hand becomes only slightly larger",
    )

    selector._last_primary_center_px = (100.0, 100.0)
    selector._last_seen_time = time.time() - 1.0
    selector.select((), FRAME_WIDTH, FRAME_HEIGHT)
    suite.check_equal(
        "lost hand beyond grace period clears primary memory",
        selector._last_primary_center_px,
        None,
        input_data="selector memory set manually, then no hands returned after grace period",
    )

    return suite.summary()


if __name__ == "__main__":
    run()

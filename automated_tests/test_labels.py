from __future__ import annotations

from bootstrap import ensure_repo_root_on_path
from common import PlainTestSuite

ensure_repo_root_on_path()

from hand_controller.ml.labels import canonicalize_label


def run() -> object:
    suite = PlainTestSuite("Label Normalization")
    suite.check_equal(
        "left click phrase becomes left_click",
        canonicalize_label("left click"),
        "left_click",
        input_data='raw label = "left click"',
    )
    suite.check_equal(
        "double click aliases to left_click",
        canonicalize_label("double left click"),
        "left_click",
        input_data='raw label = "double left click"',
    )
    suite.check_equal(
        "none becomes idle",
        canonicalize_label(None),
        "idle",
        input_data="raw label = None",
    )
    suite.check_equal(
        "spacing is normalized",
        canonicalize_label("  right   click "),
        "right_click",
        input_data='raw label = "  right   click "',
    )
    suite.check_equal(
        "unknown labels stay readable",
        canonicalize_label("custom pose"),
        "custom_pose",
        input_data='raw label = "custom pose"',
    )
    return suite.summary()


if __name__ == "__main__":
    run()

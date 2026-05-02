from __future__ import annotations

from pathlib import Path
import json
import tempfile

from bootstrap import ensure_repo_root_on_path
from common import PlainTestSuite

ensure_repo_root_on_path()

from hand_controller.config.settings import build_default_config, build_factory_default_config


def run() -> object:
    suite = PlainTestSuite("Settings")

    factory = build_factory_default_config()
    suite.check_equal(
        "factory default theme is dark",
        factory.general.theme,
        "Dark",
        input_data="factory default config with no tuning file",
    )
    suite.check_equal(
        "factory default camera index is zero",
        factory.camera.index,
        0,
        input_data="factory default config with no tuning file",
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)

        valid_path = temp_root / "valid_tuning.json"
        valid_path.write_text(
            json.dumps(
                {
                    "camera": {"index": 2},
                    "keyboard": {"show_selfie": False},
                    "mouse_motion": {"sensitivity": 1.23},
                }
            ),
            encoding="utf-8",
        )
        config = build_default_config(valid_path)
        suite.check_equal(
            "camera override is applied",
            config.camera.index,
            2,
            input_data='valid_tuning.json contains camera.index = 2',
        )
        suite.check_false(
            "keyboard show_selfie override is applied",
            config.keyboard.show_selfie,
            input_data='valid_tuning.json contains keyboard.show_selfie = False',
        )
        suite.check_close(
            "mouse sensitivity override is applied",
            config.mouse_motion.sensitivity,
            1.23,
            input_data='valid_tuning.json contains mouse_motion.sensitivity = 1.23',
        )

        bad_section_path = temp_root / "bad_section.json"
        bad_section_path.write_text(json.dumps({"unknown_section": {}}), encoding="utf-8")
        suite.expect_exception(
            "unknown top-level tuning section raises ValueError",
            lambda: build_default_config(bad_section_path),
            ValueError,
            input_data='bad_section.json contains top-level section "unknown_section"',
        )

        bad_field_path = temp_root / "bad_field.json"
        bad_field_path.write_text(json.dumps({"camera": {"bad_field": 1}}), encoding="utf-8")
        suite.expect_exception(
            "unknown tuning field raises ValueError",
            lambda: build_default_config(bad_field_path),
            ValueError,
            input_data='bad_field.json contains camera.bad_field = 1',
        )

    return suite.summary()


if __name__ == "__main__":
    run()

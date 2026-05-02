from __future__ import annotations

import argparse
import json

from .config.settings import AppConfig, build_default_config, tuning_snapshot
from .runtime.state import RuntimeState


def build_boot_message(config: AppConfig, state: RuntimeState) -> str:
    return "\n".join(
        [
            "Hand Controller Rewrite",
            f"python_target={config.python_version}",
            f"camera={config.camera.width}x{config.camera.height}@{config.camera.index}",
            f"mode={state.mode.value}",
            f"control_enabled={state.control_enabled}",
            f"tuning={config.tuning_path or 'defaults'}",
            f"ml_enabled={config.ml.enabled}",
            "status=phase-k7-ready",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vision-smoke",
        action="store_true",
        help="Run the Phase 2 camera + hand-tracking smoke test.",
    )
    parser.add_argument(
        "--mouse-smoke",
        action="store_true",
        help="Run the live control smoke test with mouse, keyboard, and ML command integration.",
    )
    parser.add_argument(
        "--control-smoke",
        action="store_true",
        help="Alias for --mouse-smoke.",
    )
    parser.add_argument(
        "--ui-smoke",
        action="store_true",
        help="Run the Phase K1 control-panel + transparent-overlay smoke test.",
    )
    parser.add_argument(
        "--ui-live",
        action="store_true",
        help="Run the live control panel + transparent-overlay path with the real CV worker.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run a repo-local validation check for imports, local artifacts, and ML loading.",
    )
    parser.add_argument(
        "--tuning",
        type=str,
        default=None,
        help="Optional path to a JSON tuning file. Defaults to tuning.local.json in the repo root if present.",
    )
    args = parser.parse_args()

    config = build_default_config(args.tuning)
    state = RuntimeState()

    if args.vision_smoke:
        from .runtime.vision_baseline import run_vision_smoke

        run_vision_smoke(config)
        return

    if args.mouse_smoke or args.control_smoke:
        from .runtime.mouse_smoke import run_mouse_smoke

        print(build_boot_message(config, state))
        print(json.dumps(tuning_snapshot(config), indent=2))
        run_mouse_smoke(config)
        return

    if args.ui_smoke:
        from .runtime.ui_foundation_smoke import run_ui_foundation_smoke

        print(build_boot_message(config, state))
        run_ui_foundation_smoke(config)
        return

    if args.ui_live:
        from .runtime.ui_live_control import run_ui_live_control

        print(build_boot_message(config, state))
        run_ui_live_control(config)
        return

    if args.validate:
        from .runtime.validation import run_validation

        print(build_boot_message(config, state))
        run_validation(config)
        return

    print(build_boot_message(config, state))
    print("hint=run with --vision-smoke, --control-smoke, --ui-smoke, --ui-live, or --validate for repo checks")


if __name__ == "__main__":
    main()

from __future__ import annotations

from bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

import test_hand_selector
import test_keyboard_controller
import test_labels
import test_ml_adapter
import test_mouse_clicks
import test_safety
import test_settings


def main() -> int:
    print("HAND CONTROLLER REWRITE - AUTOMATED TEST SCRIPTS")
    print("=" * 72)

    modules = [
        test_labels,
        test_settings,
        test_safety,
        test_hand_selector,
        test_mouse_clicks,
        test_keyboard_controller,
        test_ml_adapter,
    ]

    total_passed = 0
    total_failed = 0
    total_tests = 0

    for module in modules:
        result = module.run()
        total_passed += result.passed
        total_failed += result.failed
        total_tests += result.total

    print("FINAL SUMMARY")
    print(f"Total Passed: {total_passed}")
    print(f"Total Failed: {total_failed}")
    print(f"Total Tests : {total_tests}")
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

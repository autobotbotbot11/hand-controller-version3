from __future__ import annotations

from dataclasses import dataclass
import traceback


UNSET = object()


@dataclass(slots=True, frozen=True)
class SuiteResult:
    name: str
    passed: int
    failed: int

    @property
    def total(self) -> int:
        return self.passed + self.failed


class PlainTestSuite:
    def __init__(self, name: str) -> None:
        self.name = name
        self.passed = 0
        self.failed = 0
        self.case_number = 0

    def _stringify(self, value) -> str:
        if value is None:
            return "(none)"
        if isinstance(value, str):
            text = value
        else:
            text = repr(value)

        if len(text) > 180:
            return text[:177] + "..."
        return text

    def _record(
        self,
        ok: bool,
        title: str,
        *,
        test_type: str = "Functional",
        input_data: str | None = None,
        expected=UNSET,
        actual=UNSET,
        notes: str | None = None,
    ) -> None:
        self.case_number += 1
        if ok:
            self.passed += 1
        else:
            self.failed += 1

        print(f"TEST SUITE : {self.name}")
        print(f"TEST CASE  : {self.case_number:02d} - {title}")
        print(f"TEST TYPE  : {test_type}")
        print(f"INPUT DATA : {input_data or '(see test script)'}")
        if expected is not UNSET:
            print(f"EXPECTED   : {self._stringify(expected)}")
        if actual is not UNSET:
            print(f"ACTUAL     : {self._stringify(actual)}")
        if notes:
            print(f"NOTES      : {notes}")
        print(f"STATUS     : {'PASS' if ok else 'FAIL'}")
        print("-" * 72)

    def check_equal(self, title: str, actual, expected, *, input_data: str | None = None) -> None:
        self._record(
            actual == expected,
            title,
            input_data=input_data,
            expected=expected,
            actual=actual,
        )

    def check_true(self, title: str, value, *, input_data: str | None = None) -> None:
        self._record(
            bool(value),
            title,
            input_data=input_data,
            expected=True,
            actual=bool(value),
        )

    def check_false(self, title: str, value, *, input_data: str | None = None) -> None:
        self._record(
            not bool(value),
            title,
            input_data=input_data,
            expected=False,
            actual=bool(value),
        )

    def check_close(
        self,
        title: str,
        actual: float,
        expected: float,
        tolerance: float = 1e-6,
        *,
        input_data: str | None = None,
    ) -> None:
        ok = abs(actual - expected) <= tolerance
        self._record(
            ok,
            title,
            input_data=input_data,
            expected=f"{expected!r} +/- {tolerance!r}",
            actual=actual,
        )

    def expect_exception(
        self,
        title: str,
        func,
        expected_exception: type[BaseException],
        *,
        input_data: str | None = None,
    ) -> None:
        try:
            func()
        except expected_exception:
            self._record(
                True,
                title,
                input_data=input_data,
                expected=f"{expected_exception.__name__} is raised",
                actual=f"{expected_exception.__name__} was raised",
            )
        except Exception as exc:  # pragma: no cover - diagnostic path
            self._record(
                False,
                title,
                input_data=input_data,
                expected=f"{expected_exception.__name__} is raised",
                actual=f"{type(exc).__name__} was raised",
                notes=str(exc),
            )
        else:
            self._record(
                False,
                title,
                input_data=input_data,
                expected=f"{expected_exception.__name__} is raised",
                actual="No exception was raised",
            )

    def run_case(self, title: str, func, *, input_data: str | None = None) -> None:
        try:
            func()
        except Exception as exc:  # pragma: no cover - diagnostic path
            trace = traceback.format_exc(limit=2).replace("\n", " | ")
            self._record(
                False,
                title,
                input_data=input_data,
                expected="Case runs without unexpected exception",
                actual=f"{type(exc).__name__} was raised",
                notes=trace,
            )

    def summary(self) -> SuiteResult:
        total = self.passed + self.failed
        print(f"SUMMARY - {self.name}: passed={self.passed}, failed={self.failed}, total={total}")
        print("-" * 72)
        return SuiteResult(name=self.name, passed=self.passed, failed=self.failed)

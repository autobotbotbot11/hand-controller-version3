from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import subprocess
import sys
from typing import Any


@dataclass(slots=True, frozen=True)
class CameraSource:
    label: str
    index: int
    device_name: str | None = None


def _backend_candidates(cv2: Any) -> list[int | None]:
    candidates: list[int | None] = []
    if sys.platform == "win32":
        # Prefer DirectShow first on Windows. It opens much faster on this repo's
        # target hardware and still falls back cleanly if unavailable.
        for attr in ("CAP_DSHOW", "CAP_MSMF"):
            value = getattr(cv2, attr, None)
            if isinstance(value, int) and value not in candidates:
                candidates.append(value)
    if None not in candidates:
        candidates.append(None)
    return candidates


def _open_capture(
    cv2: Any,
    *,
    index: int,
    width: int,
    height: int,
) -> tuple[Any | None, int | None]:
    for backend in _backend_candidates(cv2):
        cap = None
        try:
            cap = cv2.VideoCapture(index) if backend is None else cv2.VideoCapture(index, backend)
            if cap is not None and cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                return cap, backend
        except Exception:
            pass
        finally:
            if cap is not None and not cap.isOpened():
                try:
                    cap.release()
                except Exception:
                    pass
    return None, None


@contextmanager
def _quiet_cv_logging(cv2: Any):
    get_level = getattr(cv2, "getLogLevel", None)
    set_level = getattr(cv2, "setLogLevel", None)
    if not callable(get_level) or not callable(set_level):
        yield
        return

    previous = None
    try:
        previous = get_level()
        set_level(0)
    except Exception:
        previous = None

    try:
        yield
    finally:
        if previous is not None:
            try:
                set_level(previous)
            except Exception:
                pass


def _windows_camera_names() -> list[str]:
    if sys.platform != "win32":
        return []

    commands = [
        (
            "$ErrorActionPreference='Stop';"
            "$names = Get-PnpDevice -Class Camera,Image | "
            "Where-Object { $_.Status -eq 'OK' -and $_.FriendlyName } | "
            "Select-Object -ExpandProperty FriendlyName;"
            "$names | ConvertTo-Json -Compress"
        ),
        (
            "$ErrorActionPreference='Stop';"
            "$names = Get-CimInstance Win32_PnPEntity | "
            "Where-Object { ($_.PNPClass -eq 'Camera' -or $_.PNPClass -eq 'Image') -and $_.Status -eq 'OK' -and $_.Name } | "
            "Select-Object -ExpandProperty Name;"
            "$names | ConvertTo-Json -Compress"
        ),
    ]
    for script in commands:
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                timeout=4,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            continue
        if result.returncode != 0 or not result.stdout.strip():
            continue
        try:
            data = json.loads(result.stdout.strip())
        except Exception:
            data = result.stdout.strip()
        if isinstance(data, str):
            names = [data]
        elif isinstance(data, list):
            names = [str(item).strip() for item in data if str(item).strip()]
        else:
            names = []
        if names:
            return names
    return []


def _label_camera_sources(indices: list[int], *, device_names: list[str]) -> list[CameraSource]:
    labeled: list[CameraSource] = []
    for order, index in enumerate(indices):
        device_name = device_names[order] if order < len(device_names) else None
        if device_name:
            suffix = " (Default)" if index == 0 else f" (Index {index})"
            label = f"{device_name}{suffix}"
        else:
            label = "Default Webcam (Index 0)" if index == 0 else f"Camera {index} (Index {index})"
        labeled.append(CameraSource(label=label, index=index, device_name=device_name))
    return labeled


def detect_available_cameras(
    *,
    max_index: int = 5,
    width: int = 640,
    height: int = 480,
    include_placeholder: bool = True,
) -> list[CameraSource]:
    try:
        import cv2
    except ModuleNotFoundError:
        return [CameraSource(label="Default Webcam (Index 0)", index=0)] if include_placeholder else []

    detected_indices: list[int] = []
    with _quiet_cv_logging(cv2):
        for index in range(max_index):
            cap, _ = _open_capture(cv2, index=index, width=width, height=height)
            if cap is None:
                continue
            try:
                detected_indices.append(index)
            finally:
                try:
                    cap.release()
                except Exception:
                    pass
    if not detected_indices:
        return [CameraSource(label="Default Webcam (Index 0)", index=0)] if include_placeholder else []
    return _label_camera_sources(detected_indices, device_names=_windows_camera_names())



def probe_camera_index(*, index: int, width: int = 640, height: int = 480) -> bool:
    try:
        import cv2
    except ModuleNotFoundError:
        return False

    with _quiet_cv_logging(cv2):
        cap, _ = _open_capture(cv2, index=index, width=width, height=height)
    if cap is None:
        return False
    try:
        return True
    finally:
        try:
            cap.release()
        except Exception:
            pass


class Camera:
    """Small OpenCV camera wrapper with explicit lifecycle control."""

    def __init__(self, index: int = 0, width: int = 640, height: int = 480):
        import cv2

        self.index = index
        self.width = width
        self.height = height
        self._cv2 = cv2
        self.cap, self.backend = _open_capture(
            cv2,
            index=self.index,
            width=self.width,
            height=self.height,
        )

    def read(self):
        if self.cap is None:
            return False, None
        return self.cap.read()

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def is_opened(self) -> bool:
        return bool(self.cap is not None and self.cap.isOpened())

    def __enter__(self) -> "Camera":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

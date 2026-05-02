from __future__ import annotations

import importlib
import json
from pathlib import Path

from ..config.settings import AppConfig, REPO_ROOT, RUNTIME_BUNDLE_ROOT
from ..ml import MLPredictor


def _check_import(module_name: str) -> tuple[bool, str]:
    try:
        importlib.import_module(module_name)
        return True, "ok"
    except Exception as exc:  # pragma: no cover - diagnostic path
        return False, f"{type(exc).__name__}: {exc}"


def _format_status(name: str, ok: bool, detail: str) -> str:
    return f"{name}={'ok' if ok else 'fail'} | {detail}"


def run_validation(config: AppConfig) -> None:
    repo_root = REPO_ROOT
    local_artifacts_dir = RUNTIME_BUNDLE_ROOT / "artifacts"

    lines: list[str] = [
        "Hand Controller Rewrite Validation",
        f"repo_root={repo_root}",
        f"runtime_bundle_root={RUNTIME_BUNDLE_ROOT}",
        f"tuning={config.tuning_path or 'defaults'}",
        f"local_artifacts_dir={local_artifacts_dir}",
    ]

    expected_artifacts = (
        local_artifacts_dir / "validator_scaler.joblib",
        local_artifacts_dir / "validator_label_encoder.joblib",
        local_artifacts_dir / "validator_MLP.joblib",
        local_artifacts_dir / "validator_model_meta.json",
    )
    for artifact_path in expected_artifacts:
        exists = artifact_path.exists()
        detail = str(artifact_path)
        if exists:
            detail += f" | size={artifact_path.stat().st_size}"
        lines.append(_format_status(f"artifact:{artifact_path.name}", exists, detail))

    for module_name in ("mediapipe", "joblib", "sklearn", "PyQt5", "pyautogui"):
        ok, detail = _check_import(module_name)
        lines.append(_format_status(f"import:{module_name}", ok, detail))

    predictor, reason = MLPredictor.try_create(config.ml)
    if predictor is None:
        lines.append(_format_status("ml_predictor", False, reason or "unknown failure"))
    else:
        scaler_path = str(Path(predictor.scaler_path).resolve()) if predictor.scaler_path is not None else "missing"
        encoder_path = str(Path(predictor.encoder_path).resolve()) if predictor.encoder_path is not None else "missing"
        model_path = str(Path(predictor.model_path).resolve()) if predictor.model_path is not None else "missing"
        local_base = str(local_artifacts_dir.resolve())
        local_only = all(path.startswith(local_base) for path in (scaler_path, encoder_path, model_path))
        lines.append(_format_status("ml_predictor", True, "loaded"))
        lines.append(f"ml_scaler_path={scaler_path}")
        lines.append(f"ml_label_encoder_path={encoder_path}")
        lines.append(f"ml_model_path={model_path}")
        lines.append(f"ml_uses_local_artifacts={local_only}")

    meta_path = local_artifacts_dir / "validator_model_meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
            labels = meta.get("labels")
            if isinstance(labels, list):
                lines.append(f"ml_meta_labels={', '.join(str(label) for label in labels)}")
            sklearn_version = meta.get("sklearn_version")
            if sklearn_version:
                lines.append(f"ml_meta_sklearn_version={sklearn_version}")
        except Exception as exc:  # pragma: no cover - diagnostic path
            lines.append(_format_status("artifact:validator_model_meta.json", False, f"parse error: {exc}"))

    lines.append("camera_probe=skipped")
    lines.append("ui_live_runtime=use `python -m hand_controller --ui-live --tuning .\\tuning.local.json` for end-to-end UI validation")
    print("\n".join(lines))

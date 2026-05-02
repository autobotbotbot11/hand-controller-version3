from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config.settings import MLConfig
from ..vision.models import DetectedHand
from .geo18 import extract_geo18
from .labels import ACTIVE_ACTION_LABELS, IGNORED_BEHAVIOR_LABELS, ML_LABEL_IDLE, canonicalize_label


@dataclass(frozen=True, slots=True)
class MLPrediction:
    raw_label: str = ML_LABEL_IDLE
    label: str = ML_LABEL_IDLE
    p1: float | None = None
    margin: float | None = None
    available: bool = False
    reason: str | None = None


def _resolve_artifact(primary: str, fallback: str) -> Path | None:
    primary_path = Path(primary).expanduser().resolve()
    if primary_path.exists():
        return primary_path

    fallback_path = Path(fallback).expanduser().resolve()
    if fallback_path.exists():
        return fallback_path
    return None


class MLPredictor:
    def __init__(self, config: MLConfig) -> None:
        self.config = config
        self.scaler_path = _resolve_artifact(config.scaler_path, config.fallback_scaler_path)
        self.encoder_path = _resolve_artifact(config.label_encoder_path, config.fallback_label_encoder_path)
        self.model_path = _resolve_artifact(config.model_path, config.fallback_model_path)

        missing = []
        if self.scaler_path is None:
            missing.append("scaler")
        if self.encoder_path is None:
            missing.append("label_encoder")
        if self.model_path is None:
            missing.append("model")
        if missing:
            names = ", ".join(missing)
            raise FileNotFoundError(f"Missing ML artifacts: {names}")

        try:
            import joblib
            import numpy as np
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "ML dependencies are missing. Install requirements.txt before using Phase 6."
            ) from exc

        self._np = np
        self.scaler = joblib.load(self.scaler_path)
        self.label_encoder = joblib.load(self.encoder_path)
        self.model = joblib.load(self.model_path)

    @classmethod
    def try_create(cls, config: MLConfig) -> tuple["MLPredictor | None", str | None]:
        if not config.enabled:
            return None, "ML disabled in config"
        try:
            return cls(config), None
        except Exception as exc:  # pragma: no cover - soft-fail path
            return None, str(exc)

    def _top1_margin(self, probs) -> tuple[int, float, float]:
        order = self._np.argsort(probs)[::-1]
        top = int(order[0])
        p1 = float(probs[top])
        p2 = float(probs[order[1]]) if len(order) > 1 else 0.0
        return top, p1, (p1 - p2)

    def _filter_label(self, raw_label: str, p1: float, margin: float) -> str:
        canonical = canonicalize_label(raw_label)
        if canonical in IGNORED_BEHAVIOR_LABELS:
            return ML_LABEL_IDLE
        if canonical not in ACTIVE_ACTION_LABELS:
            return ML_LABEL_IDLE
        if canonical == ML_LABEL_IDLE:
            return ML_LABEL_IDLE
        if p1 < self.config.gate_min_p1 or margin < self.config.gate_min_margin:
            return ML_LABEL_IDLE
        return canonical

    def predict(self, hand: DetectedHand | None) -> MLPrediction:
        if hand is None:
            return MLPrediction(available=True)

        features = extract_geo18(hand)
        scaled = self.scaler.transform([features])
        probs = self.model.predict_proba(scaled)[0]
        top_index, p1, margin = self._top1_margin(probs)
        raw_label = str(self.label_encoder.inverse_transform([top_index])[0])
        filtered_label = self._filter_label(raw_label, p1, margin)
        return MLPrediction(
            raw_label=canonicalize_label(raw_label),
            label=filtered_label,
            p1=p1,
            margin=margin,
            available=True,
            reason=None,
        )

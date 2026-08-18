"""Training-matched realtime pose feature extraction.

MediaPipe emits normalized coordinates, while the training pipeline engineered
features in pixel space. Callers must therefore provide the decoded frame width
and height. One ``RealtimeFeatureExtractor`` must be used per user session.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


WINDOW_SIZE = 30
WINDOW_STEP = 15
# Webcam landmarks are noisier than the training videos. These values still
# reject badly cropped poses, while tolerating short confidence dips.
MIN_VIS_MEAN = 0.40
MIN_VALID_RATIO = 0.50
SMOOTH_W = 5
MAX_HISTORY_FRAMES = 120

LM = {
    "NOSE": 0,
    "LEFT_SHOULDER": 11,
    "RIGHT_SHOULDER": 12,
    "LEFT_ELBOW": 13,
    "RIGHT_ELBOW": 14,
    "LEFT_WRIST": 15,
    "RIGHT_WRIST": 16,
    "LEFT_HIP": 23,
    "RIGHT_HIP": 24,
    "LEFT_KNEE": 25,
    "RIGHT_KNEE": 26,
    "LEFT_ANKLE": 27,
    "RIGHT_ANKLE": 28,
}

WINDOW_SIGNALS = [
    "shoulder_abd_deg",
    "elbow_L_deg",
    "elbow_R_deg",
    "knee_L_deg",
    "knee_R_deg",
    "hip_L_deg",
    "hip_R_deg",
    "hip_abd_deg",
    "trunk_lean_deg",
    "elbow_sym_deg",
    "knee_sym_deg",
    "hip_sym_deg",
    "shoulder_abd_sym_deg",
    "hip_abd_sym_deg",
    "left_knee_in_norm",
    "right_knee_in_norm",
    "wrist_y_norm",
    "hip_y_norm",
    "knee_y_norm",
    "forearm_L_norm",
    "forearm_R_norm",
    "hk_ratio_L",
    "hk_ratio_R",
    "torso_len_norm",
]

JERK_SIGNALS = {
    "knee_L_deg",
    "knee_R_deg",
    "hip_L_deg",
    "hip_R_deg",
    "shoulder_abd_deg",
    "elbow_L_deg",
    "elbow_R_deg",
}

ENGINEERED_FEATURES = [
    "knee_mean_deg",
    "hip_mean_deg",
    "elbow_mean_deg",
    "depth_proxy_mean",
    "lean_proxy_mean",
]


def _full_feature_names() -> List[str]:
    names: List[str] = []
    for signal in WINDOW_SIGNALS:
        names.extend(f"{signal}_{stat}" for stat in ("mean", "min", "max", "std", "range"))
        if signal in JERK_SIGNALS:
            names.append(f"{signal}_jerk")
    names.extend(ENGINEERED_FEATURES)
    return names


FULL_WINDOW_FEATURE_NAMES = _full_feature_names()


def angle_3pts(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Return angle ABC in degrees."""
    ba = a - b
    bc = c - b
    denominator = (np.linalg.norm(ba) * np.linalg.norm(bc)) + 1e-8
    cosine = float(np.dot(ba, bc) / denominator)
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


def calculate_angle(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> float:
    """Backward-compatible angle helper used by the rep counter in main.py."""
    return angle_3pts(
        np.asarray(a, dtype=np.float64),
        np.asarray(b, dtype=np.float64),
        np.asarray(c, dtype=np.float64),
    )


def angle_between(v1: np.ndarray, v2: np.ndarray) -> float:
    denominator = (np.linalg.norm(v1) * np.linalg.norm(v2)) + 1e-8
    cosine = float(np.dot(v1, v2) / denominator)
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


def dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def moving_average(values: np.ndarray, window: int = SMOOTH_W) -> np.ndarray:
    if window <= 1:
        return values
    padding = window // 2
    padded = np.pad(values, (padding, padding), mode="edge")
    return np.convolve(padded, np.ones(window, dtype=np.float64) / window, mode="valid")


def safe_stats(values: np.ndarray) -> Dict[str, float]:
    values = np.asarray(values, dtype=np.float64)
    if values.size == 0 or np.all(np.isnan(values)):
        return {name: np.nan for name in ("mean", "min", "max", "std", "range")}
    minimum = float(np.nanmin(values))
    maximum = float(np.nanmax(values))
    return {
        "mean": float(np.nanmean(values)),
        "min": minimum,
        "max": maximum,
        "std": float(np.nanstd(values)),
        "range": maximum - minimum,
    }


def jerkiness(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=np.float64)
    if len(values) < 5 or np.any(np.isnan(values)):
        values = pd.Series(values).interpolate(limit_direction="both").to_numpy(dtype=np.float64)
    acceleration = np.diff(np.diff(values))
    return float(np.mean(np.abs(acceleration))) if len(acceleration) else np.nan


def _value(landmark: Any, field: str, default: float = 0.0) -> float:
    raw = landmark.get(field, default) if isinstance(landmark, Mapping) else getattr(landmark, field, default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def landmarks_to_pixel_arrays(
    landmarks: Sequence[Any], frame_width: int, frame_height: int
) -> Tuple[np.ndarray, np.ndarray]:
    if landmarks is None or len(landmarks) < 33:
        raise ValueError("Expected at least 33 MediaPipe pose landmarks")
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError("Frame width and height must be positive")
    points = np.asarray(
        [[_value(item, "x") * frame_width, _value(item, "y") * frame_height] for item in landmarks[:33]],
        dtype=np.float32,
    )
    visibility = np.asarray([_value(item, "visibility", 1.0) for item in landmarks[:33]], dtype=np.float32)
    return points, visibility


def compute_frame_features(points: np.ndarray, visibility: np.ndarray) -> Dict[str, float]:
    key_indices = [LM[name] for name in (
        "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW",
        "LEFT_WRIST", "RIGHT_WRIST", "LEFT_HIP", "RIGHT_HIP",
        "LEFT_KNEE", "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE",
    )]
    if float(np.nanmean(visibility[key_indices])) < MIN_VIS_MEAN:
        return {"valid": 0.0}

    ls, rs = points[LM["LEFT_SHOULDER"]], points[LM["RIGHT_SHOULDER"]]
    le, re = points[LM["LEFT_ELBOW"]], points[LM["RIGHT_ELBOW"]]
    lw, rw = points[LM["LEFT_WRIST"]], points[LM["RIGHT_WRIST"]]
    lh, rh = points[LM["LEFT_HIP"]], points[LM["RIGHT_HIP"]]
    lk, rk = points[LM["LEFT_KNEE"]], points[LM["RIGHT_KNEE"]]
    la, ra = points[LM["LEFT_ANKLE"]], points[LM["RIGHT_ANKLE"]]
    nose = points[LM["NOSE"]]

    mid_shoulder = (ls + rs) / 2.0
    mid_hip = (lh + rh) / 2.0
    mid_knee = (lk + rk) / 2.0
    shoulder_width = dist(ls, rs) + 1e-8

    left_elbow, right_elbow = angle_3pts(ls, le, lw), angle_3pts(rs, re, rw)
    left_knee, right_knee = angle_3pts(lh, lk, la), angle_3pts(rh, rk, ra)
    left_hip, right_hip = angle_3pts(ls, lh, lk), angle_3pts(rs, rh, rk)
    trunk_left, trunk_right = ls - lh, rs - rh
    shoulder_left = angle_between(trunk_left, le - ls)
    shoulder_right = angle_between(trunk_right, re - rs)
    hip_left = angle_between(trunk_left, lk - lh)
    hip_right = angle_between(trunk_right, rk - rh)

    return {
        "valid": 1.0,
        "shoulder_abd_deg": (shoulder_left + shoulder_right) / 2.0,
        "elbow_L_deg": left_elbow,
        "elbow_R_deg": right_elbow,
        "knee_L_deg": left_knee,
        "knee_R_deg": right_knee,
        "hip_L_deg": left_hip,
        "hip_R_deg": right_hip,
        "hip_abd_deg": (hip_left + hip_right) / 2.0,
        "trunk_lean_deg": angle_3pts(nose, mid_hip, mid_knee),
        "elbow_sym_deg": abs(left_elbow - right_elbow),
        "knee_sym_deg": abs(left_knee - right_knee),
        "hip_sym_deg": abs(left_hip - right_hip),
        "shoulder_abd_sym_deg": abs(shoulder_left - shoulder_right),
        "hip_abd_sym_deg": abs(hip_left - hip_right),
        "left_knee_in_norm": float((lk[0] - la[0]) / shoulder_width),
        "right_knee_in_norm": float((rk[0] - ra[0]) / shoulder_width),
        "wrist_y_norm": float(((lw[1] + rw[1]) / 2.0 - mid_shoulder[1]) / shoulder_width),
        "hip_y_norm": float((mid_hip[1] - mid_shoulder[1]) / shoulder_width),
        "knee_y_norm": float((mid_knee[1] - mid_shoulder[1]) / shoulder_width),
        "forearm_L_norm": dist(le, lw) / shoulder_width,
        "forearm_R_norm": dist(re, rw) / shoulder_width,
        "hk_ratio_L": (dist(lh, lk) / shoulder_width) / ((dist(lk, la) / shoulder_width) + 1e-8),
        "hk_ratio_R": (dist(rh, rk) / shoulder_width) / ((dist(rk, ra) / shoulder_width) + 1e-8),
        "torso_len_norm": dist(mid_shoulder, mid_hip) / shoulder_width,
    }


def extract_frame_features_from_landmarks(
    landmarks: Sequence[Any], frame_width: int, frame_height: int
) -> Dict[str, float]:
    points, visibility = landmarks_to_pixel_arrays(landmarks, frame_width, frame_height)
    return compute_frame_features(points, visibility)


def smooth_history(raw: pd.DataFrame) -> pd.DataFrame:
    smoothed = raw.copy()
    for column in WINDOW_SIGNALS:
        if column not in smoothed:
            smoothed[column] = np.nan
        values = pd.to_numeric(smoothed[column], errors="coerce").to_numpy(dtype=np.float64)
        values = pd.Series(values).interpolate(limit_direction="both").to_numpy(dtype=np.float64)
        smoothed[column] = values if np.all(np.isnan(values)) else moving_average(values)
    return smoothed


def build_window_feature_dict(smoothed: pd.DataFrame) -> Optional[Dict[str, float]]:
    if smoothed.empty or "valid" not in smoothed:
        return None
    valid = smoothed[smoothed["valid"] >= 1.0].reset_index(drop=True)
    if len(valid) < WINDOW_SIZE:
        return None
    chunk = valid.iloc[-WINDOW_SIZE:]
    row: Dict[str, float] = {}
    for signal in WINDOW_SIGNALS:
        values = chunk[signal].to_numpy(dtype=np.float64)
        stats = safe_stats(values)
        for name, value in stats.items():
            row[f"{signal}_{name}"] = value
        if signal in JERK_SIGNALS:
            row[f"{signal}_jerk"] = jerkiness(values)

    row["knee_mean_deg"] = float((chunk["knee_L_deg"].mean() + chunk["knee_R_deg"].mean()) / 2.0)
    row["hip_mean_deg"] = float((chunk["hip_L_deg"].mean() + chunk["hip_R_deg"].mean()) / 2.0)
    row["elbow_mean_deg"] = float((chunk["elbow_L_deg"].mean() + chunk["elbow_R_deg"].mean()) / 2.0)
    row["depth_proxy_mean"] = float(chunk["knee_y_norm"].mean())
    row["lean_proxy_mean"] = float(180.0 - chunk["trunk_lean_deg"].mean())
    return row if np.all(np.isfinite(np.asarray(list(row.values()), dtype=np.float64))) else None


class RealtimeFeatureExtractor:
    """Produce one training-matched feature row every 15 valid frames."""

    def __init__(self, max_history_frames: int = MAX_HISTORY_FRAMES) -> None:
        self.history: Deque[Dict[str, float]] = deque(maxlen=max_history_frames)
        self.frame_index = 0
        self.valid_frames_seen = 0
        self.valid_frames_at_last_output = 0
        self.last_frame_valid = False

    def reset(self) -> None:
        self.history.clear()
        self.frame_index = 0
        self.valid_frames_seen = 0
        self.valid_frames_at_last_output = 0
        self.last_frame_valid = False

    def add(
        self, landmarks: Optional[Sequence[Any]], frame_width: int, frame_height: int
    ) -> Optional[Dict[str, float]]:
        self.frame_index += 1
        if landmarks is None or len(landmarks) < 33:
            self.last_frame_valid = False
            self.history.append({"valid": 0.0, "frame": float(self.frame_index)})
            return None

        features = extract_frame_features_from_landmarks(landmarks, frame_width, frame_height)
        features["frame"] = float(self.frame_index)
        self.history.append(features)
        self.last_frame_valid = features.get("valid", 0.0) >= 1.0
        if not self.last_frame_valid:
            return None

        self.valid_frames_seen += 1
        if self.valid_frames_seen < WINDOW_SIZE:
            return None
        if self.valid_frames_at_last_output and (
            self.valid_frames_seen - self.valid_frames_at_last_output < WINDOW_STEP
        ):
            return None

        raw = pd.DataFrame(list(self.history))
        recent = raw.tail(max(WINDOW_SIZE, 50))
        if float(recent["valid"].fillna(0.0).mean()) < MIN_VALID_RATIO:
            return None

        row = build_window_feature_dict(smooth_history(raw))
        if row is not None:
            self.valid_frames_at_last_output = self.valid_frames_seen
        return row

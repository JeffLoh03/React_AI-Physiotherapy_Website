import json
import base64
import cv2
import numpy as np
import pandas as pd
import mediapipe as mp
import time

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import joblib
from collections import deque, Counter
from typing import Deque, Dict, List, Optional, Tuple
from pydantic import BaseModel

from pose_features import FULL_WINDOW_FEATURE_NAMES, RealtimeFeatureExtractor, calculate_angle
from session_manager import SessionManager
from auth import create_access_token, decode_access_token, get_current_user, require_role
from database import (
    init_db, create_user, authenticate_user, get_user_profile,
    save_session, get_user_sessions, search_patient_by_username,
    get_patient_analytics, create_care_relationship, remove_care_relationship,
    is_doctor_for_patient,
    get_doctor_patients, create_plan_assignment, get_assignment,
    get_patient_assignments, update_assignment_status
)

app = FastAPI()

# Enable CORS
cors_origins = [origin.strip() for origin in os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
).split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
init_db()

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, "models", "pose_landmarker_lite.task")
CLASSIFIER_PATH = os.path.join(BASE_DIR, "models", "exercise_classifier_best.pkl")
FEATURE_ORDER_PATH = os.path.join(BASE_DIR, "models", "feature_order.json")
EX_NAMES_PATH = os.path.join(BASE_DIR, "models", "exercise_names.json")

# ----------------------------
# Globals
# ----------------------------
landmarker = None
classifier = None
feature_order: Optional[List[str]] = None
ex_names: Dict[str, str] = {}
rehabilitation_plans = {}

# ----------------------------
# Realtime config
# ----------------------------
WINDOW_SIZE = 30
WINDOW_STEP = 15

PRED_BUFFER = 8
VOTE_DOMINANCE = 0.60
MIN_VALID_VOTES = 3

CONF_THRESHOLD = 0.30
MARGIN_THRESHOLD = 0.08

USE_EXERCISE_LOCK = True
LOCK_SECONDS = 2.5
LOCK_MIN_CONF = 0.35

REP_COOLDOWN = 0.8
ANGLE_SMOOTH_W = 3
PHASE_CONFIRM_FRAMES = 2
FEEDBACK_CHANGE_INTERVAL = 1.5
NO_POSE_CONFIRM_FRAMES = 5

USE_MOVEMENT_GATE = True
MOVE_STD_THRESHOLD = 0.8
MOVE_SIGNAL = "knee_mean_deg"

# ----------------------------
# Motion Speed Detection
# ----------------------------
USE_SPEED_DETECTION = True
SPEED_SLOW_THRESHOLD = 30.0  # degrees per second - warning
SPEED_FAST_THRESHOLD = 50.0  # degrees per second - critical
SPEED_CHECK_WINDOW = 0.1  # seconds between speed checks

SIGNALS = [
    "shoulder_abd_deg",
    "elbow_L_deg", "elbow_R_deg",
    "knee_L_deg", "knee_R_deg",
    "hip_L_deg", "hip_R_deg",
    "hip_abd_deg",
    "trunk_lean_deg",
    "elbow_sym_deg", "knee_sym_deg", "hip_sym_deg",
    "shoulder_abd_sym_deg", "hip_abd_sym_deg",
    "left_knee_in_norm", "right_knee_in_norm",
    "wrist_y_norm", "hip_y_norm", "knee_y_norm",
    "forearm_L_norm", "forearm_R_norm",
    "hk_ratio_L", "hk_ratio_R",
    "torso_len_norm",
]

JERK_SIGNALS = {
    "knee_L_deg", "knee_R_deg", "hip_L_deg", "hip_R_deg",
    "shoulder_abd_deg", "elbow_L_deg", "elbow_R_deg",
}

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

# ----------------------------
# Pydantic Models
# ----------------------------
class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str  # "patient" or "doctor"
    doctor_invite_code: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    success: bool
    user_id: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None
    access_token: Optional[str] = None
    message: str

class PlanAssignmentRequest(BaseModel):
    patient_id: str
    plan_id: str
    notes: str = ""
    start_date: Optional[str] = None

class AssignmentStatusRequest(BaseModel):
    status: str

class UserProfileResponse(BaseModel):
    user_id: str
    username: str
    role: str
    total_xp: int
    current_streak: int
    total_sessions: int
    best_form_quality: float
    last_session_date: Optional[str]

# ----------------------------
# MediaPipe setup
# ----------------------------
BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = mp.tasks.vision.PoseLandmarker
PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode


# ----------------------------
# Geometry helpers
# ----------------------------
def _angle_3pts(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    ba = a - b
    bc = c - b
    denom = (np.linalg.norm(ba) * np.linalg.norm(bc)) + 1e-8
    cosv = float(np.dot(ba, bc) / denom)
    return float(np.degrees(np.arccos(np.clip(cosv, -1.0, 1.0))))


def _angle_between(v1: np.ndarray, v2: np.ndarray) -> float:
    denom = (np.linalg.norm(v1) * np.linalg.norm(v2)) + 1e-8
    cosv = float(np.dot(v1, v2) / denom)
    return float(np.degrees(np.arccos(np.clip(cosv, -1.0, 1.0))))


def _dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def _safe_stats(arr: np.ndarray) -> Dict[str, float]:
    arr = np.asarray(arr, dtype=np.float64)
    if arr.size == 0 or np.all(np.isnan(arr)):
        return {"mean": np.nan, "min": np.nan, "max": np.nan, "std": np.nan, "range": np.nan}
    mn = float(np.nanmean(arr))
    mi = float(np.nanmin(arr))
    ma = float(np.nanmax(arr))
    sd = float(np.nanstd(arr))
    return {"mean": mn, "min": mi, "max": ma, "std": sd, "range": ma - mi}


def _jerkiness(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=np.float64)
    if len(x) < 5:
        return float("nan")
    v = np.diff(x)
    a = np.diff(v)
    if len(a) == 0:
        return float("nan")
    return float(np.mean(np.abs(a)))


# ----------------------------
# Frame features
# ----------------------------
def compute_frame_features_from_landmarks(landmarks) -> Dict[str, float]:
    pts = np.array([[p.x, p.y] for p in landmarks], dtype=np.float32)
    vis = np.array([float(getattr(p, "visibility", 1.0)) for p in landmarks], dtype=np.float32)

    key_idx = [
        LM["LEFT_SHOULDER"], LM["RIGHT_SHOULDER"],
        LM["LEFT_ELBOW"], LM["RIGHT_ELBOW"],
        LM["LEFT_WRIST"], LM["RIGHT_WRIST"],
        LM["LEFT_HIP"], LM["RIGHT_HIP"],
        LM["LEFT_KNEE"], LM["RIGHT_KNEE"],
        LM["LEFT_ANKLE"], LM["RIGHT_ANKLE"],
    ]

    if float(np.nanmean(vis[key_idx])) < 0.3:
        return {"valid": 0.0}

    LS, RS = pts[LM["LEFT_SHOULDER"]], pts[LM["RIGHT_SHOULDER"]]
    LE, RE = pts[LM["LEFT_ELBOW"]], pts[LM["RIGHT_ELBOW"]]
    LW, RW = pts[LM["LEFT_WRIST"]], pts[LM["RIGHT_WRIST"]]
    LH, RH = pts[LM["LEFT_HIP"]], pts[LM["RIGHT_HIP"]]
    LK, RK = pts[LM["LEFT_KNEE"]], pts[LM["RIGHT_KNEE"]]
    LA, RA = pts[LM["LEFT_ANKLE"]], pts[LM["RIGHT_ANKLE"]]
    NOSE = pts[LM["NOSE"]]

    mid_sh = (LS + RS) / 2.0
    mid_hip = (LH + RH) / 2.0
    mid_knee = (LK + RK) / 2.0
    mid_ank = (LA + RA) / 2.0

    left_elbow = _angle_3pts(LS, LE, LW)
    right_elbow = _angle_3pts(RS, RE, RW)
    left_knee = _angle_3pts(LH, LK, LA)
    right_knee = _angle_3pts(RH, RK, RA)
    left_hip = _angle_3pts(LS, LH, LK)
    right_hip = _angle_3pts(RS, RH, RK)

    trunk_L = LS - LH
    arm_L = LE - LS
    trunk_R = RS - RH
    arm_R = RE - RS

    shoulder_abd_L = _angle_between(trunk_L, arm_L)
    shoulder_abd_R = _angle_between(trunk_R, arm_R)
    shoulder_abd = (shoulder_abd_L + shoulder_abd_R) / 2.0

    thigh_L = LK - LH
    thigh_R = RK - RH
    hip_abd_L = _angle_between(trunk_L, thigh_L)
    hip_abd_R = _angle_between(trunk_R, thigh_R)
    hip_abd = (hip_abd_L + hip_abd_R) / 2.0

    trunk_lean = _angle_3pts(NOSE, mid_hip, mid_knee)

    sh_w = _dist(LS, RS) + 1e-8

    return {
        "valid": 1.0,
        "shoulder_abd_deg": shoulder_abd,
        "elbow_L_deg": left_elbow,
        "elbow_R_deg": right_elbow,
        "knee_L_deg": left_knee,
        "knee_R_deg": right_knee,
        "hip_L_deg": left_hip,
        "hip_R_deg": right_hip,
        "hip_abd_deg": hip_abd,
        "trunk_lean_deg": trunk_lean,

        "elbow_sym_deg": abs(left_elbow - right_elbow),
        "knee_sym_deg": abs(left_knee - right_knee),
        "hip_sym_deg": abs(left_hip - right_hip),
        "shoulder_abd_sym_deg": abs(shoulder_abd_L - shoulder_abd_R),
        "hip_abd_sym_deg": abs(hip_abd_L - hip_abd_R),

        "left_knee_in_norm": float((LK[0] - LA[0]) / sh_w),
        "right_knee_in_norm": float((RK[0] - RA[0]) / sh_w),
        "wrist_y_norm": float(((LW[1] + RW[1]) / 2.0 - mid_sh[1]) / sh_w),
        "hip_y_norm": float((mid_hip[1] - mid_sh[1]) / sh_w),
        "knee_y_norm": float((mid_knee[1] - mid_sh[1]) / sh_w),
        "ank_y_norm": float((mid_ank[1] - mid_sh[1]) / sh_w),

        "forearm_L_norm": _dist(LE, LW) / sh_w,
        "forearm_R_norm": _dist(RE, RW) / sh_w,
        "hk_ratio_L": (_dist(LH, LK) / sh_w) / ((_dist(LK, LA) / sh_w) + 1e-8),
        "hk_ratio_R": (_dist(RH, RK) / sh_w) / ((_dist(RK, RA) / sh_w) + 1e-8),
        "torso_len_norm": _dist(mid_sh, mid_hip) / sh_w,
    }


# ----------------------------
# Window vector
# ----------------------------
def build_window_vector(frame_feats: List[Dict[str, float]], order: List[str]) -> np.ndarray:
    row: Dict[str, float] = {}

    for s in SIGNALS:
        arr = np.array([f.get(s, np.nan) for f in frame_feats], dtype=np.float64)
        st = _safe_stats(arr)
        row[f"{s}_mean"] = st["mean"]
        row[f"{s}_min"] = st["min"]
        row[f"{s}_max"] = st["max"]
        row[f"{s}_std"] = st["std"]
        row[f"{s}_range"] = st["range"]

        if s in JERK_SIGNALS:
            row[f"{s}_jerk"] = _jerkiness(arr)

    row["knee_mean_deg"] = float((row.get("knee_L_deg_mean", np.nan) + row.get("knee_R_deg_mean", np.nan)) / 2.0)
    row["hip_mean_deg"] = float((row.get("hip_L_deg_mean", np.nan) + row.get("hip_R_deg_mean", np.nan)) / 2.0)
    row["elbow_mean_deg"] = float((row.get("elbow_L_deg_mean", np.nan) + row.get("elbow_R_deg_mean", np.nan)) / 2.0)
    row["depth_proxy_mean"] = float(row.get("knee_y_norm_mean", np.nan))
    row["lean_proxy_mean"] = float(180.0 - row.get("trunk_lean_deg_mean", np.nan))

    vec = np.array([row.get(k, np.nan) for k in order], dtype=np.float32)
    vec = np.nan_to_num(vec, nan=0.0, posinf=0.0, neginf=0.0)
    return vec.reshape(1, -1)


# ----------------------------
# Stable voting
# ----------------------------
def stable_mode(labels: Deque[str]) -> str:
    valid = [x for x in labels if x and x != "Unknown"]
    if len(valid) < MIN_VALID_VOTES:
        return "Unknown"

    counter = Counter(valid)
    label, count = counter.most_common(1)[0]

    if (count / len(valid)) >= VOTE_DOMINANCE:
        return label

    return "Unknown"


def steady_feedback(candidate: str, state: Dict[str, object]) -> str:
    """Rate-limit instruction changes while allowing the current text to persist."""
    if not candidate:
        return ""
    now = time.time()
    current = str(state.get("text", ""))
    changed_at = float(state.get("changed_at", 0.0))
    if candidate == current:
        return candidate
    if not current or now - changed_at >= FEEDBACK_CHANGE_INTERVAL:
        state["text"] = candidate
        state["changed_at"] = now
        return candidate
    return ""


# ----------------------------
# Angle per exercise
# ----------------------------
REP_PROFILES: Dict[str, Dict[str, object]] = {
    "shoulder_abduction": {
        "min_excursion": 18.0, "target": 90.0, "tolerance": 25.0,
    },
    "shoulder_vw": {
        "min_excursion": 18.0, "target": 100.0, "tolerance": 25.0,
    },
    "inclined_pushup": {
        "min_excursion": 25.0, "target": 95.0, "tolerance": 25.0,
    },
    "hip_abduction": {
        "min_excursion": 12.0, "target": 125.0, "tolerance": 25.0,
    },
    "forward_lunge": {
        "min_excursion": 22.0, "target": 105.0, "tolerance": 25.0,
    },
    "squat": {
        "min_excursion": 22.0, "target": 105.0, "tolerance": 25.0,
    },
}


def exercise_key(display_label: str) -> str:
    label = (display_label or "").lower()
    if "hip abduction" in label:
        return "hip_abduction"
    if "v-w" in label or "vw" in label:
        return "shoulder_vw"
    if "push" in label:
        return "inclined_pushup"
    if "lunge" in label:
        return "forward_lunge"
    if "squat" in label:
        return "squat"
    return "shoulder_abduction"


EXPECTED_CLASS_BY_EXERCISE = {
    "shoulder_abduction": "Ex1",
    "shoulder_vw": "Ex2",
    "inclined_pushup": "Ex3",
    "hip_abduction": "Ex4",
    "forward_lunge": "Ex5",
    "squat": "Ex6",
}


def expected_class_for_exercise(display_label: str) -> str:
    return EXPECTED_CLASS_BY_EXERCISE[exercise_key(display_label)]


def plan_target_for_exercise(
    plan_exercises: Dict[str, Dict[str, object]], display_label: str
) -> Optional[Dict[str, object]]:
    """Match model display names and shorter plan names to the same exercise."""
    wanted_key = exercise_key(display_label)
    return next(
        (
            target
            for name, target in plan_exercises.items()
            if exercise_key(name) == wanted_key
        ),
        None,
    )


def _pixel_point(landmarks, index: int, frame_width: int, frame_height: int) -> List[float]:
    return [landmarks[index].x * frame_width, landmarks[index].y * frame_height]


def _side_angle(
    landmarks, indices: Tuple[int, int, int], frame_width: int, frame_height: int
) -> Tuple[float, float]:
    visibility = min(float(getattr(landmarks[index], "visibility", 1.0)) for index in indices)
    points = [_pixel_point(landmarks, index, frame_width, frame_height) for index in indices]
    return float(calculate_angle(points[0], points[1], points[2])), visibility


def _bilateral_metric(
    landmarks,
    left_indices: Tuple[int, int, int],
    right_indices: Tuple[int, int, int],
    frame_width: int,
    frame_height: int,
    mode: str = "average",
) -> Tuple[float, str]:
    left_angle, left_visibility = _side_angle(
        landmarks, left_indices, frame_width, frame_height
    )
    right_angle, right_visibility = _side_angle(
        landmarks, right_indices, frame_width, frame_height
    )
    visible = []
    if left_visibility >= 0.45:
        visible.append((left_angle, "left"))
    if right_visibility >= 0.45:
        visible.append((right_angle, "right"))
    if not visible:
        visible = [(left_angle, "left"), (right_angle, "right")]
    if mode == "minimum":
        return min(visible, key=lambda item: item[0])
    return float(sum(item[0] for item in visible) / len(visible)), "both" if len(visible) == 2 else visible[0][1]


def angle_for_exercise(
    display_label: str, landmarks, frame_width: int, frame_height: int
) -> Tuple[float, float, str, str]:
    """Return visibility-aware pixel-space motion angle, target, key, and measured side."""
    key = exercise_key(display_label)
    profile = REP_PROFILES[key]
    if key == "shoulder_abduction":
        angle, side = _bilateral_metric(
            landmarks, (23, 11, 13), (24, 12, 14), frame_width, frame_height
        )
    elif key in {"shoulder_vw", "inclined_pushup"}:
        angle, side = _bilateral_metric(
            landmarks, (11, 13, 15), (12, 14, 16), frame_width, frame_height
        )
    elif key == "hip_abduction":
        angle, side = _bilateral_metric(
            landmarks, (11, 23, 25), (12, 24, 26), frame_width, frame_height,
            mode="minimum",
        )
    elif key == "forward_lunge":
        angle, side = _bilateral_metric(
            landmarks, (23, 25, 27), (24, 26, 28), frame_width, frame_height,
            mode="minimum",
        )
    else:
        angle, side = _bilateral_metric(
            landmarks, (23, 25, 27), (24, 26, 28), frame_width, frame_height
        )
    return angle, float(profile["target"]), key, side


# ----------------------------
# Improved rep counter
# Counts only complete cycle:
# high -> low -> high OR low -> high -> low
# ----------------------------
def rep_update(display_label: str, angle_value: float, state: Dict[str, object]) -> Tuple[int, Optional[str]]:
    key = exercise_key(display_label)
    profile = REP_PROFILES[key]
    # Smooth angle
    buf = state.setdefault("angle_buffer", [])
    buf.append(float(angle_value))

    if len(buf) > ANGLE_SMOOTH_W:
        buf.pop(0)

    angle_s = float(sum(buf) / len(buf))

    reps = int(state.get("reps", 0))
    last_rep_time = float(state.get("last_rep_time", 0.0))
    stage = str(state.get("stage", "waiting_start"))
    if stage == "start":
        stage = "waiting_start"

    # Motion speed detection
    last_angle = float(state.get("last_angle", angle_s))
    last_angle_time = float(state.get("last_angle_time", time.time()))
    now = time.time()
    time_delta = max(now - last_angle_time, 0.01)  # Avoid division by zero

    speed_warning = None
    if USE_SPEED_DETECTION and time_delta >= SPEED_CHECK_WINDOW:
        angular_velocity = abs(angle_s - last_angle) / time_delta
        state["angular_velocity"] = angular_velocity

        if angular_velocity > SPEED_FAST_THRESHOLD:
            speed_warning = "TOO_FAST"
        elif angular_velocity > SPEED_SLOW_THRESHOLD:
            speed_warning = "SLOW_DOWN"

        state["last_angle"] = angle_s
        state["last_angle_time"] = now

    state["speed_warning"] = speed_warning

    min_excursion = float(profile.get("min_excursion", 20.0))
    start_anchor = float(state.get("start_anchor", angle_s))
    active_anchor = float(state.get("active_anchor", angle_s))

    # Calibrate to the user's real starting pose. The first meaningful movement
    # may increase or decrease the angle, so both A -> B -> A directions work.
    start_condition = True
    delta_from_start = angle_s - start_anchor
    active_condition = abs(delta_from_start) >= min_excursion

    motion_direction = int(state.get("motion_direction", 0))
    if stage == "active" and motion_direction:
        active_anchor = (
            max(active_anchor, angle_s)
            if motion_direction > 0
            else min(active_anchor, angle_s)
        )
        state["active_anchor"] = active_anchor

    return_tolerance = max(8.0, min_excursion * 0.45)
    if motion_direction > 0:
        reversal = active_anchor - angle_s
        returned_to_start = angle_s <= start_anchor + return_tolerance
    elif motion_direction < 0:
        reversal = angle_s - active_anchor
        returned_to_start = angle_s >= start_anchor - return_tolerance
    else:
        reversal = 0.0
        returned_to_start = False
    return_condition = returned_to_start and reversal >= min_excursion * 0.65

    expected_condition = (
        start_condition if stage == "waiting_start"
        else active_condition if stage == "ready"
        else return_condition
    )
    phase_frames = int(state.get("phase_frames", 0)) + 1 if expected_condition else 0

    if phase_frames >= PHASE_CONFIRM_FRAMES:
        previous_stage = stage
        if stage == "waiting_start":
            stage = "ready"
            state["start_anchor"] = angle_s
        elif stage == "ready":
            stage = "active"
            state["active_anchor"] = angle_s
            state["motion_direction"] = 1 if delta_from_start > 0 else -1
        elif stage == "active" and now - last_rep_time >= REP_COOLDOWN:
            reps += 1
            stage = "ready"
            state["start_anchor"] = angle_s
            state["motion_direction"] = 0
            state["last_rep_time"] = now
            print(f"[REP] {display_label} count={reps} angle={angle_s:.1f}")
        phase_frames = 0
        if previous_stage != stage:
            print(f"[PHASE] {display_label} {previous_stage}->{stage} angle={angle_s:.1f}")

    state["stage"] = stage
    state["phase_frames"] = phase_frames
    state["reps"] = reps
    state["angle_smoothed"] = angle_s

    return reps, speed_warning



# ----------------------------
# Startup
# ----------------------------
@app.on_event("startup")
def startup_event():
    global landmarker, classifier, feature_order, ex_names, rehabilitation_plans

    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=VisionRunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=0.35,
        min_pose_presence_confidence=0.35,
    )

    landmarker = PoseLandmarker.create_from_options(options)
    print("SUCCESS: Loaded MediaPipe model")

    classifier = joblib.load(CLASSIFIER_PATH)
    print(f"SUCCESS: Loaded Classifier from {CLASSIFIER_PATH}")
    print("Classifier classes:", getattr(classifier, "classes_", None))

    with open(FEATURE_ORDER_PATH, "r", encoding="utf-8") as f:
        feature_order = json.load(f)

    if feature_order != FULL_WINDOW_FEATURE_NAMES:
        raise RuntimeError(
            "feature_order.json does not match the training-matched realtime extractor"
        )

    print(f"SUCCESS: Loaded feature_order.json ({len(feature_order)} features)")

    with open(EX_NAMES_PATH, "r", encoding="utf-8") as f:
        ex_names = json.load(f)

    print("SUCCESS: Loaded exercise_names.json")

    # Load rehabilitation plans
    plans_path = os.path.join(BASE_DIR, "rehabilitation_plans.json")
    try:
        with open(plans_path, "r", encoding="utf-8") as f:
            rehabilitation_plans = json.load(f)
        print(f"SUCCESS: Loaded rehabilitation plans ({len(rehabilitation_plans.get('plans', []))} plans)")
    except Exception as e:
        print(f"WARNING: Could not load rehabilitation plans: {e}")


# ----------------------------
# API Endpoints
# ----------------------------
@app.get("/api/rehabilitation-plans")
async def get_rehabilitation_plans(user: Dict[str, object] = Depends(get_current_user)):
    return rehabilitation_plans


# ----------------------------
# Authentication Endpoints
# ----------------------------
@app.post("/api/auth/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """Register a new user (patient or doctor)"""
    if request.role not in ["patient", "doctor"]:
        raise HTTPException(status_code=400, detail="Role must be 'patient' or 'doctor'")
    if len(request.username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if request.role == "doctor":
        invite_code = os.getenv("DOCTOR_INVITE_CODE")
        if not invite_code or request.doctor_invite_code != invite_code:
            raise HTTPException(status_code=403, detail="A valid clinician invite code is required")

    user_id = create_user(request.username, request.password, request.role)

    if user_id is None:
        return AuthResponse(
            success=False,
            message="Username already exists"
        )

    return AuthResponse(
        success=True,
        user_id=user_id,
        username=request.username.strip(),
        role=request.role,
        access_token=create_access_token(user_id, request.username.strip(), request.role),
        message="Registration successful"
    )


@app.post("/api/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """Login user and return user_id"""
    user_id = authenticate_user(request.username, request.password)

    if user_id is None:
        return AuthResponse(
            success=False,
            message="Invalid username or password"
        )

    profile = get_user_profile(user_id)
    return AuthResponse(
        success=True,
        user_id=user_id,
        username=profile['username'],
        role=profile['role'],
        access_token=create_access_token(user_id, profile['username'], profile['role']),
        message="Login successful"
    )


@app.get("/api/user/profile/{user_id}", response_model=UserProfileResponse)
async def get_profile(user_id: str, user: Dict[str, object] = Depends(get_current_user)):
    """Get user profile"""
    if user["sub"] != user_id:
        if user["role"] != "doctor" or not is_doctor_for_patient(str(user["sub"]), user_id):
            raise HTTPException(status_code=403, detail="You do not have access to this profile")
    profile = get_user_profile(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="User not found")
    return profile


@app.get("/api/user/sessions/{user_id}")
async def get_sessions(user_id: str, user: Dict[str, object] = Depends(get_current_user)):
    """Get user's session history"""
    if user["sub"] != user_id:
        if user["role"] != "doctor" or not is_doctor_for_patient(str(user["sub"]), user_id):
            raise HTTPException(status_code=403, detail="You do not have access to these sessions")
    sessions = get_user_sessions(user_id)
    return {"sessions": sessions, "count": len(sessions)}


@app.get("/api/doctor/search-patient/{username}")
async def doctor_search_patient(username: str, user: Dict[str, object] = Depends(get_current_user)):
    """Doctor searches for patient by username"""
    require_role(user, "doctor")
    patient = search_patient_by_username(username)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient["is_linked"] = is_doctor_for_patient(str(user["sub"]), patient["user_id"])
    return patient


@app.post("/api/doctor/patients/{patient_id}")
async def link_patient(patient_id: str, user: Dict[str, object] = Depends(get_current_user)):
    require_role(user, "doctor")
    if not create_care_relationship(str(user["sub"]), patient_id):
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"success": True}


@app.get("/api/doctor/patients")
async def list_doctor_patients(user: Dict[str, object] = Depends(get_current_user)):
    require_role(user, "doctor")
    return {"patients": get_doctor_patients(str(user["sub"]))}


@app.delete("/api/doctor/patients/{patient_id}")
async def unlink_patient(patient_id: str, user: Dict[str, object] = Depends(get_current_user)):
    require_role(user, "doctor")
    if not remove_care_relationship(str(user["sub"]), patient_id):
        raise HTTPException(status_code=404, detail="Linked patient not found")
    return {"success": True}


@app.get("/api/doctor/patient-analytics/{patient_id}")
async def get_patient_analytics_endpoint(
    patient_id: str,
    days: int = Query(default=30, ge=1, le=3650),
    user: Dict[str, object] = Depends(get_current_user),
):
    """Doctor gets patient analytics"""
    require_role(user, "doctor")
    if not is_doctor_for_patient(str(user["sub"]), patient_id):
        raise HTTPException(status_code=403, detail="Link this patient before viewing analytics")
    analytics = get_patient_analytics(patient_id, days)
    if not analytics:
        raise HTTPException(status_code=404, detail="Patient not found")
    return analytics


@app.post("/api/doctor/assignments")
async def assign_plan(request: PlanAssignmentRequest, user: Dict[str, object] = Depends(get_current_user)):
    require_role(user, "doctor")
    plan = next(
        (item for item in rehabilitation_plans.get("plans", []) if item.get("planId") == request.plan_id),
        None,
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="Rehabilitation plan not found")
    assignment = create_plan_assignment(
        str(user["sub"]), request.patient_id, plan, request.notes, request.start_date
    )
    if assignment is None:
        raise HTTPException(status_code=403, detail="Link this patient before assigning a plan")
    return assignment


@app.get("/api/patient/assignments")
async def patient_assignments(
    active_only: bool = True, user: Dict[str, object] = Depends(get_current_user)
):
    require_role(user, "patient")
    return {"assignments": get_patient_assignments(str(user["sub"]), active_only)}


@app.patch("/api/patient/assignments/{assignment_id}")
async def set_assignment_status(
    assignment_id: str,
    request: AssignmentStatusRequest,
    user: Dict[str, object] = Depends(get_current_user),
):
    require_role(user, "patient")
    if request.status not in {"active", "completed", "paused"}:
        raise HTTPException(status_code=400, detail="Invalid assignment status")
    if not update_assignment_status(assignment_id, str(user["sub"]), request.status):
        raise HTTPException(status_code=404, detail="Assignment not found")
    return {"success": True}


# ----------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token", "")
    auth_user = decode_access_token(token)
    if auth_user is None or auth_user.get("role") != "patient":
        await websocket.close(code=1008, reason="Authentication required")
        return
    await websocket.accept()
    current_user_id = str(auth_user["sub"])
    session_manager = SessionManager()
    feature_extractor = RealtimeFeatureExtractor()

    pred_buf: Deque[str] = deque(maxlen=PRED_BUFFER)

    stable_ex = "Unknown"
    lock_ex = "Unknown"
    lock_until = 0.0

    rep_state: Dict[str, object] = {
        "stage": "waiting_start",
        "phase_frames": 0,
        "reps": 0,
        "last_rep_time": 0.0,
        "angle_buffer": [],
        "current_exercise": "Unknown",
    }

    last_conf = 0.0
    manual_exercise: Optional[str] = None
    selected_plan_id: Optional[str] = None
    selected_assignment_id: Optional[str] = None
    plan_exercises: Dict[str, Dict[str, object]] = {}
    last_logged_stable = ""
    no_pose_frames = 0
    feedback_state: Dict[str, object] = {"text": "", "changed_at": 0.0}

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if "command" in message:
                cmd = message["command"]

                if cmd == "START_SESSION":
                    selected_plan_id = message.get("selectedPlan")
                    selected_assignment_id = message.get("assignmentId")
                    selected_plan = next(
                        (item for item in rehabilitation_plans.get("plans", []) if item.get("planId") == selected_plan_id),
                        None,
                    )
                    if selected_assignment_id:
                        assignment = get_assignment(selected_assignment_id)
                        if (
                            not assignment
                            or assignment["patient_id"] != current_user_id
                            or assignment["status"] != "active"
                        ):
                            await websocket.send_text(json.dumps({"error": "Invalid plan assignment"}))
                            continue
                        selected_plan = assignment["plan"]
                        selected_plan_id = assignment["plan_id"]
                    if selected_plan is None:
                        await websocket.send_text(json.dumps({"error": "Invalid rehabilitation plan"}))
                        continue

                    plan_exercises = {item["name"]: item for item in selected_plan.get("exercises", [])}
                    manual_exercise = next(iter(plan_exercises), None)
                    session_manager.start_session(selected_plan_id, selected_assignment_id)
                    feature_extractor.reset()
                    pred_buf.clear()

                    stable_ex = "Unknown"
                    last_logged_stable = ""
                    lock_ex = "Unknown"
                    lock_until = 0.0

                    rep_state = {
                        "stage": "waiting_start",
                        "phase_frames": 0,
                        "reps": 0,
                        "last_rep_time": 0.0,
                        "angle_buffer": [],
                        "current_exercise": "Unknown",
                        "good_reps": 0,
                        "bad_reps": 0,
                        "last_feedback": "",
                        "last_feedback_time": 0.0,
                    }

                    last_conf = 0.0
                    no_pose_frames = 0
                    feedback_state = {"text": "", "changed_at": 0.0}

                elif cmd == "PAUSE_SESSION":
                    session_manager.pause_session()

                elif cmd == "RESUME_SESSION":
                    session_manager.resume_session()

                elif cmd == "SELECT_EXERCISE":
                    exercise_name = message.get("exerciseName")
                    if exercise_name not in plan_exercises:
                        await websocket.send_text(json.dumps({"error": "Exercise is not part of this plan"}))
                        continue
                    manual_exercise = exercise_name
                    feature_extractor.reset()
                    pred_buf.clear()
                    stable_ex = "Unknown"
                    lock_ex = "Unknown"
                    lock_until = 0.0
                    last_conf = 0.0
                    last_logged_stable = ""
                    no_pose_frames = 0
                    feedback_state = {"text": "", "changed_at": 0.0}
                    rep_state = {
                        "stage": "waiting_start",
                        "phase_frames": 0,
                        "reps": 0,
                        "last_rep_time": 0.0,
                        "angle_buffer": [],
                        "current_exercise": manual_exercise,
                        "good_reps": 0,
                        "bad_reps": 0,
                        "last_feedback": "",
                        "last_feedback_time": 0.0,
                    }

                elif cmd == "END_SESSION":
                    summary = session_manager.end_session()
                    if summary is None:
                        await websocket.send_text(json.dumps({"error": "No active session"}))
                        continue

                    if current_user_id:
                        session_data = {
                            'duration': summary.get('durationSeconds', 0),
                            'exercise_name': summary.get('mostFrequentExercise', 'Unknown'),
                            'total_reps': summary.get('totalReps', 0),
                            'form_quality': summary.get('formQuality', 100),
                            'speed_warnings_count': summary.get('speedWarningsCount', 0),
                            'exercise_results': summary.get('exerciseResults', []),
                            'plan_id': summary.get('planId'),
                            'assignment_id': summary.get('assignmentId'),
                            'landmarks': [],
                        }
                        session_id = save_session(current_user_id, session_data)
                        summary["sessionId"] = session_id
                    await websocket.send_text(json.dumps({"summary": summary}))

                continue

            if "frame" not in message:
                continue

            encoded_data = message["frame"].split(",")[1] if "," in message["frame"] else message["frame"]
            nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None or landmarker is None or classifier is None or feature_order is None:
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            detection_result = landmarker.detect(mp_image)

            active_exercise_name = manual_exercise or str(
                rep_state.get("current_exercise", "Unknown")
            )
            active_target = plan_target_for_exercise(plan_exercises, active_exercise_name)
            active_target_reps = max(int((active_target or {}).get("targetReps", 12)), 1)
            active_target_sets = max(int((active_target or {}).get("targetSets", 3)), 1)
            active_reps = int(rep_state.get("reps", 0))

            response = {
                "detectedExerciseLabel": "Unknown",
                "confidenceScore": 0.0,
                "repCount": active_reps,
                "angleValue": 0.0,
                "angleError": 0.0,
                "feedbackText": "",
                "currentExercise": active_exercise_name,
                "currentSet": min((active_reps // active_target_reps) + 1, active_target_sets),
                "setsCompleted": min(active_reps // active_target_reps, active_target_sets),
                "targetReps": active_target_reps,
                "targetSets": active_target_sets,
            }

            frame_height, frame_width = frame.shape[:2]
            landmarks = detection_result.pose_landmarks[0] if detection_result.pose_landmarks else None
            if landmarks is None:
                no_pose_frames += 1
                if no_pose_frames >= NO_POSE_CONFIRM_FRAMES:
                    response["feedbackText"] = "Step back and keep your full body in view"
            else:
                no_pose_frames = 0
            feature_row = feature_extractor.add(landmarks, frame_width, frame_height)

            if landmarks is not None and not feature_extractor.last_frame_valid:
                response["feedbackText"] = "Move fully into view"
                response["feedbackText"] = steady_feedback(response["feedbackText"], feedback_state)
                await websocket.send_text(json.dumps(response))
                continue

            if landmarks is not None:

                detected_label = "Unknown"
                conf = 0.0

                if feature_row is not None:
                    x_df = pd.DataFrame(
                        [[feature_row[name] for name in feature_order]],
                        columns=feature_order,
                        dtype=np.float64,
                    )

                    probs = classifier.predict_proba(x_df)[0]
                    order_idx = np.argsort(probs)[::-1]

                    top1_i = int(order_idx[0])
                    top2_i = int(order_idx[1]) if len(order_idx) > 1 else top1_i

                    top1 = float(probs[top1_i])
                    top2 = float(probs[top2_i])
                    margin = top1 - top2

                    conf = top1
                    detected_label = str(classifier.classes_[top1_i])

                    if conf < CONF_THRESHOLD or margin < MARGIN_THRESHOLD:
                        detected_label = "Unknown"

                    last_conf = conf

                    print(f"[RAW] {detected_label} conf={conf:.3f} margin={margin:.3f}")

                if USE_MOVEMENT_GATE and feature_row is not None:
                    if detected_label in {"Ex1", "Ex2"}:
                        movement_std = feature_row.get("shoulder_abd_deg_std", 0.0)
                    elif detected_label == "Ex3":
                        movement_std = (
                            feature_row.get("elbow_L_deg_std", 0.0)
                            + feature_row.get("elbow_R_deg_std", 0.0)
                        ) / 2.0
                    elif detected_label == "Ex4":
                        movement_std = feature_row.get("hip_abd_deg_std", 0.0)
                    else:
                        movement_std = (
                            feature_row.get("knee_L_deg_std", 0.0)
                            + feature_row.get("knee_R_deg_std", 0.0)
                        ) / 2.0
                    if movement_std < MOVE_STD_THRESHOLD:
                        detected_label = "Unknown"

                if detected_label != "Unknown":
                    pred_buf.append(detected_label)

                voted = stable_mode(pred_buf)

                now = time.time()

                if USE_EXERCISE_LOCK:
                    if lock_ex != "Unknown" and now < lock_until:
                        stable_ex = lock_ex
                    else:
                        if voted != "Unknown" and last_conf >= LOCK_MIN_CONF:
                            lock_ex = voted
                            lock_until = now + LOCK_SECONDS
                            stable_ex = voted
                        else:
                            stable_ex = "Unknown"
                else:
                    stable_ex = voted

                if stable_ex != last_logged_stable:
                    print(f"[STABLE] {last_logged_stable or 'None'} -> {stable_ex}")
                    last_logged_stable = stable_ex

                classified_name = ex_names.get(stable_ex, stable_ex)
                display_name = manual_exercise or classified_name

                if manual_exercise:
                    expected_class = expected_class_for_exercise(manual_exercise)
                    if stable_ex != expected_class:
                        actual_exercise = classified_name if stable_ex != "Unknown" else "Analyzing..."
                        response.update({
                            "detectedExerciseLabel": actual_exercise,
                            "currentExercise": manual_exercise,
                            "confidenceScore": float(last_conf),
                            "feedbackText": (
                                f"Do {manual_exercise}. Detected: {actual_exercise}"
                                if stable_ex != "Unknown"
                                else f"Hold on—checking for {manual_exercise}"
                            ),
                            "repCount": int(rep_state.get("reps", 0)),
                            "formQuality": 0.0,
                            "goodFormReps": int(rep_state.get("good_reps", 0)),
                            "repPhase": "exercise_check",
                            "measuredSide": "none",
                            "exerciseMatched": False,
                        })
                        response["feedbackText"] = steady_feedback(response["feedbackText"], feedback_state)
                        await websocket.send_text(json.dumps(response))
                        continue

                if display_name != "Unknown" and rep_state.get("current_exercise") != display_name:
                    rep_state = {
                        "stage": "waiting_start",
                        "phase_frames": 0,
                        "reps": 0,
                        "last_rep_time": 0.0,
                        "angle_buffer": [],
                        "current_exercise": display_name,
                        "good_reps": 0,
                        "bad_reps": 0,
                        "last_feedback": "",
                        "last_feedback_time": 0.0,
                    }

                if display_name != "Unknown":
                    angle_value, target, rep_exercise_key, measured_side = angle_for_exercise(
                        display_name, landmarks, frame_width, frame_height
                    )
                    previous_reps = int(rep_state.get("reps", 0))
                    reps, speed_warning = rep_update(display_name, angle_value, rep_state)

                    angle_used = float(rep_state.get("angle_smoothed", angle_value))
                    angle_error = angle_used - target
                    best_rep_error = min(
                        float(rep_state.get("best_rep_error", float("inf"))), abs(angle_error)
                    )

                    # Count form once per completed repetition, rather than once per video frame.
                    if reps > previous_reps:
                        form_tolerance = float(REP_PROFILES[rep_exercise_key]["tolerance"])
                        if best_rep_error <= form_tolerance:
                            rep_state["good_reps"] = int(rep_state.get("good_reps", 0)) + 1
                        else:
                            rep_state["bad_reps"] = int(rep_state.get("bad_reps", 0)) + 1
                        rep_state["best_rep_error"] = float("inf")
                    else:
                        rep_state["best_rep_error"] = best_rep_error

                    stage = str(rep_state.get("stage", "waiting_start"))
                    if stage == "waiting_start":
                        feedback = "Move to the starting position"
                    elif stage == "ready":
                        feedback = "Begin the movement with control"
                    else:
                        feedback = "Return to the starting position"

                    if stage == "active" and abs(angle_error) > 20:
                        if rep_exercise_key in {"squat", "forward_lunge", "hip_abduction"}:
                            feedback = "Complete the range, then return slowly"
                        else:
                            feedback = "Control the return movement"

                    total_reps_tracked = int(rep_state.get("good_reps", 0)) + int(rep_state.get("bad_reps", 0))
                    form_quality = (
                        100.0 if total_reps_tracked == 0
                        else (int(rep_state.get("good_reps", 0)) / total_reps_tracked) * 100.0
                    )
                    exercise_target = plan_target_for_exercise(plan_exercises, display_name)
                    # Never interpret a missing plan lookup as a one-rep set.
                    target_reps = max(int((exercise_target or {}).get("targetReps", 12)), 1)
                    target_sets = max(int((exercise_target or {}).get("targetSets", 3)), 1)
                    sets_completed = min(reps // target_reps, target_sets)
                    current_set = min((reps // target_reps) + 1, target_sets)
                    session_manager.update(
                        display_name,
                        reps,
                        form_quality,
                        speed_warning,
                        int(rep_state.get("good_reps", 0)),
                        sets_completed,
                    )

                    response = {
                        "detectedExerciseLabel": display_name,
                        "confidenceScore": float(last_conf),
                        "repCount": reps,
                        "angleValue": angle_used,
                        "angleError": angle_error,
                        "feedbackText": feedback,
                        "speedWarning": speed_warning,
                        "formQuality": float(form_quality),
                        "goodFormReps": int(rep_state.get("good_reps", 0)),
                        "currentSet": current_set,
                        "setsCompleted": sets_completed,
                        "targetReps": target_reps,
                        "targetSets": target_sets,
                        "setCompleted": (
                            exercise_target is not None
                            and reps > previous_reps
                            and reps % target_reps == 0
                        ),
                        "exerciseComplete": (
                            exercise_target is not None
                            and reps >= target_reps * target_sets
                        ),
                        "repPhase": stage,
                        "measuredSide": measured_side,
                        "currentExercise": display_name,
                        "exerciseMatched": True,
                    }

            response["feedbackText"] = steady_feedback(
                str(response.get("feedbackText", "")), feedback_state
            )
            await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        print("Client disconnected")

    except Exception as e:
        print(f"Server Error: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)

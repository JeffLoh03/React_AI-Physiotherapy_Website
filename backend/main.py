import json
import base64
import cv2
import numpy as np
import pandas as pd
import mediapipe as mp
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
import os
import joblib
from collections import deque, Counter
from typing import Deque, Dict, List, Optional, Tuple

from pose_features import calculate_angle
from session_manager import SessionManager

app = FastAPI()

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
session_manager = SessionManager()

# ----------------------------
# Realtime config
# ----------------------------
WINDOW_SIZE = 30
WINDOW_STEP = 15

PRED_BUFFER = 20
VOTE_DOMINANCE = 0.60
MIN_VALID_VOTES = 3

CONF_THRESHOLD = 0.30
MARGIN_THRESHOLD = 0.08

USE_EXERCISE_LOCK = True
LOCK_SECONDS = 2.5
LOCK_MIN_CONF = 0.35

REP_COOLDOWN = 0.8
ANGLE_SMOOTH_W = 5

USE_MOVEMENT_GATE = True
MOVE_STD_THRESHOLD = 0.8
MOVE_SIGNAL = "knee_mean_deg"

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


# ----------------------------
# Angle per exercise
# ----------------------------
def angle_for_exercise(display_label: str, landmarks) -> Tuple[float, float]:
    lbl = (display_label or "").lower()

    p_shoulder = [landmarks[12].x, landmarks[12].y]
    p_elbow = [landmarks[14].x, landmarks[14].y]
    p_wrist = [landmarks[16].x, landmarks[16].y]
    p_hip = [landmarks[24].x, landmarks[24].y]
    p_knee = [landmarks[26].x, landmarks[26].y]
    p_ankle = [landmarks[28].x, landmarks[28].y]

    angle_value = calculate_angle(p_shoulder, p_elbow, p_wrist)
    target = 90.0

    if "squat" in lbl or "lunge" in lbl:
        angle_value = calculate_angle(p_hip, p_knee, p_ankle)
        target = 90.0

    elif "hip abduction" in lbl:
        angle_value = calculate_angle(p_shoulder, p_hip, p_knee)
        target = 120.0

    elif "shoulder" in lbl:
        angle_value = calculate_angle(p_hip, p_shoulder, p_elbow)
        target = 90.0

    elif "push" in lbl or "v-w" in lbl or "vw" in lbl:
        angle_value = calculate_angle(p_shoulder, p_elbow, p_wrist)
        target = 90.0

    return float(angle_value), float(target)


# ----------------------------
# Improved rep counter
# Counts only complete cycle:
# high -> low -> high OR low -> high -> low
# ----------------------------
def rep_update(display_label: str, angle_value: float, state: Dict[str, object]) -> int:
    lbl = (display_label or "").lower()

    # Smooth angle
    buf = state.setdefault("angle_buffer", [])
    buf.append(float(angle_value))

    if len(buf) > ANGLE_SMOOTH_W:
        buf.pop(0)

    angle_s = float(sum(buf) / len(buf))

    reps = int(state.get("reps", 0))
    last_rep_time = float(state.get("last_rep_time", 0.0))
    stage = state.get("stage", "start")

    # start_is_high = True:
    # standing/straight position -> bent/down position -> standing/straight position = 1 rep
    if "squat" in lbl or "lunge" in lbl:
        start_th = 160.0
        opposite_th = 95.0
        start_is_high = True

    elif "push" in lbl:
        start_th = 150.0
        opposite_th = 85.0
        start_is_high = True

    elif "v-w" in lbl or "vw" in lbl:
        start_th = 150.0
        opposite_th = 85.0
        start_is_high = True

    # start_is_high = False:
    # arm/leg down position -> raised/abducted position -> back down = 1 rep
    elif "shoulder" in lbl:
        start_th = 40.0
        opposite_th = 75.0
        start_is_high = False

    elif "hip abduction" in lbl:
        start_th = 40.0
        opposite_th = 70.0
        start_is_high = False

    else:
        start_th = 150.0
        opposite_th = 85.0
        start_is_high = True

    now = time.time()

    if start_is_high:
        # Example: squat = standing -> down -> standing
        if stage == "start":
            if angle_s < opposite_th:
                stage = "opposite"

        elif stage == "opposite":
            if angle_s > start_th:
                if now - last_rep_time >= REP_COOLDOWN:
                    reps += 1
                    stage = "start"
                    state["last_rep_time"] = now

    else:
        # Example: shoulder abduction = arm down -> arm up -> arm down
        if stage == "start":
            if angle_s > opposite_th:
                stage = "opposite"

        elif stage == "opposite":
            if angle_s < start_th:
                if now - last_rep_time >= REP_COOLDOWN:
                    reps += 1
                    stage = "start"
                    state["last_rep_time"] = now

    state["stage"] = stage
    state["reps"] = reps
    state["angle_smoothed"] = angle_s

    return reps


# ----------------------------
# Startup
# ----------------------------
@app.on_event("startup")
def startup_event():
    global landmarker, classifier, feature_order, ex_names

    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=VisionRunningMode.IMAGE,
        num_poses=1,
    )

    landmarker = PoseLandmarker.create_from_options(options)
    print("SUCCESS: Loaded MediaPipe model")

    classifier = joblib.load(CLASSIFIER_PATH)
    print(f"SUCCESS: Loaded Classifier from {CLASSIFIER_PATH}")
    print("Classifier classes:", getattr(classifier, "classes_", None))

    with open(FEATURE_ORDER_PATH, "r", encoding="utf-8") as f:
        feature_order = json.load(f)

    print(f"SUCCESS: Loaded feature_order.json ({len(feature_order)} features)")

    with open(EX_NAMES_PATH, "r", encoding="utf-8") as f:
        ex_names = json.load(f)

    print("SUCCESS: Loaded exercise_names.json")


# ----------------------------
# WebSocket
# ----------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    frame_buf: Deque[Dict[str, float]] = deque(maxlen=WINDOW_SIZE)
    pred_buf: Deque[str] = deque(maxlen=PRED_BUFFER)

    stable_ex = "Unknown"
    lock_ex = "Unknown"
    lock_until = 0.0

    rep_state: Dict[str, object] = {
        "stage": "start",
        "reps": 0,
        "last_rep_time": 0.0,
        "angle_buffer": [],
        "current_exercise": "Unknown",
    }

    step_counter = 0
    last_conf = 0.0

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if "command" in message:
                cmd = message["command"]

                if cmd == "START_SESSION":
                    session_manager.start_session()
                    frame_buf.clear()
                    pred_buf.clear()

                    stable_ex = "Unknown"
                    lock_ex = "Unknown"
                    lock_until = 0.0

                    rep_state = {
                        "stage": "start",
                        "reps": 0,
                        "last_rep_time": 0.0,
                        "angle_buffer": [],
                        "current_exercise": "Unknown",
                    }

                    step_counter = 0
                    last_conf = 0.0

                elif cmd == "END_SESSION":
                    summary = session_manager.end_session()
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

            response = {
                "detectedExerciseLabel": "Unknown",
                "confidenceScore": 0.0,
                "repCount": int(rep_state.get("reps", 0)),
                "angleValue": 0.0,
                "angleError": 0.0,
                "feedbackText": "No pose detected",
            }

            if detection_result.pose_landmarks:
                landmarks = detection_result.pose_landmarks[0]
                ff = compute_frame_features_from_landmarks(landmarks)

                if ff.get("valid", 0.0) < 1.0:
                    await websocket.send_text(json.dumps(response))
                    continue

                frame_buf.append(ff)
                step_counter += 1

                detected_label = "Unknown"
                conf = 0.0

                if len(frame_buf) >= WINDOW_SIZE and (step_counter % WINDOW_STEP == 0):
                    x = build_window_vector(list(frame_buf), feature_order)
                    x_df = pd.DataFrame(x, columns=feature_order)

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

                if USE_MOVEMENT_GATE and len(frame_buf) >= WINDOW_SIZE:
                    window_vals = np.array([f.get("knee_L_deg", 0.0) for f in frame_buf], dtype=np.float64)

                    if np.nanstd(window_vals) < MOVE_STD_THRESHOLD:
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

                print(f"[STABLE] {stable_ex}")

                display_name = ex_names.get(stable_ex, stable_ex)

                if stable_ex != "Unknown" and rep_state.get("current_exercise") != display_name:
                    rep_state = {
                        "stage": "start",
                        "reps": 0,
                        "last_rep_time": 0.0,
                        "angle_buffer": [],
                        "current_exercise": display_name,
                    }

                if stable_ex != "Unknown":
                    angle_value, target = angle_for_exercise(display_name, landmarks)
                    reps = rep_update(display_name, angle_value, rep_state)

                    angle_used = float(rep_state.get("angle_smoothed", angle_value))
                    angle_error = angle_used - target

                    feedback = "Good rep!"

                    if abs(angle_error) > 8:
                        if "squat" in display_name.lower() or "lunge" in display_name.lower():
                            feedback = "Go deeper" if angle_error > 0 else "Too deep"
                        else:
                            feedback = "Raise a bit higher" if angle_error > 0 else "Lower a bit"

                    session_manager.update(display_name, reps)

                    response = {
                        "detectedExerciseLabel": display_name,
                        "confidenceScore": float(last_conf),
                        "repCount": reps,
                        "angleValue": angle_used,
                        "angleError": angle_error,
                        "feedbackText": feedback,
                    }

            await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        print("Client disconnected")

    except Exception as e:
        print(f"Server Error: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
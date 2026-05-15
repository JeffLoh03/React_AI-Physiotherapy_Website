# AI-Physio Assistant (MVP)

A proposal-compliant web prototype for real-time exercise classification and feedback.

## 1. Prerequisites

- Node.js (v18+)
- Python (v3.9+)

## 2. Setup & Installation

### Frontend (Web)
The frontend is located in the root directory.
```bash
npm install
npm run dev
```
Access at `http://localhost:5173`.

### Backend (Server)
The backend is located in `/server`.
```bash
cd server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 3. CRITICAL: Manual File Copy

You **MUST** copy your trained models and logic files into the `/server` directory:

1.  **Model**: Copy `pose_landmarker_lite.task` -> `/server/models/`
2.  **Classifier**: Copy `exercise_classifier_best.pkl` -> `/server/models/`
3.  **Logic**: Copy `rep_counter_rule_based.py` -> `/server/`

**Directory Structure Check:**
```
/server
  /models
    pose_landmarker_lite.task
    exercise_classifier_best.pkl
  rep_counter_rule_based.py
  pose_features.py
  session_manager.py
  main.py
  requirements.txt
```

## 4. Running the Backend

```bash
cd server
python main.py
```
WebSocket will start at `ws://localhost:8000/ws`.

## 5. Usage Guide

1.  **Start**: Open the web app and click "Start Live Session".
2.  **Webcam**: Allow camera access.
3.  **Real-time**:
    -   Perform exercises in view of the camera.
    -   The panel will show the **Detected Exercise** and **Confidence Score**.
    -   Feedback ("Raise/Lower") is based on the angle of the detected joint.
4.  **End Session**: Click "End" to view the summary and download the JSON report.

## 6. Troubleshooting

-   **Classification Error**: If the classifier fails, check `pose_features.py`. The feature vector MUST match the columns used during training.
-   **Camera Blocked**: Ensure browser permissions are allowed.

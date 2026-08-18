# re+active Physio AI

re+active is an AI-assisted rehabilitation web application. Patients can follow rehabilitation plans, receive live pose feedback, count repetitions and sets, and review session progress. Doctors can link patients, assign plans, and review patient analytics.

## Technology

- Frontend: React, TypeScript, Vite, Tailwind CSS, Three.js and Recharts
- Backend: FastAPI, MediaPipe, OpenCV, pandas and scikit-learn
- Communication: REST APIs and WebSockets
- Storage: SQLite for the current local version
- Machine learning: MediaPipe Pose Landmarker and an exercise classifier

## Project structure

```text
FYP Web/
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── auth.py
│   ├── pose_features.py
│   ├── session_manager.py
│   ├── rehabilitation_plans.json
│   ├── requirements.txt
│   ├── models/
│   └── tests/
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── .env.example
└── README.md
```

## Prerequisites

- Python 3.11 recommended
- Node.js 18 or newer
- npm
- A webcam
- The required files in `backend/models/` (download the classifier as described below)

See [backend/models/README.txt](backend/models/README.txt) for the model checklist.

### Download the exercise classifier

The 168 MB classifier is distributed as a GitHub release asset instead of being
stored in Git history. From the repository root, download it to the required
runtime location:

```powershell
Invoke-WebRequest -Uri "https://github.com/JeffLoh03/AI-Physiotherapy_Website/releases/download/model-v1/exercise_classifier_best.pkl" -OutFile "backend/models/exercise_classifier_best.pkl"
```

You can also download `exercise_classifier_best.pkl` from the
[`model-v1` release](https://github.com/JeffLoh03/AI-Physiotherapy_Website/releases/tag/model-v1)
and place it in `backend/models/` manually.

## Run locally

The backend and frontend run in separate terminals.

### Terminal 1: backend

From the repository root:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Set development secrets in the same PowerShell window. Replace the example values:

```powershell
$env:ENVIRONMENT="development"
$env:APP_SECRET="replace-with-a-long-random-secret"
$env:DOCTOR_INVITE_CODE="replace-with-a-private-clinician-code"
$env:CORS_ORIGINS="http://localhost:3000"
$env:AUTH_TOKEN_TTL_SECONDS="28800"
```

Start the API:

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend is available at:

- API: `http://localhost:8000`
- Interactive API documentation: `http://localhost:8000/docs`
- WebSocket: `ws://localhost:8000/ws`

On macOS or Linux, activate the environment with `source .venv/bin/activate` and use `export NAME="value"` for environment variables.

> The backend does not automatically load `backend/.env.example`. Set the variables in your shell or configure them through your hosting provider.

### Terminal 2: frontend

Open another terminal at the repository root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open `http://localhost:3000`.

The local frontend environment should contain:

```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

## Main workflow

1. Register a patient account, or register a doctor using the configured clinician invite code.
2. A doctor searches for a patient and adds the patient to their persistent care list.
3. The doctor assigns a rehabilitation plan.
4. The patient starts the assigned plan from the patient dashboard.
5. During a session, the camera sends frames to the FastAPI WebSocket for pose classification, form feedback, and repetition counting.
6. Completed sessions appear in patient and doctor analytics.

## Development checks

Run frontend checks:

```powershell
cd frontend
npm run lint
npm run build
```

Run backend tests:

```powershell
cd backend
python -m unittest discover -s tests -v
```

## Environment variables

### Backend

| Variable | Purpose |
| --- | --- |
| `ENVIRONMENT` | Use `development` locally and `production` when deployed |
| `APP_SECRET` | Signs authentication tokens; use a long private value |
| `DOCTOR_INVITE_CODE` | Required when registering a doctor account |
| `CORS_ORIGINS` | Comma-separated frontend origins allowed to call the API |
| `AUTH_TOKEN_TTL_SECONDS` | Login-token lifetime in seconds |

### Frontend

| Variable | Purpose |
| --- | --- |
| `VITE_API_URL` | Public FastAPI base URL |
| `VITE_WS_URL` | Public session WebSocket URL |

Never commit real secrets or a production `.env` file.

## Data and model notes

- The SQLite database is created and migrated automatically as `backend/app_data.db`.
- The database file and local environment files are intentionally ignored by Git.
- One pose feature extractor is created per WebSocket session so different users do not share pose history.
- The saved classifier and `feature_order.json` must match the 132 features produced by `pose_features.py`.
- Only load trusted `.pkl` or joblib model files.

## Deployment overview

Deploy the two applications separately:

- `frontend/`: static Vite site built with `npm ci && npm run build`; publish `dist/`
- `backend/`: Python web service built with `pip install -r requirements.txt`; start with `uvicorn main:app --host 0.0.0.0 --port $PORT`

For production:

- Use `https://` for `VITE_API_URL` and `wss://` for `VITE_WS_URL`.
- Set `ENVIRONMENT=production` and configure all secrets through the host.
- Set `CORS_ORIGINS` to the exact deployed frontend origin.
- Move SQLite to persistent storage or migrate to PostgreSQL before storing real data.
- The classifier is published as the `model-v1` GitHub release asset. Download it during deployment or include it in the backend container image.

## Troubleshooting

### Camera does not start

- Allow camera permission in the browser.
- Keep the complete body visible with suitable lighting.
- Deployed camera access requires HTTPS.

### Backend cannot load the model

- Confirm every required file listed in `backend/models/README.txt` is present.
- Confirm `feature_order.json` matches the classifier training columns.

### Frontend cannot reach the backend

- Confirm both servers are running.
- Check `VITE_API_URL`, `VITE_WS_URL`, and `CORS_ORIGINS`.
- Restart the Vite server after changing frontend environment variables.

### PowerShell blocks virtual-environment activation

Run Python through the environment directly:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

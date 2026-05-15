# Physio AI App (Rebuilt)

A web-based **AI physiotherapy assistant** that uses **MediaPipe pose estimation**, a trained **exercise classification model**, and a **rule-based repetition counter** to monitor rehabilitation exercises in real time.

The rebuilt project keeps the original design direction, including a **black and neon purple interface**, a **3D hero section**, and a **camera-based exercise session page**.

---

## Project Overview

This project is divided into two main parts:

| Part | Description |
|---|---|
| `frontend/` | Vite + React user interface for the website and camera session page |
| `backend/` | FastAPI WebSocket server that processes webcam frames using MediaPipe and the trained classifier |

The system receives video frames from the frontend, processes body landmarks using MediaPipe, predicts the exercise type using the trained machine learning model, counts repetitions using rule-based logic, and sends the results back to the frontend in real time.

---

## Folder Structure

```bash
Physio-AI-App/
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   ├── vite.config.js
│   └── .env.example
│
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── models/
│   │   ├── pose_landmarker_lite.task
│   │   └── exercise_classifier_best.pkl
│   └── .gitignore
│
├── README.md
└── .gitignore
```

---

## Model Files

The backend requires two model files:

```bash
backend/models/pose_landmarker_lite.task
backend/models/exercise_classifier_best.pkl
```

The trained exercise classification model can be downloaded from Google Drive:

[Download exercise classifier model](https://drive.google.com/file/d/1n9cGPcyNe9nRnaOw261G--XQzeJkMb4n/view?usp=drive_link)

After downloading, place the model file inside:

```bash
backend/models/
```

Your final model folder should look like this:

```bash
backend/models/
├── pose_landmarker_lite.task
└── exercise_classifier_best.pkl
```

---

## Important GitHub Note

Large model files should usually **not** be pushed directly to GitHub.

Add the following lines to your `.gitignore` file:

```gitignore
backend/models/*.pkl
backend/models/*.task
backend/.venv/
frontend/node_modules/
.env
```

This keeps your repository clean and avoids uploading large or environment-specific files.

Instead, upload the model file to Google Drive and provide the download link in this README.

---

## Requirements

Before running the project, make sure you have installed:

| Tool | Purpose |
|---|---|
| Python 3.10 or above | Backend server |
| Node.js 18 or above | Frontend React app |
| npm | Install frontend dependencies |
| Git | Version control |

---

## Running the Project Locally

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd Physio-AI-App
```

Replace `<your-repository-url>` with your actual GitHub repository link.

---

## Backend Setup

Go to the backend folder:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate the virtual environment.

For Windows:

```bash
.venv\Scripts\activate
```

For macOS or Linux:

```bash
source .venv/bin/activate
```

Install the required Python packages:

```bash
pip install -r requirements.txt
```

Make sure the required model files are placed inside:

```bash
backend/models/
```

Start the backend server:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend WebSocket server will run at:

```bash
ws://localhost:8000/ws
```

---

## Frontend Setup

Open a new terminal and go to the frontend folder:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Create an environment file from the example file:

```bash
cp .env.example .env
```

For Windows Command Prompt, use:

```bash
copy .env.example .env
```

Inside `.env`, make sure the WebSocket URL is set correctly:

```env
VITE_WS_URL=ws://localhost:8000/ws
```

Run the frontend development server:

```bash
npm run dev
```

Open the website using the URL printed by Vite. It is usually:

```bash
http://localhost:5173
```

---

## WebSocket Configuration

The frontend reads the backend WebSocket URL from:

```env
VITE_WS_URL
```

If no value is provided, the default WebSocket URL is:

```bash
ws://localhost:8000/ws
```

Use this setting when running locally:

```env
VITE_WS_URL=ws://localhost:8000/ws
```

If the backend is deployed online, replace the value with your deployed backend WebSocket URL.

Example:

```env
VITE_WS_URL=wss://your-backend-domain.com/ws
```

---

## Main Features

- Real-time camera-based exercise monitoring
- MediaPipe pose landmark detection
- Machine learning exercise classification
- Confidence score display
- Rule-based repetition counting
- Real-time user feedback panel
- Web-based interface using React
- FastAPI backend with WebSocket communication
- Clean black and neon purple UI design

---

## Basic System Workflow

```text
User opens camera session
        ↓
Frontend captures webcam frames
        ↓
Frames are sent to FastAPI backend through WebSocket
        ↓
MediaPipe detects body landmarks
        ↓
Feature extraction is performed
        ↓
Machine learning model predicts exercise type
        ↓
Rule-based logic counts repetitions
        ↓
Backend sends prediction, confidence score, feedback, and count back to frontend
        ↓
Frontend displays results in real time
```

---

## Common Issues and Fixes

### 1. Backend cannot find model file

Make sure the model files are inside:

```bash
backend/models/
```

Required files:

```bash
pose_landmarker_lite.task
exercise_classifier_best.pkl
```

---

### 2. Frontend cannot connect to backend

Check that the backend is running:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Then check your `.env` file:

```env
VITE_WS_URL=ws://localhost:8000/ws
```

Restart the frontend after editing `.env`:

```bash
npm run dev
```

---

### 3. Camera is not working

Make sure:

- Browser camera permission is allowed
- No other application is using the webcam
- The website is opened in a modern browser such as Chrome or Edge

---

### 4. `npm install` error

Try deleting `node_modules` and reinstalling:

```bash
rm -rf node_modules package-lock.json
npm install
```

For Windows, manually delete the `node_modules` folder and `package-lock.json`, then run:

```bash
npm install
```

---

## Suggested Repository Structure for GitHub

Before pushing to GitHub, make sure your repository does not include:

```bash
backend/.venv/
frontend/node_modules/
backend/models/*.pkl
backend/models/*.task
.env
```

Only push the source code, configuration files, and README.

Recommended command:

```bash
git add .
git commit -m "Initial commit for Physio AI App"
git push origin main
```

---

## Project Status

This project is currently developed as a final year project prototype. The system has completed three main implementation components:

1. Machine learning model training for exercise classification
2. Rule-based repetition counter development and evaluation
3. Web application integration for real-time physiotherapy monitoring

---

## Author

**Jeff Loh Wei Kit**  
Bachelor in Digital Health (Hons)  
IMU University

---

## Disclaimer

This application is developed for academic and prototype purposes. It is not intended to replace professional physiotherapy assessment, clinical diagnosis, or medical advice.

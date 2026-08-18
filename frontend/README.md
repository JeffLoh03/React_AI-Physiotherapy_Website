# re+active Frontend

This directory contains the React and TypeScript user interface for re+active Physio AI.

For complete backend and frontend setup, see the [project README](../README.md).

## Requirements

- Node.js 18 or newer
- npm
- The FastAPI backend running locally or at a public URL

## Install and run

From the repository root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open `http://localhost:3000`.

On macOS or Linux, copy the environment file with `cp .env.example .env`.

## Environment configuration

Local defaults:

```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

| Variable | Description |
| --- | --- |
| `VITE_API_URL` | FastAPI base URL used for authentication, plans, profiles and analytics |
| `VITE_WS_URL` | WebSocket URL used for live camera sessions |

After changing `.env`, restart `npm run dev` because Vite reads these values at startup.

For a deployed site, use HTTPS equivalents:

```env
VITE_API_URL=https://api.example.com
VITE_WS_URL=wss://api.example.com/ws
```

Do not place passwords, backend secrets, or clinician invite codes in `VITE_` variables. Vite variables are included in the browser bundle.

## Available commands

Run all commands from `frontend/`:

| Command | Purpose |
| --- | --- |
| `npm run dev` | Start the development server on port 3000 |
| `npm run lint` | Run TypeScript validation without emitting files |
| `npm run build` | Create a production build in `dist/` |
| `npm run preview` | Preview the production build locally |
| `npm run clean` | Remove the generated `dist/` directory |

## Main routes

| Route | Description |
| --- | --- |
| `/` | Public landing page |
| `/auth` | Patient and doctor sign-in/registration |
| `/patient-dashboard` | Protected patient plans and analytics |
| `/doctor-dashboard` | Protected care list, plan assignment and patient analytics |
| `/session` | Protected live patient rehabilitation session |

Protected routes require a valid backend authentication token and the correct account role.

## Important directories

```text
frontend/
├── public/                 Static assets and the public plan copy
├── src/components/         Reusable interface components
├── src/lib/                API, frame capture and chart helpers
├── src/pages/              Route-level pages
├── src/App.tsx             Routes and route protection
├── src/index.css           Global styles
├── package.json            Dependencies and scripts
└── vite.config.ts          Vite configuration
```

## Production build

```powershell
cd frontend
npm ci
npm run lint
npm run build
```

Deploy the generated `dist/` directory as a static site. Configure the host to rewrite unknown paths to `/index.html` so React Router routes work after a browser refresh.

Camera access requires permission from the user and a secure HTTPS origin when deployed.

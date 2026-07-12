# Sleep Tracker - Full Stack Web Application

A sleep tracking application with AI-powered insights, Fitbit integration, and Firebase authentication.

![Dashboard](assets/screenshots/dashboard.png)

## Features

- **User Authentication**: Secure login with Firebase (Email/Password + Google Sign-in)
- **Manual Sleep Logging**: Log your sleep with quality ratings and notes
- **Fitbit Integration**: Connect via OAuth and sync sleep data from your Fitbit device, with sync history logs
- **AI-Powered Insights**: Personalized sleep analysis and recommendations via OpenAI or Google Gemini (falls back to rule-based analysis when no API key is configured)
- **Interactive Dashboard**: Visualize sleep patterns, statistics, and trends with charts
- **Sleep Goals**: Set sleep targets and track progress against them

## Screenshots

| Trends | AI Insights |
|---|---|
| ![Trends](assets/screenshots/trends.png) | ![AI Insights](assets/screenshots/insights.png) |

| Sleep Log | Login |
|---|---|
| ![Sleep Log](assets/screenshots/sleep-log.png) | ![Login](assets/screenshots/login.png) |

## Tech Stack

### Backend
- **Django 4.2** with **Django REST Framework**: RESTful API
- **Firebase Admin SDK**: Server-side token verification (custom DRF authentication class)
- **OpenAI (gpt-4o)** or **Google Gemini (gemini-1.5-flash)**: AI insights, selectable via `AI_PROVIDER`
- **SQLite** (local default) / **PostgreSQL** (via `DATABASE_URL` or `DB_*` vars)
- **WhiteNoise + Gunicorn**: Static files and production serving

### Frontend
- **React 18** + **TypeScript** with **Vite** (dev server on port 3000, proxies `/api` to the backend)
- **Tailwind CSS**, **Headless UI**, **Heroicons**: Styling and UI components
- **Chart.js** (react-chartjs-2): Data visualization
- **Zustand**: State management (auth + sleep stores)
- **React Router**: Navigation with protected routes
- **Axios**, **React Hook Form**, **react-hot-toast**, **date-fns**

## Project Structure

```
sleepinsight/
├── backend/                  # Django backend
│   ├── sleep_tracker/        # Project settings & root URLconf
│   ├── users/                # Custom user model, Firebase auth, profiles
│   ├── sleep/                # Sleep records & goals
│   ├── fitbit_integration/   # Fitbit OAuth, sync & sync logs
│   ├── ai_insights/          # AI-powered analysis (OpenAI/Gemini)
│   ├── build.sh              # Render build script
│   ├── Procfile              # Gunicorn start command
│   └── requirements.txt
│
├── frontend/                 # React frontend
│   ├── src/
│   │   ├── components/       # Layout, ProtectedRoute, charts
│   │   ├── pages/            # Dashboard, SleepLog, Trends, Insights,
│   │   │                     # Settings, Login, Register, FitbitCallback
│   │   ├── services/         # API client (axios) & Firebase
│   │   ├── stores/           # Zustand stores (auth, sleep)
│   │   └── config.ts         # Firebase & API configuration
│   ├── vercel.json           # Vercel deployment config
│   └── package.json
│
├── render.yaml               # Render blueprint (API + PostgreSQL)
└── README.md
```

## How It Works

Authentication is fully delegated to Firebase: the React app signs the user in with the Firebase Web SDK and attaches the resulting ID token to every API request. On the backend, a custom DRF authentication class verifies the token with the Firebase Admin SDK and automatically provisions a local Django user on first sight — there is no separate registration endpoint or session/JWT handling to configure.

Sleep data comes from two sources that share the same models: manual entries created in the UI, and records imported through the Fitbit OAuth integration. The insights module summarizes recent records (duration, efficiency, sleep stages, consistency, sleep debt) and sends that summary to the configured AI provider; without an API key it degrades to built-in rule-based analysis, so the feature works out of the box.

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Firebase project (required — handles all authentication)
- Fitbit Developer account (optional — only for device sync)
- OpenAI or Google Gemini API key (optional — AI insights fall back to rule-based analysis)

### 1. Clone the Repository

```bash
git clone https://github.com/hhzks/sleep-insight-app.git
cd sleep-insight-app
```

### 2. Firebase Setup

1. Create a new project at [Firebase Console](https://console.firebase.google.com)
2. Enable Authentication with Email/Password and Google providers
3. Generate a new service account key:
   - Go to Project Settings > Service Accounts
   - Click "Generate new private key"
   - Save the JSON file securely (you'll copy values from it into `.env`)

### 3. Fitbit Setup (Optional)

1. Register an app at [Fitbit Developer](https://dev.fitbit.com/apps)
2. Set OAuth 2.0 Application Type to "Personal"
3. Set Callback URL to `http://localhost:3000/fitbit/callback`
4. Note your Client ID and Client Secret

### 4. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and configure
cp .env.example .env
# Edit .env with your credentials

# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### 5. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Copy environment file and configure
cp .env.example .env.local
# Edit .env.local with your Firebase config

# Start development server
npm run dev
```

### 6. Access the Application

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api
- Django Admin: http://localhost:8000/admin

## Configuration

### Backend Environment Variables

See `backend/.env.example` for the full template.

| Variable | Description |
|----------|-------------|
| `DJANGO_SECRET_KEY` | Django secret key |
| `DEBUG` | Enable debug mode (defaults to `True` locally) |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed frontend origins |
| `DATABASE_URL` | Full database URL (takes priority; used on Render) |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL settings (used if `DATABASE_URL` is unset; falls back to SQLite) |
| `FIREBASE_PROJECT_ID` | Firebase project ID |
| `FIREBASE_PRIVATE_KEY` | Firebase service account private key |
| `FIREBASE_CLIENT_EMAIL` | Firebase service account email |
| `FITBIT_CLIENT_ID` | Fitbit OAuth client ID |
| `FITBIT_CLIENT_SECRET` | Fitbit OAuth client secret |
| `FITBIT_REDIRECT_URI` | Fitbit OAuth callback URL (defaults to `http://localhost:3000/fitbit/callback`) |
| `AI_PROVIDER` | `openai` (default) or `gemini` |
| `OPENAI_API_KEY` | OpenAI API key (used when `AI_PROVIDER=openai`) |
| `GEMINI_API_KEY` | Google Gemini API key (used when `AI_PROVIDER=gemini`) |

### Frontend Environment Variables

See `frontend/.env.example` for the full template.

| Variable | Description |
|----------|-------------|
| `VITE_FIREBASE_API_KEY` | Firebase Web API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase auth domain |
| `VITE_FIREBASE_PROJECT_ID` | Firebase project ID |
| `VITE_FIREBASE_STORAGE_BUCKET` | Firebase storage bucket |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Firebase messaging sender ID |
| `VITE_FIREBASE_APP_ID` | Firebase app ID |
| `VITE_API_BASE_URL` | Backend API URL (defaults to `http://localhost:8000/api`) |

## API Endpoints

### Authentication
All endpoints require a Firebase ID token in the Authorization header:
```
Authorization: Bearer <firebase-id-token>
```

List endpoints are paginated (20 per page).

### Users
- `GET /api/users/me/` - Get current user profile
- `PATCH /api/users/me/` - Update profile
- `PATCH /api/users/preferences/` - Update preferences

### Sleep Records
- `GET /api/sleep/records/` - List sleep records
- `POST /api/sleep/records/` - Create sleep record
- `GET /api/sleep/records/{id}/` - Get sleep record
- `PATCH /api/sleep/records/{id}/` - Update sleep record
- `DELETE /api/sleep/records/{id}/` - Delete sleep record
- `GET /api/sleep/records/statistics/` - Get statistics
- `GET /api/sleep/records/recent/` - Get recent records
- `GET /api/sleep/records/trends/` - Get trends

### Sleep Goals
- `GET /api/sleep/goals/` - Get sleep goals
- `POST /api/sleep/goals/` - Create/update goals
- `GET /api/sleep/goals/progress/` - Get progress

### Fitbit Integration
- `GET /api/fitbit/auth-url/` - Get OAuth URL
- `POST /api/fitbit/callback/` - Handle OAuth callback
- `GET /api/fitbit/status/` - Get connection status
- `DELETE /api/fitbit/status/` - Disconnect Fitbit
- `POST /api/fitbit/sync/` - Sync sleep data
- `GET /api/fitbit/sync-logs/` - Get sync history

### AI Insights
- `POST /api/insights/generate/` - Generate AI insights
- `GET /api/insights/list/` - List saved insights
- `GET /api/insights/{id}/` - Get insight details
- `GET /api/insights/tips/` - Get sleep tips
- `GET /api/insights/tips/{category}/` - Get tips by category
- `GET /api/insights/quick/` - Get quick summary

## Development

### Linting

```bash
cd frontend
npm run lint
```

### Database Migrations

```bash
cd backend
python manage.py makemigrations
python manage.py migrate
```

## Deployment

The repository ships with configuration for Render (backend + database) and Vercel (frontend).

### Backend — Render

`render.yaml` defines a blueprint with:
- A **web service** (`sleep-tracker-api`) that runs `backend/build.sh` (installs dependencies, collects static files, runs migrations) and serves with Gunicorn
- A free **PostgreSQL database** wired in via `DATABASE_URL`

Create a Blueprint on [Render](https://render.com) pointed at this repository, then fill in the environment variables marked `sync: false` (Firebase, Fitbit, CORS origins, AI keys) in the dashboard.

### Frontend — Vercel

`frontend/vercel.json` configures the Vite build with SPA rewrites. Import the repository into [Vercel](https://vercel.com) with `frontend` as the root directory and set the `VITE_*` environment variables (point `VITE_API_BASE_URL` at your deployed backend, e.g. `https://<your-service>.onrender.com/api`).

Or build manually:

```bash
cd frontend
npm run build
# Deploy the 'dist' folder to your hosting service
```

## License

MIT License

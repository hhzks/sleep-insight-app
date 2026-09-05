# Sleep Tracker

A sleep tracking application with AI-powered insights, Fitbit integration, and Firebase authentication.

![Dashboard](assets/screenshots/dashboard.png)

## Features

- **User Authentication**: Secure login with Firebase (Email/Password + Google Sign-in)
- **Manual Sleep Logging**: Log your sleep with quality ratings and notes
- **Fitbit Integration**: Connect via OAuth and sync sleep data from your Fitbit device, with sync history logs
- **Nightly Sync**: Connected accounts are re-read once a day on the worker, so sleep data arrives without anyone pressing a button (per-user opt-out in Settings)
- **AI-Powered Insights**: Personalized sleep analysis from a self-hosted Ollama model, generated in the background and polled by the UI (falls back to rule-based analysis when the model is unreachable)
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
- **Self-hosted Ollama (`qwen2.5:7b-instruct`)**: AI insights generated on your own inference server (falls back to rule-based analysis when the server is unreachable)
- **Celery + Redis**: Insight generation runs as a task on a separate worker process; a beat schedule embedded in that same worker reaps stale jobs every 5 minutes and runs the nightly Fitbit sync
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
│   ├── ai_insights/          # AI-powered analysis (self-hosted Ollama, Celery tasks)
│   ├── bin/                  # web/worker entrypoints - shared by the
│   │                         # Dockerfile CMD and fly.toml [processes]
│   ├── Dockerfile            # Multi-stage build, runs as a non-root user
│   ├── fly.toml              # Fly app: web + worker process groups
│   ├── build.sh              # Render build script (legacy)
│   ├── Procfile              # Gunicorn start command (legacy)
│   └── requirements.txt
│
├── frontend/                 # React frontend
│   ├── public/
│   │   └── _redirects        # Cloudflare Pages SPA rewrite
│   ├── src/
│   │   ├── components/       # Layout, ProtectedRoute, charts
│   │   ├── pages/            # Dashboard, SleepLog, Trends, Insights,
│   │   │                     # Settings, Login, Register, FitbitCallback
│   │   ├── services/         # API client (axios) & Firebase
│   │   ├── stores/           # Zustand stores (auth, sleep)
│   │   └── config.ts         # Firebase & API configuration
│   ├── vercel.json           # Vercel deployment config (legacy)
│   └── package.json
│
├── .github/workflows/ci.yml  # Tests on every PR, deploys on main
├── render.yaml               # Render blueprint (legacy)
└── README.md
```

## How It Works

Authentication is fully delegated to Firebase: the React app signs the user in with the Firebase Web SDK and attaches the resulting ID token to every API request. On the backend, a custom DRF authentication class verifies the token with the Firebase Admin SDK and automatically provisions a local Django user on first sight; there is no separate registration endpoint or session/JWT handling to configure.

Sleep data comes from two sources that share the same models: manual entries created in the UI, and records imported through the Fitbit OAuth integration.

Fitbit import runs through one function, `fitbit_integration/sync.py`, which both the "Sync now" button and the nightly scheduled task call, so the two cannot drift. The schedule is a single fixed-UTC run rather than per-user local time: each run re-reads `FITBIT_SYNC_LOOKBACK_DAYS` and every record is keyed on Fitbit's `logId`, so a night that uploads after the run is picked up by the next one as an update. That also makes a missed run self-healing instead of a permanent gap. Failures are classified rather than lumped together - only a rejected authorisation (`FitbitAuthError`) counts towards `FITBIT_MAX_AUTH_FAILURES`, at which point the token is deleted and the user is asked to reconnect; a Fitbit outage (`FitbitUnavailable`) never disconnects anyone.

Fitbit access and refresh tokens are encrypted at rest with Fernet, via a `TextField` subclass in `fitbit_integration/fields.py` that encrypts on write and decrypts on read - so `services.py` never sees ciphertext and needs no encryption code of its own. They are long-lived grants that the nightly sync refreshes and uses with no user present, so what an attacker could do with a stolen row is not bounded by anyone's session.

Keys live in `FITBIT_TOKEN_ENCRYPTION_KEYS`, newest first:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`MultiFernet` decrypts with any key in the list and encrypts with the first, so rotating is: mint a key, prepend it, re-save every `FitbitToken` row, then drop the trailing key. Removing a key that still has rows encrypted under it makes those rows unreadable, and the error says so rather than failing quietly.

> **Set this secret before deploying the migration that introduces it.** `0003_encrypt_tokens_at_rest` converts existing plaintext rows in place and runs in `release_command`. With the key unset it raises `ImproperlyConfigured` and exits non-zero, so Fly aborts the deploy with the old code still serving - safe, but stalled until the secret exists. The conversion skips rows that already decrypt, so a retried release command cannot double-encrypt anything, and the migration reverses cleanly back to plaintext.

Encryption protects the tokens from here on. It does not reach backups or WAL segments written while they were plaintext; those grants stay valid until each user's next refresh replaces them. The insights module summarizes recent records (duration, efficiency, sleep stages, consistency, sleep debt) and sends that summary to a self-hosted Ollama server. Because CPU inference takes minutes, generation runs as a Celery task on a separate worker process and the UI polls for the result; if the model is unreachable, slow, or returns malformed output, the app falls back to built-in rule-based analysis and tells the user it did so.

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Firebase project (required, handles all authentication)
- Fitbit Developer account (optional, only for device sync)
- Self-hosted Ollama server (optional, AI insights fall back to rule-based analysis if unavailable)
- Redis (required to run the Celery worker; without it, AI insight requests stay `queued` forever - even the rule-based fallback path runs as a Celery task)

### Setting Up the Inference Server (optional)

Insights are generated by an Ollama server you host. These steps target an
Oracle Cloud Ampere A1 instance (ARM64, CPU-only) since that's what I'm using, but any Linux box works.

1. **Install Ollama and pull the model:**

   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull qwen2.5:7b-instruct
   ```

   On 4 A1 cores expect 1.5–3 minutes per generation. Use `qwen2.5:3b-instruct`
   if that is too slow then use a smaller model by changing `OLLAMA_MODEL` in the config.

2. **Keep the model resident** so the first request of the day is not 30 seconds
   slower. Add to `/etc/systemd/system/ollama.service.d/override.conf`:

   ```ini
   [Service]
   Environment="OLLAMA_KEEP_ALIVE=-1"
   ```

   Then `sudo systemctl daemon-reload && sudo systemctl restart ollama`.

   **Leave Ollama bound to `127.0.0.1`.** It has no authentication of its own;
   Caddy is what stands between it and the internet.

3. **Point a DNS name at the instance** since Caddy needs a resolvable hostname to obtain a Let's Encrypt certificate.

4. **Install Caddy** and use this `Caddyfile`, which rejects anything without
   the right bearer token:

   ```
   llm.example.com {
       @unauthorized not header Authorization "Bearer {env.OLLAMA_TOKEN}"
       respond @unauthorized "Unauthorized" 401
       reverse_proxy 127.0.0.1:11434 {
           header_up Host {upstream_hostport}
       }
   }
   ```

   Put `OLLAMA_TOKEN` in Caddy's systemd environment, not in the Caddyfile.

   The `header_up Host` line is required. Ollama rejects requests whose `Host`
   header is not local — a DNS-rebinding protection — so without it Ollama
   returns a bare `403` even when your token is correct. Rewriting the header
   makes the proxy hop look like what it is: a local request. Verify with
   `curl -H "Authorization: Bearer wrong" https://llm.example.com/api/tags`,
   which should return `401` (Caddy rejecting you); a `403` there means the
   request reached Ollama and this line is missing.

5. **Open port 443 (and only 443!!).** On OCI this takes two steps, and skipping
   the second is will probably make the server appear dead:

   ```bash
   # 1. Add an ingress rule for TCP 443 in the VCN security list (OCI console)
   # 2. Allow it at the host firewall too:
   sudo iptables -I INPUT 1 -p tcp --dport 443 -j ACCEPT
   sudo netfilter-persistent save
   ```

6. **Verify from the backend:**

   ```bash
   OLLAMA_BASE_URL=https://llm.example.com OLLAMA_API_KEY=your-token \
     python manage.py check_ollama
   ```

   This reports reachability, auth, model availability, and round-trip time,
   naming the likely cause for each failure mode.

### Setting up the app (local version)

#### 1. Clone the Repository

```bash
git clone https://github.com/hhzks/sleep-insight-app.git
cd sleep-insight-app
```

#### 2. Firebase Setup

1. Create a new project at [Firebase Console](https://console.firebase.google.com)
2. Enable Authentication with Email/Password and Google providers
3. Generate a new service account key:
   - Go to Project Settings > Service Accounts
   - Click "Generate new private key"
   - Save the JSON file securely (you'll copy values from it into `.env`)

#### 3. Fitbit Setup (Optional)

1. Register an app at [Fitbit Developer](https://dev.fitbit.com/apps)
2. Set OAuth 2.0 Application Type to "Personal"
3. Set Callback URL to `http://localhost:3000/fitbit/callback`
4. Note your Client ID and Client Secret

#### 4. Backend Setup

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

AI insight generation additionally needs a Redis broker and a Celery worker
consuming from it - `manage.py runserver` alone only queues the job. Start
Redis (`docker run --rm -p 6379:6379 redis:7-alpine` works), then in a
second terminal with the virtualenv active:

```bash
celery -A sleep_tracker worker --loglevel=info
```

This is optional if you don't need AI insights; the rest of the app runs
without it.

#### 5. Frontend Setup

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

#### 6. Access the Application

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api
- Django Admin: http://localhost:8000/admin

Steps for hosting are listed below

### Configuration

#### Backend Environment Variables

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
| `FITBIT_TOKEN_ENCRYPTION_KEYS` | Fernet keys for token encryption at rest, newest first, comma-separated (**required**) |
| `FITBIT_SYNC_LOOKBACK_DAYS` | Days each nightly sync re-reads (defaults to 3) |
| `FITBIT_MAX_AUTH_FAILURES` | Consecutive auth failures before a user is disconnected (defaults to 3) |
| `OLLAMA_BASE_URL` | Ollama server URL (defaults to `http://localhost:11434`) |
| `OLLAMA_API_KEY` | Ollama bearer token (blank locally; set for production proxies) |
| `OLLAMA_MODEL` | Model name (defaults to `qwen2.5:7b-instruct`) |
| `OLLAMA_TIMEOUT_SECONDS` | Max generation time in seconds (defaults to 300) |
| `OLLAMA_NUM_PREDICT` | Max tokens the model may generate per response (defaults to 1000) |
| `OLLAMA_TEMPERATURE` | Sampling temperature for generation (defaults to 0.7) |
| `OLLAMA_INVALID_RETRIES` | Retries after malformed model output before falling back to rules (defaults to 1) |
| `INSIGHT_JOB_STALE_MINUTES` | Max job age before reaper kills it (defaults to 15) |
| `CELERY_BROKER_URL` | Redis URL for the Celery broker (defaults to `redis://localhost:6379/0`) |

Generation runs as a Celery task with a soft and a hard time limit derived from `OLLAMA_TIMEOUT_SECONDS`, and the stale-job reaper (`INSIGHT_JOB_STALE_MINUTES`) must not fire before Celery's own hard kill does. The enforced ordering, checked at startup by `ai_insights.E001`, is:

```
worst case  <  soft limit  <  hard limit  <  stale window
OLLAMA_TIMEOUT_SECONDS * (1 + OLLAMA_INVALID_RETRIES)  <  worst case + 60  <  soft limit + 60  <  INSIGHT_JOB_STALE_MINUTES * 60
```

With the defaults (`OLLAMA_TIMEOUT_SECONDS=300`, `OLLAMA_INVALID_RETRIES=1`, `INSIGHT_JOB_STALE_MINUTES=15`) that's `600 < 660 < 720 < 900`. If you raise `OLLAMA_TIMEOUT_SECONDS`, raise `INSIGHT_JOB_STALE_MINUTES` to match or the reaper will kill jobs Celery is still legitimately running.

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
- `PATCH /api/fitbit/status/` - Turn nightly sync on or off
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

### Tests

```bash
# Backend (Django test runner)
cd backend
python manage.py test

# Frontend (Vitest)
cd frontend
npm test
```

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

Production runs on **Fly.io** (backend) and **Cloudflare Pages** (frontend), deployed by GitHub Actions on every push to `main`. Render and Vercel configuration is still in the repository but is no longer the target — see [Legacy hosts](#legacy-hosts).

### Backend — Fly.io

`backend/fly.toml` defines a single app with two process groups, both running the same image built from `backend/Dockerfile`:

| Group | Entrypoint | Role |
| --- | --- | --- |
| `web` | `backend/bin/web` | Gunicorn, behind Fly's load balancer |
| `worker` | `backend/bin/worker` | Celery worker with embedded beat |

Both groups reference the `bin/` scripts rather than restating the command, so the Dockerfile `CMD` and `fly.toml` cannot drift apart.

Migrations run through `release_command`, in a one-off machine that must exit 0 before any new machine takes traffic — deliberately not during the image build, where a build step would race concurrent deploys and could apply schema changes while the old code is still serving.

Only the `web` group is attached to `http_service`. The health check at `/api/health/` sends a `Host: health.check` header, because Fly probes machines over its private network and Django would otherwise reject every probe with `DisallowedHost`; that hostname is in `ALLOWED_HOSTS` in `[env]` for exactly this reason.

Two managed services are required:

- **PostgreSQL** — any provider, wired in via `DATABASE_URL`
- **Redis** — the Celery broker, via `CELERY_BROKER_URL`. Use a `rediss://` URL

Set the rest as Fly secrets (`fly secrets set`): `DJANGO_SECRET_KEY`, `FIREBASE_PROJECT_ID`, `FIREBASE_CLIENT_EMAIL`, `FIREBASE_PRIVATE_KEY`, `FITBIT_CLIENT_ID`, `FITBIT_CLIENT_SECRET`, `FITBIT_REDIRECT_URI`, `FITBIT_TOKEN_ENCRYPTION_KEYS`, `CORS_ALLOWED_ORIGINS`, `OLLAMA_BASE_URL`, `OLLAMA_API_KEY`.

> `FIREBASE_PRIVATE_KEY` must keep its literal `\n` sequences rather than real newlines; `users/firebase_auth.py` expands them on load.

Scaling the `worker` group past one machine will duplicate every scheduled reap *and* fan out the nightly Fitbit sync twice, because beat is embedded in the worker. Promote beat to its own process group first.

### Frontend — Cloudflare Pages

The build output is `frontend/dist`, published with `wrangler pages deploy`.

`frontend/public/_redirects` rewrites unmatched paths to `/index.html` with status 200, which is what lets React Router handle a hard load of a deep link such as `/insights`. Without it Cloudflare returns 404 for every route except `/`.

`VITE_*` values are inlined by Vite at **build** time, so they must be present in the build step rather than on the host. They are stored as repository *variables*, not secrets: the Firebase web config ships to every browser inside the bundle, so treating it as secret buys nothing. Access is controlled by Firebase Auth rules and authorised domains.

### Continuous deployment

`.github/workflows/ci.yml` runs backend tests (against a real PostgreSQL 16 service container) and frontend lint/test/build on every pull request. Pushes to `main` additionally run two deploy jobs, each gated on its own test job.

| Name | Kind | Purpose |
| --- | --- | --- |
| `FLY_API_TOKEN` | secret | `fly tokens create deploy` |
| `CLOUDFLARE_API_TOKEN` | secret | Pages token, created in the Cloudflare dashboard |
| `CLOUDFLARE_ACCOUNT_ID` | secret | From `wrangler whoami` |
| `VITE_FIREBASE_*` (6) | variable | Firebase web config |
| `VITE_API_BASE_URL` | variable | e.g. `https://<app>.fly.dev/api` |

After the first deploy, three settings must be updated by hand to point at the new hostnames: `CORS_ALLOWED_ORIGINS` on Fly, the authorised domains list in the Firebase console, and the redirect URL in the Fitbit developer portal.

### Legacy hosts

`render.yaml` and `frontend/vercel.json` predate the move and are kept only so the project can still be stood up on those platforms.

`render.yaml` defines no worker service, so AI insight generation — a Celery task — has no process to run it there; jobs queue and never complete. The rest of the app is unaffected.

To build the frontend for any other host:

```bash
cd frontend
npm run build
# Deploy the 'dist' folder to your hosting service
```

## License

MIT License

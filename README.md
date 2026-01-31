# Sleep Tracker - Full Stack Web Application

A comprehensive sleep tracking application with AI-powered insights, Fitbit integration, and Firebase authentication.

## Features

- **User Authentication**: Secure login with Firebase (Email/Password + Google Sign-in)
- **Manual Sleep Logging**: Log your sleep with quality ratings and notes
- **Fitbit Integration**: Automatically sync sleep data from your Fitbit device
- **AI-Powered Insights**: Get personalized sleep analysis and recommendations
- **Interactive Dashboard**: Visualize your sleep patterns with charts
- **Sleep Goals**: Set and track your sleep targets

## Tech Stack

### Backend
- **Django 4.2**: Python web framework
- **Django REST Framework**: RESTful API
- **Firebase Admin SDK**: Server-side authentication
- **OpenAI GPT-4**: AI-powered insights
- **SQLite/PostgreSQL**: Database

### Frontend
- **React 18**: UI library
- **TypeScript**: Type-safe JavaScript
- **Vite**: Build tool
- **Tailwind CSS**: Styling
- **Chart.js**: Data visualization
- **Zustand**: State management
- **React Router**: Navigation

## Project Structure

```
sleep/
├── backend/                  # Django backend
│   ├── sleep_tracker/        # Main project settings
│   ├── users/                # User authentication & profiles
│   ├── sleep/                # Sleep records & goals
│   ├── fitbit_integration/   # Fitbit OAuth & sync
│   ├── ai_insights/          # AI-powered analysis
│   └── requirements.txt
│
├── frontend/                 # React frontend
│   ├── src/
│   │   ├── components/       # Reusable components
│   │   ├── pages/            # Page components
│   │   ├── services/         # API & Firebase services
│   │   ├── stores/           # Zustand state stores
│   │   └── config.ts         # Configuration
│   └── package.json
│
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Firebase project
- Fitbit Developer account (optional)
- OpenAI API key (optional, for AI insights)

### 1. Firebase Setup

1. Create a new project at [Firebase Console](https://console.firebase.google.com)
2. Enable Authentication with Email/Password and Google providers
3. Generate a new service account key:
   - Go to Project Settings > Service Accounts
   - Click "Generate new private key"
   - Save the JSON file securely

### 2. Fitbit Setup (Optional)

1. Register an app at [Fitbit Developer](https://dev.fitbit.com/apps)
2. Set OAuth 2.0 Application Type to "Personal"
3. Set Callback URL to `http://localhost:3000/fitbit/callback`
4. Note your Client ID and Client Secret

### 3. Backend Setup

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

### 4. Frontend Setup

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

### 5. Access the Application

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api
- Django Admin: http://localhost:8000/admin

## Configuration

### Backend Environment Variables

| Variable | Description |
|----------|-------------|
| `DJANGO_SECRET_KEY` | Django secret key |
| `DEBUG` | Enable debug mode |
| `FIREBASE_PROJECT_ID` | Firebase project ID |
| `FIREBASE_PRIVATE_KEY` | Firebase service account private key |
| `FIREBASE_CLIENT_EMAIL` | Firebase service account email |
| `FITBIT_CLIENT_ID` | Fitbit OAuth client ID |
| `FITBIT_CLIENT_SECRET` | Fitbit OAuth client secret |
| `OPENAI_API_KEY` | OpenAI API key for AI insights |

### Frontend Environment Variables

| Variable | Description |
|----------|-------------|
| `VITE_FIREBASE_API_KEY` | Firebase Web API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase auth domain |
| `VITE_FIREBASE_PROJECT_ID` | Firebase project ID |
| `VITE_API_BASE_URL` | Backend API URL |

## API Endpoints

### Authentication
All endpoints require Firebase ID token in Authorization header:
```
Authorization: Bearer <firebase-id-token>
```

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

### AI Insights
- `POST /api/insights/generate/` - Generate AI insights
- `GET /api/insights/list/` - List saved insights
- `GET /api/insights/{id}/` - Get insight details
- `GET /api/insights/tips/` - Get sleep tips
- `GET /api/insights/quick/` - Get quick summary

## Development

### Running Tests

```bash
# Backend tests
cd backend
python manage.py test

# Frontend tests
cd frontend
npm test
```

### Database Migrations

```bash
cd backend
python manage.py makemigrations
python manage.py migrate
```

## Deployment

### Backend (Example with Gunicorn)

```bash
pip install gunicorn
gunicorn sleep_tracker.wsgi:application --bind 0.0.0.0:8000
```

### Frontend (Build for Production)

```bash
cd frontend
npm run build
# Deploy the 'dist' folder to your hosting service
```

## License

MIT License
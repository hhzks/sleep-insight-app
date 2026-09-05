"""
Django settings for sleep_tracker project.
"""

import os
import sys
from pathlib import Path
from celery.schedules import crontab
from dotenv import load_dotenv
import dj_database_url

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-change-this-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party apps
    'rest_framework',
    'corsheaders',
    # Local apps
    'users',
    'sleep',
    'fitbit_integration',
    'ai_insights',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sleep_tracker.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'sleep_tracker.wsgi.application'

# Database
# Priority: DATABASE_URL (e.g. Render) > individual DB_* vars (Postgres) >
# a local SQLite database for development.
if os.environ.get('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.config(conn_max_age=600),
    }
elif os.environ.get('DB_NAME'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME'),
            'USER': os.environ.get('DB_USER', ''),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', ''),
            'PORT': os.environ.get('DB_PORT', ''),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Serve compressed static files with cache-busting hashes via WhiteNoise.
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model
AUTH_USER_MODEL = 'users.User'

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'users.authentication.FirebaseAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# CORS settings
CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:3000,http://127.0.0.1:3000'
).split(',')
CORS_ALLOW_CREDENTIALS = True

# Firebase settings
FIREBASE_CONFIG = {
    'PROJECT_ID': os.environ.get('FIREBASE_PROJECT_ID', ''),
    'PRIVATE_KEY': os.environ.get('FIREBASE_PRIVATE_KEY', ''),
    'CLIENT_EMAIL': os.environ.get('FIREBASE_CLIENT_EMAIL', ''),
}

# Fitbit API settings
FITBIT_CLIENT_ID = os.environ.get('FITBIT_CLIENT_ID', '')
FITBIT_CLIENT_SECRET = os.environ.get('FITBIT_CLIENT_SECRET', '')
FITBIT_REDIRECT_URI = os.environ.get('FITBIT_REDIRECT_URI', 'http://localhost:3000/fitbit/callback')

# Fernet keys for Fitbit token encryption at rest, newest first. Rotating:
# mint a key, prepend it, re-save the rows, then drop the trailing key.
# Unset is fatal at first use rather than at import, so management commands
# that never touch a token still run without it.
FITBIT_TOKEN_ENCRYPTION_KEYS = [
    key.strip()
    for key in os.environ.get('FITBIT_TOKEN_ENCRYPTION_KEYS', '').split(',')
    if key.strip()
]

# CI deliberately runs with no Fitbit credentials so the suite stays runnable
# from forks, and most of it touches FitbitToken. Rather than make the key an
# exception to that, tests fall back to a fixed throwaway one - reusing the
# same argv check that makes Celery tasks run eagerly, so a production process
# cannot reach this branch.
if not FITBIT_TOKEN_ENCRYPTION_KEYS and len(sys.argv) > 1 and sys.argv[1] == 'test':
    FITBIT_TOKEN_ENCRYPTION_KEYS = ['xUuBjSAdgcOFCM4kL1YIWy_ZBb0AKkFOAJhBTKPFuUo=']

# Consecutive authorisation failures before a user's Fitbit is disconnected.
# Only FitbitAuthError counts, so this is a tolerance for Fitbit briefly
# rejecting a grant it later honours - not for outages, which never count.
FITBIT_MAX_AUTH_FAILURES = int(os.environ.get('FITBIT_MAX_AUTH_FAILURES', '3'))

# How many days back each scheduled sync re-reads. Devices upload late and
# Fitbit revises staging after the fact, so a window wider than one night
# is what makes a missed run self-healing rather than a permanent gap.
FITBIT_SYNC_LOOKBACK_DAYS = int(os.environ.get('FITBIT_SYNC_LOOKBACK_DAYS', '3'))

# Local model (Ollama) settings for sleep insights.
# In production OLLAMA_BASE_URL points at an HTTPS reverse proxy that checks
# OLLAMA_API_KEY; locally it points at a bare Ollama with no token.
OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_API_KEY = os.environ.get('OLLAMA_API_KEY', '')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen2.5:7b-instruct')
OLLAMA_TIMEOUT_SECONDS = int(os.environ.get('OLLAMA_TIMEOUT_SECONDS', '300'))
OLLAMA_NUM_PREDICT = int(os.environ.get('OLLAMA_NUM_PREDICT', '1000'))
OLLAMA_TEMPERATURE = float(os.environ.get('OLLAMA_TEMPERATURE', '0.7'))
OLLAMA_INVALID_RETRIES = int(os.environ.get('OLLAMA_INVALID_RETRIES', '1'))

# Worst-case time one generation may legitimately take.
INSIGHT_WORST_CASE_SECONDS = OLLAMA_TIMEOUT_SECONDS * (1 + OLLAMA_INVALID_RETRIES)

# Celery's two kill switches, derived so that raising OLLAMA_TIMEOUT_SECONDS
# cannot silently invert the chain. Literals here would mean a raised Ollama
# timeout gets truncated by Celery instead - visible only as generations that
# mysteriously stop at the old bound.
#   soft: raises SoftTimeLimitExceeded, caught by run_insight_job's except
#   hard: SIGKILLs the worker child, leaving the row for the reaper
INSIGHT_TASK_SOFT_TIME_LIMIT = INSIGHT_WORST_CASE_SECONDS + 60
INSIGHT_TASK_TIME_LIMIT = INSIGHT_TASK_SOFT_TIME_LIMIT + 60

# Must exceed INSIGHT_TASK_TIME_LIMIT, or the reaper kills jobs Celery is
# still running. Enforced by the ai_insights.E001 system check.
INSIGHT_JOB_STALE_MINUTES = int(os.environ.get('INSIGHT_JOB_STALE_MINUTES', '15'))

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}

# Celery
# Broker only - no result backend. Job state lives on the InsightJob row,
# which the API already treats as the source of truth.
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = None

# Celery's Redis transport polls with BRPOP roughly 1-4x per second even when
# the queue is empty. At the default that is ~350k commands/day of pure idle
# chatter, which exhausts serverless-Redis quotas on its own. Generations take
# 2-3 minutes, so 5s of pickup latency is imperceptible. This is a cost
# control - do not remove it as a "tuning nicety".
CELERY_BROKER_TRANSPORT_OPTIONS = {'polling_interval': 5}

CELERY_TASK_ACKS_LATE = False
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Reaping used to happen as a side effect of a client polling a job. That
# coupled cleanup to traffic: with nobody polling, stale rows sat forever.
CELERY_BEAT_SCHEDULE = {
    'reap-stale-insight-jobs': {
        'task': 'ai_insights.reap_stale_jobs',
        'schedule': 300,  # every 5 minutes
    },
    # A single fixed-UTC run rather than per-user local time: each run
    # re-reads FITBIT_SYNC_LOOKBACK_DAYS, and imports are keyed on Fitbit's
    # logId, so a night that lands after the run is picked up by the next
    # one as an update. The hour therefore affects freshness, never
    # correctness. 09:00 UTC is late enough that most devices have uploaded.
    'nightly-fitbit-sync': {
        'task': 'fitbit_integration.sync_all_users',
        'schedule': crontab(hour=9, minute=0),
    },
}


def _celery_tasks_run_eagerly(argv):
    # argv[1] is the management command itself, so a command that merely
    # takes a 'test' argument cannot flip this on in a production process.
    return len(argv) > 1 and argv[1] == 'test'


# Tests run tasks inline so the suite needs no broker.
CELERY_TASK_ALWAYS_EAGER = _celery_tasks_run_eagerly(sys.argv)
CELERY_TASK_EAGER_PROPAGATES = True

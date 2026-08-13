"""
Django settings for sleep_tracker project.
"""

import os
from pathlib import Path
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

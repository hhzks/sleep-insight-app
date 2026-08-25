"""Celery application for background insight generation.

Task bodies live in <app>/tasks.py; this module only builds the app.
"""
import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sleep_tracker.settings')

app = Celery('sleep_tracker')

# All CELERY_-prefixed Django settings become Celery config.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Discovers tasks.py in every INSTALLED_APPS entry.
app.autodiscover_tasks()

# Sleep Tracker Django Project

# Imported here so the Celery app is configured whenever Django starts -
# this is what makes @shared_task registration work in web and worker alike.
from .celery import app as celery_app

__all__ = ('celery_app',)

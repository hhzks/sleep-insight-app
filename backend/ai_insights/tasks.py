"""Celery task definitions for insight generation.

Deliberately thin. All behaviour lives in jobs.py so it stays testable
without a broker, and so the queue can be swapped without touching logic.
"""
from celery import shared_task
from django.conf import settings

from .jobs import reap_stale_jobs, run_insight_job


@shared_task(
    name='ai_insights.generate_insight',
    soft_time_limit=settings.INSIGHT_TASK_SOFT_TIME_LIMIT,
    time_limit=settings.INSIGHT_TASK_TIME_LIMIT,
    max_retries=0,
)
def generate_insight_task(job_id):
    """Run one generation to a terminal status.

    SoftTimeLimitExceeded is caught by run_insight_job's broad except, which
    records error_code='internal' - intentional, not incidental.
    """
    run_insight_job(job_id)


@shared_task(name='ai_insights.reap_stale_jobs')
def reap_stale_jobs_task():
    """Scheduled cleanup. See CELERY_BEAT_SCHEDULE in settings.py."""
    return reap_stale_jobs()

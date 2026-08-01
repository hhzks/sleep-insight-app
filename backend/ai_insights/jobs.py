"""
Background execution of insight generation.

Jobs run in a daemon thread on the web process rather than a queue worker,
because Render has no free background-worker tier. The trade-off is that a
job dies if the instance restarts or spins down mid-generation; reap_stale_jobs
converts that into a clean failure instead of a job stuck in 'running'.

Swapping this module for Celery later leaves the InsightJob row and the API
untouched.
"""
import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.db.models import Q
from django.utils import timezone

from .models import InsightJob
from .services import generate_insights

logger = logging.getLogger(__name__)


def start_insight_job(user, days):
    """Queue a generation job. Returns (job, already_running).

    If the user already has an active job, that job is returned untouched and
    no new work is spawned.
    """
    reap_stale_jobs()

    existing = InsightJob.objects.filter(
        user=user, status__in=InsightJob.ACTIVE_STATUSES
    ).first()
    if existing is not None:
        return existing, True

    job = InsightJob.objects.create(user=user, days=days)
    _spawn_thread(job.id)
    return job, False


def _spawn_thread(job_id):
    """Start the worker thread. Patched in tests to run inline."""
    thread = threading.Thread(target=run_insight_job, args=(job_id,), daemon=True)
    thread.start()


def run_insight_job(job_id, provider=None):
    """Execute one job to completion, recording the outcome on the row."""
    try:
        job = InsightJob.objects.filter(pk=job_id).first()
        if job is None:
            logger.warning('insight job %s vanished before it ran', job_id)
            return

        job.status = InsightJob.STATUS_RUNNING
        job.started_at = timezone.now()
        job.save(update_fields=['status', 'started_at'])

        try:
            result = generate_insights(job.user, job.days, provider=provider)
        except Exception as exc:  # noqa: BLE001 - a thread must never die silently
            logger.exception('insight job %s failed', job_id)
            job.status = InsightJob.STATUS_FAILED
            job.error_code = 'internal'
            job.error_detail = str(exc)
        else:
            job.status = InsightJob.STATUS_SUCCEEDED
            job.source = result.source
            job.result = result.payload
            job.error_code = result.error_code
            job.error_detail = result.error_detail

        job.finished_at = timezone.now()
        job.save(update_fields=[
            'status', 'source', 'result', 'error_code', 'error_detail', 'finished_at',
        ])
    finally:
        # Django only closes connections for request threads. Without this a
        # worker thread leaks one connection per job.
        #
        # Guarded on in_atomic_block: a real worker thread's connection is
        # never inside an atomic block, so this always fires in production.
        # It only skips when this function is invoked synchronously from
        # inside a wrapping transaction (as tests do, calling it directly
        # rather than through _spawn_thread) — there, Django's close()
        # doesn't actually free anything anyway (it just marks the
        # connection dirty for the enclosing atomic() to roll back), so
        # calling it would only corrupt the caller's transaction/connection
        # without preventing any leak.
        if not connection.in_atomic_block:
            connection.close()


def reap_stale_jobs():
    """Fail jobs that outlived the stale window. Returns how many were reaped."""
    cutoff = timezone.now() - timedelta(minutes=settings.INSIGHT_JOB_STALE_MINUTES)

    stale = InsightJob.objects.filter(
        Q(status=InsightJob.STATUS_RUNNING, started_at__lt=cutoff)
        | Q(status=InsightJob.STATUS_QUEUED, created_at__lt=cutoff)
    )

    reaped = stale.update(
        status=InsightJob.STATUS_FAILED,
        error_code='internal',
        error_detail='Job exceeded the stale threshold and was reaped.',
        finished_at=timezone.now(),
    )
    if reaped:
        logger.error('reaped %s stale insight job(s)', reaped)
    return reaped

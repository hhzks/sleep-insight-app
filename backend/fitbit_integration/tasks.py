"""Celery task definitions for the nightly Fitbit sync.

Deliberately thin, matching ai_insights: all behaviour lives in sync.py so
it stays testable without a broker.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import FitbitToken
from .services import FitbitError
from .sync import sync_user_sleep

logger = logging.getLogger(__name__)


@shared_task(name='fitbit_integration.sync_all_users')
def sync_all_users_task():
    """Dispatch one sync task per user who opted into nightly sync.

    Fan-out rather than one long loop: a single user's failure cannot abort
    everyone else's sync, and each user's result lands in their own sync log.
    Returns the number of users dispatched.
    """
    user_ids = FitbitToken.objects.filter(auto_sync=True).values_list('user_id', flat=True)

    dispatched = 0
    for user_id in user_ids:
        sync_user_task.delay(user_id)
        dispatched += 1

    logger.info('Nightly Fitbit sync dispatched for %s user(s)', dispatched)
    return dispatched


@shared_task(name='fitbit_integration.sync_user')
def sync_user_task(user_id):
    """Sync one user's recent nights. Returns the number of records synced.

    Never raises for an expected Fitbit failure: sync_user_sleep has already
    written the failed sync log and, for a rejected authorisation, counted it
    towards disconnection. Retrying here would only duplicate work that
    tomorrow's run repeats anyway.
    """
    user = get_user_model().objects.filter(pk=user_id).first()
    if user is None:
        # Queue time separates dispatch from pickup; the account may be gone.
        logger.info('Skipping Fitbit sync for missing user %s', user_id)
        return 0

    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=settings.FITBIT_SYNC_LOOKBACK_DAYS)

    try:
        outcome = sync_user_sleep(user, start_date, end_date)
    except FitbitError as exc:
        logger.warning('Fitbit sync failed for user %s: %s', user_id, exc)
        return 0

    return outcome.records_synced

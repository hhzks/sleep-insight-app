"""Importing Fitbit sleep data.

The single place sleep records arrive from Fitbit. Both entry points call
it - the "Sync now" button and the nightly scheduled task - so failure
accounting cannot drift between them. Task bodies stay in tasks.py; this
module has no Celery import and is testable without a broker, matching
the split ai_insights uses.
"""
import logging
from dataclasses import dataclass
from datetime import date

from django.conf import settings
from django.db import transaction

from sleep.models import SleepRecord, SleepStageData

from .models import FitbitSyncLog, FitbitToken
from .services import FitbitAuthError, FitbitError, FitbitService, parse_fitbit_sleep_data

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncOutcome:
    """What a completed sync imported."""

    records_synced: int
    start_date: date
    end_date: date


def sync_user_sleep(user, start_date, end_date):
    """Import one user's sleep records for a date range.

    Returns a SyncOutcome. Raises FitbitError (already recorded in a failed
    FitbitSyncLog) when the import could not complete, so callers only have
    to decide how to *report* a failure, never how to record one.
    """
    sync_log = FitbitSyncLog.objects.create(
        user=user,
        sync_date=end_date,
        status='pending',
    )

    service = FitbitService(user=user)

    try:
        sleep_data = service.get_sleep_log_range(
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
        )
        records_synced = _save_records(user, parse_fitbit_sleep_data(sleep_data))
    except FitbitError as exc:
        _record_failure(user, sync_log, exc)
        raise
    except Exception as exc:
        # An unexpected fault must still leave the log terminal rather than
        # stranding a 'pending' row that nothing will ever finish.
        _record_failure(user, sync_log, exc)
        raise

    sync_log.status = 'success'
    sync_log.records_synced = records_synced
    sync_log.save(update_fields=['status', 'records_synced'])

    _clear_auth_failures(user)

    return SyncOutcome(
        records_synced=records_synced,
        start_date=start_date,
        end_date=end_date,
    )


def _save_records(user, records):
    """Write parsed records, updating any night already imported."""
    saved = 0

    for record_data in records:
        stage_data = record_data.pop('stage_data', [])

        with transaction.atomic():
            sleep_record, _ = SleepRecord.objects.update_or_create(
                user=user,
                external_id=record_data['external_id'],
                defaults={
                    'date_of_sleep': record_data['date_of_sleep'],
                    'start_time': record_data['start_time'],
                    'end_time': record_data['end_time'],
                    'duration_minutes': record_data['duration_minutes'],
                    'minutes_asleep': record_data['minutes_asleep'],
                    'minutes_awake': record_data['minutes_awake'],
                    'efficiency': record_data['efficiency'],
                    'is_main_sleep': record_data['is_main_sleep'],
                    'sleep_type': record_data['sleep_type'],
                    'source': 'fitbit',
                    'deep_sleep_minutes': record_data.get('deep_sleep_minutes'),
                    'light_sleep_minutes': record_data.get('light_sleep_minutes'),
                    'rem_sleep_minutes': record_data.get('rem_sleep_minutes'),
                },
            )

            if stage_data:
                # Replace wholesale: Fitbit revises a night's staging, and
                # stage rows carry no external identity to match on.
                SleepStageData.objects.filter(sleep_record=sleep_record).delete()
                SleepStageData.objects.bulk_create([
                    SleepStageData(
                        sleep_record=sleep_record,
                        stage=stage['stage'],
                        start_time=stage['start_time'],
                        duration_seconds=stage['duration_seconds'],
                    )
                    for stage in stage_data
                ])

        saved += 1

    return saved


def _record_failure(user, sync_log, exc):
    """Finalise the sync log, and count the failure if it was an auth failure."""
    sync_log.status = 'failed'
    sync_log.error_message = str(exc)
    sync_log.save(update_fields=['status', 'error_message'])

    if isinstance(exc, FitbitAuthError):
        _count_auth_failure(user, sync_log)


def _count_auth_failure(user, sync_log):
    """Advance the disconnect countdown, disconnecting at the limit.

    Only reached for FitbitAuthError, so an outage on Fitbit's side can
    never disconnect anyone.
    """
    token = FitbitToken.objects.filter(user=user).first()
    if token is None:
        return

    token.consecutive_auth_failures += 1

    if token.consecutive_auth_failures >= settings.FITBIT_MAX_AUTH_FAILURES:
        # Deleting the row is exactly what manual disconnection does, so the
        # UI reports "not connected" with no extra state to interpret.
        token.delete()
        sync_log.error_message = (
            'Fitbit authorisation was rejected repeatedly, so the account has '
            'been disconnected. Reconnect Fitbit to resume syncing.'
        )
        sync_log.save(update_fields=['error_message'])
        logger.warning(
            'Disconnected Fitbit for user %s after repeated auth failures', user.pk
        )
        return

    token.save(update_fields=['consecutive_auth_failures'])


def _clear_auth_failures(user):
    """A successful sync retires any failure history."""
    FitbitToken.objects.filter(user=user).exclude(
        consecutive_auth_failures=0
    ).update(consecutive_auth_failures=0)

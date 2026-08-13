"""The Celery task is a thin wrapper over run_insight_job."""
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_insights.jobs import start_insight_job
from ai_insights.models import InsightJob
from ai_insights.services import SOURCE_LOCAL_MODEL, InsightsResult
from ai_insights.tasks import generate_insight_task, reap_stale_jobs_task
from sleep_tracker.celery import app

User = get_user_model()

PAYLOAD = {'overall_assessment': 'ok', 'score': 77, 'insights': [], 'tips': ['sleep more']}


class GenerateInsightTaskTests(TestCase):
    def test_registered_under_a_stable_name(self):
        # The name is a wire contract: a queued message names its task, so
        # renaming this strands anything already in the broker.
        self.assertEqual(generate_insight_task.name, 'ai_insights.generate_insight')

    def test_time_limits_come_from_settings(self):
        self.assertEqual(generate_insight_task.soft_time_limit, settings.INSIGHT_TASK_SOFT_TIME_LIMIT)
        self.assertEqual(generate_insight_task.time_limit, settings.INSIGHT_TASK_TIME_LIMIT)

    def test_does_not_retry(self):
        # A redelivered 3-minute generation is duplicated expensive work on a
        # 2-core box; the reaper plus a user-initiated retry is the design.
        self.assertEqual(generate_insight_task.max_retries, 0)

    @patch('ai_insights.tasks.run_insight_job')
    def test_delegates_to_run_insight_job(self, mock_run):
        generate_insight_task.apply(args=['abc-123'])
        mock_run.assert_called_once_with('abc-123')


class BeatScheduleTests(TestCase):
    def test_reaper_is_scheduled(self):
        entry = settings.CELERY_BEAT_SCHEDULE['reap-stale-insight-jobs']
        self.assertEqual(entry['task'], 'ai_insights.reap_stale_jobs')

        # A name matching the string in this test proves nothing on its own:
        # settings.py and tasks.py could both drift to the same wrong string,
        # or autodiscover_tasks() could silently stop finding tasks.py, and
        # this comparison would still pass. Checking the app's actual task
        # registry catches that - a scheduled name beat cannot dispatch
        # surfaces in production only as "Received unregistered task".
        self.assertIn(entry['task'], app.tasks)

    def test_reaper_runs_more_often_than_the_stale_window(self):
        # A schedule slower than the window means jobs sit failed-but-unreaped
        # for up to one extra period, which users see as a hung spinner.
        entry = settings.CELERY_BEAT_SCHEDULE['reap-stale-insight-jobs']
        self.assertLess(entry['schedule'], settings.INSIGHT_JOB_STALE_MINUTES * 60)


class ReapTaskTests(TestCase):
    @patch('ai_insights.tasks.reap_stale_jobs')
    def test_reap_task_delegates(self, mock_reap):
        mock_reap.return_value = 3
        self.assertEqual(reap_stale_jobs_task.apply().get(), 3)
        mock_reap.assert_called_once_with()


class RealDispatchTests(TestCase):
    """Drives a job through the actual dispatch mechanism end to end.

    Every other test in this suite mocks at the `_enqueue` or
    `generate_insight_task` seam, so nothing exercises `_enqueue` ->
    `transaction.on_commit` -> `generate_insight_task.delay` -> Celery's
    eager execution -> `run_insight_job` as one chain. That chain is exactly
    where dispatch breaks in practice: a dropped `autodiscover_tasks()`, a
    task whose body stops calling `run_insight_job`, or an `on_commit`
    callback that never fires would all sail through the mocked tests.

    Only `generate_insights` is patched (so this makes no network call);
    everything downstream of it - task registration, `.delay()`, and Celery
    running the task inline under `CELERY_TASK_ALWAYS_EAGER` - is real.
    """

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')

    @patch('ai_insights.jobs.generate_insights')
    def test_start_insight_job_reaches_succeeded_through_real_dispatch(self, mock_generate):
        mock_generate.return_value = InsightsResult(payload=PAYLOAD, source=SOURCE_LOCAL_MODEL)

        with self.captureOnCommitCallbacks(execute=True):
            job, already_running = start_insight_job(self.user, days=30)

        self.assertFalse(already_running)
        job.refresh_from_db()
        self.assertEqual(job.status, InsightJob.STATUS_SUCCEEDED)
        self.assertEqual(job.source, SOURCE_LOCAL_MODEL)
        self.assertEqual(job.result, PAYLOAD)
        mock_generate.assert_called_once_with(self.user, 30, provider=None)

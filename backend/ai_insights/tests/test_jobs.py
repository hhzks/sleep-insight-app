"""
Background execution, dedupe, and stale-job reaping.
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from ai_insights.jobs import reap_stale_jobs, run_insight_job, start_insight_job
from ai_insights.models import InsightJob
from ai_insights.providers.ollama import OllamaUnavailable
from ai_insights.services import SOURCE_LOCAL_MODEL, SOURCE_RULE_BASED
from sleep.models import SleepRecord

User = get_user_model()

MODEL_PAYLOAD = {
    'overall_assessment': 'Solid week.',
    'score': 81,
    'insights': [{
        'type': 'pattern',
        'priority': 'low',
        'title': 'Consistent Schedule',
        'content': 'Your bedtime barely moved this week.',
    }],
    'tips': ['Keep it up'],
}


class FakeProvider:
    """Returns a payload or raises, like OllamaClient."""

    def __init__(self, result):
        self.result = result

    def generate(self, system_prompt, user_prompt, schema):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def night(user, days_ago):
    """Create one main-sleep record `days_ago` nights back."""
    end = timezone.now() - timedelta(days=days_ago)
    return SleepRecord.objects.create(
        user=user, date_of_sleep=end.date(),
        start_time=end - timedelta(hours=8), end_time=end,
        duration_minutes=480, minutes_asleep=430, minutes_awake=50,
        efficiency=90, source='manual', is_main_sleep=True,
    )


class StartInsightJobTests(TestCase):
    """Starting a job queues exactly one unit of work per user."""

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')

    @patch('ai_insights.jobs._spawn_thread')
    def test_creates_a_queued_job_and_spawns_a_thread(self, mock_spawn):
        job, already_running = start_insight_job(self.user, days=30)
        self.assertFalse(already_running)
        self.assertEqual(job.status, InsightJob.STATUS_QUEUED)
        self.assertEqual(job.days, 30)
        mock_spawn.assert_called_once_with(job.id)

    @patch('ai_insights.jobs._spawn_thread')
    def test_second_call_returns_the_existing_job(self, mock_spawn):
        first, _ = start_insight_job(self.user, days=30)
        second, already_running = start_insight_job(self.user, days=7)
        self.assertTrue(already_running)
        self.assertEqual(first.id, second.id)
        self.assertEqual(InsightJob.objects.count(), 1)
        self.assertEqual(mock_spawn.call_count, 1)

    @patch('ai_insights.jobs._spawn_thread')
    def test_other_users_jobs_do_not_block(self, mock_spawn):
        other = User.objects.create(email='other@example.com', firebase_uid='uid-2')
        start_insight_job(other, days=30)
        _, already_running = start_insight_job(self.user, days=30)
        self.assertFalse(already_running)
        self.assertEqual(InsightJob.objects.count(), 2)

    @patch('ai_insights.jobs._spawn_thread')
    def test_finished_job_does_not_block_a_new_one(self, mock_spawn):
        first, _ = start_insight_job(self.user, days=30)
        first.status = InsightJob.STATUS_SUCCEEDED
        first.save()
        second, already_running = start_insight_job(self.user, days=30)
        self.assertFalse(already_running)
        self.assertNotEqual(first.id, second.id)


class RunInsightJobTests(TestCase):
    """The job body records its outcome on the row."""

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')
        for days_ago in range(1, 8):
            night(self.user, days_ago)

    def test_success_stores_result_and_source(self):
        job = InsightJob.objects.create(user=self.user, days=30)
        run_insight_job(job.id, provider=FakeProvider(MODEL_PAYLOAD))
        job.refresh_from_db()
        self.assertEqual(job.status, InsightJob.STATUS_SUCCEEDED)
        self.assertEqual(job.source, SOURCE_LOCAL_MODEL)
        self.assertEqual(job.result['score'], 81)
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.finished_at)

    def test_model_failure_still_succeeds_with_rule_based_source(self):
        job = InsightJob.objects.create(user=self.user, days=30)
        run_insight_job(job.id, provider=FakeProvider(OllamaUnavailable('refused')))
        job.refresh_from_db()
        self.assertEqual(job.status, InsightJob.STATUS_SUCCEEDED)
        self.assertEqual(job.source, SOURCE_RULE_BASED)
        self.assertEqual(job.error_code, 'unreachable')
        self.assertIn('refused', job.error_detail)

    def test_unexpected_exception_marks_the_job_failed(self):
        job = InsightJob.objects.create(user=self.user, days=30)
        with patch('ai_insights.jobs.generate_insights', side_effect=ValueError('boom')):
            run_insight_job(job.id)
        job.refresh_from_db()
        self.assertEqual(job.status, InsightJob.STATUS_FAILED)
        self.assertEqual(job.error_code, 'internal')
        self.assertIn('boom', job.error_detail)

    def test_missing_job_id_creates_nothing_and_does_not_raise(self):
        import uuid
        before = InsightJob.objects.count()
        run_insight_job(uuid.uuid4())
        self.assertEqual(InsightJob.objects.count(), before)


@override_settings(INSIGHT_JOB_STALE_MINUTES=15)
class ReapStaleJobsTests(TestCase):
    """Jobs killed by a restart must not sit in 'running' forever."""

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')

    def test_reaps_running_job_past_the_threshold(self):
        job = InsightJob.objects.create(
            user=self.user, days=30, status=InsightJob.STATUS_RUNNING,
            started_at=timezone.now() - timedelta(minutes=20),
        )
        self.assertEqual(reap_stale_jobs(), 1)
        job.refresh_from_db()
        self.assertEqual(job.status, InsightJob.STATUS_FAILED)
        self.assertEqual(job.error_code, 'internal')

    def test_leaves_a_recently_started_job_alone(self):
        job = InsightJob.objects.create(
            user=self.user, days=30, status=InsightJob.STATUS_RUNNING,
            started_at=timezone.now() - timedelta(minutes=5),
        )
        self.assertEqual(reap_stale_jobs(), 0)
        job.refresh_from_db()
        self.assertEqual(job.status, InsightJob.STATUS_RUNNING)

    def test_reaps_a_job_that_never_started(self):
        job = InsightJob.objects.create(user=self.user, days=30)
        InsightJob.objects.filter(pk=job.pk).update(
            created_at=timezone.now() - timedelta(minutes=20)
        )
        self.assertEqual(reap_stale_jobs(), 1)
        job.refresh_from_db()
        self.assertEqual(job.status, InsightJob.STATUS_FAILED)

    def test_leaves_terminal_jobs_alone(self):
        InsightJob.objects.create(
            user=self.user, days=30, status=InsightJob.STATUS_SUCCEEDED,
            started_at=timezone.now() - timedelta(hours=3),
        )
        self.assertEqual(reap_stale_jobs(), 0)

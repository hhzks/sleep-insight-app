"""
The job API: kick off generation, poll it, resume it.
"""
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from ai_insights.models import InsightJob
from ai_insights.services import SOURCE_LOCAL_MODEL, SOURCE_RULE_BASED
from sleep.models import SleepRecord

User = get_user_model()

PAYLOAD = {'overall_assessment': 'ok', 'score': 77, 'insights': [], 'tips': ['sleep more']}


def night(user, days_ago):
    """Create one main-sleep record `days_ago` nights back."""
    end = timezone.now() - timedelta(days=days_ago)
    return SleepRecord.objects.create(
        user=user, date_of_sleep=end.date(),
        start_time=end - timedelta(hours=8), end_time=end,
        duration_minutes=480, minutes_asleep=430, minutes_awake=50,
        efficiency=90, source='manual', is_main_sleep=True,
    )


class GenerateEndpointTests(TestCase):
    """POST /generate/ queues work and returns immediately."""

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        for days_ago in range(1, 8):
            night(self.user, days_ago)

    @patch('ai_insights.jobs._spawn_thread')
    def test_returns_202_with_a_job_id(self, mock_spawn):
        response = self.client.post('/api/insights/generate/', {'days': 30}, format='json')
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data['status'], 'queued')
        self.assertFalse(response.data['already_running'])
        self.assertTrue(InsightJob.objects.filter(id=response.data['job_id']).exists())

    @patch('ai_insights.jobs._spawn_thread')
    def test_second_request_reports_already_running(self, mock_spawn):
        first = self.client.post('/api/insights/generate/', {'days': 30}, format='json')
        second = self.client.post('/api/insights/generate/', {'days': 30}, format='json')
        self.assertEqual(second.status_code, 202)
        self.assertTrue(second.data['already_running'])
        self.assertEqual(first.data['job_id'], second.data['job_id'])

    @patch('ai_insights.jobs._spawn_thread')
    def test_clamps_the_days_parameter(self, mock_spawn):
        response = self.client.post('/api/insights/generate/', {'days': 5000}, format='json')
        job = InsightJob.objects.get(id=response.data['job_id'])
        self.assertEqual(job.days, 365)

    @patch('ai_insights.jobs._spawn_thread')
    def test_defaults_days_when_missing_or_invalid(self, mock_spawn):
        response = self.client.post('/api/insights/generate/', {'days': 'lots'}, format='json')
        self.assertEqual(InsightJob.objects.get(id=response.data['job_id']).days, 30)

    def test_requires_authentication(self):
        self.assertEqual(APIClient().post('/api/insights/generate/').status_code, 401)


class JobPollingTests(TestCase):
    """GET /jobs/<id>/ reports progress and results."""

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_running_job_reports_running(self):
        job = InsightJob.objects.create(
            user=self.user, days=30, status=InsightJob.STATUS_RUNNING,
            started_at=timezone.now(),
        )
        response = self.client.get(f'/api/insights/jobs/{job.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'running')

    def test_succeeded_job_returns_the_result(self):
        job = InsightJob.objects.create(
            user=self.user, days=30, status=InsightJob.STATUS_SUCCEEDED,
            source=SOURCE_LOCAL_MODEL, result=PAYLOAD,
        )
        response = self.client.get(f'/api/insights/jobs/{job.id}/')
        self.assertEqual(response.data['result'], PAYLOAD)
        self.assertEqual(response.data['source'], SOURCE_LOCAL_MODEL)
        self.assertNotIn('notice', response.data)

    def test_degraded_job_carries_a_notice(self):
        job = InsightJob.objects.create(
            user=self.user, days=30, status=InsightJob.STATUS_SUCCEEDED,
            source=SOURCE_RULE_BASED, result=PAYLOAD, error_code='timeout',
            error_detail='no response within 300s',
        )
        response = self.client.get(f'/api/insights/jobs/{job.id}/')
        self.assertIn('notice', response.data)
        self.assertNotIn('300s', str(response.data))

    def test_another_users_job_is_not_found(self):
        other = User.objects.create(email='other@example.com', firebase_uid='uid-2')
        job = InsightJob.objects.create(user=other, days=30)
        self.assertEqual(self.client.get(f'/api/insights/jobs/{job.id}/').status_code, 404)

    def test_unknown_job_is_not_found(self):
        self.assertEqual(
            self.client.get(f'/api/insights/jobs/{uuid.uuid4()}/').status_code, 404
        )

    def test_requires_authentication(self):
        job = InsightJob.objects.create(user=self.user, days=30)
        self.assertEqual(APIClient().get(f'/api/insights/jobs/{job.id}/').status_code, 401)


@override_settings(INSIGHT_JOB_STALE_MINUTES=15)
class StaleJobReapingOnPollTests(TestCase):
    """A job killed by a restart resolves to failed on the next poll."""

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_poll_reaps_a_stale_job(self):
        job = InsightJob.objects.create(
            user=self.user, days=30, status=InsightJob.STATUS_RUNNING,
            started_at=timezone.now() - timedelta(minutes=30),
        )
        response = self.client.get(f'/api/insights/jobs/{job.id}/')
        self.assertEqual(response.data['status'], 'failed')
        self.assertEqual(response.data['error'], InsightJob.FAILED_MESSAGE)


class ActiveJobTests(TestCase):
    """GET /jobs/active/ lets the UI resume polling after a reload."""

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_returns_204_when_nothing_is_running(self):
        self.assertEqual(self.client.get('/api/insights/jobs/active/').status_code, 204)

    def test_returns_the_active_job(self):
        job = InsightJob.objects.create(
            user=self.user, days=30, status=InsightJob.STATUS_RUNNING,
            started_at=timezone.now(),
        )
        response = self.client.get('/api/insights/jobs/active/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['job_id'], str(job.id))

    def test_ignores_finished_jobs(self):
        InsightJob.objects.create(
            user=self.user, days=30, status=InsightJob.STATUS_SUCCEEDED,
            source=SOURCE_LOCAL_MODEL, result=PAYLOAD,
        )
        self.assertEqual(self.client.get('/api/insights/jobs/active/').status_code, 204)

    def test_ignores_other_users_jobs(self):
        other = User.objects.create(email='other@example.com', firebase_uid='uid-2')
        InsightJob.objects.create(user=other, days=30, status=InsightJob.STATUS_RUNNING)
        self.assertEqual(self.client.get('/api/insights/jobs/active/').status_code, 204)

"""
The InsightJob record and its API representation.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_insights.models import InsightJob
from ai_insights.services import DEGRADED_NOTICE, SOURCE_LOCAL_MODEL, SOURCE_RULE_BASED

User = get_user_model()

PAYLOAD = {'overall_assessment': 'ok', 'score': 80, 'insights': [], 'tips': []}


class InsightJobResponseTests(TestCase):
    """to_response() is the only shape the API returns for a job."""

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')

    def test_running_job_reports_status_only(self):
        job = InsightJob.objects.create(user=self.user, days=30, status=InsightJob.STATUS_RUNNING)
        self.assertEqual(job.to_response(), {'job_id': str(job.id), 'status': 'running'})

    def test_successful_model_job_returns_result_without_notice(self):
        job = InsightJob.objects.create(
            user=self.user, days=30, status=InsightJob.STATUS_SUCCEEDED,
            source=SOURCE_LOCAL_MODEL, result=PAYLOAD,
        )
        response = job.to_response()
        self.assertEqual(response['source'], SOURCE_LOCAL_MODEL)
        self.assertEqual(response['result'], PAYLOAD)
        self.assertNotIn('notice', response)

    def test_degraded_job_carries_the_notice(self):
        job = InsightJob.objects.create(
            user=self.user, days=30, status=InsightJob.STATUS_SUCCEEDED,
            source=SOURCE_RULE_BASED, result=PAYLOAD, error_code='unreachable',
            error_detail='connection refused to https://llm.example.com',
        )
        response = job.to_response()
        self.assertEqual(response['notice'], DEGRADED_NOTICE)
        self.assertEqual(response['source'], SOURCE_RULE_BASED)

    def test_response_never_leaks_operator_detail(self):
        job = InsightJob.objects.create(
            user=self.user, days=30, status=InsightJob.STATUS_SUCCEEDED,
            source=SOURCE_RULE_BASED, result=PAYLOAD, error_code='unreachable',
            error_detail='connection refused to https://llm.example.com',
        )
        serialized = str(job.to_response())
        self.assertNotIn('llm.example.com', serialized)
        self.assertNotIn('unreachable', serialized)

    def test_failed_job_returns_generic_message(self):
        job = InsightJob.objects.create(
            user=self.user, days=30, status=InsightJob.STATUS_FAILED,
            error_code='internal', error_detail='ZeroDivisionError at line 42',
        )
        response = job.to_response()
        self.assertEqual(response['error'], InsightJob.FAILED_MESSAGE)
        self.assertNotIn('ZeroDivisionError', str(response))


class InsightJobStringContractTests(TestCase):
    """Pin the verbatim literal strings that are contract with the frontend.

    test_degraded_job_carries_the_notice above compares the response against
    the DEGRADED_NOTICE constant, which would not catch a typo in the
    constant itself. These tests pin the literal values.
    """

    def test_degraded_notice_matches_the_exact_contract_string(self):
        self.assertEqual(
            DEGRADED_NOTICE,
            'Your AI model was unavailable, so these insights were generated from built-in rules.',
        )

    def test_failed_message_matches_the_exact_contract_string(self):
        self.assertEqual(
            InsightJob.FAILED_MESSAGE,
            'Insight generation could not be completed. Please try again.',
        )

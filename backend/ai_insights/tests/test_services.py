"""
Insight generation orchestration: model, validation, fallback, persistence.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from ai_insights.models import SleepInsight
from ai_insights.providers.ollama import OllamaTimeout, OllamaUnavailable
from ai_insights.services import (
    SOURCE_INSUFFICIENT_DATA,
    SOURCE_LOCAL_MODEL,
    SOURCE_RULE_BASED,
    generate_insights,
)
from sleep.models import SleepRecord

User = get_user_model()

MODEL_PAYLOAD = {
    'overall_assessment': 'Your sleep is short but efficient.',
    'score': 72,
    'insights': [
        {
            'type': 'recommendation',
            'priority': 'medium',
            'title': 'Extend Your Sleep Window',
            'content': 'Aim to be in bed 30 minutes earlier.',
        }
    ],
    'tips': ['Dim the lights an hour before bed'],
}


class FakeProvider:
    """Stands in for OllamaClient; scripted to succeed or fail on demand."""

    def __init__(self, results):
        # `results` is a list of payloads to return or exceptions to raise.
        self.results = list(results)
        self.calls = 0

    def generate(self, system_prompt, user_prompt, schema):
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def night(user, days_ago):
    """Create one main-sleep record `days_ago` nights back."""
    end = timezone.now() - timedelta(days=days_ago)
    return SleepRecord.objects.create(
        user=user,
        date_of_sleep=end.date(),
        start_time=end - timedelta(hours=8),
        end_time=end,
        duration_minutes=480,
        minutes_asleep=400,
        minutes_awake=80,
        efficiency=83,
        source='manual',
        is_main_sleep=True,
    )


class GenerateInsightsTests(TestCase):
    """The model is preferred; every failure degrades to rule-based."""

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')
        for days_ago in range(1, 8):
            night(self.user, days_ago)

    def test_model_success_reports_local_model_source(self):
        provider = FakeProvider([MODEL_PAYLOAD])
        result = generate_insights(self.user, days=30, provider=provider)
        self.assertEqual(result.source, SOURCE_LOCAL_MODEL)
        self.assertEqual(result.payload['score'], 72)
        self.assertIsNone(result.error_code)
        self.assertEqual(provider.calls, 1)

    def test_model_success_persists_insight_rows(self):
        generate_insights(self.user, days=30, provider=FakeProvider([MODEL_PAYLOAD]))
        rows = SleepInsight.objects.filter(user=self.user)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().title, 'Extend Your Sleep Window')

    def test_unreachable_server_falls_back_to_rules(self):
        provider = FakeProvider([OllamaUnavailable('refused')])
        result = generate_insights(self.user, days=30, provider=provider)
        self.assertEqual(result.source, SOURCE_RULE_BASED)
        self.assertEqual(result.error_code, 'unreachable')
        self.assertTrue(result.payload['insights'])

    def test_timeout_falls_back_with_timeout_code(self):
        result = generate_insights(
            self.user, days=30, provider=FakeProvider([OllamaTimeout('slow')])
        )
        self.assertEqual(result.source, SOURCE_RULE_BASED)
        self.assertEqual(result.error_code, 'timeout')

    def test_fallback_still_persists_insight_rows(self):
        generate_insights(
            self.user, days=30, provider=FakeProvider([OllamaUnavailable('refused')])
        )
        self.assertTrue(SleepInsight.objects.filter(user=self.user).exists())

    def test_invalid_output_is_retried_once_then_succeeds(self):
        provider = FakeProvider([{'nonsense': True}, MODEL_PAYLOAD])
        result = generate_insights(self.user, days=30, provider=provider)
        self.assertEqual(provider.calls, 2)
        self.assertEqual(result.source, SOURCE_LOCAL_MODEL)

    def test_invalid_output_twice_falls_back(self):
        provider = FakeProvider([{'nonsense': True}, {'still': 'wrong'}])
        result = generate_insights(self.user, days=30, provider=provider)
        self.assertEqual(provider.calls, 2)
        self.assertEqual(result.source, SOURCE_RULE_BASED)
        self.assertEqual(result.error_code, 'invalid_response')

    def test_error_detail_is_recorded_for_the_operator(self):
        result = generate_insights(
            self.user, days=30, provider=FakeProvider([OllamaUnavailable('refused')])
        )
        self.assertIn('refused', result.error_detail)


class GenerateInsightsWithoutDataTests(TestCase):
    """A user with no records never reaches the model."""

    def setUp(self):
        self.user = User.objects.create(email='new@example.com', firebase_uid='uid-2')

    def test_skips_the_model_entirely(self):
        provider = FakeProvider([MODEL_PAYLOAD])
        result = generate_insights(self.user, days=30, provider=provider)
        self.assertEqual(provider.calls, 0)
        self.assertEqual(result.source, SOURCE_INSUFFICIENT_DATA)
        self.assertIsNone(result.payload['score'])

    def test_persists_nothing(self):
        generate_insights(self.user, days=30, provider=FakeProvider([MODEL_PAYLOAD]))
        self.assertFalse(SleepInsight.objects.filter(user=self.user).exists())

"""
Configuration for the local model provider.
"""
from django.conf import settings
from django.test import TestCase, override_settings

from ai_insights.apps import (
    check_ollama_base_url_has_a_scheme,
    check_stale_window_covers_worst_case,
)


class OllamaSettingsTests(TestCase):
    """Ollama config must be present with safe local-dev defaults."""

    def test_defaults_are_present(self):
        self.assertEqual(settings.OLLAMA_BASE_URL, 'http://localhost:11434')
        self.assertEqual(settings.OLLAMA_API_KEY, '')
        self.assertEqual(settings.OLLAMA_MODEL, 'qwen2.5:7b-instruct')
        self.assertEqual(settings.OLLAMA_TIMEOUT_SECONDS, 300)
        self.assertEqual(settings.OLLAMA_NUM_PREDICT, 1000)
        self.assertEqual(settings.OLLAMA_TEMPERATURE, 0.7)
        self.assertEqual(settings.OLLAMA_INVALID_RETRIES, 1)
        self.assertEqual(settings.INSIGHT_JOB_STALE_MINUTES, 15)

    def test_cloud_provider_settings_are_gone(self):
        for name in ('AI_PROVIDER', 'OPENAI_API_KEY', 'GEMINI_API_KEY'):
            self.assertFalse(hasattr(settings, name), f'{name} should be removed')

    def test_stale_window_exceeds_worst_case_generation(self):
        worst_case = settings.OLLAMA_TIMEOUT_SECONDS * (1 + settings.OLLAMA_INVALID_RETRIES)
        self.assertGreater(settings.INSIGHT_JOB_STALE_MINUTES * 60, worst_case)

    def test_task_time_limits_are_derived_from_the_ollama_timeout(self):
        self.assertEqual(settings.INSIGHT_WORST_CASE_SECONDS, 600)
        self.assertEqual(settings.INSIGHT_TASK_SOFT_TIME_LIMIT, 660)
        self.assertEqual(settings.INSIGHT_TASK_TIME_LIMIT, 720)

    def test_the_full_timeout_chain_is_ordered(self):
        self.assertLess(settings.INSIGHT_WORST_CASE_SECONDS, settings.INSIGHT_TASK_SOFT_TIME_LIMIT)
        self.assertLess(settings.INSIGHT_TASK_SOFT_TIME_LIMIT, settings.INSIGHT_TASK_TIME_LIMIT)
        self.assertLess(settings.INSIGHT_TASK_TIME_LIMIT, settings.INSIGHT_JOB_STALE_MINUTES * 60)


class StaleWindowSystemCheckTests(TestCase):
    """The django.core.checks registration must catch a bad combination at

    startup instead of leaving the invariant to survive only as a comment.
    """

    def test_no_error_for_the_defaults(self):
        self.assertEqual(check_stale_window_covers_worst_case(None), [])

    @override_settings(
        OLLAMA_TIMEOUT_SECONDS=300,
        OLLAMA_INVALID_RETRIES=1,
        INSIGHT_JOB_STALE_MINUTES=5,
    )
    def test_error_for_a_violating_combination(self):
        errors = check_stale_window_covers_worst_case(None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, 'ai_insights.E001')
        self.assertIn('INSIGHT_JOB_STALE_MINUTES', errors[0].msg)
        self.assertIn('OLLAMA_TIMEOUT_SECONDS', errors[0].msg)


class HardLimitSystemCheckTests(TestCase):
    """E001 must guard the reaper against Celery's hard kill, not just the
    raw generation budget. A stale window sitting between the two would let
    the reaper fail a job Celery is still legitimately running."""

    @override_settings(INSIGHT_JOB_STALE_MINUTES=11)  # 660s: > worst case, < hard limit
    def test_stale_window_below_the_hard_limit_is_an_error(self):
        errors = check_stale_window_covers_worst_case(None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, 'ai_insights.E001')

    @override_settings(INSIGHT_JOB_STALE_MINUTES=15)  # 900s: > hard limit
    def test_stale_window_above_the_hard_limit_passes(self):
        self.assertEqual(check_stale_window_covers_worst_case(None), [])


class BaseUrlSchemeSystemCheckTests(TestCase):
    """A schemeless OLLAMA_BASE_URL must fail at startup, not degrade silently.

    `requests` raises MissingSchema for a URL with no scheme; that subclasses
    RequestException, so the client reports OllamaUnavailable and every
    generation falls back to rule-based analysis. Catching it at startup turns
    a silent runtime degradation into a loud deploy-time failure.
    """

    def test_no_error_for_the_defaults(self):
        self.assertEqual(check_ollama_base_url_has_a_scheme(None), [])

    @override_settings(OLLAMA_BASE_URL='https://llm.example.com')
    def test_no_error_for_https(self):
        self.assertEqual(check_ollama_base_url_has_a_scheme(None), [])

    @override_settings(OLLAMA_BASE_URL='llm.example.com')
    def test_error_for_a_missing_scheme(self):
        errors = check_ollama_base_url_has_a_scheme(None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, 'ai_insights.E002')
        self.assertIn('OLLAMA_BASE_URL', errors[0].msg)

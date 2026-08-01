"""
Configuration for the local model provider.
"""
from django.conf import settings
from django.test import TestCase, override_settings

from ai_insights.apps import check_stale_window_covers_worst_case


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

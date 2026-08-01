"""
Configuration for the local model provider.
"""
from django.conf import settings
from django.test import TestCase


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

"""
Prompt construction and the response schema.
"""
from django.test import SimpleTestCase

from ai_insights.prompts import INSIGHTS_SCHEMA, SYSTEM_PROMPT, build_insights_prompt


def summary(**overrides):
    """A representative sleep summary as build_sleep_summary produces one."""
    data = {
        'period_days': 30,
        'total_records': 28,
        'avg_sleep_hours': 6.4,
        'avg_time_in_bed_hours': 7.1,
        'avg_efficiency': 89.0,
        'avg_deep_sleep_minutes': 52,
        'avg_rem_sleep_minutes': 84,
        'avg_light_sleep_minutes': 250,
        'consistency_score': 72.0,
        'target_hours': 8.0,
        'sleep_debt_hours': 6.9,
        'trend': 'declining',
    }
    data.update(overrides)
    return data


class BuildInsightsPromptTests(SimpleTestCase):
    """The prompt must carry every summary figure the model reasons over."""

    def test_includes_the_summary_figures(self):
        prompt = build_insights_prompt(summary())
        self.assertIn('6.4', prompt)
        self.assertIn('89.0', prompt)
        self.assertIn('72.0', prompt)
        self.assertIn('declining', prompt)
        self.assertIn('30 days', prompt)

    def test_system_prompt_demands_json(self):
        self.assertIn('JSON', SYSTEM_PROMPT)


class InsightsSchemaTests(SimpleTestCase):
    """The schema is handed to Ollama for constrained decoding."""

    def test_requires_the_four_top_level_keys(self):
        self.assertEqual(
            sorted(INSIGHTS_SCHEMA['required']),
            ['insights', 'overall_assessment', 'score', 'tips'],
        )

    def test_insight_type_and_priority_are_enumerated(self):
        item = INSIGHTS_SCHEMA['properties']['insights']['items']
        self.assertEqual(item['properties']['type']['enum'], ['pattern', 'recommendation', 'alert'])
        self.assertEqual(item['properties']['priority']['enum'], ['low', 'medium', 'high'])

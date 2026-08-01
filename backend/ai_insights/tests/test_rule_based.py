"""
Rule-based fallback insight generation.
"""
from django.test import SimpleTestCase

from ai_insights.rule_based import generate_rule_based_insights, insufficient_data_payload


def summary(**overrides):
    """A healthy sleep summary; override keys to trigger specific rules."""
    data = {
        'period_days': 30,
        'total_records': 28,
        'avg_sleep_hours': 8.1,
        'avg_time_in_bed_hours': 8.6,
        'avg_efficiency': 94.0,
        'avg_deep_sleep_minutes': 70,
        'avg_rem_sleep_minutes': 95,
        'avg_light_sleep_minutes': 300,
        'consistency_score': 90.0,
        'target_hours': 8.0,
        'sleep_debt_hours': 0.0,
        'trend': 'stable',
    }
    data.update(overrides)
    return data


class RuleBasedInsightTests(SimpleTestCase):
    """Rules must fire on the conditions they describe."""

    def test_short_sleep_produces_high_priority_alert(self):
        result = generate_rule_based_insights(summary(avg_sleep_hours=5.5))
        alerts = [i for i in result['insights'] if i['priority'] == 'high']
        self.assertTrue(alerts)
        self.assertEqual(alerts[0]['type'], 'alert')

    def test_low_efficiency_produces_recommendation(self):
        result = generate_rule_based_insights(summary(avg_efficiency=74.0))
        types = [i['type'] for i in result['insights']]
        self.assertIn('recommendation', types)

    def test_declining_trend_produces_alert(self):
        result = generate_rule_based_insights(summary(trend='declining'))
        titles = [i['title'] for i in result['insights']]
        self.assertIn('Sleep Quality Declining', titles)

    def test_score_clamped_to_valid_range(self):
        worst = generate_rule_based_insights(
            summary(avg_sleep_hours=2.0, avg_efficiency=40.0,
                    consistency_score=5.0, avg_deep_sleep_minutes=5, trend='declining')
        )
        best = generate_rule_based_insights(summary())
        self.assertGreaterEqual(worst['score'], 0)
        self.assertLessEqual(best['score'], 100)

    def test_always_returns_at_least_one_tip(self):
        self.assertTrue(generate_rule_based_insights(summary())['tips'])

    def test_returns_at_most_three_tips(self):
        result = generate_rule_based_insights(
            summary(avg_sleep_hours=4.0, avg_efficiency=60.0,
                    consistency_score=20.0, avg_deep_sleep_minutes=10)
        )
        self.assertLessEqual(len(result['tips']), 3)

    def test_output_passes_validation(self):
        from ai_insights.validation import validate_insights_payload
        validate_insights_payload(generate_rule_based_insights(summary(avg_sleep_hours=5.0)))


class InsufficientDataPayloadTests(SimpleTestCase):
    """Users with no records get guidance, not an error."""

    def test_has_null_score_and_tips(self):
        result = insufficient_data_payload()
        self.assertIsNone(result['score'])
        self.assertEqual(result['insights'], [])
        self.assertTrue(result['tips'])

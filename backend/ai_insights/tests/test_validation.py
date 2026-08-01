"""
Validation of model-produced insight payloads.
"""
from django.test import SimpleTestCase

from ai_insights.validation import InvalidInsightsPayload, validate_insights_payload


def payload(**overrides):
    """A well-formed payload; override one key to make it malformed."""
    data = {
        'overall_assessment': 'You are sleeping less than your target.',
        'score': 68,
        'insights': [
            {
                'type': 'alert',
                'priority': 'high',
                'title': 'Sleep Duration Below Target',
                'content': 'You average 6.4 hours against an 8 hour target.',
            }
        ],
        'tips': ['Go to bed 30 minutes earlier'],
    }
    data.update(overrides)
    return data


class ValidateInsightsPayloadTests(SimpleTestCase):
    """Malformed model output must be rejected so it can be retried."""

    def test_accepts_a_well_formed_payload(self):
        self.assertEqual(validate_insights_payload(payload()), payload())

    def test_rejects_non_dict(self):
        with self.assertRaises(InvalidInsightsPayload):
            validate_insights_payload(['not', 'a', 'dict'])

    def test_rejects_missing_score(self):
        broken = payload()
        del broken['score']
        with self.assertRaises(InvalidInsightsPayload):
            validate_insights_payload(broken)

    def test_rejects_non_integer_score(self):
        with self.assertRaises(InvalidInsightsPayload):
            validate_insights_payload(payload(score='high'))

    def test_rejects_out_of_range_score(self):
        with self.assertRaises(InvalidInsightsPayload):
            validate_insights_payload(payload(score=140))

    def test_rejects_empty_insights(self):
        with self.assertRaises(InvalidInsightsPayload):
            validate_insights_payload(payload(insights=[]))

    def test_rejects_unknown_insight_type(self):
        with self.assertRaises(InvalidInsightsPayload):
            validate_insights_payload(payload(insights=[{
                'type': 'prophecy',
                'priority': 'high',
                'title': 'T',
                'content': 'C',
            }]))

    def test_rejects_unknown_priority(self):
        with self.assertRaises(InvalidInsightsPayload):
            validate_insights_payload(payload(insights=[{
                'type': 'alert',
                'priority': 'urgent',
                'title': 'T',
                'content': 'C',
            }]))

    def test_rejects_insight_missing_content(self):
        with self.assertRaises(InvalidInsightsPayload):
            validate_insights_payload(payload(insights=[{
                'type': 'alert',
                'priority': 'high',
                'title': 'T',
            }]))

    def test_rejects_non_string_tips(self):
        with self.assertRaises(InvalidInsightsPayload):
            validate_insights_payload(payload(tips=[{'tip': 'nope'}]))

    def test_accepts_empty_tips(self):
        self.assertEqual(validate_insights_payload(payload(tips=[]))['tips'], [])

    def test_rejects_bool_score(self):
        # isinstance(True, int) is True in Python, so score=True would
        # silently pass an isinstance(score, int) check. Locks in the
        # deliberate `isinstance(score, bool)` exclusion in validation.py.
        with self.assertRaises(InvalidInsightsPayload):
            validate_insights_payload(payload(score=True))

    def test_rejects_title_over_255_characters(self):
        with self.assertRaises(InvalidInsightsPayload):
            validate_insights_payload(payload(insights=[{
                'type': 'alert',
                'priority': 'high',
                'title': 'T' * 256,
                'content': 'C',
            }]))

    def test_accepts_title_at_255_characters(self):
        result = validate_insights_payload(payload(insights=[{
            'type': 'alert',
            'priority': 'high',
            'title': 'T' * 255,
            'content': 'C',
        }]))
        self.assertEqual(len(result['insights'][0]['title']), 255)

"""
Offline evaluation of model output: the checks and the eval_insights command.
"""
import json
import os
import tempfile
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from ai_insights.evaluation import (
    CASES,
    check_payload,
    evaluate_once,
    summarize,
    unverified_numbers,
)
from ai_insights.providers.ollama import OllamaInvalidResponse, OllamaUnavailable

CASES_BY_NAME = {case['name']: case for case in CASES}
SHORT = CASES_BY_NAME['short_sleep']
HEALTHY = CASES_BY_NAME['healthy']


def insight(type_='recommendation', priority='medium', content='Keep a routine.'):
    return {'type': type_, 'priority': priority, 'title': 'Title', 'content': content}


def payload(score=60, insights=None):
    return {
        'overall_assessment': 'Assessment.',
        'score': score,
        'insights': insights if insights is not None else [insight()] * 3,
        'tips': ['Tip'],
    }


class FakeProvider:
    """Returns scripted results in order; exceptions are raised."""

    def __init__(self, results):
        self.results = list(results)

    def generate(self, system_prompt, user_prompt, schema):
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class CaseFixtureTests(SimpleTestCase):
    """The fixtures must look like real build_sleep_summary output."""

    def test_sleep_debt_follows_the_summary_formula(self):
        for case in CASES:
            summary = case['summary']
            expected = round(
                max(0, (summary['target_hours'] - summary['avg_sleep_hours'])
                    * summary['period_days'] / 7), 1
            )
            self.assertEqual(summary['sleep_debt_hours'], expected, case['name'])

    def test_every_case_has_a_known_expectation(self):
        for case in CASES:
            self.assertIn(case['expect'], ('good', 'poor', None), case['name'])


class UnverifiedNumberTests(SimpleTestCase):
    """Numbers the model states must come from the data it was given."""

    def test_numbers_from_the_summary_are_verified(self):
        text = 'You average 5.4 hours at 90% efficiency with 11.1 hours of debt.'
        self.assertEqual(unverified_numbers(text, SHORT['summary']), [])

    def test_rounded_values_are_verified(self):
        # avg_sleep_hours is 5.4; "5 hours" is an honest rounding.
        self.assertEqual(unverified_numbers('About 5 hours.', SHORT['summary']), [])

    def test_derived_values_are_verified(self):
        # 8.0 target - 5.4 average = 2.6 hours short; 5.4 h = 324 min.
        text = 'You are 2.6 hours short, about 324 minutes asleep.'
        self.assertEqual(unverified_numbers(text, SHORT['summary']), [])

    def test_invented_numbers_are_reported(self):
        text = 'Your efficiency is 72% and you sleep 4.2 hours.'
        self.assertEqual(unverified_numbers(text, SHORT['summary']), [72.0, 4.2])

    def test_generic_advice_numbers_are_ignored(self):
        text = 'Go to bed 30 minutes earlier and stop caffeine 6 hours before bed.'
        self.assertEqual(unverified_numbers(text, SHORT['summary']), [])


class CheckPayloadTests(SimpleTestCase):

    def test_insight_count_must_match_the_prompt(self):
        self.assertTrue(check_payload(payload(insights=[insight()] * 3), SHORT)['insight_count_ok'])
        self.assertFalse(check_payload(payload(insights=[insight()] * 2), SHORT)['insight_count_ok'])
        self.assertFalse(check_payload(payload(insights=[insight()] * 6), SHORT)['insight_count_ok'])

    def test_poor_data_must_raise_an_alert_or_high_priority(self):
        calm = payload(insights=[insight()] * 3)
        flagged = payload(insights=[insight(priority='high')] + [insight()] * 2)
        self.assertFalse(check_payload(calm, SHORT)['severity_ok'])
        self.assertTrue(check_payload(flagged, SHORT)['severity_ok'])

    def test_good_data_must_not_raise_an_alert(self):
        alarmed = payload(insights=[insight(type_='alert')] + [insight()] * 2)
        self.assertFalse(check_payload(alarmed, HEALTHY)['severity_ok'])
        self.assertTrue(check_payload(payload(), HEALTHY)['severity_ok'])

    def test_collects_unverified_numbers_from_every_text_field(self):
        result = check_payload(
            payload(insights=[insight(content='Efficiency is 72%.')] * 3), SHORT
        )
        self.assertIn(72.0, result['unverified_numbers'])


class EvaluateOnceTests(SimpleTestCase):

    def test_records_a_valid_response(self):
        result = evaluate_once(FakeProvider([payload(score=55)]), SHORT)
        self.assertTrue(result['valid'])
        self.assertEqual(result['case'], 'short_sleep')
        self.assertEqual(result['checks']['score'], 55)
        self.assertGreaterEqual(result['latency_seconds'], 0)

    def test_schema_failure_is_invalid_not_fatal(self):
        result = evaluate_once(FakeProvider([{'score': 50}]), SHORT)
        self.assertFalse(result['valid'])
        self.assertIn('missing required key', result['error'])
        self.assertIsNone(result['checks'])

    def test_unparseable_output_is_invalid_not_fatal(self):
        result = evaluate_once(FakeProvider([OllamaInvalidResponse('not JSON')]), SHORT)
        self.assertFalse(result['valid'])

    def test_transport_failure_propagates(self):
        with self.assertRaises(OllamaUnavailable):
            evaluate_once(FakeProvider([OllamaUnavailable('refused')]), SHORT)


class SummarizeTests(SimpleTestCase):

    def run_for(self, case, score):
        return evaluate_once(FakeProvider([payload(score=score)]), case)

    def test_score_order_passes_when_good_beats_poor(self):
        results = [self.run_for(HEALTHY, 85), self.run_for(SHORT, 50)]
        self.assertTrue(summarize(results)['score_order_ok'])

    def test_score_order_fails_when_poor_beats_good(self):
        results = [self.run_for(HEALTHY, 50), self.run_for(SHORT, 85)]
        self.assertFalse(summarize(results)['score_order_ok'])

    def test_reports_first_attempt_validity_rate(self):
        results = [
            self.run_for(SHORT, 50),
            evaluate_once(FakeProvider([{'score': 50}]), SHORT),
        ]
        self.assertEqual(summarize(results)['valid_rate'], 0.5)

    def test_includes_the_rule_based_score_for_comparison(self):
        per_case = summarize([self.run_for(SHORT, 50)])['cases']['short_sleep']
        self.assertIsInstance(per_case['rule_based_score'], int)


@override_settings(OLLAMA_BASE_URL='https://llm.example.com', OLLAMA_MODEL='qwen2.5:7b-instruct')
class EvalInsightsCommandTests(SimpleTestCase):

    @patch('ai_insights.management.commands.eval_insights.OllamaClient')
    def test_runs_each_selected_case_the_requested_number_of_times(self, mock_client):
        mock_client.return_value.generate.return_value = payload()
        out = StringIO()
        call_command('eval_insights', '--case', 'short_sleep', '--runs', '2', stdout=out)
        self.assertEqual(mock_client.return_value.generate.call_count, 2)
        self.assertIn('short_sleep', out.getvalue())
        self.assertIn('qwen2.5:7b-instruct', out.getvalue())

    @patch('ai_insights.management.commands.eval_insights.OllamaClient')
    def test_writes_raw_responses_to_the_output_file(self, mock_client):
        mock_client.return_value.generate.return_value = payload(score=42)
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'eval.json')
            call_command(
                'eval_insights', '--case', 'short_sleep', '--runs', '1',
                '--output', path, stdout=StringIO(),
            )
            with open(path, encoding='utf-8') as handle:
                report = json.load(handle)
        self.assertEqual(report['model'], 'qwen2.5:7b-instruct')
        self.assertEqual(report['runs'][0]['payload']['score'], 42)
        self.assertIn('summary', report)

    @patch('ai_insights.management.commands.eval_insights.OllamaClient')
    def test_stops_on_a_transport_failure(self, mock_client):
        mock_client.return_value.generate.side_effect = OllamaUnavailable('refused')
        err = StringIO()
        with self.assertRaises(SystemExit):
            call_command('eval_insights', '--runs', '1', stdout=StringIO(), stderr=err)
        self.assertIn('check_ollama', err.getvalue())

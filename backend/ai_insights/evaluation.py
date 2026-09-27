"""
Offline evaluation of local model insight output.

Sends the production prompt to the real model for a fixed set of sleep
summaries and scores each response with automatic checks. The checks catch
schema drift, invented numbers, and scores that ignore the data. They cannot
tell whether the advice is good, so read the saved responses as well.
"""
import re
import statistics
import time

from .prompts import INSIGHTS_SCHEMA, SYSTEM_PROMPT, build_insights_prompt
from .providers.ollama import OllamaInvalidResponse
from .rule_based import generate_rule_based_insights
from .validation import InvalidInsightsPayload, validate_insights_payload

# Each summary has the shape build_sleep_summary returns, with a 30-day period
# and sleep_debt_hours computed by its formula. `expect` is the verdict any
# sensible reader would reach from the data: 'good', 'poor', or None when the
# picture is mixed and no severity or score order is enforced.
CASES = [
    {
        'name': 'healthy',
        'expect': 'good',
        'summary': {
            'period_days': 30, 'total_records': 30,
            'avg_sleep_hours': 7.9, 'avg_time_in_bed_hours': 8.4, 'avg_efficiency': 94.0,
            'avg_deep_sleep_minutes': 95, 'avg_rem_sleep_minutes': 110,
            'avg_light_sleep_minutes': 269, 'consistency_score': 90.0,
            'target_hours': 8.0, 'sleep_debt_hours': 0.4, 'trend': 'stable',
        },
    },
    {
        'name': 'short_sleep',
        'expect': 'poor',
        'summary': {
            'period_days': 30, 'total_records': 28,
            'avg_sleep_hours': 5.4, 'avg_time_in_bed_hours': 6.0, 'avg_efficiency': 90.0,
            'avg_deep_sleep_minutes': 60, 'avg_rem_sleep_minutes': 70,
            'avg_light_sleep_minutes': 194, 'consistency_score': 80.0,
            'target_hours': 8.0, 'sleep_debt_hours': 11.1, 'trend': 'stable',
        },
    },
    {
        'name': 'low_efficiency',
        'expect': 'poor',
        'summary': {
            'period_days': 30, 'total_records': 30,
            'avg_sleep_hours': 6.8, 'avg_time_in_bed_hours': 8.6, 'avg_efficiency': 79.0,
            'avg_deep_sleep_minutes': 70, 'avg_rem_sleep_minutes': 85,
            'avg_light_sleep_minutes': 253, 'consistency_score': 75.0,
            'target_hours': 8.0, 'sleep_debt_hours': 5.1, 'trend': 'stable',
        },
    },
    {
        'name': 'irregular_schedule',
        'expect': None,
        'summary': {
            'period_days': 30, 'total_records': 27,
            'avg_sleep_hours': 7.2, 'avg_time_in_bed_hours': 7.9, 'avg_efficiency': 91.1,
            'avg_deep_sleep_minutes': 80, 'avg_rem_sleep_minutes': 95,
            'avg_light_sleep_minutes': 257, 'consistency_score': 40.0,
            'target_hours': 8.0, 'sleep_debt_hours': 3.4, 'trend': 'stable',
        },
    },
    {
        # Manual entries carry no stage data; the model must not invent any.
        'name': 'no_stage_data',
        'expect': 'good',
        'summary': {
            'period_days': 30, 'total_records': 25,
            'avg_sleep_hours': 7.5, 'avg_time_in_bed_hours': 8.1, 'avg_efficiency': 92.6,
            'avg_deep_sleep_minutes': 0, 'avg_rem_sleep_minutes': 0,
            'avg_light_sleep_minutes': 0, 'consistency_score': 85.0,
            'target_hours': 8.0, 'sleep_debt_hours': 2.1, 'trend': 'stable',
        },
    },
    {
        'name': 'declining',
        'expect': 'poor',
        'summary': {
            'period_days': 30, 'total_records': 29,
            'avg_sleep_hours': 6.1, 'avg_time_in_bed_hours': 7.0, 'avg_efficiency': 87.1,
            'avg_deep_sleep_minutes': 40, 'avg_rem_sleep_minutes': 65,
            'avg_light_sleep_minutes': 261, 'consistency_score': 60.0,
            'target_hours': 8.0, 'sleep_debt_hours': 8.1, 'trend': 'declining',
        },
    },
]

# The prompt asks for "3-5 insights".
MIN_INSIGHTS = 3
MAX_INSIGHTS = 5

_NUMBER_RE = re.compile(r'(?<![\w.])\d+(?:\.\d+)?')

# Numbers common in generic sleep advice ("30 minutes earlier", "7-9 hours",
# "6 hours before bed"). They are not claims about the user's data, so the
# grounding check skips them. The cost: an invented "8 hours" goes unflagged.
_GENERIC_NUMBERS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 30, 45, 60, 90, 100}

_HOUR_FIELDS = ('avg_sleep_hours', 'avg_time_in_bed_hours', 'target_hours', 'sleep_debt_hours')
_MINUTE_FIELDS = ('avg_deep_sleep_minutes', 'avg_rem_sleep_minutes', 'avg_light_sleep_minutes')


def _reference_values(summary):
    """Every number the model could honestly state from this summary."""
    # Differences the model is likely to state ("2.6 hours short", "36
    # minutes awake in bed").
    differences = [
        summary['target_hours'] - summary['avg_sleep_hours'],
        summary['avg_time_in_bed_hours'] - summary['avg_sleep_hours'],
    ]
    hour_values = [summary[field] for field in _HOUR_FIELDS] + differences

    values = [v for v in summary.values() if isinstance(v, (int, float))]
    values += differences
    values += [hours * 60 for hours in hour_values]
    values += [summary[field] / 60 for field in _MINUTE_FIELDS]
    return values


def unverified_numbers(text, summary):
    """Return the numbers in `text` that no summary value accounts for.

    A whole number matches a value within 0.5, so honest rounding ("5 hours"
    for 5.4) passes; a decimal must match within 0.05.
    """
    references = _reference_values(summary)
    unverified = []
    for match in _NUMBER_RE.findall(text):
        number = float(match)
        if '.' not in match and number in _GENERIC_NUMBERS:
            continue
        tolerance = 0.05 if '.' in match else 0.5
        if not any(abs(number - value) <= tolerance for value in references):
            unverified.append(number)
    return unverified


def check_payload(payload, case):
    """Score one validated payload against the case it was generated for."""
    insights = payload['insights']
    texts = [payload['overall_assessment'], *payload['tips']]
    for insight in insights:
        texts += [insight['title'], insight['content']]

    flags_problem = any(
        insight['type'] == 'alert' or insight['priority'] == 'high' for insight in insights
    )
    if case['expect'] == 'poor':
        severity_ok = flags_problem
    elif case['expect'] == 'good':
        severity_ok = not any(insight['type'] == 'alert' for insight in insights)
    else:
        severity_ok = True

    return {
        'score': payload['score'],
        'insight_count': len(insights),
        'insight_count_ok': MIN_INSIGHTS <= len(insights) <= MAX_INSIGHTS,
        'severity_ok': severity_ok,
        'unverified_numbers': [
            number for text in texts for number in unverified_numbers(text, case['summary'])
        ],
    }


def evaluate_once(provider, case):
    """Send one case to the model with no retry and score the response.

    Malformed output is recorded as invalid. Transport failures (unreachable,
    timeout, auth) propagate: they say nothing about output quality.
    """
    started = time.monotonic()
    payload = None
    error = None
    try:
        payload = provider.generate(
            SYSTEM_PROMPT, build_insights_prompt(case['summary']), INSIGHTS_SCHEMA
        )
        validate_insights_payload(payload)
    except (InvalidInsightsPayload, OllamaInvalidResponse) as exc:
        error = str(exc)
    latency = time.monotonic() - started

    return {
        'case': case['name'],
        'valid': error is None,
        'error': error,
        'latency_seconds': round(latency, 2),
        'payload': payload,
        'checks': check_payload(payload, case) if error is None else None,
    }


def _rate(flags):
    return round(sum(flags) / len(flags), 2) if flags else None


def summarize(results):
    """Aggregate evaluate_once results per case and overall."""
    cases_by_name = {case['name']: case for case in CASES}
    per_case = {}
    for name in dict.fromkeys(result['case'] for result in results):
        runs = [result for result in results if result['case'] == name]
        checks = [result['checks'] for result in runs if result['valid']]
        scores = [check['score'] for check in checks]
        per_case[name] = {
            'expect': cases_by_name[name]['expect'],
            'runs': len(runs),
            'valid': sum(result['valid'] for result in runs),
            'mean_score': round(statistics.mean(scores), 1) if scores else None,
            'min_score': min(scores) if scores else None,
            'max_score': max(scores) if scores else None,
            'rule_based_score': generate_rule_based_insights(
                cases_by_name[name]['summary']
            )['score'],
            'insight_count_ok': sum(check['insight_count_ok'] for check in checks),
            'severity_ok': sum(check['severity_ok'] for check in checks),
            'unverified_numbers': sorted(
                {number for check in checks for number in check['unverified_numbers']}
            ),
            'mean_latency_seconds': round(
                statistics.mean(result['latency_seconds'] for result in runs), 1
            ),
        }

    good = [c['mean_score'] for c in per_case.values()
            if c['expect'] == 'good' and c['mean_score'] is not None]
    poor = [c['mean_score'] for c in per_case.values()
            if c['expect'] == 'poor' and c['mean_score'] is not None]
    all_checks = [result['checks'] for result in results if result['valid']]

    return {
        'cases': per_case,
        'valid_rate': _rate([result['valid'] for result in results]),
        'insight_count_ok_rate': _rate([check['insight_count_ok'] for check in all_checks]),
        'severity_ok_rate': _rate([check['severity_ok'] for check in all_checks]),
        'runs_with_unverified_numbers': sum(
            bool(check['unverified_numbers']) for check in all_checks
        ),
        # Every good case must outscore every poor case. None when the run
        # did not cover both kinds.
        'score_order_ok': min(good) > max(poor) if good and poor else None,
    }

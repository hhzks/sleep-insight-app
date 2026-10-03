"""
Measure the quality of the configured model's insight output.

Sends fixed sleep summaries to the real Ollama server, with no retry and no
rule-based fallback, and reports automatic checks per case. Run it after
changing OLLAMA_MODEL or prompts.py and compare the result with the last run.
On CPU inference each run takes minutes, so start with --runs 1.
"""
import json
import sys

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand
from django.utils import timezone

from ai_insights.evaluation import CASES, evaluate_once, summarize
from ai_insights.providers.ollama import OllamaClient, OllamaError


def _yes_no(value):
    return '-' if value is None else ('PASS' if value else 'FAIL')


class Command(BaseCommand):
    help = 'Run the insight prompt against fixed sleep summaries and score the output.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--runs', type=int, default=3,
            help='Generations per case. Output varies between runs (default: 3).',
        )
        parser.add_argument(
            '--case', action='append', dest='cases',
            choices=[case['name'] for case in CASES],
            help='Run only this case. Repeat to select more than one.',
        )
        parser.add_argument(
            '--output',
            help='Write every raw response and check result to this JSON file.',
        )

    def handle(self, *args, **options):
        runs = options['runs']
        selected = options['cases']
        cases = [case for case in CASES if not selected or case['name'] in selected]

        self.stdout.write(f'Server:  {settings.OLLAMA_BASE_URL}')
        self.stdout.write(f'Model:   {settings.OLLAMA_MODEL}')
        self.stdout.write(f'Cases:   {len(cases)} x {runs} runs')

        started_at = timezone.now()
        results = []
        try:
            client = OllamaClient()
            for case in cases:
                for run in range(runs):
                    result = evaluate_once(client, case)
                    results.append(result)
                    if result['valid']:
                        detail = f'score={result["checks"]["score"]}'
                    else:
                        detail = f'INVALID ({result["error"]})'
                    self.stdout.write(
                        f'  {case["name"]} run {run + 1}/{runs}: {detail} '
                        f'{result["latency_seconds"]:.1f}s'
                    )
        except (ImproperlyConfigured, OllamaError) as exc:
            self.stderr.write(
                f'FAILED: {exc}. The server did not answer, so no quality result '
                'is possible. Run "python manage.py check_ollama" to find the cause.'
            )
            sys.exit(1)

        summary = summarize(results)
        self._write_report(summary)

        if options['output']:
            report = {
                'model': settings.OLLAMA_MODEL,
                'temperature': settings.OLLAMA_TEMPERATURE,
                'started_at': started_at.isoformat(),
                'summary': summary,
                'runs': results,
            }
            with open(options['output'], 'w', encoding='utf-8') as handle:
                json.dump(report, handle, indent=2)
            self.stdout.write(f'Raw responses written to {options["output"]}')

    def _write_report(self, summary):
        self.stdout.write('')
        self.stdout.write(
            f'{"case":<20}{"expect":<8}{"valid":>7}{"score":>8}{"range":>10}'
            f'{"rules":>7}{"count":>7}{"sev":>6}{"secs":>8}'
        )
        for name, case in summary['cases'].items():
            score_range = (
                f'{case["min_score"]}-{case["max_score"]}'
                if case['mean_score'] is not None else '-'
            )
            self.stdout.write(
                f'{name:<20}{case["expect"] or "mixed":<8}'
                f'{case["valid"]:>4}/{case["runs"]:<2}'
                f'{case["mean_score"] if case["mean_score"] is not None else "-":>8}'
                f'{score_range:>10}{case["rule_based_score"]:>7}'
                f'{case["insight_count_ok"]:>7}{case["severity_ok"]:>6}'
                f'{case["mean_latency_seconds"]:>8}'
            )
            if case['unverified_numbers']:
                numbers = ', '.join(f'{n:g}' for n in case['unverified_numbers'])
                self.stdout.write(f'  numbers not in the data: {numbers}')

        self.stdout.write('')
        self.stdout.write(f'Valid on first attempt:       {summary["valid_rate"]}')
        self.stdout.write(f'3-5 insights:                 {summary["insight_count_ok_rate"]}')
        self.stdout.write(f'Severity matches the data:    {summary["severity_ok_rate"]}')
        self.stdout.write(
            f'Runs with unverified numbers: {summary["runs_with_unverified_numbers"]}'
        )
        self.stdout.write(
            f'Good cases outscore poor:     {_yes_no(summary["score_order_ok"])}'
        )
        self.stdout.write(
            'These checks do not judge the advice itself. Read the raw responses '
            '(--output) before you change the model or the prompt.'
        )

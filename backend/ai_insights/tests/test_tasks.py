"""The Celery task is a thin wrapper over run_insight_job."""
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase

from ai_insights.tasks import generate_insight_task, reap_stale_jobs_task


class GenerateInsightTaskTests(TestCase):
    def test_registered_under_a_stable_name(self):
        # The name is a wire contract: a queued message names its task, so
        # renaming this strands anything already in the broker.
        self.assertEqual(generate_insight_task.name, 'ai_insights.generate_insight')

    def test_time_limits_come_from_settings(self):
        self.assertEqual(generate_insight_task.soft_time_limit, settings.INSIGHT_TASK_SOFT_TIME_LIMIT)
        self.assertEqual(generate_insight_task.time_limit, settings.INSIGHT_TASK_TIME_LIMIT)

    def test_does_not_retry(self):
        # A redelivered 3-minute generation is duplicated expensive work on a
        # 2-core box; the reaper plus a user-initiated retry is the design.
        self.assertEqual(generate_insight_task.max_retries, 0)

    @patch('ai_insights.tasks.run_insight_job')
    def test_delegates_to_run_insight_job(self, mock_run):
        generate_insight_task.apply(args=['abc-123'])
        mock_run.assert_called_once_with('abc-123')


class BeatScheduleTests(TestCase):
    def test_reaper_is_scheduled(self):
        entry = settings.CELERY_BEAT_SCHEDULE['reap-stale-insight-jobs']
        self.assertEqual(entry['task'], 'ai_insights.reap_stale_jobs')

    def test_reaper_runs_more_often_than_the_stale_window(self):
        # A schedule slower than the window means jobs sit failed-but-unreaped
        # for up to one extra period, which users see as a hung spinner.
        entry = settings.CELERY_BEAT_SCHEDULE['reap-stale-insight-jobs']
        self.assertLess(entry['schedule'], settings.INSIGHT_JOB_STALE_MINUTES * 60)


class ReapTaskTests(TestCase):
    @patch('ai_insights.tasks.reap_stale_jobs')
    def test_reap_task_delegates(self, mock_reap):
        mock_reap.return_value = 3
        self.assertEqual(reap_stale_jobs_task.apply().get(), 3)
        mock_reap.assert_called_once_with()

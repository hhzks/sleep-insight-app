"""The Celery app must load with Django and carry the derived limits."""
from django.conf import settings
from django.test import TestCase

from sleep_tracker.celery import app


class CeleryAppTests(TestCase):
    def test_app_is_named_for_the_project(self):
        self.assertEqual(app.main, 'sleep_tracker')

    def test_broker_polling_interval_is_throttled(self):
        # Celery's Redis transport issues BRPOP ~1-4x/second while idle.
        # Left at the default this is ~350k commands/day against a queue
        # seeing ~10 real jobs, which is a cost control, not a nicety.
        self.assertEqual(app.conf.broker_transport_options['polling_interval'], 5)

    def test_no_result_backend_is_configured(self):
        # The InsightJob row is the source of truth; a result backend would
        # be a second, divergent copy of job state.
        self.assertFalse(app.conf.result_backend)

    def test_tasks_run_eagerly_under_test(self):
        self.assertTrue(settings.CELERY_TASK_ALWAYS_EAGER)

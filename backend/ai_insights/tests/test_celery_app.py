"""The Celery app must load with Django and carry the derived limits."""
from django.conf import settings
from django.test import TestCase

from sleep_tracker.celery import app
from sleep_tracker.settings import _celery_tasks_run_eagerly


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


class CeleryTasksRunEagerlyTests(TestCase):
    """Coverage for the argv predicate, isolated from the real sys.argv.

    A plain `'test' in argv` membership check would also enable eager mode
    for a hypothetical production command invoked as e.g.
    `manage.py notify_users test`, silently defeating the whole point of
    running insight generation on a worker. These cases pin the fix's
    positional check so a future regression back to membership fails loudly.
    """

    def test_eager_when_test_is_the_management_command(self):
        self.assertTrue(_celery_tasks_run_eagerly(['manage.py', 'test']))

    def test_not_eager_when_test_is_a_trailing_argument(self):
        self.assertFalse(
            _celery_tasks_run_eagerly(['manage.py', 'somecommand', 'test'])
        )

    def test_not_eager_with_no_command(self):
        self.assertFalse(_celery_tasks_run_eagerly(['manage.py']))

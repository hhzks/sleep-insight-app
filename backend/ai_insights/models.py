"""
AI Insights Models
"""
import uuid

from django.db import models
from django.conf import settings


class SleepInsight(models.Model):
    """Store AI-generated sleep insights."""
    
    INSIGHT_TYPES = [
        ('daily', 'Daily Summary'),
        ('weekly', 'Weekly Analysis'),
        ('monthly', 'Monthly Review'),
        ('pattern', 'Pattern Detection'),
        ('recommendation', 'Recommendation'),
        ('alert', 'Alert'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sleep_insights'
    )
    
    insight_type = models.CharField(max_length=20, choices=INSIGHT_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')
    
    title = models.CharField(max_length=255)
    content = models.TextField()
    
    # Related data
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    
    # User interaction
    is_read = models.BooleanField(default=False)
    is_helpful = models.BooleanField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'sleep_insights'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.title}"


class SleepTip(models.Model):
    """Pre-defined sleep improvement tips."""
    
    CATEGORIES = [
        ('hygiene', 'Sleep Hygiene'),
        ('routine', 'Bedtime Routine'),
        ('environment', 'Sleep Environment'),
        ('lifestyle', 'Lifestyle'),
        ('nutrition', 'Nutrition'),
        ('exercise', 'Exercise'),
        ('stress', 'Stress Management'),
        ('technology', 'Technology'),
    ]
    
    category = models.CharField(max_length=20, choices=CATEGORIES)
    title = models.CharField(max_length=255)
    content = models.TextField()
    short_tip = models.CharField(max_length=255)
    
    # Conditions for showing this tip
    min_sleep_hours = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    max_sleep_hours = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    min_efficiency = models.PositiveIntegerField(null=True, blank=True)
    max_efficiency = models.PositiveIntegerField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sleep_tips'
        ordering = ['order', 'category']
    
    def __str__(self):
        return f"{self.category} - {self.title}"


class InsightJob(models.Model):
    """One background insight-generation run.

    A model failure still counts as succeeded with source='rule_based' — the
    user got insights, just not model-generated ones. STATUS_FAILED means we
    have nothing to show.
    """

    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'

    STATUSES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_SUCCEEDED, 'Succeeded'),
        (STATUS_FAILED, 'Failed'),
    ]

    ACTIVE_STATUSES = (STATUS_QUEUED, STATUS_RUNNING)

    SOURCES = [
        ('local_model', 'Local model'),
        ('rule_based', 'Rule based'),
        ('insufficient_data', 'Insufficient data'),
    ]

    ERROR_CODES = [
        ('timeout', 'Timeout'),
        ('unreachable', 'Unreachable'),
        ('auth', 'Auth'),
        ('invalid_response', 'Invalid response'),
        ('internal', 'Internal'),
    ]

    FAILED_MESSAGE = 'Insight generation could not be completed. Please try again.'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='insight_jobs',
    )

    days = models.PositiveIntegerField(default=30)
    status = models.CharField(max_length=20, choices=STATUSES, default=STATUS_QUEUED)
    source = models.CharField(max_length=20, choices=SOURCES, null=True, blank=True)
    result = models.JSONField(null=True, blank=True)

    # Operator-facing only; never serialized to the client.
    error_code = models.CharField(max_length=20, choices=ERROR_CODES, null=True, blank=True)
    error_detail = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sleep_insight_jobs'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'status'])]

    def __str__(self):
        return f'{self.user.email} - {self.status}'

    def to_response(self):
        """The client-facing view of this job. Never includes operator detail."""
        # Imported here to avoid a circular import: services imports models.
        from .services import DEGRADED_NOTICE, SOURCE_RULE_BASED

        response = {'job_id': str(self.id), 'status': self.status}

        if self.status == self.STATUS_SUCCEEDED:
            response['source'] = self.source
            response['result'] = self.result
            if self.source == SOURCE_RULE_BASED:
                response['notice'] = DEGRADED_NOTICE
        elif self.status == self.STATUS_FAILED:
            response['error'] = self.FAILED_MESSAGE

        return response

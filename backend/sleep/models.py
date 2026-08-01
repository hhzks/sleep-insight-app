"""
Sleep Models for tracking sleep data
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class SleepRecord(models.Model):
    """Model for storing sleep records."""
    
    SOURCE_CHOICES = [
        ('manual', 'Manual Entry'),
        ('fitbit', 'Fitbit'),
        ('apple_health', 'Apple Health'),
        ('google_fit', 'Google Fit'),
    ]
    
    SLEEP_TYPE_CHOICES = [
        ('stages', 'Stages (detailed)'),
        ('classic', 'Classic'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sleep_records'
    )
    
    # Core sleep data
    date_of_sleep = models.DateField(db_index=True, help_text="The date this sleep is logged for")
    start_time = models.DateTimeField(help_text="When sleep started")
    end_time = models.DateTimeField(help_text="When sleep ended")
    
    # Duration metrics
    duration_minutes = models.PositiveIntegerField(help_text="Total time in bed (minutes)")
    minutes_asleep = models.PositiveIntegerField(help_text="Actual sleep time (minutes)")
    minutes_awake = models.PositiveIntegerField(default=0, help_text="Time awake during sleep (minutes)")
    
    # Sleep quality
    efficiency = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True, blank=True,
        help_text="Sleep efficiency percentage"
    )
    
    # Sleep stages (for detailed tracking)
    deep_sleep_minutes = models.PositiveIntegerField(null=True, blank=True)
    light_sleep_minutes = models.PositiveIntegerField(null=True, blank=True)
    rem_sleep_minutes = models.PositiveIntegerField(null=True, blank=True)
    
    # Quality rating (user self-reported)
    quality_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True,
        help_text="User's subjective quality rating (1-5)"
    )
    
    # Additional metadata
    sleep_type = models.CharField(max_length=20, choices=SLEEP_TYPE_CHOICES, default='classic')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='manual')
    external_id = models.CharField(max_length=255, blank=True, help_text="ID from external source (e.g., Fitbit)")
    is_main_sleep = models.BooleanField(default=True, help_text="Whether this is the main sleep period")
    
    # Notes
    notes = models.TextField(blank=True, help_text="User notes about this sleep")
    
    # Factors that may affect sleep
    caffeine_intake = models.BooleanField(null=True, blank=True)
    alcohol_intake = models.BooleanField(null=True, blank=True)
    exercise_today = models.BooleanField(null=True, blank=True)
    stress_level = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True,
        help_text="Stress level (1-5)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sleep_records'
        ordering = ['-date_of_sleep', '-start_time']
        constraints = [
            # Keeps Fitbit sync idempotent. Conditional because manual entries
            # leave external_id blank, and every blank would otherwise collide.
            models.UniqueConstraint(
                fields=['user', 'external_id'],
                condition=~models.Q(external_id=''),
                name='unique_user_external_id',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'date_of_sleep']),
            models.Index(fields=['user', 'start_time']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.date_of_sleep}"
    
    @property
    def duration_hours(self):
        """Return duration in hours."""
        return round(self.duration_minutes / 60, 2)
    
    @property
    def sleep_hours(self):
        """Return actual sleep time in hours."""
        return round(self.minutes_asleep / 60, 2)


class SleepStageData(models.Model):
    """Detailed sleep stage data for a sleep record."""
    
    STAGE_CHOICES = [
        ('deep', 'Deep Sleep'),
        ('light', 'Light Sleep'),
        ('rem', 'REM Sleep'),
        ('wake', 'Awake'),
        ('restless', 'Restless'),
        ('asleep', 'Asleep'),
    ]
    
    sleep_record = models.ForeignKey(
        SleepRecord,
        on_delete=models.CASCADE,
        related_name='stage_data'
    )
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    start_time = models.DateTimeField()
    duration_seconds = models.PositiveIntegerField()
    
    class Meta:
        db_table = 'sleep_stage_data'
        ordering = ['start_time']
    
    def __str__(self):
        return f"{self.sleep_record_id} - {self.stage} ({self.duration_seconds}s)"


class SleepGoal(models.Model):
    """User's sleep goals."""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sleep_goal'
    )
    
    target_hours = models.DecimalField(
        max_digits=3, decimal_places=1, default=8.0,
        validators=[MinValueValidator(4), MaxValueValidator(12)]
    )
    target_bedtime = models.TimeField(null=True, blank=True)
    target_waketime = models.TimeField(null=True, blank=True)
    
    # Weekly goals
    min_sleep_hours_weekly = models.PositiveIntegerField(default=49, help_text="Minimum total sleep hours per week")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sleep_goals'
    
    def __str__(self):
        return f"{self.user.email} - {self.target_hours}h goal"

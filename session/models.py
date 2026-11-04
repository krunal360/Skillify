from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Session(models.Model):
    STATUS_CHOICES = [
        ('upcoming',  'Upcoming'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    LEVEL_CHOICES = [
        ('beginner',     'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced',     'Advanced'),
    ]

    tutor            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tutor_sessions')
    title            = models.CharField(max_length=255)
    description      = models.TextField(blank=True, default='')
    skill            = models.ForeignKey('skills.Skill', on_delete=models.CASCADE, related_name='sessions')
    date             = models.DateField()
    start_time       = models.TimeField()
    end_time         = models.TimeField()
    credits_required = models.IntegerField(default=50)
    session_type     = models.CharField(max_length=20, default='one-to-one')
    max_participants = models.IntegerField(default=1)
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')
    level            = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner') 
    created_at       = models.DateTimeField(auto_now_add=True)

    # ── Reschedule proposed times ─────────────────────────────────────
    proposed_date       = models.DateField(null=True, blank=True)
    proposed_start_time = models.TimeField(null=True, blank=True)
    proposed_end_time   = models.TimeField(null=True, blank=True)

    class Meta:
        app_label = 'session'
        db_table  = 'core_session'

    def __str__(self):
        return f"{self.title} by {self.tutor.get_full_name()}"

    def average_rating(self):
        from reviews.models import Review
        reviews = Review.objects.filter(session=self)
        if reviews.exists():
            return round(reviews.aggregate(models.Avg('rating'))['rating__avg'], 1)
        return 0

    def duration_minutes(self):
        from datetime import datetime
        start = datetime.combine(self.date, self.start_time)
        end   = datetime.combine(self.date, self.end_time)
        return int((end - start).total_seconds() / 60)


class Booking(models.Model):
    STATUS_CHOICES = [
        ('confirmed',      'Confirmed'),
        ('in_progress',    'In Progress'),
        ('completed',      'Completed'),
        ('cancelled',      'Cancelled'),
        ('pending_review', 'Pending Review'),
    ]

    RESCHEDULE_STATUS_CHOICES = [
        ('none',     'None'),
        ('pending',  'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ]

    # ── Core fields ───────────────────────────────────────────────────
    learner      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    session      = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='bookings')
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='confirmed')
    booked_at    = models.DateTimeField(auto_now_add=True)
    credits_paid = models.IntegerField(default=0)

    # ── Zoom fields ───────────────────────────────────────────────────
    zoom_meeting_id = models.CharField(max_length=100, blank=True, default='')
    zoom_host_url   = models.TextField(blank=True, null=True, default=None)
    zoom_join_url   = models.TextField(blank=True, null=True, default=None)

    # ── Session tracking ──────────────────────────────────────────────
    session_started_at = models.DateTimeField(null=True, blank=True)
    tutor_confirmed    = models.BooleanField(default=False)
    learner_confirmed  = models.BooleanField(default=False)
    auto_complete_at   = models.DateTimeField(null=True, blank=True)

    # ── Email tracking ────────────────────────────────────────────────
    tutor_email_sent = models.BooleanField(default=False)

    # ── Reschedule fields ─────────────────────────────────────────────
    proposed_date       = models.DateField(null=True, blank=True)
    proposed_start_time = models.TimeField(null=True, blank=True)
    proposed_end_time   = models.TimeField(null=True, blank=True)
    reschedule_status   = models.CharField(
        max_length=20,
        choices=RESCHEDULE_STATUS_CHOICES,
        default='none'
    )
    reschedule_deadline = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label       = 'session'
        db_table        = 'session_booking'
        unique_together = ('learner', 'session')

    def __str__(self):
        return f"{self.learner.username} -> {self.session.title}"

    def can_start(self):
        from datetime import datetime
        now = timezone.now()
        session_datetime = timezone.make_aware(
            datetime.combine(self.session.date, self.session.start_time)
        )
        diff = session_datetime - now
        return (
            timezone.timedelta(minutes=-60) <= diff <= timezone.timedelta(minutes=15)
        )

    def is_overdue_for_auto_complete(self):
        if self.auto_complete_at and not self.learner_confirmed:
            return timezone.now() >= self.auto_complete_at
        return False
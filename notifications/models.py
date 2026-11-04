from django.db import models
from django.contrib.auth.models import User


class Notification(models.Model):

    NOTIFICATION_TYPES = [
        ('session_booked',       'Session Booked'),
        ('session_cancelled',    'Session Cancelled'),
        ('session_starting',     'Session Starting Soon'),
        ('reschedule_requested', 'Reschedule Requested'),
        ('reschedule_accepted',  'Reschedule Accepted'),
        ('reschedule_declined',  'Reschedule Declined'),
        ('review_received',      'Review Received'),
        ('credits_received',     'Credits Received'),
        ('announcement', 'Announcement'),
        ('dispute_filed', 'Dispute Filed'),
        ('dispute_resolved', 'Dispute Resolved'),
    ]

    ICON_MAP = {
        'session_booked':       'bi-calendar-check-fill',
        'session_cancelled':    'bi-calendar-x-fill',
        'session_starting':     'bi-alarm-fill',
        'reschedule_requested': 'bi-calendar-event-fill',
        'reschedule_accepted':  'bi-calendar2-check-fill',
        'reschedule_declined':  'bi-calendar2-x-fill',
        'review_received':      'bi-star-fill',
        'credits_received':     'bi-coin',
    }

    COLOR_MAP = {
        'session_booked':       'success',
        'session_cancelled':    'danger',
        'session_starting':     'warning',
        'reschedule_requested': 'warning',
        'reschedule_accepted':  'success',
        'reschedule_declined':  'danger',
        'review_received':      'primary',
        'credits_received':     'success',
    }

    recipient        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title            = models.CharField(max_length=255)
    message          = models.TextField()
    link             = models.CharField(max_length=500, blank=True, default='')
    is_read          = models.BooleanField(default=False)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.recipient.username} — {self.notification_type} — {'read' if self.is_read else 'unread'}"

    @property
    def icon(self):
        return self.ICON_MAP.get(self.notification_type, 'bi-bell-fill')

    @property
    def color(self):
        return self.COLOR_MAP.get(self.notification_type, 'primary')

    @classmethod
    def create(cls, recipient, notification_type, title, message, link=''):
        """Convenience method to create a notification."""
        return cls.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
        )
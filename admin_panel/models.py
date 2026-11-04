from django.db import models
from django.contrib.auth.models import User


class AdminAnnouncement(models.Model):
    AUDIENCE_CHOICES = [
        ('all', 'All Users'),
        ('tutors', 'Tutors Only'),
        ('learners', 'Learners Only'),
        ('both', 'Both Role Users'),
        ('specific', 'Specific User'),
    ]

    admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='announcements_sent'
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    audience = models.CharField(
        max_length=20,
        choices=AUDIENCE_CHOICES,
        default='all'
    )
    specific_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='announcements_received'
    )
    sent_to_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Admin Announcement'
        verbose_name_plural = 'Admin Announcements'

    def __str__(self):
        return f"{self.title} → {self.get_audience_display()} ({self.created_at.strftime('%d %b %Y')})"
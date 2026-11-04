from django.db import models
from django.contrib.auth.models import User


class AdminAnnouncement(models.Model):
    AUDIENCE_CHOICES = [
        ('all',      'All Users'),
        ('tutors',   'Tutors'),
        ('learners', 'Learners'),
        ('specific', 'Specific User'),
    ]

    admin         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='announcements')
    title         = models.CharField(max_length=255)
    message       = models.TextField()
    audience      = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default='all')
    specific_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='targeted_announcements')
    sent_to_count = models.IntegerField(default=0)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} → {self.audience}"
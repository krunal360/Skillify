from django.db import models
from django.contrib.auth.models import User
from session.models import Session, Booking


class Review(models.Model):
    TAG_CHOICES = [
        ('helpful',       'Helpful'),
        ('clear',         'Clear Explanation'),
        ('patient',       'Patient'),
        ('knowledgeable', 'Knowledgeable'),
        ('punctual',      'Punctual'),
        ('engaging',      'Engaging'),
    ]

    booking     = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='review', null=True, blank=True)
    session     = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='reviews')
    reviewer    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given')
    tutor       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_received')
    rating      = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment     = models.TextField(blank=True, default='')
    recommended = models.BooleanField(default=False)
    tags        = models.JSONField(default=list, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('session', 'reviewer')

    def __str__(self):
        return f"Review by {self.reviewer.username} — {self.rating}/5"

    def tag_labels(self):
        tag_map = dict(self.TAG_CHOICES)
        return [tag_map.get(t, t) for t in self.tags]
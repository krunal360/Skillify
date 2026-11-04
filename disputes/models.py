from django.db import models
from django.contrib.auth.models import User


class Dispute(models.Model):

    REASON_CHOICES = [
        ('session_not_completed',    'Session was not completed as agreed'),
        ('tutor_no_show',            'Tutor did not show up'),
        ('learner_no_show',          'Learner did not show up'),
        ('technical_issues',         'Technical problems during session'),
        ('content_not_as_described', 'Session content did not match description'),
        ('inappropriate_behavior',   'Inappropriate behavior during session'),
        ('payment_issue',            'Credits not transferred correctly'),
        ('recording_sharing',        'Zoom recording shared without consent'),
        ('other',                    'Other reason'),
    ]

    STATUS_CHOICES = [
        ('open',         'Open'),
        ('under_review', 'Under Review'),
        ('resolved',     'Resolved'),
        ('rejected',     'Rejected'),
    ]

    booking          = models.ForeignKey('session.Booking', on_delete=models.CASCADE, related_name='disputes')
    filed_by         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='filed_disputes')
    against          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='disputes_against')
    reason           = models.CharField(max_length=40, choices=REASON_CHOICES)
    description      = models.TextField()
    evidence_file    = models.FileField(upload_to='disputes/evidence/', blank=True, null=True)
    evidence_url     = models.URLField(blank=True, default='')
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    resolution_note  = models.TextField(blank=True, default='')
    resolved_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_disputes')
    resolved_at      = models.DateTimeField(null=True, blank=True)
    credits_refunded = models.BooleanField(default=False)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Dispute #{self.pk} — {self.get_reason_display()} ({self.status})"

    @property
    def is_open(self):
        return self.status in ['open', 'under_review']

    @property
    def is_closed(self):
        return self.status in ['resolved', 'rejected']

    @property
    def has_evidence(self):
        return bool(self.evidence_file or self.evidence_url)

    @property
    def status_color(self):
        return {
            'open':         '#F59E0B',
            'under_review': '#3B82F6',
            'resolved':     '#10B981',
            'rejected':     '#EF4444',
        }.get(self.status, '#6c757d')


class DisputeResponse(models.Model):
    """
    Response/defence added by the other party to an existing dispute.
    Only the party against whom the dispute was filed can add a response.
    """
    dispute       = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='responses')
    responded_by  = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dispute_responses')
    response      = models.TextField()
    evidence_file = models.FileField(upload_to='disputes/responses/', blank=True, null=True)
    evidence_url  = models.URLField(blank=True, default='')
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Response to Dispute #{self.dispute.pk} by {self.responded_by.get_full_name()}"

    @property
    def has_evidence(self):
        return bool(self.evidence_file or self.evidence_url)
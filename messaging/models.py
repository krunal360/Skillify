from django.db import models
from django.contrib.auth.models import User


class Conversation(models.Model):
    participant_1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations_as_p1')
    participant_2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations_as_p2')
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('participant_1', 'participant_2')

    def __str__(self):
        return f"{self.participant_1.username} — {self.participant_2.username}"

    def get_other_participant(self, user):
        if self.participant_1 == user:
            return self.participant_2
        return self.participant_1

    def get_unread_count(self, user):
        return self.messages.filter(is_read=False).exclude(sender=user).count()

    def get_last_message(self):
        return self.messages.order_by('-created_at').first()


class Message(models.Model):
    FILE_TYPE_CHOICES = [
        ('none',     'None'),
        ('image',    'Image'),
        ('document', 'Document'),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    content      = models.TextField(blank=True, default='')
    file         = models.FileField(upload_to='messaging/attachments/', null=True, blank=True)
    file_type    = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='none')
    file_name    = models.CharField(max_length=255, blank=True, default='')
    is_read      = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message from {self.sender.username} in {self.conversation}"

    def is_image(self):
        return self.file_type == 'image'

    def is_document(self):
        return self.file_type == 'document'
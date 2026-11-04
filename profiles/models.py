from django.db import models
from django.contrib.auth.models import User


class Certificate(models.Model):
    tutor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='certificates')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='certificates/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'profiles'
        db_table = 'profiles_certificate'

    def __str__(self):
        return f"{self.title} - {self.tutor.get_full_name()}"

    def is_image(self):
        return self.file.name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))

    def is_pdf(self):
        return self.file.name.lower().endswith('.pdf')
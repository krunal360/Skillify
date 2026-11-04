from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('learner', 'Learner'),
        ('tutor', 'Tutor'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='learner')
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    bio = models.TextField(blank=True, default='')
    learner_bio = models.TextField(blank=True, null=True, default=None)
    expertise = models.CharField(max_length=255, blank=True, default='')
    demo_video = models.URLField(blank=True, default='')
    linkedin = models.URLField(blank=True, default='')
    github = models.URLField(blank=True, default='')
    skills = models.ManyToManyField('skills.Skill', blank=True, related_name='users')
    learning_interests = models.ManyToManyField('skills.Skill', blank=True, related_name='interested_learners')
    trust_score = models.FloatField(default=0.0)
    otp = models.CharField(max_length=6, blank=True, default='')
    otp_created_at = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    class Meta:
        app_label = 'users'
        db_table = 'core_userprofile'

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    def avatar_url(self):
        if self.profile_picture:
            return self.profile_picture.url
        name = self.user.get_full_name() or self.user.username
        name_encoded = name.replace(' ', '+')
        colors = ['4ECDC4', '667eea', 'f093fb', '4facfe', 'FFB84D', 'f5576c']
        color = colors[self.user.pk % len(colors)]
        return f"https://ui-avatars.com/api/?name={name_encoded}&background={color}&color=fff&size=150"

    def get_embed_video_url(self):
        import re
        url = self.demo_video
        if not url:
            return ''

        # YouTube
        if 'youtube.com/watch' in url:
            match = re.search(r'v=([a-zA-Z0-9_-]+)', url)
            if match:
                return f'https://www.youtube.com/embed/{match.group(1)}'
        elif 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[-1].split('?')[0]
            return f'https://www.youtube.com/embed/{video_id}'
        elif 'youtube.com/embed/' in url:
            return url

        # Vimeo
        elif 'vimeo.com/' in url:
            match = re.search(r'vimeo\.com/(\d+)', url)
            if match:
                return f'https://player.vimeo.com/video/{match.group(1)}'

        # Loom
        elif 'loom.com/share/' in url:
            video_id = url.split('loom.com/share/')[-1].split('?')[0]
            return f'https://www.loom.com/embed/{video_id}'

        # Google Drive
        elif 'drive.google.com/file/d/' in url:
            match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
            if match:
                return f'https://drive.google.com/file/d/{match.group(1)}/preview'

        return url
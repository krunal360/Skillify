from django.db import models


class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, default='bi-lightbulb')

    class Meta:
        app_label = 'skills'
        db_table = 'core_skill'

    def __str__(self):
        return self.name
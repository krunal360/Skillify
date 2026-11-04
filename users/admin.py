from django.contrib import admin
from users.models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'trust_score', 'is_verified')
    list_filter = ('role', 'is_verified')
from django.contrib import admin
from profiles.models import Certificate


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ('title', 'tutor', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('title', 'tutor__first_name', 'tutor__last_name')
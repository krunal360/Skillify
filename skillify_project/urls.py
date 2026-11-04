from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from debug_toolbar.toolbar import debug_toolbar_urls
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', include('users.urls')),
    path('', include('skills.urls')),
    path('', include('session.urls')),
    path('', include('profiles.urls')),
    path('', include('reviews.urls')),
    path('', include('messaging.urls')),
    path('', include('trust.urls')),
    path('', include('notifications.urls')),
    path('', include('core.urls')),
    path('', include('disputes.urls')),
    path('skillify-admin/', include('skillify_admin.urls')),
] + debug_toolbar_urls()

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
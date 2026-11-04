from django.urls import path
from notifications import views

urlpatterns = [
    path('notifications/',                      views.notifications_page,         name='notifications_page'),
    path('notifications/unread-count/',         views.unread_count_api,           name='notifications_unread_count'),
    path('notifications/recent/',               views.recent_notifications_api,   name='notifications_recent'),
    path('notifications/mark-read/<int:pk>/',   views.mark_read,                  name='notification_mark_read'),
    path('notifications/mark-all-read/',        views.mark_all_read,              name='notifications_mark_all_read'),
]
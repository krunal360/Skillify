from django.urls import path
from messaging import views

urlpatterns = [
    path('messages/',                          views.inbox_view,         name='inbox'),
    path('messages/<int:conversation_id>/',    views.conversation_view,  name='conversation'),
    path('messages/start/<int:user_id>/',      views.start_conversation, name='start_conversation'),
    path('messages/send/',                     views.send_message,       name='send_message'),
    path('messages/mark-read/<int:conversation_id>/', views.mark_read,  name='mark_read'),
    path('messages/unread-count/',             views.unread_count,       name='unread_count'),
    path('messages/poll/<int:conversation_id>/', views.poll_messages, name='poll_messages'),
]
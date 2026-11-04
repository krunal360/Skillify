from django.urls import path
from session import views

urlpatterns = [
    path('my-sessions/',                        views.my_sessions_view,         name='my_sessions'),
    path('create-session/',                     views.create_session_view,      name='create_session'),
    path('book/<int:session_id>/',              views.book_session_view,        name='book_session'),
    path('cancel-booking/<int:booking_id>/',    views.cancel_booking_view,      name='cancel_booking'),
    path('start-session/<int:booking_id>/',     views.start_session_view,       name='start_session'),
    path('mark-complete/<int:booking_id>/',     views.mark_complete_view,       name='mark_complete'),
    path('reschedule/<int:session_id>/',        views.reschedule_session_view,  name='reschedule_session'),
    path('reschedule-accept/<int:booking_id>/', views.reschedule_accept_view,   name='reschedule_accept'),
    path('reschedule-decline/<int:booking_id>/',views.reschedule_decline_view,  name='reschedule_decline'),
    path('api/book/<int:session_id>/',          views.api_book_session,         name='api_book_session'),
]
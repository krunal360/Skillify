from django.urls import path
from profiles import views

urlpatterns = [
    path('profile/edit/', views.edit_tutor_profile_view, name='edit_tutor_profile'),
    path('profile/<int:pk>/', views.tutor_profile_view, name='tutor_profile'),
]
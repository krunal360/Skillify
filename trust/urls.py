from django.urls import path
from trust import views

app_name = 'trust'

urlpatterns = [
    path('score/<int:pk>/', views.trust_score_api, name='score_api'),
]
from django.urls import path
from skills import views

urlpatterns = [
    path('browse-skills/', views.browse_skills_view, name='browse_skills'),
]
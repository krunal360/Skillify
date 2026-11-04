from django.urls import path
from skillify_admin import views

urlpatterns = [
    path('login/',          views.admin_login_view,          name='admin_login'),
    path('logout/',         views.admin_logout_view,         name='admin_logout'),
    path('',                views.admin_dashboard_view,      name='admin_dashboard'),
    path('analytics/',      views.admin_analytics_view,      name='admin_analytics'),
    path('users/',          views.admin_users_view,          name='admin_users'),
    path('tutors/',         views.admin_tutors_view,         name='admin_tutors'),
    path('skills/',         views.admin_skills_view,         name='admin_skills'),
    path('sessions/',       views.admin_sessions_view,       name='admin_sessions'),
    path('reviews/',        views.admin_reviews_view,        name='admin_reviews'),
    path('disputes/',       views.admin_disputes_view,       name='admin_disputes'),
    path('reports/',        views.admin_reports_view,        name='admin_reports'),
    path('announcements/',  views.admin_announcements_view,  name='admin_announcements'),
    path('manage-admins/',  views.admin_manage_admins_view,  name='admin_manage_admins'),
]
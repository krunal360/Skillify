from django.urls import path
from core import views

urlpatterns = [
    # Auth
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('resend-otp/', views.resend_otp_view, name='resend_otp'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('reset-password/', views.reset_password_view, name='reset_password'),
    path('resend-reset-otp/', views.resend_reset_otp_view, name='resend_reset_otp'),

    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # Role
    path('switch-role/', views.switch_role, name='switch_role'),

    # API
    path('api/switch-role/', views.api_switch_role, name='api_switch_role'),
    path('api/check-email/', views.api_check_email, name='api_check_email'),
    path('api/register/', views.api_register, name='api_register'),

    path('wallet/', views.wallet_view, name='wallet'),
    path('wallet/export/', views.wallet_export_view, name='wallet_export'),

    
]
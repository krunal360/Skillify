from django.urls import path
from reviews import views

urlpatterns = [
    path('leave-review/<int:booking_id>/', views.leave_review_view, name='leave_review'),
]
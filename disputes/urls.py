from django.urls import path
from disputes import views

urlpatterns = [
    path('disputes/file/<int:booking_id>/', views.file_dispute_view,          name='file_dispute'),
    path('disputes/<int:pk>/',             views.view_dispute_view,           name='view_dispute'),
    path('disputes/<int:pk>/respond/',     views.add_dispute_response_view,   name='add_dispute_response'),
    path('disputes/',                      views.my_disputes_view,            name='my_disputes'),
]
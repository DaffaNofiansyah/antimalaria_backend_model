from django.urls import path

from . import views

urlpatterns = [
    path("predict/", views.PredictIC50View.as_view(), name="predict"),
    path('results/<str:task_id>/', views.TaskResultView.as_view(), name='task-result'),
]
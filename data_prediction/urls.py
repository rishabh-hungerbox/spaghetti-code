from django.urls import path

from . import views

urlpatterns = [
    path('vendor-day-level-predictor', views.VendorDataPredictionView.as_view()),
    path('vendor-item-level-predictor', views.VendorDataPredictionView.as_view()),
    ]

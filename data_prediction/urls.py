from django.urls import path

from . import views

urlpatterns = [
    path('vendor-day-level-predictor', views.VendorDataPredictionView.as_view()),
    path('order-populator', views.OrderPopulatorView.as_view()),
    path('vendor-chat-bot', views.VendorChatBotView.as_view()),
    path('vendor-item-level-predictor', views.VendorDataPredictionView.as_view()),
    path('review-populator', views.ReviewPopulatorView.as_view()),
    ]

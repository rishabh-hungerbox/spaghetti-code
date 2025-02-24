from django.urls import path

from . import views

urlpatterns = [
    path('vendor-day-level-predictor', views.VendorDataPredictionView.as_view()),
    path('order-populator', views.OrderPopulatorView.as_view()),
    path('vendor-chat-bot', views.VendorChatBotView.as_view()),
    path('vendor-item-level-predictor', views.VendorDataPredictionView.as_view()),
    path('review-populator', views.ReviewPopulatorView.as_view()),
    path('item-level-forecast', views.ItemLevelForecastView.as_view()),
    path('sentiment-analysis', views.SentimentAnalysisView.as_view()),
    path('arima', views.ArimaVendorDataPredictionView.as_view()),
    path('item-level-order-prediction', views.ItemLevelOrderPredictionView.as_view()),
    path('ration-finder', views.RationFinderView.as_view()),
    path('ration-prediction', views.RationPredictionView.as_view())
    ]

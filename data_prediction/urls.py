from django.urls import path

from . import views

urlpatterns = [
    path('vendor-day-level-predictor', views.VendorDataPredictionView.as_view()),
    path('order-populator', views.OrderPopulatorView.as_view()),
    path('vendor-chat-bot', views.VendorChatBotView.as_view()),
    path('vendor-item-level-predictor', views.VendorDataPredictionView.as_view()),
    path('review-populator', views.ReviewPopulatorView.as_view()),
    path('sentiment-analysis', views.SentimentAnalysisView.as_view()),
    path('arima', views.ArimaVendorDataPredictionView.as_view()),
    path('ration-finder', views.RationFinderView.as_view()),
    path('ration-prediction', views.RationPredictionView.as_view()),
    path('product-forecastor', views.ProductForecastorView.as_view()),
    path('vendor', views.VendorView.as_view()),
    path('company', views.CompanyView.as_view()),
    path('product-daily-forecastor', views.ProductDailyForecastorView.as_view()),
    path('image-analyzer', views.ImageAnalyzerView.as_view()),
    ]

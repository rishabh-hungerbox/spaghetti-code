from django.urls import path

from . import views

urlpatterns = [
    path('get-master-menu', views.MenuMapperAIView.as_view()),
    path('get-menu-image', views.MenuMapperImageView.as_view()),
    ]


from django.urls import include, path

urlpatterns = [
    path('api/ai/menu-mapping/', include('menu_mapping.urls')),
    path('api/ai/data-prediction/', include('data_prediction.urls')),
    ]

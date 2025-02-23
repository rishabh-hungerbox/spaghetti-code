
from django.urls import include, path

urlpatterns = [
    path('api/ai/v2/menu-mapping/', include('menu_mapping.urls')),
    path('api/ai/v2/data-prediction/', include('data_prediction.urls')),
    ]

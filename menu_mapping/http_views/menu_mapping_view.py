from django.http import HttpResponse, JsonResponse
from rest_framework.views import APIView
from menu_mapping.helper_classes.menu_mapper_helper import get_master_menu_response, process_data
from menu_mapping.helper_classes.utility import MenuMappingUtility
from io import TextIOWrapper
import csv
from menu_mapping.models import MenuMappingPrediction
import threading


class MenuMapperAIView(APIView):
    """ Get relevant master menus based on provided child menu name"""
    def get(self, request):
        menu_name = request.query_params.get('menu_name')
        relevant_items = get_master_menu_response(menu_name)
        return JsonResponse({'result': relevant_items})


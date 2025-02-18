from django.http import HttpResponse, JsonResponse
from rest_framework.views import APIView
from menu_mapping.helper_classes.menu_mapper_helper import get_master_menu_response
from menu_mapping.helper_classes.utility import MenuMappingUtility
from io import TextIOWrapper
import csv
from menu_mapping.helper_classes.image_generator import ImageGenerator
from menu_mapping.models import MenuMappingPrediction
import threading


class MenuMapperAIView(APIView):
    """ Get relevant master menus based on provided child menu name"""
    def get(self, request):
        menu_name = request.query_params.get('menu_name')
        # Create threads for parallel execution
        # data_thread = threading.Thread(target=lambda: setattr(threading.current_thread(), 'data_result', get_master_menu_response(menu_name)))
        # image_thread = threading.Thread(target=lambda: setattr(threading.current_thread(), 'image_result', ImageGenerator.generate_image(menu_name)))

        # # Start both threads
        # data_thread.start() 
        # image_thread.start()

        # # Wait for both threads to complete
        # data_thread.join()
        # image_thread.join()

        # # Get results
        # data = data_thread.data_result
        # link = image_thread.image_result
        data = get_master_menu_response(menu_name)
        link = ImageGenerator.generate_image(menu_name)
        data['image_url'] = link
        return JsonResponse(data, safe=False)
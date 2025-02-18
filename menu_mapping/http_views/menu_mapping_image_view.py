from django.http import HttpResponse, JsonResponse
from rest_framework.views import APIView
from menu_mapping.helper_classes.image_generator import ImageGenerator


class MenuMapperImageView(APIView):
    def get(self, request):
        menu_name = request.query_params.get('menu_name')
        s3_links = ImageGenerator.generate_image(menu_name)
        return JsonResponse({'image_links': s3_links}, safe=False)
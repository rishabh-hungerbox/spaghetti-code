from django.http import JsonResponse
from rest_framework.views import APIView
from etc.query_utility import QueryUtility
import json
from google import genai
import os


class CompanyView(APIView):
    def get(self, request):
        env = request.GET.get('env')
        data = []
        if env == 'prod':
            data = [
                {
                    'company_id': 135,
                    'company_name': 'Tata Consultancy Services'
                },
                {
                    'company_id': 200,
                    'company_name': 'American Express'
                },
            ]
        else:
            data = [
                {
                    'company_id': 388,
                    'company_name': 'Swish'
                },
                {
                    'company_id': 390,
                    'company_name': 'AI Avengers'
                },
            ]
        return JsonResponse(data, safe=False)

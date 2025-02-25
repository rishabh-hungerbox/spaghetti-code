from django.http import JsonResponse
from rest_framework.views import APIView
from etc.query_utility import QueryUtility
import json
from google import genai
import os
from etc.settings import tunnel_mysql, DATABASES

class CompanyView(APIView):
    def get(self, request):
        env = request.GET.get('env')
        data = []
        if env == 'prod':
            if os.getenv('APP_ENV') == 'local':
                DATABASES['mysql']['HOST'] = os.getenv('DB_HOST_PROD')
                DATABASES['mysql']['PORT'] = os.getenv('DB_PORT_PROD')
                DATABASES['mysql']['USER'] = os.getenv('DB_USERNAME_PROD')
                DATABASES['mysql']['PASSWORD'] = os.getenv('DB_PASSWORD_PROD')
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
            DATABASES['mysql']['HOST'] = os.environ.get('DB_HOST')
            DATABASES['mysql']['PORT'] = os.environ.get('DB_PORT')
            DATABASES['mysql']['USER'] = os.environ.get('DB_USERNAME')
            DATABASES['mysql']['PASSWORD'] = os.environ.get('DB_PASSWORD')
            if os.getenv('APP_ENV') == 'local':
                DATABASES['mysql']['HOST'] = '127.0.0.1'
                DATABASES['mysql']['PORT'] = int(tunnel_mysql.local_bind_port)
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

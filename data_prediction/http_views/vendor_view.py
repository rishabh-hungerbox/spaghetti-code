from django.http import JsonResponse
from rest_framework.views import APIView
from etc.query_utility import QueryUtility
import json
from google import genai
import os
from etc.query_utility import QueryUtility


class VendorView(APIView):
    def get(self, request):
        company_id = request.GET.get('company_id')
        print(company_id)
        query = '''select id, vendor_name from vendor where company_id = %s and active = 1;'''
        data = QueryUtility.execute_query(query, [company_id], db='mysql')
        return JsonResponse(data, safe=False)

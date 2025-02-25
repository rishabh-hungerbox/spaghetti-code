from django.http import JsonResponse
from rest_framework.views import APIView
from etc.query_utility import QueryUtility
import json
from google import genai
import os
from data_prediction.models import IngredientsData
from django.core.cache import cache
import hashlib

CACHE_TTL = 7200

# Initialize genai client - ensure API key is set in environment variables
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# Define response schema for structured output
response_schema = {
    'type': 'array',
    'items': {
        'type': 'object',
        'properties': {
            'ingredient': {'type': 'string'},
            'measurement_unit': {'type': 'string'},
            'measurement_value': {'type': 'number'}
        },
        'required': ['ingredient', 'measurement_unit', 'measurement_value']
    }
}



class RationFinderView(APIView):
    def get(self, request):
        vendor_id = request.GET.get('vendor_id')
        prediction_days = request.GET.get('prediction_days')
        
        # Generate cache key based on parameters
        cache_key = hashlib.md5(f"ration_finder_{vendor_id}_{prediction_days}".encode()).hexdigest()
        
        # Try to get cached results first
        cached_results = cache.get(cache_key)
        if cached_results:
            return JsonResponse(cached_results, safe=False)
            
        # Query to fetch last 300 days of order data
        query = '''select name from vendor_menu where vendor_id = %s;'''
        products = QueryUtility.execute_query(query, [vendor_id], db='mysql')
        
        for product in products:
            name = product['name']
            prompt = f'''You are an expert cook who knows detailed recipes of all food items.
            You need to find the ration required to make the given product.
            Provide list of ingredients along with the quantity required to make the product. (in grams or milliliters)
            Note: Use Indian Name like 'Atta', 'Ghee' instead of 'Wheat Flour', 'Butter'
            Don't add description to ingredients like 'Green chilies (slit)', 'Carrot (peeled and chopped)'
            keep the ingridents name simple and same like Capitalization format.
            


            Product is {name}'''

            print(prompt)

            # Model configuration
            model_name = "models/gemini-2.0-flash"
            
            # Generate prediction
            result = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    'response_mime_type': 'application/json',
                    'response_schema': response_schema,
                    'temperature': 0.0,
                    'top_p': 1.0,
                    'top_k': 1000,
                    'candidate_count': 1,
                    'seed': 42,
                }
            )

            ingridents = json.loads(result.text)
            print(ingridents)
            # Check if record already exists for this vendor_id and menu_name
            existing_record = IngredientsData.objects.using('mysql').filter(
                vendor_id=vendor_id,
                menu_name=name
            ).exists()
            
            if existing_record:
                continue
            IngredientsData.objects.using('mysql').create(
                vendor_id=vendor_id,
                menu_name=name,
                ingredients=ingridents
            )
            
        query = '''select * from ingredients_data where vendor_id = %s;'''
        ingredients = QueryUtility.execute_query(query, [vendor_id], db='mysql')

        # Cache the results before returning
        cache.set(cache_key, ingredients, CACHE_TTL)    
        return JsonResponse(ingredients, safe=False)

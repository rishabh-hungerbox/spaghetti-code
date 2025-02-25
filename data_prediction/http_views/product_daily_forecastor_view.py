from django.http import JsonResponse
from rest_framework.views import APIView
from etc.query_utility import QueryUtility
import json
from google import genai
import os
from django.core.cache import cache
import hashlib

# Initialize genai client - ensure API key is set in environment variables
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


response_schema = {
                'type': 'object',
                'properties': {
                    'item_predictions': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'product_name': {'type': 'string'},
                                'last_day_order_count': {'type': 'integer'},
                                'this_day_prediction': {'type': 'integer'},
                                'increase_percentage': {'type': 'number'},
                            },
                            'required': ['product_name', 'last_day_order_count', 'this_day_prediction', 'increase_percentage']
                        }
                    },
                },
                'required': ['item_predictions']
            }


class ProductDailyForecastorView(APIView):
    def get(self, request):
        vendor_id = request.GET.get('vendor_id')

        product_query = '''select vm.name, vm.id from vendor_menu vm where vm.vendor_id = %s and vm.active = 1;'''
        product_results = QueryUtility.execute_query(product_query, [vendor_id], db='mysql')
        product_map = {}
        for row in product_results:
            product_map[row['name']] = row['id']

        sales_query = '''select created_date, max(vm.name) as product_name, count(*) as order_count
from sales_order so
join order_items oi on oi.order_id = so.id
join vendor_menu vm on vm.id = oi.product_id
where so.vendor_id in (%s)
and created_date > DATE_FORMAT(NOW() - INTERVAL 90 DAY, %s)
group by created_date, oi.product_id
order by created_date, product_name asc;'''
        sales_results = QueryUtility.execute_query(sales_query, [vendor_id, '%Y-%m-%d'], db='mysql')

        sales_data = 'created_date, product_name, order_count\n'
        for row in sales_results:
            sales_data += f'{row["created_date"]}, {row["product_name"]}, {row["order_count"]}\n'

        response = find_sales_data(sales_data)
        for item in response['item_predictions']:
            item['product_id'] = product_map.get(item['product_name'], -1)
        return JsonResponse(response)


def find_sales_data(sales_data):
    prompt = f'''You are an AI system specialized in analyzing corporate food ordering patterns and making predictions.

System Context:
- You analyze food ordering patterns for a corporate food service provider
- The data represents daily order counts from a specific vendor
- The business operates primarily on weekdays
- The prediction should account for weekly patterns and holidays

Historical Sales Data:
{sales_data}

Required Analysis:
1. Based on the daily item sales data, predict the sales for the next day
2. Based on the last day, give a percentage of increase or decrease in sales
3. The prediction should be based on the most recent day and the previous day
Please provide the response in the specified JSON format with order_data and reasoning.
        '''

    # Generate cache key from prompt
    cache_key = f"sales_prediction_{hashlib.md5(prompt.encode()).hexdigest()}"
    
    # Try to get cached response
    cached_response = cache.get(cache_key)
    if cached_response:
        return cached_response

    print(prompt)

    model_name = "models/gemini-2.0-flash"
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
        })
    
    response = json.loads(result.text)
    
    # Cache the response for 1 hour (3600 seconds)
    cache.set(cache_key, response, 7200)
    
    return response
    

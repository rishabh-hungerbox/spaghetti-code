from django.http import JsonResponse
from rest_framework.views import APIView
from etc.query_utility import QueryUtility
import json
from google import genai
import os

# Initialize genai client - ensure API key is set in environment variables
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

response_schema = {
                'type': 'object',
                'properties': {
                    'item_forecast': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'string'},
                                'name': {'type': 'string'},
                                'forecast_percentage': {'type': 'integer'},
                                'reasoning': {'type': 'string'}
                            },
                            'required': ['id', 'name', 'forecast_percentage', 'reasoning']
                        }
                    },
                },
                'required': ['item_forecast']
            }


class ItemLevelForecastView(APIView):
    def get(self, request):
        vendor_id = request.GET.get('vendor_id')

        query = 'select id, name from vendor_menu where vendor_id = %s order by id;'
        data = QueryUtility.execute_query(query, [vendor_id], db='mysql')

        DATE_FORMAT = '%Y-%m-%d'
        sales_query = '''select oi.product_id, max(vm.name) as name, so.created_date, count(so.id) as order_count from sales_order so
                        join order_items oi on so.id = oi.order_id
                        join vendor_menu vm on vm.id = oi.product_id
                        where so.created_date > DATE_FORMAT(NOW() - INTERVAL 30 DAY, %s)
                        and so.vendor_id = %s
                        group by so.created_date
                        order by oi.product_id, so.created_date;'''
        sales_results = QueryUtility.execute_query(sales_query, [DATE_FORMAT, vendor_id], db='mysql')

        sales_data = 'id, name, date, order_count\n'
        available_sales_product_id = set()
        for row in sales_results:
            sales_data += f'{row["product_id"]}, {row["name"]}, {row["created_date"]}, {str(row["order_count"])}\n'
            available_sales_product_id.add(str(row["product_id"]))
            
        item_info = 'id, name\n'
        response = {
            'item_forecast': []
        }
        for row in data:
            if str(row["id"]) in available_sales_product_id:
                item_info += f'{row["id"]}: {row["name"]}\n'
            else:
                response['item_forecast'].append({
                    'id': str(row["id"]),
                    'name': row["name"],
                    'forecast_percentage': 0,
                    'reasoning': 'No sales data available'
                })
            
        prompt = '''Given the item list and sales data, tell how much the item sales has increased or decreased in percentage, by weekly basis
        if the sales are not available for the item, tell 0%, give reasoing for the percentage also.

        item list:
        {item_info}

        sales data:
        {sales_data}
        '''

        # Model name - Use specific version if available, otherwise use base model name
        model_name = "models/gemini-2.0-flash"  # Example of a specific version - check Gemini API documentation for available versions. If not available, use "gemini-pro" or "gemini-2-pro" as appropriate, or "gemini-2-flash" as in your original code if that's the intended model.

        result = client.models.generate_content(
                    model=model_name,  # Use the deterministic model name
                    contents=prompt.format(item_info=item_info, sales_data=sales_data),
                    config={
                            'response_mime_type': 'application/json',
                            'response_schema': response_schema,
                            'temperature': 0.0,  # Set temperature to 0 for maximum determinism
                            'top_p': 1.0,     # Set top_p to 1.0 for determinism with temperature 0
                            'top_k': 1000,    # Set top_k to a high value for determinism with temperature 0 and top_p 1.0
                            'candidate_count': 1,  # Keep candidate_count to 1 to reduce variability
                            'seed': 42,        # Keep seed for reproducibility in case of underlying randomness (less impact with temperature 0 but good practice)
                        },)
        
        llm_response = json.loads(result.text)
        for item in llm_response['item_forecast']:
            response['item_forecast'].append({
                'id': item['id'],
                'name': item['name'],
                'forecast_percentage': item['forecast_percentage'],
                'reasoning': item['reasoning']
            })
        return JsonResponse(response)

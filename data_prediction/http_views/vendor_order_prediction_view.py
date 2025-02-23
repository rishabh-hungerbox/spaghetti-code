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
                    'order_data': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'date': {'type': 'string'},
                                'order_count': {'type': 'integer'}
                            },
                            'required': ['date', 'order_count']
                        }
                    },
                    'reasoning': {'type': 'string'}
                },
                'required': ['order_data', 'reasoning']
            }


class VendorDataPredictionView(APIView):
    def get(self, request):
        vendor_id = request.GET.get('vendor_id')
        DATE_FORMAT = '%Y-%m-%d'
        query = '''select so.created_date, count(so.id) as order_count from sales_order so
                    where so.created_date > DATE_FORMAT(NOW() - INTERVAL 30 DAY, %s)
                    and so.vendor_id = %s
                    group by so.created_date
                    order by so.created_date;'''
        data = QueryUtility.execute_query(query, [DATE_FORMAT, vendor_id], db='mysql')

        response = {'current_data': [], 'predicted_data': []}

        prompt = 'Given the following orders with date followed by order count\n'

        for row in data:
            prompt += f'{row["created_date"]}: {row["order_count"]}\n'
            response['current_data'].append({
                'date': str(row['created_date']), # Ensure date is serialized as string for JSON consistency
                'order_count': row['order_count']
            })

        prompt += '''\nBased on the historical data above:
1. Predict the order count for the next 7 days
2. Provide clear reasoning based on the patterns identified
3. Ensure predictions follow the observed patterns and trends'''

        # Model name - Use specific version if available, otherwise use base model name
        model_name = "models/gemini-2.0-flash"  # Example of a specific version - check Gemini API documentation for available versions. If not available, use "gemini-pro" or "gemini-2-pro" as appropriate, or "gemini-2-flash" as in your original code if that's the intended model.

        result = client.models.generate_content(
                    model=model_name,  # Use the deterministic model name
                    contents=prompt,
                    config={
                            'response_mime_type': 'application/json',
                            'response_schema': response_schema,
                            'temperature': 0.0,  # Set temperature to 0 for maximum determinism
                            'top_p': 1.0,     # Set top_p to 1.0 for determinism with temperature 0
                            'top_k': 1000,    # Set top_k to a high value for determinism with temperature 0 and top_p 1.0
                            'candidate_count': 1,  # Keep candidate_count to 1 to reduce variability
                            'seed': 42,        # Keep seed for reproducibility in case of underlying randomness (less impact with temperature 0 but good practice)
                        },)

        response['predicted_data'] = json.loads(result.text)
        return JsonResponse(response)

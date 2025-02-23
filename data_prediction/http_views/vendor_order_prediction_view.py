from django.http import JsonResponse
from rest_framework.views import APIView
from etc.query_utility import QueryUtility
import json
from google import genai
import os


# Initialize genai client - ensure API key is set in environment variables
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Define response schema for structured output
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
        
        # Query to fetch last 300 days of order data
        query = '''
            SELECT 
                so.created_date, 
                COUNT(so.id) as order_count 
            FROM sales_order so
            WHERE so.created_date between '2024-01-01' and '2025-01-31'
                AND so.vendor_id = %s
            GROUP BY so.created_date
            ORDER BY so.created_date;
        '''
        data = QueryUtility.execute_query(query, [vendor_id], db='mysql')

        response = {'current_data': [], 'predicted_data': []}

        # Format historical data for response and create data string for prompt
        historical_data_str = ""
        for row in data:
            historical_data_str += f'{row["created_date"]}: {row["order_count"]}\n'
            # response['current_data'].append({
            #     'date': str(row['created_date']),
            #     'order_count': row['order_count']
            # })
        print(historical_data_str)

        # Construct structured prompt with system role and context
        prompt = f'''You are an AI system specialized in analyzing corporate food ordering patterns and making predictions.

System Context:
- You analyze food ordering patterns for a corporate food service provider
- The data represents daily order counts from a specific vendor
- The business operates primarily on weekdays
- The prediction should account for weekly patterns and holidays

Business Rules:
1. Weekday Patterns:
   - Monday and Friday: Generally lower order counts due to employee leave patterns
   - Tuesday, Wednesday, Thursday: Peak ordering days
   - Tuesday and Wednesday typically show highest order volumes
2. Weekend/Holiday Impact:
   - Significantly reduced orders on weekends (Saturday and Sunday)
   - Similar reduction on public holidays
3. Seasonal Considerations:
   - Consider any visible seasonal patterns in the historical data
   - Account for upcoming holidays or special events

Historical Data:
{historical_data_str}

Required Analysis:
1. Generate daily order count predictions for the next 30 days
2. Provide detailed reasoning for your predictions, including:
   - Weekly patterns identified in historical data
   - Any seasonal trends observed
   - Impact of upcoming holidays or events
3. Ensure predictions maintain consistency with:
   - Historical weekly patterns
   - Typical day-of-week variations
   - Seasonal trends if present

Please provide the response in the specified JSON format with order_data and reasoning.'''

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

        response['predicted_data'] = json.loads(result.text)
        return JsonResponse(response)

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
                    'product_name': {'type': 'string'},
                    'order_count': {'type': 'integer'}
                },
                'required': ['date', 'product_name', 'order_count']
            }
        },
        'reasoning': {'type': 'string'}
    },
    'required': ['order_data', 'reasoning']
}


class ItemLevelOrderPredictionView(APIView):
    def get(self, request):
        vendor_id = request.GET.get('vendor_id')
        prediction_days = request.GET.get('prediction_days')
        DATE_FORMAT = '%Y-%m-%d'
        
        # Query to fetch last 300 days of order data
        query = '''
            select created_date, max(vm.name) as product_name, count(*) as order_count
from sales_order so
join order_items oi on oi.order_id = so.id
join vendor_menu vm on vm.id = oi.product_id
where so.vendor_id in (%s)
and created_date > DATE_FORMAT(NOW() - INTERVAL 90 DAY, %s)
group by created_date, oi.product_id
order by created_date, product_name asc;'''
        data = QueryUtility.execute_query(query, [vendor_id, DATE_FORMAT], db='mysql')

        response = {'current_data': [], 'predicted_data': []}

        # Format historical data for response and create data string for prompt
        historical_data_str = "created_date, product_name, order_count\n"
        for row in data:
            historical_data_str += f'{row["created_date"]}, {row["product_name"]}, {row["order_count"]}\n'
            response['current_data'].append({
                'date': str(row['created_date']),
                'product_name': row['product_name'],
                'order_count': row['order_count']
            })
        print(historical_data_str)
        
        # Holiday data
        holiday_str = '''- 2024-12-25, Christmas Day
- 2025-01-01, New Year's Day
- 2025-01-14, Makar Sankranti / Pongal
- 2025-01-23, Netaji Subhas Chandra Bose Jayanti
- 2025-01-26, Republic Day
- 2025-02-14, Maha Shivaratri
- 2025-03-17, Holi
- 2025-03-21, Good Friday
'''


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
   
Holiday Data:
{holiday_str}

Historical Data:
{historical_data_str}

Required Analysis:
1. Generate daily order count predictions for the next {prediction_days} days for each product
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

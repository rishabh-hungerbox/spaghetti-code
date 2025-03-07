from django.http import JsonResponse
from rest_framework.views import APIView
from etc.query_utility import QueryUtility
import json
from google import genai
import os
from django.core.cache import cache
import hashlib
import time


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

# Add after existing imports
CACHE_TTL = 7200  # 7200 seconds = 2 hours


class VendorDataPredictionView(APIView):
    def get(self, request):
        vendor_id = request.GET.get('vendor_id')
        prediction_days = request.GET.get('prediction_days')
        DATE_FORMAT = '%Y-%m-%d'

        # Query to fetch last 300 days of order data
        query = '''
            select created_date, count(*) as order_count from sales_order
where vendor_id in (%s)
and created_date > DATE_FORMAT(NOW() - INTERVAL 60 DAY, %s)
group by created_date, vendor_id
order by created_date, vendor_id asc;'''
        data = QueryUtility.execute_query(query, [vendor_id, DATE_FORMAT], db='mysql')

        response = {'current_data': [], 'predicted_data': []}

        # Format historical data for response and create data string for prompt
        historical_data_str = "created_date, order_count\n"
        for row in data:
            historical_data_str += f'{row["created_date"]}: {row["order_count"]}\n'
            response['current_data'].append({
                'date': str(row['created_date']),
                'order_count': row['order_count']
            })
            
        vs_query = '''SELECT
                    CASE day_of_week
                        WHEN 0 THEN 'Sunday'
                        WHEN 1 THEN 'Monday'
                        WHEN 2 THEN 'Tuesday'
                        WHEN 3 THEN 'Wednesday'
                        WHEN 4 THEN 'Thursday'
                        WHEN 5 THEN 'Friday'
                        WHEN 6 THEN 'Saturday'
                    END AS day_of_week,
                    COUNT(*) AS schedules
                FROM vendor_schedules
                WHERE vendor_id = %s AND active = 1
                GROUP BY day_of_week
                ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday');'''
                
        vendor_schedule_data = QueryUtility.execute_query(vs_query, [vendor_id], db='mysql')
        vendor_schedule_str = 'Day of the week, Schedule Count \n'
        for row in vendor_schedule_data:
            vendor_schedule_str += f'{row["day_of_week"]}: {row["schedules"]}\n'
        
        # Holiday data
        holiday_str = ''' date, holiday, region, weightage
- 2024-12-25, Christmas Day, India, 10
- 2025-01-01, New Year's Day, India, 10
- 2025-01-14, Makar Sankranti / Pongal, India, 8
- 2025-01-26, Republic Day, India, 10
- 2025-02-26, Maha Shivaratri, India, 9
- 2025-03-14, Holi, India, 9
- 2023-03-30, Ugadi/ Godi Padva, India, 7
- 2023-03-31, Eid, India, 5
'''

        query_location = '''select max(c.name) as city_name, max(s.name) as state_name from vendor v
join vendor_location vl on v.id = vl.vendor_id
join location l on vl.location_id = l.id
join addresses a on l.address_id = a.id
join states s on a.state_id = s.id
join hungerbox.cities c on a.city_id = c.id
where v.id = %s and l.active = 1 and vl.active = 1 group by c.id, s.id;'''
        location_data = QueryUtility.execute_query(query_location, [vendor_id], db='mysql')
        if len(location_data) > 0:
            location_str = f'City: {location_data[0]["city_name"]}, State: {location_data[0]["state_name"]}'
        else:
            location_str = ''

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
   
Holiday Data with weightage of holiday, high weightage means more impact on order count:
{holiday_str}

Location Data:
{location_str}

Vendor Schedule Data, Day of week on which schedule do not exist will not have orders:
{vendor_schedule_str}

Historical Data:
{historical_data_str}

Required Analysis:
1. Generate daily order count predictions for the next {prediction_days} days
2. Provide detailed reasoning for your predictions, including:
   - Weekly patterns identified in historical data
   - Any seasonal trends observed
   - Impact of upcoming holidays or events
3. Ensure predictions maintain consistency with:
   - Historical weekly patterns
   - Typical day-of-week variations
   - Seasonal trends if present
4. Don't talk about holiday weightag

Please provide the response in the specified JSON format with order_data and reasoning.'''

        print(prompt)

        # Generate cache key from prompt
        cache_key = hashlib.md5(prompt.format(
            historical_data_str=historical_data_str,
            holiday_str=holiday_str,
            location_str=location_str,
            vendor_schedule_str=vendor_schedule_str,
            prediction_days=prediction_days
        ).encode()).hexdigest()
        
        # Try to get cached response
        cached_response = cache.get(cache_key)
        if cached_response:
            time.sleep(0.3)
            return JsonResponse(cached_response)

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
        
        # Cache the response before returning
        cache.set(cache_key, response, CACHE_TTL)
        return JsonResponse(response)
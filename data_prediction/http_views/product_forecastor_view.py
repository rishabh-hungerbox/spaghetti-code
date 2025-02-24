from django.http import JsonResponse
from rest_framework.views import APIView
from etc.query_utility import QueryUtility
import json
from google import genai
import os

# Initialize genai client - ensure API key is set in environment variables
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

feedback_schema = {
    'type': 'object',
    'properties': {
        'feedback_summary': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'points': {'type': 'string'}
                },
                'required': ['points']
            }
        },
        'suggestions': {
            'type': 'array', 
            'items': {
                'type': 'object',
                'properties': {
                    'points': {'type': 'string'}
                },
                'required': ['points']
            }
        }
    },
    'required': ['feedback_summary', 'suggestions']
}


response_schema = {
                'type': 'object',
                'properties': {
                    'order_data': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'date': {'type': 'string'},
                                'order_count': {'type': 'integer'},
                            },
                            'required': ['date', 'order_count']
                        }
                    },
                    'reasoning': {'type': 'string'}
                },
                'required': ['order_data', 'reasoning']
            }


class ProductForecastorView(APIView):
    def get(self, request):
        product_id = request.GET.get('product_id')
        vendor_id = request.GET.get('vendor_id')
        prediction_days = request.GET.get('prediction_days', 30)
        DATE_FORMAT = '%Y-%m-%d'

        sales_query = '''select so.created_date, sum(oi.qty) as order_count from sales_order so
join order_items oi on oi.order_id = so.id
where product_id = %s
and so.created_date > DATE_FORMAT(NOW() - INTERVAL 60 DAY, %s)
group by so.created_date;'''
        sales_results = QueryUtility.execute_query(sales_query, [product_id, DATE_FORMAT], db='mysql')

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

        sales_data = 'date, order_count\n'
        response = {
            'current_data': []
        }
        for row in sales_results:
            sales_data += f'{row["created_date"]}, {str(row["order_count"])}\n'
            response['current_data'].append({
                'date': row['created_date'],
                'order_count': int(row['order_count'])
            })
            
        ingredients_query = '''select vm.name, ingredients from vendor_menu vm
join ingredients_data id on vm.vendor_id = id.vendor_id and vm.name = id.menu_name
where vm.id = %s;'''
        ingredients_results = QueryUtility.execute_query(ingredients_query, [product_id], db='mysql')
        if len(ingredients_results) == 0:
            raise Exception('No ingredients found for the product')
        
        product_name = ingredients_results[0]['name']
        ingredients = ingredients_results[0]['ingredients']
        
        ingredients_data= json.loads(ingredients)
        response['predicted_data'] = find_sales_data(holiday_str, sales_data, prediction_days)
        response['ingredients_data'] = ingredients_data
        response['feedback'] = product_feedback(vendor_id, product_name)
        return JsonResponse(response)


def find_sales_data(holiday_str, sales_data, prediction_days):
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

Historical Sales Data:
{sales_data}

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

Please provide the response in the specified JSON format with order_data and reasoning.
        '''

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
    return json.loads(result.text)


def product_feedback(vendor_id, product_name):
    DATE_FORMAT = '%Y-%m-%d'
    review_query = '''SELECT
        concat(r.rating, '/5') as 'rating',
        group_concat(
                (
                    CASE
                        WHEN ro.type = 'text' THEN ror.value
                        WHEN ro.type = 'checkbox' AND ror.value in ('1', 'true') THEN ro.question
                        WHEN ro.type = 'star' AND ror.value != '' THEN ro.type || ':' || ror.value
                        ELSE ''
                        END
                    )
                SEPARATOR '. '
            ) AS user_comment
    FROM review r
             LEFT JOIN review_options_response ror ON ror.review_id = r.id
             LEFT JOIN review_options ro ON ro.id = ror.review_option_id
    WHERE r.vendor_id in (%s)
    AND r.order_created_date > DATE_FORMAT(NOW() - INTERVAL 90 DAY, %s)
    AND r.reference = 'order' and r.order_items = %s
GROUP BY r.id order by date(r.created_at), order_items;'''
    review_results = QueryUtility.execute_query(review_query, [vendor_id, DATE_FORMAT, product_name], db='mysql')
    review_str = 'Rating out of 5, User Comment\n'
    for row in review_results:
        review_str += f'{row["rating"]}, {row["user_comment"]}\n'
        
    prompt = f'''You are an AI system specialized to analyze customer feedback and provide feedback on the product.
    Customer Feedback:
    {review_str}

    Required Analysis:
    1. Analyze the customer feedback and provide feedback on the product.
    2. Give a summary of the feedback in 2-3 points.
    3. Give suggestions to improve the product based on the said feedback using 2-3 points.
    '''
    model_name = "models/gemini-2.0-flash"
    result = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config={
            'response_mime_type': 'application/json',
            'response_schema': feedback_schema,
            'temperature': 0.0,
            'top_p': 1.0,
            'top_k': 1000,
            'candidate_count': 1,
            'seed': 42,
        })
    return json.loads(result.text)
    

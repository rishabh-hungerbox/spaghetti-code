from django.http import JsonResponse
from rest_framework.views import APIView
from etc.query_utility import QueryUtility
import json
from google import genai
import os
from etc.redis_fetcher import CacheHandler

# Initialize genai client - ensure API key is set in environment variables
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


class VendorChatBotView(APIView):
    def get(self, request):
        vendor_id = request.GET.get('vendor_id')
        question = request.GET.get('question')
        session_id = request.GET.get('session_id')
        question_answer_data = ''
        cache_data = None
        
        if session_id:
            cache_key = f'question_answer_chat_{session_id}'
            cache_data = CacheHandler.get_dict_cache_data(cache_key)
            if cache_data:
                for data in cache_data:
                    question_answer_data += f'System: {data["question"]}\n'
                    question_answer_data += f'Vendor: {data["answer"]}\n'

        DATE_FORMAT = '%Y-%m-%d'

        # Get vendor information
        vendor_query = '''select vendor_name, description from vendor where id = %s;'''
        vendor_data = QueryUtility.execute_query(vendor_query, [vendor_id], db='mysql')
        vendor_name = vendor_data[0]['vendor_name']
        description = vendor_data[0]['description']

        # Get review data
        review_query = '''SELECT
        r.order_items,
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
            ) AS user_comment,
    date(r.created_at) as 'comment_date'
    FROM review r
             LEFT JOIN review_options_response ror ON ror.review_id = r.id
             LEFT JOIN review_options ro ON ro.id = ror.review_option_id
    WHERE r.vendor_id in (%s)
    AND r.order_created_date > DATE_FORMAT(NOW() - INTERVAL 30 DAY, %s)
    AND r.reference = 'order'
GROUP BY r.id order by date(r.created_at), order_items;'''
        reviews = QueryUtility.execute_query(review_query, [vendor_id, DATE_FORMAT], db='mysql')
        review_data = ''
        
        review_data_dict = {}
        for row in reviews:
            if row['comment_date'] not in review_data_dict:
                review_data_dict[row['comment_date']] = []
                review_data += f'\nReview Date: {row["comment_date"]}\n'
            review_data_dict[row['comment_date']].append({
                'order_items': row['order_items'],
                'rating': row['rating'],
                'user_comment': row['user_comment']
            })
            review_data += f'- Item: {row["order_items"]} - Rating (out of 5): {row["rating"]}'
            if row['user_comment'] != '':
                review_data += f'- Comment: {row["user_comment"]}\n'

        # Get sales data
        query = '''select so.created_date, max(vm.name) as 'menu_name', count(oi.qty) as order_count from sales_order so
                    join order_items oi on so.id = oi.order_id
                    join vendor_menu vm on vm.id = oi.product_id
                    where so.created_date > DATE_FORMAT(NOW() - INTERVAL 30 DAY, %s)
                    and so.vendor_id = %s
                    group by so.created_date, oi.product_id
                    order by so.created_date;'''
        data = QueryUtility.execute_query(query, [DATE_FORMAT, vendor_id], db='mysql')

        # Format historical data
        historical_data = ""
        order_date_data = {}
        for row in data:
            if row['created_date'] not in order_date_data:
                order_date_data[row['created_date']] = []
            order_date_data[row['created_date']].append({
                'menu_name': row['menu_name'],
                'order_count': row['order_count']
            })

        for date, items in order_date_data.items():
            historical_data += f'\nDate: {date}\n'
            for item in items:
                historical_data += f'- {item["menu_name"]}: {item["order_count"]} orders\n'

        # Structured prompt with clear sections
        prompt = {
            "system_role": """You are an AI assistant dedicated to helping vendors understand their business performance. 
Your role is to analyze sales data and provide insights that can help improve their business. 
Focus only on business-relevant information and avoid any off-topic discussions.""",
            
            "context": {
                "vendor_name": vendor_name,
                "business_description": description,
                "data_timeframe": "Last 30 days of sales data",
                "historical_data": historical_data,
                "review_data": review_data
            },

            "guidelines": """
- Provide specific insights based on the sales data
- Focus on trends and patterns in the data
- Make business-relevant recommendations
- Stay within the scope of food service and business operations
- Do not discuss topics unrelated to the vendor's business""",

            "question": question
        }

        # Convert prompt to string format
        formatted_prompt = f"""System Role:
{prompt['system_role']}

Business Context:
Vendor: {prompt['context']['vendor_name']}
Description: {prompt['context']['business_description']}
Timeframe: {prompt['context']['data_timeframe']}

Previous Chat History:
{question_answer_data}

Historical Sales Data:
{prompt['context']['historical_data']}

Review Data:
{prompt['context']['review_data']}

Guidelines:
{prompt['guidelines']}

Question: {prompt['question']}"""

        # Model name
        model_name = "models/gemini-2.0-flash"
        
        print(formatted_prompt)

        # Generate response
        result = client.models.generate_content(
            model=model_name,
            contents=formatted_prompt
        )
        
        if session_id:
            current_data = {
                    'question': question,
                    'answer': result.text
            }
            if cache_data:
                cache_data.append(current_data)
            else:
                cache_data = [current_data]
            CacheHandler.set_dict_cache_data(cache_key, cache_data)

        return JsonResponse({'answer': result.text})

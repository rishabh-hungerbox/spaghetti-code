from django.http import JsonResponse
from rest_framework.views import APIView
from etc.query_utility import QueryUtility
import json
from google import genai
import os

# Initialize genai client - ensure API key is set in environment variables
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


class VendorChatBotView(APIView):
    def get(self, request):
        vendor_id = request.GET.get('vendor_id')
        question = request.GET.get('question')
        DATE_FORMAT = '%Y-%m-%d'
        
        # Get vendor information
        vendor_query = '''select vendor_name, description from vendor where id = %s;'''
        vendor_data = QueryUtility.execute_query(vendor_query, [vendor_id], db='mysql')
        vendor_name = vendor_data[0]['vendor_name']
        description = vendor_data[0]['description']
        
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
                "historical_data": historical_data
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

Historical Sales Data:
{prompt['context']['historical_data']}

Guidelines:
{prompt['guidelines']}

Question: {prompt['question']}"""

        # Model name
        model_name = "models/gemini-2.0-flash"

        # Generate response
        result = client.models.generate_content(
            model=model_name,
            contents=formatted_prompt
        )

        return JsonResponse({'answer': result.text})

from django.http import JsonResponse
from rest_framework.views import APIView
from etc.query_utility import QueryUtility
import json
from google import genai
import os
from etc.redis_fetcher import CacheHandler
from django.core.cache import cache
import hashlib

CACHE_TTL = 7200  # 
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
                if len(cache_data) < 7:
                    for data in cache_data:
                        question_answer_data += f'Vendor_Question: {data["question"]}\n'
                        question_answer_data += f'System_Answer: {data["answer"]}\n'

        DATE_FORMAT = '%Y-%m-%d'

        # Get vendor information
        vendor_query = '''select vendor_name, description from vendor where id = %s;'''
        vendor_data = QueryUtility.execute_query(vendor_query, [vendor_id], db='mysql')
        vendor_name = vendor_data[0]['vendor_name']
        description = vendor_data[0]['description']
        vendor_schedule_str = ''
        
        if 'schedule' in question.lower():
            # vendor schedule data
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
            min(vs.start_time) as start_time, max(vs.end_time) as end_time, l.name as location_name, c.name as company_name, ct.name as city, s.name as state_name
        FROM vendor_schedules vs
        join location l on vs.location_id = l.id
        join company c on l.company_id = c.id
        join addresses a on l.address_id = a.id
        join states s on a.state_id = s.id
        join cities ct on a.city_id = ct.id
        WHERE vs.vendor_id = %s AND vs.active = 1
        group by vs.vendor_id, vs.location_id, vs.day_of_week
        ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday');'''

            vendor_schedule_data = QueryUtility.execute_query(vs_query, [vendor_id], db='mysql')
            vendor_schedule_str = 'Day of the week, Start Time, End Time, Location Name, Company Name, City, State \n'
            for row in vendor_schedule_data:
                vendor_schedule_str += f'{row["day_of_week"]}, {row["start_time"]}, {row["end_time"]}, {row["location_name"]}, {row["company_name"]}, {row["city"]}, {row["state_name"]}\n'

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
    AND r.order_created_date > DATE_FORMAT(NOW() - INTERVAL 90 DAY, %s)
    AND r.reference = 'order'
GROUP BY r.id order by date(r.created_at), order_items;'''
        reviews = QueryUtility.execute_query(review_query, [vendor_id, DATE_FORMAT], db='mysql')

        # Get sales data first
        query = '''select so.created_date, max(vm.name) as 'menu_name', 
                    count(oi.qty) as order_count, max(oi.price) as item_price 
                    from sales_order so
                    join order_items oi on so.id = oi.order_id
                    join vendor_menu vm on vm.id = oi.product_id
                    where so.created_date > DATE_FORMAT(NOW() - INTERVAL 90 DAY, %s)
                    and so.vendor_id = %s
                    group by so.created_date, oi.product_id
                    order by so.created_date;'''
        data = QueryUtility.execute_query(query, [DATE_FORMAT, vendor_id], db='mysql')

        # First create item_total_orders and item_prices
        item_total_orders = {}  # Track total orders per item
        item_prices = {}  # Track prices per item

        # Aggregate total orders per item
        for row in data:
            if row['menu_name'] not in item_total_orders:
                item_total_orders[row['menu_name']] = 0
                item_prices[row['menu_name']] = row['item_price']
            item_total_orders[row['menu_name']] += row['order_count']

        # Then create review data and item performance
        review_data = "Item Reviews Summary:\n"
        review_data += "Item Name, Rating, Comments\n"
        review_data_dict = {}
        for row in reviews:
            review_data += f"{row['order_items']}, {row['rating']}, {row['user_comment']}\n"
            # if row['comment_date'] not in review_data_dict:
            #     review_data_dict[row['comment_date']] = []
            # review_data_dict[row['comment_date']].append({
            #     'order_items': row['order_items'],
            #     'rating': row['rating'],
            #     'user_comment': row['user_comment']
            # })

        # Organize reviews by item
        item_performance = {}
        for date, reviews in review_data_dict.items():
            for review in reviews:
                item = review['order_items']
                if item not in item_performance:
                    item_performance[item] = {
                        'ratings': [],
                        'comments': [],
                        'orders': item_total_orders.get(item, 0),
                        'price': item_prices.get(item, 0)
                    }
                item_performance[item]['ratings'].append(review['rating'])
                if review['user_comment']:
                    item_performance[item]['comments'].append(review['user_comment'])

        # Calculate average ratings
        for item in item_performance:
            ratings = item_performance[item]['ratings']
            if ratings:
                avg_rating = sum([float(r.split('/')[0]) for r in ratings]) / len(ratings)
                item_performance[item]['rating'] = avg_rating
            else:
                item_performance[item]['rating'] = None

        # Then identify best and worst selling items
        sorted_items = sorted(item_total_orders.items(), key=lambda x: x[1], reverse=True)
        best_selling = sorted_items[0]  # (item_name, order_count)
        worst_selling = sorted_items[-1]  # (item_name, order_count)

        # Create performance data structure
        performance_data = {
            'best_selling': {
                'name': best_selling[0],
                'orders': best_selling[1],
                'price': item_prices[best_selling[0]],
                'rating': item_performance.get(best_selling[0], {}).get('rating')
            },
            'worst_selling': {
                'name': worst_selling[0],
                'orders': worst_selling[1],
                'price': item_prices[worst_selling[0]],
                'rating': item_performance.get(worst_selling[0], {}).get('rating')
            }
        }

        # Format review summary
        # review_data = "\nItem Reviews Summary:\n"
        # for item, data in item_performance.items():
        #     avg_rating = data['rating']
        #     review_data += f"{item}:\n"
        #     review_data += f"- Average Rating: {avg_rating:.1f}/5\n"
        #     review_data += f"- Total Reviews: {len(data['ratings'])}\n"

        # Format historical item-level data with clear item performance metrics
        historical_data = ""
        historical_data += "\nItem Performance Data:\n"
        historical_data += "Best selling item: " + best_selling[0] + f": {best_selling[1]} orders, Price: ₹{item_prices[best_selling[0]]}\n"
        historical_data += "Worst selling item: " + worst_selling[0] + f": {worst_selling[1]} orders, Price: ₹{item_prices[worst_selling[0]]}\n"
        
        # Use static holiday data
        holiday_str = '''- 2024-12-25, Christmas Day
- 2025-01-01, New Year's Day
- 2025-01-14, Makar Sankranti / Pongal
- 2025-01-23, Netaji Subhas Chandra Bose Jayanti
- 2025-01-26, Republic Day
- 2025-02-14, Maha Shivaratri
- 2025-03-17, Holi
- 2025-03-21, Good Friday'''

        # Get revenue data with proper aggregation
        revenue_query = '''SELECT created_date AS date,
SUM(vm.price) AS daily_sales,
COUNT(*) as total_orders
from sales_order so
join order_items oi on oi.order_id = so.id
join vendor_menu vm on vm.id = oi.product_id
WHERE so.vendor_id = %s
    AND created_date > DATE_FORMAT(NOW() - INTERVAL 90 DAY, %s)
    AND so.status NOT IN ('rejected', 'payment_failed')
GROUP BY created_date
ORDER BY date'''
        
        revenue_data = QueryUtility.execute_query(revenue_query, [vendor_id, DATE_FORMAT], db='mysql')

        # Format revenue data
        daily_revenue_data = {}
        monthly_revenue_data = {}
        total_revenue = 0
        total_orders = 0

        for row in revenue_data:
            date_str = row['date'].strftime('%Y-%m-%d')
            month_str = row['date'].strftime('%Y-%m')
            daily_sales = float(row['daily_sales'])
            daily_orders = int(row['total_orders'])
            
            # Store daily data
            daily_revenue_data[date_str] = {
                'sales': daily_sales,
                'orders': daily_orders
            }
            
            # Aggregate monthly data
            if month_str not in monthly_revenue_data:
                monthly_revenue_data[month_str] = {'sales': 0, 'orders': 0}
            monthly_revenue_data[month_str]['sales'] += daily_sales
            monthly_revenue_data[month_str]['orders'] += daily_orders
            
            # Update totals
            total_revenue += daily_sales
            total_orders += daily_orders

        # Format revenue insights without order value range for monthly data
        revenue_insights = ""
        for date, data in daily_revenue_data.items():
            revenue_insights += f"\nDate: {date}\n"
            revenue_insights += f"- Daily Revenue: ₹{data['sales']:.2f}\n"
            revenue_insights += f"- Total Orders: {data['orders']}\n"

        # Add monthly summaries
        revenue_insights += "\nMonthly Performance Summary:\n"
        for month, data in monthly_revenue_data.items():
            revenue_insights += f"\nMonth: {month}\n"
            revenue_insights += f"- Total Monthly Revenue: ₹{data['sales']:.2f}\n"
            revenue_insights += f"- Total Monthly Orders: {data['orders']}\n"
            revenue_insights += f"- Average Daily Revenue: ₹{data['sales']/30:.2f}\n"
            revenue_insights += f"- Average Daily Orders: {data['orders']/30:.2f}\n"

        # Add overall summary
        revenue_insights += f"\nOverall Performance (Last 90 Days):\n"
        revenue_insights += f"- Total Revenue: ₹{total_revenue:.2f}\n"
        revenue_insights += f"- Total Orders: {total_orders}\n"
        revenue_insights += f"- Daily Average Revenue: ₹{total_revenue/90:.2f}\n"

        # Format holiday sales data
        holiday_sales = {}
        holiday_dates = [line.split(',')[0].strip('- ') for line in holiday_str.split('\n') if line]
        for row in revenue_data:
            date_str = row['date'].strftime('%Y-%m-%d')
            if date_str in holiday_dates:
                holiday_sales[date_str] = {
                    'sales': row['daily_sales'],
                    'orders': row['total_orders']
                }

        prompt = {
            'system_role': '''You are a friendly and precise AI assistant for a food vendor. You are talking to the vendor himself on chatbot. You MUST:
            1. Answer in a natural, conversational way
            2. Use exact numbers with proper formatting
            3. Include all relevant details asked for
            4. Make responses easy to read
            5. Answer questions like you are directly talking and addressing the vendor
            6. When asked to make predictions, always warn the user that the predictions can be off and please use proper forecasting model for this
            7. You can help with reciepe, food prep info, item recommendations, etc.'''
            ,

            'context': {
                'vendor_name': vendor_name,
                'business_description': description,
                'holiday_data': holiday_str,
                'holiday_sales': holiday_sales,
                'vendor_schedule_data': vendor_schedule_str,
                'revenue_insights': revenue_insights,
                'historical_data': historical_data,
                'review_data': review_data,
                'item_performance': item_performance,
                'daily_revenue': daily_revenue_data,
                'monthly_revenue': monthly_revenue_data,
                'total_revenue': {'sales': total_revenue, 'orders': total_orders},
                'performance_data': performance_data
            },
            
            'guidelines': '''
            
            1. RULES:
               - Use natural language
               - When asked about price or sales, use Rs (rupees) symbol
               - Only answer what is asked in concise form, don't add data or any other information if question is unrelated.
               - Keep response short and concise with minimal line breaks so that it looks good in chatbot
               - Don't do any other type of formatting.
               - Don't use any other formatting like bold, italic, etc or add any special characters in the response string other than line breaks.
               - Only answer the questions relevant to vendor business, vendor help, food reciepe, food recommendation, food prep info and data, don't answer off topic questions
               - When asked to make predictions, always warn the user that the predictions can be off and please use proper forecasting model for this''',
            
            'vendor_question': question
        }

        formatted_prompt = f"""System Role:
{prompt['system_role']}

Vendor That your talking to:
Vendor Name: {vendor_name}
Vendor Description: {description}

Data:
Total Revenue: {{'sales': {total_revenue}, 'orders': {total_orders}}}
Monthly Revenue: {monthly_revenue_data}
Daily Revenue: {daily_revenue_data}
Item Performance: {performance_data}
Holiday Data: {holiday_sales}
Vendor Schedule: {vendor_schedule_str}
Review Data: {review_data}

Guidelines:
{prompt['guidelines']}
Vendor_question: {prompt['vendor_question']}"""

        # Model name
        model_name = "models/gemini-2.0-flash"

        print(formatted_prompt)
        cache_key = hashlib.md5(formatted_prompt.encode()).hexdigest()
        
        # Try to get cached response
        cached_response = cache.get(cache_key)
        if cached_response:
            import time
            time.sleep(0.3)
            return JsonResponse(cached_response)

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

        cache.set(cache_key, {'answer': result.text}, CACHE_TTL)
        return JsonResponse({'answer': result.text})

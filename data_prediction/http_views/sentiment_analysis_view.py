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

# Cache TTL in seconds (2 hours)
CACHE_TTL = 7200

response_schema = {
    'type': 'object',
    'properties': {
        'sentiment_breakdown': {
            'type': 'object',
            'properties': {
                'general_sentiment': {'type': 'string'},
                'positive_review_percentage': {'type': 'number'},
                'neutral_review_percentage': {'type': 'number'}, 
                'negative_review_percentage': {'type': 'number'},
                'high_price_complain_reviews': {'type': 'number'},
                'sentiment_score': {'type': 'number'}
            },
            'required': ['general_sentiment', 'positive_review_percentage', 
                        'neutral_review_percentage', 'negative_review_percentage',
                        'high_price_complain_reviews', 'sentiment_score']
        },
        'marketing_suggestions': {
            'type': 'object',
            'properties': {
                'bundle_items': {'type': 'array', 'items': {'type': 'string'}},
                'promotional_strategies': {'type': 'array', 'items': {'type': 'string'}}
            }
        },
        'pricing_optimization': {
            'type': 'object',
            'properties': {
                'price_strategy': {'type': 'string'},
                'value_add_suggestions': {'type': 'array', 'items': {'type': 'string'}}
            }
        },
        'best_item': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string'},
                'postive_neutral_review_percentage': {'type': 'number'},
                'reasoning': {'type': 'string'}
            },
            'required': ['name', 'postive_neutral_review_percentage', 'reasoning']
        },
        'worst_item': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string'},
                'negative_review_percentage': {'type': 'number'},
                'reasoning': {'type': 'string'},
                'marketing_suggestions': {
                    'type': 'object',
                    'properties': {
                        'improvement_suggestions': {'type': 'array', 'items': {'type': 'string'}},
                        'alternative_items': {'type': 'array', 'items': {'type': 'string'}}
                    }
                },
                'pricing_optimization': {
                    'type': 'object',
                    'properties': {
                        'price_suggestion': {'type': 'string'},
                        'bundle_suggestions': {'type': 'array', 'items': {'type': 'string'}}
                    }
                }
            },
            'required': ['name', 'negative_review_percentage', 'reasoning', 'marketing_suggestions', 'pricing_optimization']
        },
        'delivery_packing_review_sentiment': {
            'type': 'object',
            'properties': {
                'sentiment': {'type': 'string'},
                'negative_review_percentage': {'type': 'number'}
            },
            'required': ['sentiment', 'negative_review_percentage']
        }
    },
    'required': ['sentiment_breakdown', 'best_item', 'worst_item']
}


class SentimentAnalysisView(APIView):
    def calculate_sentiment_score(self, reviews_data):
        """
        Calculate sentiment score (0-100) based on:
        1. Rating weights (70% of score)
        2. Comment sentiment (20% of score)
        3. Review recency (10% of score)
        """
        if not reviews_data:
            return 0

        rating_weights = {
            '5': 100,  # 5 star = 100 points
            '4': 80,   # 4 star = 80 points
            '3': 60,   # 3 star = 60 points
            '2': 40,   # 2 star = 40 points
            '1': 20    # 1 star = 20 points
        }

        # Positive and negative keywords for comment analysis
        positive_keywords = [
            'excellent', 'amazing', 'awesome', 'great', 'good', 'love', 'perfect',
            'fresh', 'tasty', 'delicious', 'wonderful', 'fantastic', 'best'
        ]
        negative_keywords = [
            'poor', 'bad', 'terrible', 'worst', 'horrible', 'disappointed',
            'cold', 'late', 'slow', 'stale', 'awful', 'not good'
        ]

        total_score = 0
        total_reviews = 0
        comment_sentiment_score = 0
        reviews_with_comments = 0

        for date, reviews in reviews_data.items():
            for review in reviews:
                total_reviews += 1
                
                # 1. Rating Score (70% weight)
                rating = review['rating'].split('/')[0]
                rating_score = rating_weights[rating]
                
                # 2. Comment Sentiment (20% weight)
                if review['user_comment']:
                    reviews_with_comments += 1
                    comment = review['user_comment'].lower()
                    positive_matches = sum(1 for word in positive_keywords if word in comment)
                    negative_matches = sum(1 for word in negative_keywords if word in comment)
                    comment_score = (positive_matches - negative_matches) * 20  # Scale to 0-100
                    comment_sentiment_score += max(0, min(100, comment_score + 50))  # Normalize to 0-100

                # 3. Recency weight (10% weight)
                # More recent reviews get slightly higher weight
                
                total_score += (
                    (rating_score * 0.7) +  # Rating component (70%)
                    (comment_score * 0.2 if review['user_comment'] else 0)  # Comment component (20%)
                    # Remaining 10% would be for recency
                )

        # Calculate final score (0-100 scale)
        rating_component = (total_score / total_reviews) if total_reviews > 0 else 0
        comment_component = (comment_sentiment_score / reviews_with_comments) if reviews_with_comments > 0 else 0
        
        final_score = min(100, max(0, (
            (rating_component * 0.7) +
            (comment_component * 0.3)
        )))

        return round(final_score, 2)

    def get(self, request):
        vendor_id = request.GET.get('vendor_id')
        DATE_FORMAT = '%Y-%m-%d'
        
        vendor_query = '''select vendor_name, description from vendor where id = %s'''
        vendor_data = QueryUtility.execute_query(vendor_query, [vendor_id], db='mysql')
        vendor_name = vendor_data[0]['vendor_name']
        vendor_description = vendor_data[0]['description']

        repeating_customers_query = '''
        WITH CustomerOrders AS (
            SELECT 
                employee_id,
                COUNT(*) as order_count
            FROM sales_order
            WHERE vendor_id = %s
                AND created_date > DATE_FORMAT(NOW() - INTERVAL 90 DAY, %s)
                AND status != 'cancelled'
            GROUP BY employee_id
        )
        SELECT 
            COUNT(employee_id) as total_customers,
            SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) as repeating_customers
        FROM CustomerOrders;
        '''
        
        customer_metrics = QueryUtility.execute_query(repeating_customers_query, [vendor_id, DATE_FORMAT], db='mysql')
        total_customers = int(customer_metrics[0]['total_customers'])
        repeating_customers = int(customer_metrics[0]['repeating_customers'])
        
        repeat_percentage = float(round((repeating_customers / total_customers * 100) if total_customers > 0 else 0, 2))

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
GROUP BY r.id order by date(r.created_at), order_items'''
        reviews = QueryUtility.execute_query(review_query, [vendor_id, DATE_FORMAT], db='mysql')
        review_data_dict = {}
        review_data = ''

        prompt = '''Analyze the following customer reviews and provide a structured breakdown:

1. Overall Sentiment Metrics:
   - Calculate exact percentages of positive (4-5★), neutral (3★), and negative (1-2★) reviews
   - Count reviews specifically mentioning price concerns or being expensive
   - Provide data-backed general sentiment summary (2-3 lines)
   Note: Positive + neutral + negative percentages must total 100%

2. Best Performing Item Analysis:
   - Identify item with highest positive+neutral review ratio
   - Calculate its positive+neutral review percentage
   - List key positive attributes mentioned in reviews
   - Marketing Opportunities:
     * Data-driven promotional strategies
   - Pricing Strategy:
     * Price optimization suggestions based on review feedback
     * Value-add opportunities supported by customer comments

3. Worst Performing Item Analysis:
   - Identify item with highest negative review ratio
   - Calculate its negative review percentage
   - List specific recurring complaints
   - Improvement Plan:
     * Action items based on negative feedback patterns
     * Alternative items with better performance metrics
   - Price Optimization:
     * Price adjustment recommendations based on feedback
     * Bundle suggestions to improve value perception

4. Delivery/Packaging Performance:
   - Calculate percentage of negative delivery/packaging mentions among all negative reviews
   - Identify specific delivery/packaging issues from reviews
   Note: Skip this section if no delivery/packaging feedback exists

Review Data:
{review_data}
'''

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

        # Model name - Use specific version if available, otherwise use base model name
        model_name = "models/gemini-2.0-flash"  # Example of a specific version - check Gemini API documentation for available versions. If not available, use "gemini-pro" or "gemini-2-pro" as appropriate, or "gemini-2-flash" as in your original code if that's the intended model.

        # Calculate sentiment score before generating response
        sentiment_score = self.calculate_sentiment_score(review_data_dict)

        # Generate cache key from prompt
        prompt_hash = hashlib.md5(prompt.format(review_data=review_data).encode()).hexdigest()
        cache_key = f'sentiment_analysis:{prompt_hash}'
        
        # Try to get cached response
        cached_response = cache.get(cache_key)
        if cached_response:
            # Update dynamic fields in cached response
            cached_response['total_reviews'] = len(reviews)
            cached_response['sentiment_breakdown']['sentiment_score'] = sentiment_score
            cached_response['sentiment_breakdown']['repeating_customers'] = repeating_customers
            cached_response['sentiment_breakdown']['total_customers'] = total_customers
            cached_response['sentiment_breakdown']['repeating_customers_percentage'] = repeat_percentage
            cached_response['vendor_name'] = vendor_name
            return JsonResponse(cached_response, safe=False)

        result = client.models.generate_content(
                    model=model_name,  # Use the deterministic model name
                    contents=prompt.format(review_data=review_data),
                    config={
                            'response_mime_type': 'application/json',
                            'response_schema': response_schema,
                            'temperature': 0.0,  # Set temperature to 0 for maximum determinism
                            'top_p': 1.0,     # Set top_p to 1.0 for determinism with temperature 0
                            'top_k': 1000,    # Set top_k to a high value for determinism with temperature 0 and top_p 1.0
                            'candidate_count': 1,  # Keep candidate_count to 1 to reduce variability
                            'seed': 42,        # Keep seed for reproducibility in case of underlying randomness (less impact with temperature 0 but good practice)
                        },)
        
        response = json.loads(result.text)
        
        # Calculate delivery/packing sentiment if not present
        if 'delivery_packing_review_sentiment' not in response:
            delivery_packing_keywords = ['delivery', 'delivered', 'packaging', 'packed', 'packing']
            total_mentions = 0
            negative_mentions = 0
            
            for date_reviews in review_data_dict.values():
                for review in date_reviews:
                    comment = review['user_comment'].lower()
                    if any(keyword in comment for keyword in delivery_packing_keywords):
                        total_mentions += 1
                        # Consider it negative if rating is 1-2 or has negative keywords
                        rating = int(review['rating'].split('/')[0])
                        if rating <= 2 or any(word in comment for word in ['late', 'poor', 'bad', 'worst', 'damaged']):
                            negative_mentions += 1
            
            response['delivery_packing_review_sentiment'] = {
                'sentiment': ('negative' if negative_mentions/total_mentions > 0.3
                            else 'positive') if total_mentions > 0
                            else 'neutral',
                'negative_review_percentage': round((negative_mentions/total_mentions * 100) if total_mentions > 0 else 0, 2)
            }

        response['total_reviews'] = len(reviews)
        response['sentiment_breakdown']['sentiment_score'] = sentiment_score
        response['sentiment_breakdown']['repeating_customers'] = repeating_customers
        response['sentiment_breakdown']['total_customers'] = total_customers
        response['sentiment_breakdown']['repeating_customers_percentage'] = repeat_percentage
        response['vendor_name'] = vendor_name
        
        # Cache the response
        cache.set(cache_key, response, CACHE_TTL)

        return JsonResponse(response, safe=False)


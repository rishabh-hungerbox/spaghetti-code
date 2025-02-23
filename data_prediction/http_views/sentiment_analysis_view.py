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
        'sentiment_breakdown': {
            'type': 'object',
            'properties': {
                'general_sentiment': {'type': 'string'},
                'positive_review_percentage': {'type': 'number'},
                'neutral_review_percentage': {'type': 'number'}, 
                'negative_review_percentage': {'type': 'number'},
                'high_price_complain_reviews': {'type': 'number'}
            },
            'required': ['general_sentiment', 'positive_review_percentage', 
                        'neutral_review_percentage', 'negative_review_percentage',
                        'high_price_complain_reviews']
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
                'reasoning': {'type': 'string'}
            },
            'required': ['name', 'negative_review_percentage', 'reasoning']
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
    def get(self, request):
        vendor_id = request.GET.get('vendor_id')
        DATE_FORMAT = '%Y-%m-%d'
        
        vendor_query = '''select vendor_name, description from vendor where id = %s'''
        vendor_data = QueryUtility.execute_query(vendor_query, [vendor_id], db='mysql')
        vendor_name = vendor_data[0]['vendor_name']
        vendor_description = vendor_data[0]['description']

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

        prompt = '''Given the following reviews, analyze them and provide a detailed breakdown in the following format:

1. Overall Sentiment Breakdown:
   - Determine the general sentiment (2-3 lines analysis of reviews)
   - Calculate percentage of positive, neutral, and negative reviews
   - Count reviews mentioning high prices or price complaints
   Note: positive, neutral, and negative reviews percentage should always add to 100%
   Note: if no reviews mention high prices or price complaints, then the high_price_complain_reviews should be 0

2. Best Performing Item:
   - Identify the item with most positive reviews
   - Calculate its positive + neutral review percentage
   - Explain why customers liked it

3. Worst Performing Item:
   - Identify the item with most negative reviews
   - Calculate its negative review percentage
   - Explain common complaints

4. Delivery and Packaging Analysis:
   - Evaluate delivery/packaging sentiment (1-2 line analysis of reviews)
   - Calculate percentage of negative delivery/packaging reviews (out of all negative reviews)
   Note: if no reviews mention delivery or packaging, then don't return  delivery_packing_review_sentiment

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
        response['total_reviews'] = len(reviews)
        response['sentiment_breakdown']['repeating_customers_percentage'] = -1
        response['vendor_name'] = vendor_name
        

        return JsonResponse(response, safe=False)


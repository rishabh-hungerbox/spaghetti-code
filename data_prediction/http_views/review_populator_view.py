from django.http import JsonResponse
from rest_framework.views import APIView
from etc.query_utility import QueryUtility
import json
import random
from data_prediction.models import Review, ReviewOptions, ReviewOptionsResponse

class ReviewPopulatorView(APIView):
    def get(self, request):
        created_date = request.GET.get('created_date')
        vendor_id = request.GET.get('vendor_id')
        product_ids = request.GET.get('product_ids')
        location_id = request.GET.get('location_id')
        rating = request.GET.get('rating')
        comment = request.GET.get('comment')
        count = request.GET.get('count')

        query = '''select id, name from vendor_menu where id in (%s);'''
        product_data = QueryUtility.execute_query(query, [product_ids], db='mysql')
        if len(product_data) != len(product_ids.split(',')):
            return JsonResponse({'status': 'error', 'message': 'Invalid product ids'})
        
        product_names = [product['name'] for product in product_data]
        product_names = ', '.join(product_names)

        # Use ORM to create sales orders
        for _ in range(int(count)):
            reference_id = random.randint(1, 1000000000)
            review = Review(
                provider='user',
                provider_id=1374836,
                reference='order',
                reference_id=reference_id,
                vendor_id=vendor_id,
                location_id=location_id,
                rating=rating,
                comment='',
                order_created_date=created_date,
                order_items=product_names
            )
            review.save(using='mysql')
            
            review_options = ReviewOptions(
                vendor_id=vendor_id,
                type='text',
                question='user comment',
                rating=rating,
                active=1,
                created_at=created_date,
                updated_at=created_date,
                reference_id=0,
                reference_type='company'
            )
            review_options.save(using='mysql')
            
            review_options_response = ReviewOptionsResponse(
                review_id=review.id,
                review_option_id=review_options.id,
                value=comment,
                created_at=created_date,
                updated_at=created_date,
                reference='order',
                reference_id=reference_id,
            )
            review_options_response.save(using='mysql')
            
            print(f"Created review with ID: {review.id}")
            print(f"Created review options with ID: {review_options.id}")
            print(f"Created review options response with ID: {review_options_response.id}")
            
        return JsonResponse({'status': 'success'})
    

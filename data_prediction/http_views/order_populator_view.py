from django.http import JsonResponse
from rest_framework.views import APIView
from etc.query_utility import QueryUtility
import json
from data_prediction.models import SalesOrder
from data_prediction.models import OrderItems

class OrderPopulatorView(APIView):
    def get(self, request):
        created_date = request.GET.get('created_date')
        vendor_id = request.GET.get('vendor_id')
        order_count = request.GET.get('order_count')
        product_id = request.GET.get('product_id')
        product_price = request.GET.get('product_price')
        location_id = request.GET.get('location_id')
        occasion_id = request.GET.get('occasion_id')

        DUMMY_USER_ID = 1374836

        # Use ORM to create sales orders
        for _ in range(int(order_count)):
            sales_order = SalesOrder(
                vendor_id=vendor_id,
                employee_id=DUMMY_USER_ID,
                qty=1,
                status='new',
                reject_message='',
                location_id=location_id,
                occasion_id=occasion_id,
                company_paid=0,
                employee_paid=0,
                container_charges=0,
                delivery_charges=0,
                convenience_fee=0,
                cgst=0,
                sgst=0,
                refundable_amount=0,
                refunded_amount=0,
                created_date=created_date
            )
            
            # Save to MySQL database
            sales_order.save(using='mysql')
            
            order_items = OrderItems(
                order_id=sales_order.id,
                product_id=product_id,
                price=product_price,
                qty=1,
                created_at=created_date,
                updated_at=created_date,
                item_price=product_price,
                is_free=0,
                is_mrp=0,
                recommendation_type='',
                recommendation_id=0,
                recommendation_score=0,
                convenience_fee=0,
                status='new',
                estimated_delivery_time=created_date,
                processed_time=created_date,
                delivery_time=created_date,
                comment='',
                container_charge=0,
                
            )
            order_items.save(using='mysql')
            print(f"Created sales order with ID: {sales_order.id}")
            print(f"Created order items with ID: {order_items.order_item_id}")
        return JsonResponse({'status': 'success'})
    

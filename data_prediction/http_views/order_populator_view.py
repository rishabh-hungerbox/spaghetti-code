from django.http import JsonResponse
from rest_framework.views import APIView
from etc.query_utility import QueryUtility
import json
from data_prediction.models import SalesOrder

class OrderPopulatorView(APIView):
    def get(self, request):
        created_date = request.GET.get('created_date')
        vendor_id = request.GET.get('vendor_id')
        order_count = request.GET.get('order_count')
        product_id = request.GET.get('product_id')
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
            print(f"Created sales order with ID: {sales_order.id}")

        return JsonResponse({'status': 'success'})
    

from django.db import models
from enum import Enum


class SalesOrder(models.Model):
    CACHE_TTL = 4 * 60
    SUBSCRIPTION_ORDER = 'subscription'
    SPACE_BOOKING_ORDER = 'space_booking'

    FULFILLED_STATUS = 'fulfilled'
    DELIVERED_STATUS = 'delivered'
    PAYMENT_FAILED_STATUS = 'payment_failed'
    PAYMENT_PENDING_STATUS = 'payment_pending'

    OPEN_ORDER_STATUS = (
        'agent_picked',
        'approval_pending',
        'attention_required',
        'confirmed',
        'new',
        'out_for_delivery',
        'partially_confirmed',
        'partially_delivered',
        'partially_processed',
        'payment_pending',
        'picked_up',
        'preorder',
        'processed',
        'reached_location',
        'ready_for_pickup',
    )
    CLOSED_ORDER_STATUS = ('delivered', 'payment_failed', 'rejected', 'not collected', 'handed_over')
    EXTERNAL_SOURCE_DEVICE = ['zomato', 'swiggy']
    ALL_STATUS = [
        'payment_pending',
        'approval_pending',
        'preorder',
        'new',
        'attention_required',
        'agent_picked',
        'payment_failed',
        'partially_confirmed',
        'confirmed',
        'partially_rejected',
        'in-transit',  # not an actual status in db, vm orders state
        'partially_processed',
        'processed',
        'ready_for_pickup',
        'picked_up',
        'out_for_delivery',
        'reached_location',
        'rejected',
        'handed_over',
        'partially_delivered',
        'delivered',
        'not collected',
    ]

    class RejectMessage(Enum):
        OUT_OF_STOCK = 'Out Of Stock'
        NOT_AVAILABLE = 'Not Available'
        CUSTOMER_REJECT = 'Customer Reject'
        HEAVY_LOAD = 'Heavy Load'
        PLACE_CLOSED = 'Place Closed'
        DEFAULT = ''

        @classmethod
        def choices(cls):
            return tuple((i.name, i.value) for i in cls)

    class OrderTypes(Enum):
        INDIVIDUAL = 'individual'
        GROUP_ORDER = 'group_order'
        ADMIN_ORDER = 'admin_order'
        CATERING = 'catering'
        GUEST_ORDER = 'guest_order'
        MEETING_ORDER = 'meeting_order'
        EVENT = 'event'
        SPACE_BOOKING = 'space_booking'
        SUBSCRIPTION = 'subscription'
        EMPLOYEE_GUEST = 'employee_guest'
        DEFAULT = ''

        @classmethod
        def choices(cls):
            return tuple((i.name, i.value) for i in cls)

    id = models.AutoField(primary_key=True)
    vendor_id = models.IntegerField()
    employee_id = models.IntegerField()
    vendor_order_ref = models.CharField(unique=True, max_length=20, blank=True, null=True)
    customer_order_ref = models.PositiveIntegerField(blank=True, null=True)
    qty = models.IntegerField(default=0)
    total_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=40)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    estimated_delivery_at = models.DateTimeField(blank=True, null=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True, auto_now_add=True)
    updated_at = models.DateTimeField(blank=True, null=True, auto_now=True)
    reject_message = models.CharField(
        max_length=15, choices=RejectMessage.choices(), default=RejectMessage.DEFAULT.value
    )
    delivery_method = models.CharField(max_length=7, blank=True, null=True)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    card_no = models.CharField(max_length=20, blank=True, null=True)
    location_id = models.IntegerField()
    occasion_id = models.IntegerField()
    preorder_delivery_time = models.DateTimeField(blank=True, null=True)
    source_device = models.CharField(max_length=11, blank=True, null=True)
    comment = models.CharField(max_length=255, blank=True, null=True)
    agent_user_id = models.IntegerField(blank=True, null=True)
    company_paid = models.FloatField(default=0)
    employee_paid = models.FloatField(default=0)
    invoice_item_id = models.IntegerField(blank=True, null=True)
    container_charges = models.FloatField(default=0)
    delivery_charges = models.FloatField(default=0.0)
    type = models.CharField(max_length=20, choices=OrderTypes.choices(), default=OrderTypes.DEFAULT.value)
    convenience_fee = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    cgst = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    created_date = models.DateField(blank=True, null=True)
    company_id = models.IntegerField(blank=True, null=True)
    refundable_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    refunded_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    delivery_executive_contact_number = models.CharField(max_length=15, blank=True, null=True)
    cess = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    parent_order_id = models.IntegerField(blank=False, null=True, default=None)
    
    
    class Meta:
        db_table = 'sales_order'  # This

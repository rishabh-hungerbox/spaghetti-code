from django.db import models


class Review(models.Model):
    provider = models.CharField(max_length=6)
    provider_id = models.IntegerField()
    reference = models.CharField(max_length=9)
    reference_id = models.IntegerField()
    rating = models.IntegerField()
    comment = models.TextField(blank=True, null=True)
    ticketable = models.IntegerField(default=1)
    created_at = models.DateTimeField(blank=True, null=True, auto_now_add=True)
    updated_at = models.DateTimeField(blank=True, null=True, auto_now=True)
    vendor_id = models.IntegerField(blank=True, null=True)
    location_id = models.IntegerField(blank=True, null=True)
    order_created_date = models.DateField(blank=True, null=True)
    order_items = models.CharField(max_length=1000, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'review'

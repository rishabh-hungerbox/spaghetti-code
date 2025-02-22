from django.db import models


class ReviewOptions(models.Model):
    vendor_id = models.IntegerField(blank=True, null=True)
    type = models.CharField(max_length=8)
    question = models.CharField(max_length=255)
    rating = models.IntegerField()
    active = models.IntegerField()
    created_at = models.DateTimeField(blank=True, null=True, auto_now_add=True)
    updated_at = models.DateTimeField(blank=True, null=True, auto_now=True)
    reference_id = models.IntegerField()
    reference_type = models.CharField(max_length=7)
    is_actionable = models.BooleanField(blank=True, null=True)
    feedback_description = models.CharField(max_length=255, blank=True, null=True)
    closure_report = models.TextField(blank=True, null=True)
    ticket_creation_message = models.TextField(blank=True, null=True)
    # is_firable = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'review_options'

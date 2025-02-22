from django.db import models


class ReviewOptionsResponse(models.Model):
    review_id = models.IntegerField()
    review_option_id = models.IntegerField()
    value = models.CharField(max_length=255)
    created_at = models.DateTimeField(blank=True, null=True, auto_now_add=True)
    updated_at = models.DateTimeField(blank=True, null=True, auto_now=True)
    reference = models.CharField(max_length=9, null=True)
    reference_id = models.IntegerField(null=True)
    sub_bucket_id = models.IntegerField(blank=True, default=None, null=True)

    class Meta:
        managed = False
        db_table = 'review_options_response'

from django.db import models


class IngredientsData(models.Model):
    vendor_id = models.IntegerField()
    menu_name = models.CharField(max_length=255)
    ingredients = models.JSONField()

    class Meta:
        db_table = 'ingredients_data'  # Sets the table name in the database
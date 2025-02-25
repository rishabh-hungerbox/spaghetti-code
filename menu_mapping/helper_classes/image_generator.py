from google import genai
from google.genai import types
from PIL import Image
import os
import uuid
from io import BytesIO
from datetime import datetime
from menu_mapping.helper_classes.s3 import S3

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
IMAGE_DIR = 'menu_mapping/output'


class ImageGenerator:
    @staticmethod
    def generate_image(prompt):
        prompt = prompt.replace("combo", "")
        
        boiler_plate = """Create a high-resolution image of [food item {prompt}] presented beautifully on a plate. 
        The scene should appear appetizing and inviting.
        The [food item {prompt}] should be freshly prepared,
        showcasing its signature characteristics like texture, color,
        and any unique features. The background should be a simple yet elegant
        dining setting, with soft natural lighting to enhance the food's
        appearance. Include subtle details like a sprig of herbs, a light garnish,
        or a side of dipping sauce if applicable, to add realism. Ensure the image
        highlights the culinary artistry in [food item {prompt}], drawing attention
        to its authentic and delightful presentation."""

        boiler_plate = "{prompt}, realistic, seperate, stock photo, restaurant, food photography, food presentation"
        # {prompt}, realistic, seperate
        
        s3_links = []

        response = client.models.generate_images(
            model='imagen-3.0-generate-002',
            prompt=boiler_plate.format(prompt=prompt),
            config=types.GenerateImagesConfig(
                number_of_images=3,
            )
        )
        for i, generated_image in enumerate(response.generated_images):
            image_bytes = generated_image.image.image_bytes
            image = Image.open(BytesIO(image_bytes))

            # Generate a unique filename
            image_name = f"output_{datetime.now().timestamp()}.png"
            image_path = os.path.join(IMAGE_DIR, image_name)
            image.save(image_path)

            s3_obj = S3()
            s3_obj.upload_public_read_file(
                image_path, os.getenv('S3_BUCKET'), 'uploads/ai/' + image_name
            )
            s3_file_path = 'https://' + os.getenv('S3_DOMAIN') + '/' + os.getenv('S3_BUCKET') + '/uploads/ai/' + image_name
            s3_links.append(s3_file_path)
        return s3_links

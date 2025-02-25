import os
import json
import tempfile
import requests
from PIL import Image
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from etc.query_utility import QueryUtility
from data_prediction.helper_classes.utility import MenuMappingUtility
from google import genai
from data_prediction.helper_classes.image_generator import ImageGenerator
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


class ImageAnalyzerView(APIView):
    parser_classes = (MultiPartParser, FormParser)  # To handle file uploads

    def get(self, request):  # Keep using GET method
        product_id = request.GET.get('product_id')
        product_name = request.GET.get('product_name')
        force_suggest = request.GET.get('force_suggest')
        image_url = MenuMappingUtility.get_product_image_url(product_id)

        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, 'downloaded_image.jpg')  # Renamed to reflect download source

        if (not image_url) or bool(int(force_suggest)):
            suggestion = ImageGenerator.generate_image(product_name)
            
            return JsonResponse({
                'image_url': image_url,
                'attractiveness_rating': None,
                'suggested_images': suggestion
            })

        # Download the image from the public S3 URL
        response = requests.get(image_url, stream=True)
        if response.status_code != 200:
            raise Exception("Failed to download image from URL")
        with open(temp_path, 'wb') as destination:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    destination.write(chunk)

        # Open and validate the image
        img = Image.open(temp_path)
        # Construct prompt for image rating
        prompt = (
            "Rate this food image out of 10 based on its visual attractiveness and appeal.\n"
            "Consider factors like:\n"
            "- Food presentation and plating\n"
            "- Color and vibrancy\n"
            "- Lighting and clarity\n"
            "- Overall appetizing appearance\n\n"
            "Provide only a single numerical rating between 1-10."
        )

        # Model configuration
        model_name = "models/gemini-2.0-flash"

        # Generate prediction with image and prompt
        result = client.models.generate_content(
            model=model_name,
            contents=[img, prompt]
        )

        response_text = result.text
        print(response_text)
        try:
            rating = int(response_text.strip())  # Attempt to extract a numerical rating
            if not 1 <= rating <= 10:
                rating = "Rating out of range"  # Handle out-of-range values
        except ValueError:
            rating = response_text.strip()  # Return the raw response if not numerical

        # Clean up temporary files
        os.remove(temp_path)
        os.rmdir(temp_dir)
        
        suggestion = []
        
        if rating <= 6:
            suggestion = ImageGenerator.generate_image(product_name)   
            
        print('hi')         

        return JsonResponse({
            'image_url': image_url,  # Return the original image URL
            'attractiveness_rating': rating,
            'suggested_images': suggestion
        })

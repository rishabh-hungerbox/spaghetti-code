"""
WSGI config for auth project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'etc.settings')

application = get_wsgi_application()

# # Global variable to store the MenuMapperAI instance
# from menu_mapping.helper_classes.menu_mapper_helper import MenuMapperAI
# global_ai_instance = MenuMapperAI(
#     prompt_id=7,
#     model="models/gemini-2.0-flash",
#     embedding="text-embedding-3-small",
#     similarity_top_k=10,
#     benchmark_on=False,
#     debug_mode=False,
#     sampling_size=50,
#     with_reranker=True
# )

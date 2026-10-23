import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "computer_class_site.settings_mailwala"
)

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()

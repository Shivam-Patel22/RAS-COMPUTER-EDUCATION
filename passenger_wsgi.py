import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "computer_class_site.settings_mailwala"
)

# Automatically apply pending database migrations on Passenger startup / restart
try:
    import django
    django.setup()
    from django.core.management import call_command
    call_command("migrate", interactive=False)
except Exception as e:
    sys.stderr.write(f"[Passenger Startup] Auto-migration warning: {e}\n")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()


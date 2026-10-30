from django.apps import AppConfig
import sys


class CoursesConfig(AppConfig):
    name = 'courses'

    def ready(self):
        # Do not run during migration commands or test runs
        if any(cmd in sys.argv for cmd in ['makemigrations', 'migrate', 'test', 'collectstatic', 'compilemessages']):
            return

        try:
            from django.core.management import call_command
            call_command('migrate', 'courses', interactive=False)
        except Exception:
            pass

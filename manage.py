#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'computer_class_site.settings')

    # Automatically run migrations when starting the server
    if len(sys.argv) > 1 and sys.argv[1] == 'runserver':
        import subprocess
        print("\n==============================================")
        print("Auto-applying database migrations...")
        print("==============================================\n")
        try:
            subprocess.run([sys.executable, sys.argv[0], "migrate"], check=False)
        except Exception as e:
            print(f"Warning: Auto-migration failed: {e}")

        try:
            # Ensure official social media links are populated for local development
            subprocess.run([
                sys.executable, sys.argv[0], "shell", "-c",
                "from core.models import ContactContent; "
                "c = ContactContent.get_solo(); "
                "changed = False; "
                "if not c.instagram_url: c.instagram_url = 'https://www.instagram.com/ras_computer_education/'; c.instagram_username = 'ras_computer_education'; changed = True; "
                "if not c.facebook_url: c.facebook_url = 'https://www.facebook.com/RASeducationgnr/'; c.facebook_name = 'RASeducationgnr'; changed = True; "
                "if changed: c.save(); print('[Auto-Config] Official Instagram & Facebook links initialized.')"
            ], check=False)
        except Exception:
            pass

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

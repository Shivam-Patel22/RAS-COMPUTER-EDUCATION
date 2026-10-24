#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'computer_class_site.settings_mailwala')
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
            social_code = (
                "from core.models import ContactContent\n"
                "c = ContactContent.get_solo()\n"
                "changed = False\n"
                "if not c.instagram_url:\n"
                "    c.instagram_url = 'https://www.instagram.com/ras_computer_education/'\n"
                "    c.instagram_username = 'ras_computer_education'\n"
                "    changed = True\n"
                "if not c.facebook_url:\n"
                "    c.facebook_url = 'https://www.facebook.com/RASeducationgnr/'\n"
                "    c.facebook_name = 'RASeducationgnr'\n"
                "    changed = True\n"
                "if changed:\n"
                "    c.save()\n"
                "    print('[Auto-Config] Official Instagram & Facebook links initialized.')\n"
            )
            subprocess.run([
                sys.executable, sys.argv[0], "shell", "-c", social_code
            ], check=False)
        except Exception:
            pass

        try:
            # Ensure verified Justdial reviews are populated if none exist
            review_code = (
                "from core.models import JustdialReview\n"
                "import datetime\n"
                "if JustdialReview.objects.count() == 0:\n"
                "    reviews = [\n"
                "        {'reviewer_name': 'Pransav', 'rating': 5, 'review_text': 'Ras Computer Education is an outstanding coaching center that truly stands out for its expert faculty. The instructors are knowledgeable and always ready to help students understand complex concepts.', 'review_date': datetime.date(2024, 3, 10), 'display_order': 1, 'is_active': True},\n"
                "        {'reviewer_name': 'Yash Prajapati', 'rating': 5, 'review_text': 'I had a great experience with Ras Computer Education, a coaching center with many facilities. The staff was friendly and helpful, and the practical computer training helped me a lot.', 'review_date': datetime.date(2024, 4, 18), 'display_order': 2, 'is_active': True},\n"
                "        {'reviewer_name': 'SHAIKH AYAN A.', 'rating': 5, 'review_text': 'I had a great experience with Ras Computer Education, a coaching center. The classrooms are highly specialized and air-conditioned, making learning comfortable and effective.', 'review_date': datetime.date(2024, 5, 22), 'display_order': 3, 'is_active': True},\n"
                "        {'reviewer_name': 'Bhavik Prajapati', 'rating': 5, 'review_text': 'One of the best computer coaching institutes in Gandhinagar Sector 22. Highly recommended for CCC and Tally courses with dedicated practical labs.', 'review_date': datetime.date(2024, 6, 15), 'display_order': 4, 'is_active': True},\n"
                "        {'reviewer_name': 'Hetal Solanki', 'rating': 5, 'review_text': 'Excellent institute for computer learning. I completed the CCC course here, and the faculty explained everything clearly with great practical support and individual guidance.', 'review_date': datetime.date(2024, 7, 20), 'display_order': 5, 'is_active': True},\n"
                "        {'reviewer_name': 'Rajesh Kumar', 'rating': 5, 'review_text': 'Best training institute for accounting and GST in Gandhinagar. The practical training on Tally and helpful faculty made learning very smooth.', 'review_date': datetime.date(2024, 8, 14), 'display_order': 6, 'is_active': True},\n"
                "    ]\n"
                "    for r in reviews:\n"
                "        JustdialReview.objects.create(**r)\n"
                "    print('[Auto-Config] Verified Justdial reviews initialized.')\n"
            )
            subprocess.run([
                sys.executable, sys.argv[0], "shell", "-c", review_code
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

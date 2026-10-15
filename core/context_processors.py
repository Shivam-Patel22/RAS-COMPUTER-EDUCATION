import sys
from .models import ContactContent

def is_running_tests():
    return 'test' in sys.argv or hasattr(sys, '_called_from_test')

def site_content(request):
    try:
        contact_obj = ContactContent.get_solo()
        if not is_running_tests():
            changed = False
            if not contact_obj.instagram_url:
                contact_obj.instagram_url = "https://www.instagram.com/ras_computer_education/"
                contact_obj.instagram_username = "ras_computer_education"
                changed = True
            if not contact_obj.facebook_url:
                contact_obj.facebook_url = "https://www.facebook.com/RASeducationgnr/"
                contact_obj.facebook_name = "RASeducationgnr"
                changed = True
            if changed:
                contact_obj.save()
        return {'site_contact': contact_obj}
    except Exception:
        return {'site_contact': None}

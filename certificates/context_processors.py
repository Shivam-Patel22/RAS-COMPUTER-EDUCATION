from .utils import (
    get_certificate_verify_url,
    OFFICIAL_INSTITUTE_ADDRESS,
    OFFICIAL_INSTITUTE_PIN,
)


def certificate_settings(request):
    """
    Exposes certificate-related global settings to templates,
    including the canonical certificate verification URL, official address, and PIN.
    """
    return {
        'certificate_verify_url': get_certificate_verify_url(),
        'official_address': OFFICIAL_INSTITUTE_ADDRESS,
        'official_pin': OFFICIAL_INSTITUTE_PIN,
    }

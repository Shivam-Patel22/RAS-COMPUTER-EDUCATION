from .utils import get_certificate_verify_url


def certificate_settings(request):
    """
    Exposes certificate-related global settings to templates,
    including the canonical certificate verification URL.
    """
    return {
        'certificate_verify_url': get_certificate_verify_url(),
    }

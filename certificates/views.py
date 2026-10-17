from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from django.utils.text import slugify
from django.db.models import Q
from .forms import CertificateVerificationForm
from .models import Certificate
from .utils import generate_certificate_pdf, get_certificate_verify_url

@csrf_exempt
@never_cache
def verify(request):
    cert_id = None
    certificate = None
    error_message = None

    if request.method == 'POST':
        form = CertificateVerificationForm(request.POST)
        if form.is_valid():
            cert_id = form.cleaned_data['certificate_id']
        else:
            cert_id = request.POST.get('certificate_id', '').strip()
    else:
        # Check GET parameter if passed from dashboard link or search form
        cert_id = request.GET.get('certificate_id', '').strip()
        if cert_id:
            form = CertificateVerificationForm(initial={'certificate_id': cert_id})
        else:
            form = CertificateVerificationForm()

    if cert_id:
        # Rate limit lookups: max 20 requests per minute per IP to prevent scraping
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        client_ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR', '')
        rate_key = f"cert_verify_rate_{client_ip}"
        try:
            from django.core.cache import cache
            attempts = cache.get(rate_key, 0)
            if attempts >= 25:
                return render(request, 'certificates/verify.html', {
                    'form': form,
                    'error_message': "Too many verification requests. Please wait a minute before trying again."
                }, status=429)
            cache.set(rate_key, attempts + 1, timeout=60)
        except Exception:
            pass

        # Rule 9: Exact match lookup ONLY (case-insensitive)
        # Supports both Certificate ID and CITI Registration Number
        try:
            certificate = Certificate.objects.select_related('course', 'student').filter(
                Q(certificate_id__iexact=cert_id) | Q(registration_number__iexact=cert_id)
            ).first()
            if not certificate:
                raise Certificate.DoesNotExist
        except Certificate.DoesNotExist:
            error_message = f"No valid certificate found matching Certificate ID / Registration No '{cert_id}'."

    if certificate:
        return render(request, 'certificates/result.html', {
            'certificate': certificate,
            'form': form,
            'certificate_verify_url': get_certificate_verify_url(),
        })

    return render(request, 'certificates/verify.html', {
        'form': form,
        'error_message': error_message
    })


@never_cache
def download_certificate_pdf(request, certificate_id):
    """
    Public download endpoint for verified certificate PDF.
    Generates authentic vector PDF in memory (ReportLab) with zero browser headers/footers.
    """
    cert = Certificate.objects.select_related('course', 'student').filter(
        Q(certificate_id__iexact=certificate_id) | Q(registration_number__iexact=certificate_id)
    ).first()
    if not cert:
        from django.http import Http404
        raise Http404("Certificate not found.")
    pdf_bytes = generate_certificate_pdf(cert)
    filename = f"{cert.certificate_id}_{slugify(cert.student_name or 'student')}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

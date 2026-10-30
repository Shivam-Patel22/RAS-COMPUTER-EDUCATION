from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from django.utils.text import slugify
from django.db.models import Q
from .forms import CertificateVerificationForm
from .models import Certificate
from .utils import (
    generate_certificate_pdf,
    get_certificate_verify_url,
    generate_qr_data_uri,
)


@csrf_exempt
@never_cache
def verify(request, certificate_id=None):
    """
    Public Certificate Verification Endpoint.
    Supports:
    1. Direct URL access from QR code scans: /verify-certificate/<certificate_id>/ or /verify/<certificate_id>/
    2. URL query parameter: /verify-certificate/?certificate_id=<certificate_id>
    3. Form submission via POST / GET search
    4. JSON responses when requested via format=json or AJAX
    """
    cert_id = None
    certificate = None
    error_message = None

    if certificate_id:
        cert_id = str(certificate_id).strip().rstrip('/')
    elif request.method == 'POST':
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

    is_json = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        request.GET.get('format') == 'json'
    )

    if cert_id:
        # Rate limit lookups: max 25 requests per minute per IP to prevent scraping
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        client_ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR', '')
        rate_key = f"cert_verify_rate_{client_ip}"
        try:
            from django.core.cache import cache
            attempts = cache.get(rate_key, 0)
            if attempts >= 25:
                if is_json:
                    return JsonResponse({
                        'error': "Too many verification requests. Please wait a minute before trying again."
                    }, status=429)
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
                parts = cert_id.split('-')
                if len(parts) == 6 and parts[0].upper() in ('RAS', 'CITI') and len(parts[4]) == 6:
                    stripped_id = '-'.join(parts[:5])
                    certificate = Certificate.objects.select_related('course', 'student').filter(
                        Q(certificate_id__iexact=stripped_id) | Q(registration_number__iexact=stripped_id)
                    ).first()
                elif len(parts) == 5 and parts[0].upper() in ('RAS', 'CITI') and len(parts[4]) == 6:
                    certificate = Certificate.objects.select_related('course', 'student').filter(
                        certificate_id__istartswith=f"{cert_id}-"
                    ).first()
            if not certificate:
                raise Certificate.DoesNotExist
        except Certificate.DoesNotExist:
            error_message = f"No valid certificate found matching Certificate ID / Registration No '{cert_id}'."

    if certificate:
        qr_verify_url = get_certificate_verify_url(cert=certificate, request=request)
        qr_data_uri = generate_qr_data_uri(qr_verify_url)
        status_label = 'Revoked' if certificate.is_revoked else 'Valid'

        if is_json:
            return JsonResponse({
                'status': status_label,
                'is_valid': not certificate.is_revoked,
                'is_revoked': certificate.is_revoked,
                'certificate_id': certificate.certificate_id,
                'student_name': certificate.student_name,
                'course_name': certificate.course.name if certificate.course else 'N/A',
                'issue_date': certificate.issue_date.strftime('%Y-%m-%d') if certificate.issue_date else 'N/A',
                'grade': certificate.grade or 'N/A',
                'verification_url': qr_verify_url,
                'revoked_at': certificate.revoked_at.strftime('%Y-%m-%d %H:%M:%S') if certificate.revoked_at else None,
                'revocation_message': "This certificate has been revoked by the administrator and is no longer valid." if certificate.is_revoked else None,
            })

        return render(request, 'certificates/result.html', {
            'certificate': certificate,
            'form': form,
            'certificate_verify_url': get_certificate_verify_url(),
            'qr_verify_url': qr_verify_url,
            'qr_data_uri': qr_data_uri,
            'status_label': status_label,
            'is_revoked': certificate.is_revoked,
        })

    if cert_id and is_json:
        return JsonResponse({
            'status': 'Invalid/Not Found',
            'is_valid': False,
            'is_revoked': False,
            'error': error_message or f"No certificate record found matching '{cert_id}'."
        }, status=404)

    return render(request, 'certificates/verify.html', {
        'form': form,
        'error_message': error_message,
        'searched_id': cert_id or ''
    })


@never_cache
def download_certificate_pdf(request, certificate_id):
    """
    Public download endpoint for verified certificate PDF.
    Generates authentic vector PDF in memory (ReportLab) with zero browser headers/footers.
    Revoked certificates cannot be downloaded.
    """
    clean_id = str(certificate_id).strip().rstrip('/')
    cert = Certificate.objects.select_related('course', 'student').filter(
        Q(certificate_id__iexact=clean_id) | Q(registration_number__iexact=clean_id)
    ).first()
    if not cert:
        parts = clean_id.split('-')
        if len(parts) == 6 and parts[0].upper() in ('RAS', 'CITI') and len(parts[4]) == 6:
            stripped_id = '-'.join(parts[:5])
            cert = Certificate.objects.select_related('course', 'student').filter(
                Q(certificate_id__iexact=stripped_id) | Q(registration_number__iexact=stripped_id)
            ).first()
        elif len(parts) == 5 and parts[0].upper() in ('RAS', 'CITI') and len(parts[4]) == 6:
            cert = Certificate.objects.select_related('course', 'student').filter(
                certificate_id__istartswith=f"{clean_id}-"
            ).first()
    if not cert:
        raise Http404("Certificate not found.")
    if cert.is_revoked:
        return HttpResponseForbidden("This certificate has been revoked by the issuing authority and cannot be downloaded.")

    pdf_bytes = generate_certificate_pdf(cert, request=request)
    filename = f"{cert.certificate_id}_{slugify(cert.student_name or 'student')}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

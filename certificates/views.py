from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from django.utils.text import slugify
from .forms import CertificateVerificationForm
from .models import Certificate
from .utils import generate_certificate_pdf

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
        # Rule 9: Exact match lookup ONLY (case-insensitive)
        try:
            certificate = Certificate.objects.select_related('course', 'student').get(certificate_id__iexact=cert_id)
        except Certificate.DoesNotExist:
            error_message = f"No valid certificate found matching Certificate ID '{cert_id}'."

    if certificate:
        return render(request, 'certificates/result.html', {
            'certificate': certificate,
            'form': form
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
    cert = get_object_or_404(Certificate.objects.select_related('course', 'student'), certificate_id__iexact=certificate_id)
    pdf_bytes = generate_certificate_pdf(cert)
    filename = f"{cert.certificate_id}_{slugify(cert.student_name or 'student')}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

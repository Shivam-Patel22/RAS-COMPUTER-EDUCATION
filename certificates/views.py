from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from .forms import CertificateVerificationForm
from .models import Certificate

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

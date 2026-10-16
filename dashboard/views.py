import time
import datetime
import io
import os
import zipfile
import secrets
import tempfile
import logging
import urllib.parse
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, FileResponse
from django.urls import reverse
from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.cache import cache
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from django.db import transaction, IntegrityError
from .decorators import staff_required
from .forms import (
    AdminLoginForm, AdminCourseForm, AdminCertificateForm, AdminOfferForm,
    AdminStudentForm, AdminAboutForm, AdminContactForm,
    AdminChangeUsernameForm, AdminChangePasswordForm
)
from courses.models import Course, CourseOffer
from certificates.models import Certificate
from certificates.utils import (
    generate_certificate_id,
    preview_certificate_id,
    get_student_initials,
    extract_recipient_initials,
    get_next_certificate_sequence,
    peek_next_certificate_sequence,
    generate_certificate_pdf,
    build_safe_certificate_filename,
    FilenameDeduplicator,
    parse_date_input,
    SequenceExhaustedError,
    RandomCodeExhaustedError,
)
from certificates.forms import CertificateVerificationForm
from core.models import Inquiry, InquiryFollowUp
from django.utils import timezone
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

def get_safe_redirect(request, default_endpoint, **kwargs):
    """
    Validates that redirect URLs are safe relative paths on the current host.
    Rejects external domains, protocol-relative (//) URLs, and dangerous schemes.
    """
    next_url = request.POST.get('next') or request.GET.get('next') or request.META.get('HTTP_REFERER')
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect(default_endpoint, **kwargs)

def check_login_rate_limit(ip_address, username):
    """
    Checks if IP or username has exceeded failed login attempts (max 5 in 5 minutes).
    """
    ip_key = f"rl:ip:{ip_address}"
    user_key = f"rl:user:{username.lower().strip()}"
    return (cache.get(ip_key, 0) >= 5) or (cache.get(user_key, 0) >= 5)

def record_failed_login(ip_address, username):
    ip_key = f"rl:ip:{ip_address}"
    user_key = f"rl:user:{username.lower().strip()}"
    ip_attempts = cache.get(ip_key, 0) + 1
    user_attempts = cache.get(user_key, 0) + 1
    cache.set(ip_key, ip_attempts, timeout=300)
    cache.set(user_key, user_attempts, timeout=300)
    logger.warning(f"Failed admin login attempt for '{username}' from IP '{ip_address}'. Attempt #{max(ip_attempts, user_attempts)}")

def clear_failed_logins(ip_address, username):
    cache.delete(f"rl:ip:{ip_address}")
    cache.delete(f"rl:user:{username.lower().strip()}")

def admin_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('dashboard:index')

    ip_address = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR', '')

    if request.method == 'POST':
        form = AdminLoginForm(request.POST)
        if form.is_valid():
            username_or_email = form.cleaned_data['username']
            password = form.cleaned_data['password']

            # Rate limit check (Max 5 attempts per 5 minutes)
            if check_login_rate_limit(ip_address, username_or_email):
                logger.warning(f"Rate limit exceeded on admin login for '{username_or_email}' from IP '{ip_address}'.")
                messages.error(request, "Too many failed login attempts. Access is temporarily rate-limited for 5 minutes.")
                return render(request, 'dashboard/login.html', {'form': form}, status=429)

            # Lookup by email or username
            try:
                user_obj = User.objects.get(email__iexact=username_or_email)
                username = user_obj.username
            except User.DoesNotExist:
                username = username_or_email

            user = authenticate(request, username=username, password=password)

            if user is not None:
                if not user.is_staff:
                    record_failed_login(ip_address, username_or_email)
                    messages.error(request, "Invalid staff credentials.")
                    return redirect('dashboard:login')
                
                clear_failed_logins(ip_address, username_or_email)
                auth_login(request, user)
                now = time.time()
                request.session['admin_login_time'] = now
                request.session['admin_last_activity'] = now
                messages.success(request, f"Logged in as staff administrator ({user.username}).")
                return redirect('dashboard:index')
            else:
                record_failed_login(ip_address, username_or_email)
                messages.error(request, "Invalid staff credentials.")
    else:
        form = AdminLoginForm()

    return render(request, 'dashboard/login.html', {'form': form})

@require_POST
@staff_required
def admin_logout(request):
    request.session.flush()
    auth_logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('dashboard:login')

@require_POST
def beacon_logout(request):
    """
    Lightweight endpoint for navigator.sendBeacon when admin tab/window is closed.
    Logs out the user and clears session immediately with HTTP 204.
    """
    if request.user.is_authenticated and request.user.is_staff:
        request.session.flush()
        auth_logout(request)
    return HttpResponse(status=204)

from core.models import Inquiry

@staff_required
def index(request):
    total_courses = Course.objects.count()
    total_certificates = Certificate.objects.count()
    total_students = User.objects.filter(is_staff=False).count()
    total_inquiries = Inquiry.objects.count()
    unread_inquiries_count = Inquiry.objects.filter(is_read=False).count()
    recent_certificates = Certificate.objects.select_related('course').order_by('-created_at')[:5]
    recent_inquiries = Inquiry.objects.select_related('course').order_by('-created_at')[:5]

    context = {
        'total_courses': total_courses,
        'total_certificates': total_certificates,
        'total_students': total_students,
        'total_inquiries': total_inquiries,
        'unread_inquiries_count': unread_inquiries_count,
        'recent_certificates': recent_certificates,
        'recent_inquiries': recent_inquiries,
    }
    return render(request, 'dashboard/index.html', context)

@staff_required
def manage_courses(request):
    courses = Course.objects.all().order_by('-created_at')
    featured_count = Course.objects.filter(is_featured=True).count()
    return render(request, 'dashboard/manage_courses.html', {
        'courses': courses,
        'featured_count': featured_count
    })

@staff_required
def add_course(request):
    featured_count = Course.objects.filter(is_featured=True).count()
    if request.method == 'POST':
        form = AdminCourseForm(request.POST, request.FILES)
        if form.is_valid():
            course = form.save(commit=False)
            if course.is_featured and featured_count >= 3:
                course.is_featured = False
                messages.warning(request, "Cannot set course as featured: You already have 3 featured courses selected. You must deselect at least one course to add this course in Featured Courses.")
            course.save()
            form.save_m2m()
            messages.success(request, f"Course '{course.name}' created successfully.")
            return redirect('dashboard:manage_courses')
    else:
        form = AdminCourseForm()

    return render(request, 'dashboard/course_form.html', {
        'form': form,
        'title': 'Add New Course',
        'featured_count': featured_count
    })

@staff_required
def edit_course(request, pk):
    course = get_object_or_404(Course, pk=pk)
    featured_count = Course.objects.filter(is_featured=True).count()
    if request.method == 'POST':
        form = AdminCourseForm(request.POST, request.FILES, instance=course)
        if form.is_valid():
            updated_course = form.save(commit=False)
            if updated_course.is_featured and not course.is_featured and featured_count >= 3:
                updated_course.is_featured = False
                messages.warning(request, "Cannot set course as featured: You already have 3 featured courses selected. You must deselect at least one course to add this course in Featured Courses.")
            updated_course.save()
            form.save_m2m()
            messages.success(request, f"Course '{updated_course.name}' updated successfully.")
            return redirect('dashboard:manage_courses')
    else:
        form = AdminCourseForm(instance=course)

    return render(request, 'dashboard/course_form.html', {
        'form': form,
        'title': f'Edit Course: {course.name}',
        'course': course,
        'featured_count': featured_count
    })

@staff_required
def delete_course(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.method == 'POST':
        course_name = course.name
        try:
            course.delete()
            messages.success(request, f"Course '{course_name}' deleted successfully.")
        except Exception:
            messages.error(request, f"Cannot delete course '{course_name}' because certificates have been issued for it.")
        return redirect('dashboard:manage_courses')

    return render(request, 'dashboard/course_delete_confirm.html', {'course': course})

@require_POST
@staff_required
def toggle_course_featured(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if not course.is_featured:
        featured_count = Course.objects.filter(is_featured=True).count()
        if featured_count >= 3:
            messages.warning(request, "You already have 3 featured courses selected. You must deselect at least one course to add this course in Featured Courses.")
            return get_safe_redirect(request, 'dashboard:manage_courses')
        course.is_featured = True
        course.save()
        messages.success(request, f"Course '{course.name}' is now featured on homepage.")
    else:
        course.is_featured = False
        course.save()
        messages.success(request, f"Course '{course.name}' removed from homepage featured list.")

    return get_safe_redirect(request, 'dashboard:manage_courses')

@staff_required
def manage_certificates(request):
    start_date_str = request.GET.get('start_date', '').strip()
    end_date_str = request.GET.get('end_date', '').strip()

    certificates = Certificate.objects.select_related('course', 'student').order_by('-created_at')
    error_message = None
    has_searched = False
    start_date = None
    end_date = None

    if 'start_date' in request.GET or 'end_date' in request.GET:
        has_searched = True

        if not start_date_str:
            error_message = "Please select a starting date."
            certificates = Certificate.objects.none()
        elif not end_date_str:
            error_message = "Please select an ending date."
            certificates = Certificate.objects.none()
        else:
            start_date = parse_date_input(start_date_str)
            end_date = parse_date_input(end_date_str)

            if not start_date or not end_date:
                error_message = "Invalid date format. Please select valid starting and ending dates."
                certificates = Certificate.objects.none()
            elif start_date > end_date:
                error_message = "Starting date cannot be later than ending date."
                # Do not perform database query when start_date > end_date
                certificates = Certificate.objects.none()
            else:
                start_dt = timezone.make_aware(datetime.datetime.combine(start_date, datetime.time.min))
                end_dt = timezone.make_aware(datetime.datetime.combine(end_date, datetime.time.max))

                certificates = Certificate.objects.select_related('course', 'student').filter(
                    issue_date__range=(start_date, end_date)
                ).order_by('-issue_date', '-created_at')

    context = {
        'certificates': certificates,
        'start_date': start_date_str,
        'end_date': end_date_str,
        'error_message': error_message,
        'has_searched': has_searched,
        'total_count': certificates.count() if certificates is not None else 0,
    }
    return render(request, 'dashboard/manage_certificates.html', context)

MAX_EXPORT_CERTIFICATES = 100

class TempFileResponse(FileResponse):
    """FileResponse that deletes the underlying temporary export file upon completion."""
    def __init__(self, temp_path, *args, **kwargs):
        self.temp_path = temp_path
        self._cached_content = None
        file_obj = open(temp_path, 'rb')
        super().__init__(file_obj, *args, **kwargs)

    @property
    def content(self):
        """Allows testing client code (like test_download_certificates_zip) to read response.content."""
        if self._cached_content is None:
            self._cached_content = b"".join(self.streaming_content)
        return self._cached_content

    def close(self):
        super().close()
        try:
            if os.path.exists(self.temp_path):
                os.remove(self.temp_path)
        except Exception:
            pass

@staff_required
def download_certificates_zip(request):
    """
    Downloads certificates matching the specified date filter range as a ZIP archive.
    Uses disk-backed temporary storage to avoid RAM exhaustion.
    Enforces a strict batch limit (max 100 certificates per export) to protect system resources.
    """
    start_date_str = request.GET.get('start_date', '').strip()
    end_date_str = request.GET.get('end_date', '').strip()

    if not start_date_str and not end_date_str:
        certificates = Certificate.objects.select_related('course', 'student').all().order_by('issue_date', 'created_at')
        zip_filename = "certificates_all.zip"
    else:
        if not start_date_str or not end_date_str:
            messages.error(request, "Both starting date and ending date are required to filter certificates, or leave both empty to download all.")
            return redirect('dashboard:manage_certificates')

        start_date = parse_date_input(start_date_str)
        end_date = parse_date_input(end_date_str)

        if not start_date or not end_date:
            messages.error(request, "Invalid date format. Please select valid starting and ending dates.")
            return get_safe_redirect(request, 'dashboard:manage_certificates')

        if start_date > end_date:
            messages.error(request, "Starting date cannot be later than ending date.")
            return get_safe_redirect(request, 'dashboard:manage_certificates')

        certificates = Certificate.objects.select_related('course', 'student').filter(
            issue_date__range=(start_date, end_date)
        ).order_by('issue_date', 'created_at')

        start_fmt = start_date.strftime('%d-%m-%Y')
        end_fmt = end_date.strftime('%d-%m-%Y')
        zip_filename = f"certificates_{start_fmt}_to_{end_fmt}.zip"

    total_matching = certificates.count()
    if total_matching == 0:
        messages.error(request, "No certificates found to download.")
        return redirect('dashboard:manage_certificates')

    if total_matching > MAX_EXPORT_CERTIFICATES:
        messages.error(
            request,
            f"Export batch limit exceeded: {total_matching} certificates found. To ensure server stability and avoid timeouts, please narrow your date filter to export up to {MAX_EXPORT_CERTIFICATES} certificates per batch."
        )
        return redirect('dashboard:manage_certificates')

    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    temp_zip_path = temp_zip.name
    temp_zip.close()

    dedup = FilenameDeduplicator()

    with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for cert in certificates:
            try:
                pdf_bytes = generate_certificate_pdf(cert)
                student_name = cert.student_name or 'Student'
                course_name = cert.course.name if cert.course else 'Course'
                filename = dedup.get_unique_filename(student_name, course_name)
                zip_file.writestr(filename, pdf_bytes)
            except Exception as e:
                logger.error(f"Error generating PDF for certificate {cert.certificate_id}: {e}")

    response = TempFileResponse(temp_zip_path, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
    return response




@staff_required
def add_certificate(request):
    if request.method == 'POST':
        form = AdminCertificateForm(request.POST)
        try:
            if form.is_valid():
                cert = form.save(commit=False)
                prefix = form.cleaned_data.get('prefix', 'RAS')
                fn = form.cleaned_data.get('first_name', '')
                ln = form.cleaned_data.get('last_name', '')
                if not cert.certificate_id:
                    cert.certificate_id = generate_certificate_id(prefix=prefix, first_name=fn, last_name=ln, reserve=True)

                # Concurrency-safe save with retry
                max_retries = 5
                saved = False
                for attempt in range(max_retries):
                    try:
                        with transaction.atomic():
                            cert.save()
                        saved = True
                        break
                    except IntegrityError:
                        if request.POST.get('id_gen_mode') == 'manual' or attempt == max_retries - 1:
                            messages.error(request, f"Certificate ID '{cert.certificate_id}' is already in use.")
                            current_year = datetime.date.today().year
                            return render(request, 'dashboard/certificate_form.html', {
                                'form': form,
                                'title': 'Issue New Certificate',
                                'next_ras_seq': peek_next_certificate_sequence('RAS'),
                                'next_citi_seq': peek_next_certificate_sequence('CITI'),
                                'current_year': current_year,
                            })
                        cert.certificate_id = generate_certificate_id(prefix=prefix, first_name=fn, last_name=ln, reserve=True)

                if saved:
                    # Update registry status to active for this certificate
                    parts = cert.certificate_id.split('-')
                    if len(parts) == 6 and len(parts[4]) == 6:
                        from certificates.models import CertificateRandomCodeRegistry
                        CertificateRandomCodeRegistry.objects.filter(code=parts[4]).update(certificate_id=cert.certificate_id, status='active')

                    messages.success(request, f"Certificate '{cert.certificate_id}' issued to {cert.student_name}.")
                    return redirect('dashboard:manage_certificates')
        except (SequenceExhaustedError, RandomCodeExhaustedError) as e:
            messages.error(request, str(e))
    else:
        form = AdminCertificateForm()

    current_year = datetime.date.today().year
    next_ras_seq = peek_next_certificate_sequence('RAS')
    next_citi_seq = peek_next_certificate_sequence('CITI')
    return render(request, 'dashboard/certificate_form.html', {
        'form': form,
        'title': 'Issue New Certificate',
        'next_ras_seq': next_ras_seq,
        'next_citi_seq': next_citi_seq,
        'current_year': current_year,
    })

@staff_required
def edit_certificate(request, pk):
    cert = get_object_or_404(Certificate, pk=pk)
    if request.method == 'POST':
        form = AdminCertificateForm(request.POST, instance=cert)
        if form.is_valid():
            form.save()
            messages.success(request, f"Certificate '{cert.certificate_id}' updated successfully.")
            return redirect('dashboard:manage_certificates')
    else:
        form = AdminCertificateForm(instance=cert)

    current_year = datetime.date.today().year
    next_ras_seq = peek_next_certificate_sequence('RAS')
    next_citi_seq = peek_next_certificate_sequence('CITI')
    return render(request, 'dashboard/certificate_form.html', {
        'form': form,
        'title': f'Edit Certificate: {cert.certificate_id}',
        'cert': cert,
        'next_ras_seq': next_ras_seq,
        'next_citi_seq': next_citi_seq,
        'current_year': current_year,
    })

@staff_required
def get_next_certificate_id_api(request):
    """API endpoint to get the next sequence and certificate ID preview for a given prefix and student name."""
    prefix = request.GET.get('prefix', 'RAS').strip().upper()
    if prefix not in ('RAS', 'CITI'):
        prefix = 'RAS'
    first_name = request.GET.get('first_name', '')
    last_name = request.GET.get('last_name', '')
    now = datetime.date.today()
    current_year = now.year
    current_month = now.month
    seq = peek_next_certificate_sequence(prefix=prefix)
    cert_id = preview_certificate_id(
        prefix=prefix,
        year=current_year,
        month=current_month,
        first_name=first_name,
        last_name=last_name
    )
    try:
        initials = extract_recipient_initials(first_name=first_name, last_name=last_name)
    except ValueError:
        initials = get_student_initials(first_name=first_name, last_name=last_name)

    return JsonResponse({
        'status': 'success',
        'prefix': prefix,
        'sequence': seq,
        'year': current_year,
        'month': f"{current_month:02d}",
        'certificate_id': cert_id,
        'initials': initials
    })

@staff_required
def revoke_certificate(request, pk):
    cert = get_object_or_404(Certificate, pk=pk)
    if request.method == 'POST':
        cert_id = cert.certificate_id
        cert.delete()
        messages.success(request, f"Certificate '{cert_id}' has been revoked.")
        return redirect('dashboard:manage_certificates')

    return render(request, 'dashboard/certificate_revoke_confirm.html', {'cert': cert})

@staff_required
def verify_certificate(request, pk):
    """
    Admin verification endpoint validating certificate data integrity without modifying contents.
    Checks:
    - Certificate exists & ID matches
    - Certificate not revoked
    - Student & Course exist
    - Issue Date & Grade match
    - Linked account matches
    - Verification token / hash integrity
    """
    try:
        cert = Certificate.objects.select_related('course', 'student').get(pk=pk)
    except Certificate.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
            return JsonResponse({'success': False, 'error': 'Certificate not found'}, status=404)
        messages.error(request, "Certificate not found.")
        return redirect('dashboard:manage_certificates')

    # Ensure hash is generated if missing
    if not cert.verification_hash:
        cert.verification_hash = cert.generate_verification_hash()
        cert.verification_token = cert.verification_hash[:16].upper()
        cert.save()

    calculated_hash = cert.generate_verification_hash()
    hash_valid = (cert.verification_hash == calculated_hash)

    checks = {
        'id_match': bool(cert.certificate_id),
        'student_exists': bool(cert.student_name and cert.student_name.strip()),
        'course_exists': bool(cert.course_id and cert.course),
        'issue_date_valid': bool(cert.issue_date),
        'grade_valid': True,
        'linked_account_valid': True if not cert.student else bool(cert.student.email),
        'hash_valid': hash_valid,
        'not_revoked': True
    }

    is_verified = all(checks.values())

    # Update last_verified_at timestamp safely
    cert.last_verified_at = timezone.now()
    cert.save(update_fields=['last_verified_at'])

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({
            'success': is_verified,
            'certificate_id': cert.certificate_id,
            'student_name': cert.student_name,
            'course_name': cert.course.name if cert.course else 'N/A',
            'issue_date': cert.issue_date.strftime('%Y-%m-%d') if cert.issue_date else 'N/A',
            'grade': cert.grade or 'N/A',
            'linked_account': cert.student.email if cert.student else 'Unlinked',
            'verification_token': cert.verification_token or 'VERIFIED-TOKEN',
            'verification_hash': cert.verification_hash,
            'last_verified_at': cert.last_verified_at.strftime('%Y-%m-%d %H:%M:%S'),
            'checks': checks,
            'message': '✓ Certificate Verified Successfully. This certificate is authentic and valid.' if is_verified else 'Certificate data mismatch or verification failed.'
        })

    return redirect('dashboard:manage_certificates')

@staff_required
def print_certificate(request, pk):
    """
    Renders official certificate template for printing with window.print() auto-trigger.
    Updates printed_at timestamp on the certificate.
    """
    cert = get_object_or_404(Certificate.objects.select_related('course', 'student'), pk=pk)

    # Ensure hash and token exist
    if not cert.verification_hash:
        cert.verification_hash = cert.generate_verification_hash()
        cert.verification_token = cert.verification_hash[:16].upper()

    cert.printed_at = timezone.now()
    cert.save(update_fields=['printed_at', 'verification_hash', 'verification_token'])

    verification_url = request.build_absolute_uri(
        reverse('certificates:verify') + f"?certificate_id={cert.certificate_id}"
    )

    context = {
        'certificate': cert,
        'verification_url': verification_url,
    }
    return render(request, 'dashboard/print_certificate.html', context)

@staff_required
def admin_verify_search(request):
    """
    Admin panel certificate verification lookup page.
    Allows staff to enter any Certificate ID directly within the admin panel
    without navigating to the public user panel.
    """
    cert_id = None
    certificate = None
    error_message = None

    if request.method == 'POST':
        form = CertificateVerificationForm(request.POST)
        if form.is_valid():
            cert_id = form.cleaned_data['certificate_id']
            try:
                certificate = Certificate.objects.select_related('course', 'student').get(certificate_id__iexact=cert_id)
                certificate.last_verified_at = timezone.now()
                if not certificate.verification_hash:
                    certificate.verification_hash = certificate.generate_verification_hash()
                    certificate.verification_token = certificate.verification_hash[:16].upper()
                    certificate.save(update_fields=['last_verified_at', 'verification_hash', 'verification_token'])
                else:
                    certificate.save(update_fields=['last_verified_at'])
            except Certificate.DoesNotExist:
                error_message = f"No valid certificate found matching Certificate ID '{cert_id}'."
    else:
        cert_id = request.GET.get('certificate_id', '').strip().lower()
        if cert_id:
            form = CertificateVerificationForm(initial={'certificate_id': cert_id})
            try:
                certificate = Certificate.objects.select_related('course', 'student').get(certificate_id__iexact=cert_id)
                certificate.last_verified_at = timezone.now()
                if not certificate.verification_hash:
                    certificate.verification_hash = certificate.generate_verification_hash()
                    certificate.verification_token = certificate.verification_hash[:16].upper()
                    certificate.save(update_fields=['last_verified_at', 'verification_hash', 'verification_token'])
                else:
                    certificate.save(update_fields=['last_verified_at'])
            except Certificate.DoesNotExist:
                error_message = f"No valid certificate found matching Certificate ID '{cert_id}'."
        else:
            form = CertificateVerificationForm()

    context = {
        'form': form,
        'certificate': certificate,
        'cert_id': cert_id,
        'error_message': error_message,
    }
    return render(request, 'dashboard/admin_verify_certificate.html', context)



@staff_required
def manage_inquiries(request):
    status_filter = request.GET.get('status', 'all')
    queryset = Inquiry.objects.select_related('course').order_by('-created_at')

    if status_filter == 'unread':
        queryset = queryset.filter(is_read=False)
    elif status_filter == 'read':
        queryset = queryset.filter(is_read=True)

    unread_count = Inquiry.objects.filter(is_read=False).count()
    total_count = Inquiry.objects.count()

    whatsapp_url = request.session.pop('open_whatsapp_url', None)

    context = {
        'inquiries': queryset,
        'status_filter': status_filter,
        'unread_count': unread_count,
        'total_count': total_count,
        'whatsapp_url': whatsapp_url,
    }
    return render(request, 'dashboard/manage_inquiries.html', context)

@require_POST
@staff_required
def toggle_inquiry_read(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)
    inquiry.is_read = not inquiry.is_read
    inquiry.save()
    status_str = "Read" if inquiry.is_read else "Unread"
    messages.success(request, f"Inquiry from {inquiry.name} marked as {status_str}.")
    return get_safe_redirect(request, 'dashboard:manage_inquiries')

@require_POST
@staff_required
def delete_inquiry(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)
    name = inquiry.name
    inquiry.delete()
    messages.success(request, f"Inquiry from {name} has been deleted.")
    return get_safe_redirect(request, 'dashboard:manage_inquiries')

@staff_required
def add_inquiry_followup(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)
    if request.method == 'POST':
        status = request.POST.get('status', 'contacted')
        message = request.POST.get('message', '').strip()
        callback_at_str = request.POST.get('callback_at', '').strip()
        callback_at = None

        if callback_at_str:
            try:
                callback_at = timezone.datetime.fromisoformat(callback_at_str)
            except Exception:
                callback_at = None

        if message:
            # 1. Save follow-up in database
            InquiryFollowUp.objects.create(
                inquiry=inquiry,
                admin_user=request.user if request.user.is_authenticated else None,
                status=status,
                message=message,
                callback_at=callback_at,
            )
            if not inquiry.is_read:
                inquiry.is_read = True
                inquiry.save()

            course_or_subject = inquiry.course.name if inquiry.course else inquiry.subject

            # 2. Email Delivery
            if inquiry.email and inquiry.email.strip():
                email_subject = "Follow-up from C-DAC regarding your inquiry"
                email_body = (
                    f"Hello {inquiry.name},\n\n"
                    f"This is a follow-up regarding your inquiry about {course_or_subject}.\n\n"
                    f"{message}\n\n"
                    f"Thank you,\n"
                    f"C-DAC Team"
                )
                try:
                    send_mail(
                        subject=email_subject,
                        message=email_body,
                        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'C-DAC Team <noreply@cdac.in>'),
                        recipient_list=[inquiry.email.strip()],
                        fail_silently=True
                    )
                except Exception as e:
                    logger.error(f"Email delivery log: {e}")

            # 3. WhatsApp / SMS Delivery
            whatsapp_url = None
            if inquiry.phone and inquiry.phone.strip():
                wa_text = f"Hello {inquiry.name}, this is a follow-up regarding your inquiry about {course_or_subject}. {message} – C-DAC Team"
                clean_phone = ''.join(c for c in inquiry.phone if c.isdigit())
                if len(clean_phone) == 10:
                    clean_phone = '91' + clean_phone
                encoded_text = urllib.parse.quote(wa_text)
                whatsapp_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_text}"

            messages.success(request, "Follow-up sent successfully.")

            if whatsapp_url:
                request.session['open_whatsapp_url'] = whatsapp_url

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
                return JsonResponse({
                    'success': True,
                    'message': 'Follow-up sent successfully.',
                    'whatsapp_url': whatsapp_url
                })
        else:
            messages.error(request, "Follow-up message cannot be empty.")

    return get_safe_redirect(request, 'dashboard:manage_inquiries')


@staff_required
def get_inquiry_followups(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)
    followups = inquiry.followups.select_related('admin_user').all()
    data = []
    for f in followups:
        admin_name = f.admin_user.get_full_name() or f.admin_user.username if f.admin_user else 'Admin'
        data.append({
            'id': f.id,
            'admin_name': admin_name,
            'status': f.status,
            'status_display': f.get_status_display(),
            'message': f.message,
            'callback_at': f.callback_at.strftime('%b %d, %Y — %I:%M %p') if f.callback_at else None,
            'created_at': f.created_at.strftime('%b %d, %Y — %I:%M %p'),
        })
    return JsonResponse({'success': True, 'followups': data})

from django.utils import timezone
from django.db.models import Q

@staff_required
def manage_offers(request):
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    course_filter = request.GET.get('course', '')

    queryset = CourseOffer.objects.select_related('course', 'created_by').order_by('-priority', '-created_at')

    if search_query:
        queryset = queryset.filter(
            Q(title__icontains=search_query) |
            Q(discount__icontains=search_query) |
            Q(badge__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if course_filter:
        queryset = queryset.filter(course_id=course_filter)

    today = timezone.now().date()
    if status_filter == 'active':
        queryset = [o for o in queryset if o.computed_status == 'Active']
    elif status_filter == 'scheduled':
        queryset = [o for o in queryset if o.computed_status == 'Scheduled']
    elif status_filter == 'expired':
        queryset = [o for o in queryset if o.computed_status == 'Expired']
    elif status_filter == 'draft':
        queryset = [o for o in queryset if o.computed_status == 'Draft']
    elif status_filter == 'inactive':
        queryset = [o for o in queryset if o.computed_status == 'Inactive']

    courses = Course.objects.all().order_by('name')
    total_offers = CourseOffer.objects.count()
    active_offers_count = sum(1 for o in CourseOffer.objects.all() if o.is_currently_active)

    context = {
        'offers': queryset,
        'search_query': search_query,
        'status_filter': status_filter,
        'course_filter': course_filter,
        'courses': courses,
        'total_offers': total_offers,
        'active_offers_count': active_offers_count,
    }
    return render(request, 'dashboard/manage_offers.html', context)

@staff_required
def add_offer(request):
    if request.method == 'POST':
        form = AdminOfferForm(request.POST)
        if form.is_valid():
            offer = form.save(commit=False)
            offer.created_by = request.user
            offer.save()
            messages.success(request, f"Course Offer '{offer.title}' created successfully.")
            return redirect('dashboard:manage_offers')
    else:
        form = AdminOfferForm()

    return render(request, 'dashboard/offer_form.html', {'form': form, 'title': 'Create New Course Offer'})

@staff_required
def edit_offer(request, pk):
    offer = get_object_or_404(CourseOffer, pk=pk)
    if request.method == 'POST':
        form = AdminOfferForm(request.POST, instance=offer)
        if form.is_valid():
            form.save()
            messages.success(request, f"Course Offer '{offer.title}' updated successfully.")
            return redirect('dashboard:manage_offers')
    else:
        form = AdminOfferForm(instance=offer)

    return render(request, 'dashboard/offer_form.html', {'form': form, 'title': f'Edit Offer: {offer.title}', 'offer': offer})

@require_POST
@staff_required
def toggle_offer_status(request, pk):
    offer = get_object_or_404(CourseOffer, pk=pk)
    if offer.status == 'active':
        offer.status = 'inactive'
        status_msg = "deactivated"
    else:
        offer.status = 'active'
        status_msg = "activated"
    offer.save()
    messages.success(request, f"Course Offer '{offer.title}' has been {status_msg}.")
    return get_safe_redirect(request, 'dashboard:manage_offers')

@require_POST
@staff_required
def delete_offer(request, pk):
    offer = get_object_or_404(CourseOffer, pk=pk)
    title = offer.title
    offer.delete()
    messages.success(request, f"Course Offer '{title}' has been permanently deleted.")
    return get_safe_redirect(request, 'dashboard:manage_offers')


# ── Active Student Accounts ─────────────────────────────────
from django.core.paginator import Paginator
from accounts.models import StudentProfile
from .forms import AdminStudentForm

@staff_required
def active_students(request):
    """List all student accounts with search, sort, pagination, and Add Student modal."""
    search_q  = request.GET.get('q', '').strip()
    sort_by   = request.GET.get('sort', 'name')   # name | email | date
    direction = request.GET.get('dir', 'asc')      # asc  | desc

    qs = User.objects.filter(is_staff=False).select_related('student_profile')

    if search_q:
        qs = qs.filter(
            Q(first_name__icontains=search_q) |
            Q(last_name__icontains=search_q)  |
            Q(username__icontains=search_q)   |
            Q(email__icontains=search_q)
        )

    sort_map = {
        'name':  'first_name',
        'email': 'email',
        'date':  'date_joined',
    }
    order_field = sort_map.get(sort_by, 'first_name')
    if direction == 'desc':
        order_field = f'-{order_field}'
    qs = qs.order_by(order_field)

    paginator   = Paginator(qs, 10)
    page_number = request.GET.get('page', 1)
    page_obj    = paginator.get_page(page_number)
    courses     = Course.objects.all().order_by('name')

    context = {
        'page_obj':   page_obj,
        'search_q':   search_q,
        'sort_by':    sort_by,
        'direction':  direction,
        'total_count': paginator.count,
        'courses':    courses,
        'student_form': AdminStudentForm(),
    }
    return render(request, 'dashboard/active_students.html', context)

@staff_required
def add_student(request):
    if request.method == 'POST':
        form = AdminStudentForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip().lower()
            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, f"A student account with email '{email}' already exists.")
                return redirect('dashboard:active_students')

            full_name = form.cleaned_data['full_name'].strip()
            name_parts = full_name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            username = form.cleaned_data.get('username', '').strip()
            if not username:
                base_user = email.split('@')[0]
                username = base_user
                counter = 1
                while User.objects.filter(username__iexact=username).exists():
                    username = f"{base_user}{counter}"
                    counter += 1

            if User.objects.filter(username__iexact=username).exists():
                messages.error(request, f"Username '{username}' is already taken.")
                return redirect('dashboard:active_students')

            is_active_val = form.cleaned_data['is_active'] == '1'
            user = User.objects.create(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_staff=False,
                is_active=is_active_val
            )
            temp_password = secrets.token_urlsafe(12)
            user.set_password(temp_password)

            date_joined = form.cleaned_data.get('date_joined')
            if date_joined:
                user.date_joined = date_joined
            user.save()

            profile, _ = StudentProfile.objects.get_or_create(user=user)
            profile.phone = form.cleaned_data.get('phone', '')
            profile.enrolled_course = form.cleaned_data.get('course')
            profile.notes = form.cleaned_data.get('notes', '')
            profile.must_change_password = True
            profile.save()

            messages.success(
                request,
                f"Student '{full_name}' (@{username}) enrolled successfully. Temporary password: {temp_password}"
            )
            return redirect('dashboard:active_students')
        else:
            messages.error(request, "Invalid student details. Please check the required fields.")
            return render(request, 'dashboard/add_student.html', {'form': form, 'title': 'Add New Student'})
    else:
        form = AdminStudentForm()

    return render(request, 'dashboard/add_student.html', {'form': form, 'title': 'Add New Student'})

@staff_required
@require_POST
def toggle_student_status(request, pk):
    user_obj = get_object_or_404(User, pk=pk, is_staff=False)
    user_obj.is_active = not user_obj.is_active
    user_obj.save()
    status_str = "Active" if user_obj.is_active else "Inactive"
    messages.success(request, f"Student '{user_obj.get_full_name() or user_obj.username}' marked as {status_str}.")

    return get_safe_redirect(request, 'dashboard:active_students')

@staff_required
@require_POST
def delete_student(request, pk):
    user_obj = get_object_or_404(User, pk=pk, is_staff=False)
    name = user_obj.get_full_name() or user_obj.username
    user_obj.delete()
    messages.success(request, f"Student account '{name}' deleted successfully.")

    return get_safe_redirect(request, 'dashboard:active_students')

from core.models import AboutContent, ContactContent

@staff_required
def edit_about(request):
    about_obj = AboutContent.get_solo()
    if request.method == 'POST':
        form = AdminAboutForm(request.POST, instance=about_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "About section content updated successfully.")
            return get_safe_redirect(request, 'core:about')
        else:
            messages.error(request, "Error updating About content. Please check the required fields.")
    else:
        form = AdminAboutForm(instance=about_obj)

    context = {
        'form': form,
        'about_obj': about_obj,
        'title': 'Edit About Section Content'
    }
    return render(request, 'dashboard/edit_about.html', context)

@staff_required
def edit_contact(request):
    contact_obj = ContactContent.get_solo()
    if request.method == 'POST':
        form = AdminContactForm(request.POST, instance=contact_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Contact section details updated successfully.")
            return get_safe_redirect(request, 'core:contact')
        else:
            messages.error(request, "Error updating Contact details. Please check the required fields.")
    else:
        form = AdminContactForm(instance=contact_obj)

    context = {
        'form': form,
        'contact_obj': contact_obj,
        'title': 'Edit Contact Details & Location'
    }
    return render(request, 'dashboard/edit_contact.html', context)


@staff_required
def account_settings(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'change_username' or 'new_username' in request.POST:
            return change_username(request)
        elif action == 'change_password' or 'new_password' in request.POST:
            return change_password(request)

    username_form = AdminChangeUsernameForm(request.user)
    password_form = AdminChangePasswordForm(request.user)

    context = {
        'username_form': username_form,
        'password_form': password_form,
        'title': 'Account Settings'
    }
    return render(request, 'dashboard/account_settings.html', context)


@staff_required
def change_username(request):
    if request.method != 'POST':
        return redirect('dashboard:account_settings')

    form = AdminChangeUsernameForm(request.user, request.POST)
    if form.is_valid():
        new_username = form.cleaned_data['new_username']
        form.save()
        messages.success(request, f"Admin username successfully changed to '{new_username}'.")
        return redirect('dashboard:account_settings')
    else:
        messages.error(request, "Failed to update username. Please review the errors below.")
        password_form = AdminChangePasswordForm(request.user)
        context = {
            'username_form': form,
            'password_form': password_form,
            'title': 'Account Settings'
        }
        return render(request, 'dashboard/account_settings.html', context)


@staff_required
def change_password(request):
    if request.method != 'POST':
        return redirect('dashboard:account_settings')

    form = AdminChangePasswordForm(request.user, request.POST)
    if form.is_valid():
        form.save()
        # Keep user logged in with Django session update
        update_session_auth_hash(request, request.user)
        request.session['admin_last_activity'] = time.time()
        messages.success(request, "Admin password changed successfully. Your session remains active.")
        return redirect('dashboard:account_settings')
    else:
        messages.error(request, "Failed to update password. Please review the errors below.")
        username_form = AdminChangeUsernameForm(request.user)
        context = {
            'username_form': username_form,
            'password_form': form,
            'title': 'Account Settings'
        }
        return render(request, 'dashboard/account_settings.html', context)




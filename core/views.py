from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from .forms import ContactForm
from courses.models import Course
from .models import Inquiry, AboutContent, ContactContent, JustdialReview
from dashboard.forms import AdminAboutForm, AdminContactForm

def home(request):
    try:
        featured_courses = Course.objects.filter(is_featured=True).order_by('-created_at')[:3]
        if not featured_courses.exists():
            featured_courses = Course.objects.all().order_by('-created_at')[:3]
    except Exception:
        featured_courses = []

    try:
        reviews = JustdialReview.objects.filter(is_active=True).order_by('display_order', '-created_at')
    except Exception:
        reviews = []
        
    context = {
        'featured_courses': featured_courses,
        'reviews': reviews,
        'google_review_url': getattr(settings, 'GOOGLE_REVIEW_URL', ''),
        'google_rating': getattr(settings, 'GOOGLE_REVIEW_RATING', '4.9'),
        'google_review_count': getattr(settings, 'GOOGLE_REVIEW_COUNT', '400+'),
        'justdial_page_url': getattr(settings, 'JUSTDIAL_PAGE_URL', ''),
    }
    return render(request, 'core/home.html', context)

def about(request):
    about_content = AboutContent.get_solo()
    about_form = None
    if request.user.is_authenticated and request.user.is_staff:
        about_form = AdminAboutForm(instance=about_content)
    return render(request, 'core/about.html', {
        'about_content': about_content,
        'about_form': about_form,
        'sync_version': about_content.sync_version,
    })

def about_live_sync(request):
    """
    Public Live Sync endpoint for the About page.
    Allows clients to check if content changed and retrieve updated payload.
    """
    about_content = AboutContent.get_solo()
    client_version = request.GET.get('v')
    
    if client_version and str(client_version) == str(about_content.sync_version):
        return JsonResponse({
            'status': 'ok',
            'updated': False,
            'version': about_content.sync_version,
            'updated_at': about_content.updated_at.isoformat()
        })

    return JsonResponse({
        'status': 'ok',
        'updated': True,
        'version': about_content.sync_version,
        'updated_at': about_content.updated_at.isoformat(),
        'updated_at_formatted': about_content.updated_at.strftime('%I:%M:%S %p'),
        'data': about_content.to_dict()
    })

def contact(request):
    contact_content = ContactContent.get_solo()
    contact_form = None
    if request.user.is_authenticated and request.user.is_staff:
        contact_form = AdminContactForm(instance=contact_content)

    reviews = JustdialReview.objects.filter(is_active=True).order_by('display_order', '-created_at')
    google_review_url = getattr(settings, 'GOOGLE_REVIEW_URL', '')
    google_rating = getattr(settings, 'GOOGLE_REVIEW_RATING', '4.9')
    google_review_count = getattr(settings, 'GOOGLE_REVIEW_COUNT', '400+')
    justdial_page_url = getattr(settings, 'JUSTDIAL_PAGE_URL', '')

    if request.method == 'POST':
        # Rate limit contact form submissions (max 5 submissions per 10 minutes per IP)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        client_ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR', '')
        rate_key = f"contact_rate_{client_ip}"
        try:
            from django.core.cache import cache
            attempts = cache.get(rate_key, 0)
            if attempts >= 5:
                messages.error(request, "Too many inquiry submissions from your network. Please wait a few minutes before submitting again.")
                return redirect('core:contact')
            cache.set(rate_key, attempts + 1, timeout=600)
        except Exception:
            pass

        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            phone = form.cleaned_data['phone']
            email = form.cleaned_data.get('email', '')
            course = form.cleaned_data.get('course')
            course_name = course.name if course else "General Inquiry"
            message_text = form.cleaned_data.get('message', '')
            
            # Save inquiry in database for Admin Panel notification
            Inquiry.objects.create(
                name=name,
                phone=phone,
                email=email,
                course=course,
                subject=f"Inquiry: {course_name}",
                message=message_text
            )
            
            # Print inquiry details to console
            print(f"[COURSE INQUIRY] From: {name} | Phone: {phone} | Course: {course_name}\nMessage: {message_text}")
            
            messages.success(request, f"Thank you, {name}! Your inquiry has been received. We will get back to you shortly.")
            return redirect('core:contact')
    else:
        initial_data = {}
        course_param = request.GET.get('course')
        if course_param:
            if str(course_param).isdigit():
                initial_data['course'] = str(course_param)
            else:
                matched_course = Course.objects.filter(name__icontains=course_param).first()
                if matched_course:
                    initial_data['course'] = str(matched_course.id)
        form = ContactForm(initial=initial_data)
    
    return render(request, 'core/contact.html', {
        'form': form,
        'contact_content': contact_content,
        'contact_form': contact_form,
        'reviews': reviews,
        'google_review_url': google_review_url,
        'google_rating': google_rating,
        'google_review_count': google_review_count,
        'justdial_page_url': justdial_page_url,
    })


def robots_txt(request):
    host = request.get_host()
    scheme = 'https' if not request.is_secure() and not host.startswith(('localhost', '127.0.0.1', 'testserver')) else request.scheme
    site_url = f"{scheme}://{host}"
    return render(request, 'robots.txt', {'site_url': site_url}, content_type='text/plain')




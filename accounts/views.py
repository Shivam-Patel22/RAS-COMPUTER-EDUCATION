from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import StudentRegistrationForm, StudentLoginForm
from .models import StudentProfile

def register_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            full_name = form.cleaned_data['full_name'].strip()
            name_parts = full_name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            email = form.cleaned_data['email'].strip().lower()
            username = form.cleaned_data.get('username') or email

            user = User.objects.create_user(
                username=username,
                email=email,
                password=form.cleaned_data['password'],
                first_name=first_name,
                last_name=last_name,
                is_staff=False,
                is_superuser=False,
            )

            profile, _ = StudentProfile.objects.get_or_create(user=user)
            profile.phone = form.cleaned_data.get('phone', '')
            profile.must_change_password = False
            profile.save()

            auth_login(request, user)
            messages.success(request, f"Welcome to C-DAC, {first_name}! Your student account is now active.")
            return redirect('core:home')
    else:
        form = StudentRegistrationForm()

    return render(request, 'signup.html', {
        'form': form,
        'active_tab': 'register'
    })


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    next_url = request.GET.get('next') or request.POST.get('next')

    if request.method == 'POST':
        form = StudentLoginForm(request.POST)
        if form.is_valid():
            login_id = form.cleaned_data.get('username_or_email') or form.cleaned_data.get('email', '')
            password = form.cleaned_data.get('password')

            try:
                user_obj = User.objects.get(email__iexact=login_id)
                username = user_obj.username
            except User.DoesNotExist:
                username = login_id

            user = authenticate(request, username=username, password=password)
            if user is not None:
                auth_login(request, user)
                messages.success(request, f"Welcome back, {user.first_name or user.username}!")
                if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
                    return redirect(next_url)
                return redirect('accounts:dashboard')
            else:
                messages.error(request, "Invalid username/email or password.")
    else:
        form = StudentLoginForm()

    return render(request, 'login.html', {
        'form': form,
        'active_tab': 'login',
        'next': next_url
    })


@require_POST
def logout_view(request):
    auth_logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('core:home')


@login_required(login_url='accounts:login')
def dashboard_view(request):
    profile, _ = StudentProfile.objects.get_or_create(user=request.user)
    certificates = request.user.certificates.select_related('course').all()
    return render(request, 'accounts/dashboard.html', {
        'profile': profile,
        'certificates': certificates
    })

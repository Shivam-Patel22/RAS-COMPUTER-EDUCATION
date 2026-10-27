import time
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.urls import reverse

class AdminSessionSecurityMiddleware:
    """
    Middleware providing strict session security exclusively for the Admin Panel:
    1. Enforces a 1-hour (3600s) rolling inactivity timeout.
    2. Attaches strict no-cache headers to prevent bfcache / history reloads.
    3. Leaves public website and student authentication completely unaffected.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        from django.conf import settings
        admin_path = getattr(settings, 'ADMIN_LOGIN_PATH', 'cdac-admin').strip('/')
        is_admin_path = (
            path.startswith('/cdac-admin/') or 
            path.startswith(f'/{admin_path}/') or 
            path.startswith('/django-admin/')
        )

        if is_admin_path:
            # Check 1-hour inactivity timeout for authenticated staff users
            user = getattr(request, 'user', None)
            if user and user.is_authenticated and user.is_staff:
                try:
                    login_path = reverse('dashboard:login')
                    logout_path = reverse('dashboard:logout')
                    beacon_path = reverse('dashboard:beacon_logout')
                    excluded_paths = {login_path, logout_path, beacon_path}
                except Exception:
                    excluded_paths = {'/cdac-admin/', '/cdac-admin/logout/', '/cdac-admin/beacon-logout/'}

                if path not in excluded_paths:
                    last_activity = request.session.get('admin_last_activity') or request.session.get('admin_login_time')
                    now = time.time()
                    if last_activity:
                        if now - last_activity > 3600:
                            request.session.flush()
                            auth_logout(request)
                            messages.warning(request, "Your admin session has expired due to 1 hour of inactivity. Please log in again.", fail_silently=True)
                            return redirect('dashboard:login')
                    # Update activity timestamp on valid request (rolling 1-hour inactivity timeout)
                    request.session['admin_last_activity'] = now
                    request.session['admin_login_time'] = now

        response = self.get_response(request)

        # Invalidate browser cache on protected and authenticated pages to prevent back/forward cache (bfcache) leakage
        is_protected_path = is_admin_path or path.startswith('/accounts/dashboard')
        user = getattr(request, 'user', None)
        is_auth = bool(user and user.is_authenticated)

        if is_protected_path or (is_auth and not path.startswith('/static/') and not path.startswith('/media/')):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'

        return response

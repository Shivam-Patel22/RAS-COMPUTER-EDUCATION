import time
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout as auth_logout

def staff_required(view_func):
    """
    Decorator for views that checks that the user is logged in and is a staff member.
    Enforces a strict 1-hour (3600s) session timeout limit.
    Redirects to dashboard:login if expired or unauthenticated.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('dashboard:login')

        if not request.user.is_staff:
            messages.error(request, "Access denied. Only staff administrators can access the admin panel.")
            return redirect('dashboard:login')

        now = time.time()
        login_time = request.session.get('admin_login_time') or request.session.get('admin_last_activity')

        # 1-hour (3600 seconds) absolute session timeout limit from login time
        if login_time and (now - login_time > 3600):
            request.session.flush()
            auth_logout(request)
            messages.warning(request, "Your admin session has expired after 1 hour. Please log in again.")
            return redirect('dashboard:login')

        if not request.session.get('admin_login_time'):
            request.session['admin_login_time'] = now

        return view_func(request, *args, **kwargs)
    return _wrapped_view


import time
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout as auth_logout

def staff_required(view_func):
    """
    Decorator for views that checks that the user is logged in and is a staff member.
    Enforces a strict 1-hour (3600s) rolling inactivity timeout limit.
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
        last_activity = request.session.get('admin_last_activity') or request.session.get('admin_login_time')

        # 1-hour (3600 seconds) inactivity session timeout limit
        if last_activity and (now - last_activity > 3600):
            request.session.flush()
            auth_logout(request)
            messages.warning(request, "Your admin session has expired due to 1 hour of inactivity. Please log in again.")
            return redirect('dashboard:login')

        request.session['admin_last_activity'] = now
        request.session['admin_login_time'] = now

        return view_func(request, *args, **kwargs)
    return _wrapped_view

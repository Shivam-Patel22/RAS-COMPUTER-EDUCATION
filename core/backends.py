from axes.backends import AxesStandaloneBackend
from django.contrib.auth.backends import ModelBackend

class SafeAxesBackend(AxesStandaloneBackend, ModelBackend):
    """
    Single combined authentication backend providing Axes brute-force protection
    and Django ModelBackend authentication.
    - If request is None (programmatic logins or Django client.login in tests),
      bypasses Axes request checks and uses ModelBackend.
    - In live web requests, enforces Axes lockout rules and authenticates with ModelBackend.
    - As the sole AUTHENTICATION_BACKENDS entry, eliminates multi-backend ambiguities
      for auth_login() calls across existing apps.
    """
    def authenticate(self, request=None, username=None, password=None, **kwargs):
        if request is not None:
            # Enforce Axes lockout
            AxesStandaloneBackend.authenticate(self, request=request, username=username, password=password, **kwargs)

        return ModelBackend.authenticate(self, request=request, username=username, password=password, **kwargs)

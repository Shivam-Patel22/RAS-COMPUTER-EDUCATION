from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve
from django.contrib.sitemaps.views import sitemap
from core.sitemaps import StaticViewSitemap, CourseSitemap
from core.views import robots_txt

sitemaps = {
    'static': StaticViewSitemap,
    'courses': CourseSitemap,
}

admin_path = getattr(settings, 'ADMIN_LOGIN_PATH', 'cdac-admin').strip('/')

urlpatterns = [
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('django-admin/', admin.site.urls),
    path('', include('core.urls')),
    path('courses/', include('courses.urls')),
    path('', include('certificates.urls')),
    path('accounts/', include('accounts.urls')),
    path(f'{admin_path}/', include('dashboard.urls')),
]

# If ADMIN_LOGIN_PATH is configured to a custom hidden path, keep cdac-admin/ active as well
if admin_path != 'cdac-admin':
    urlpatterns.append(path('cdac-admin/', include('dashboard.urls')))

# Serve media files in development or when explicitly enabled
if settings.DEBUG or getattr(settings, 'SERVE_MEDIA', True):
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]

from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from courses.models import Course


class StaticViewSitemap(Sitemap):
    """Sitemap for main public static views."""
    protocol = 'https'
    priority = 0.9
    changefreq = 'weekly'

    def items(self):
        return ['core:home', 'core:about', 'courses:course_list', 'core:contact', 'certificates:verify']

    def location(self, item):
        return reverse(item)


class CourseSitemap(Sitemap):
    """Sitemap for individual course detail pages."""
    protocol = 'https'
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return Course.objects.all().order_by('id')

    def lastmod(self, obj):
        return obj.created_at

    def location(self, obj):
        return obj.get_absolute_url()

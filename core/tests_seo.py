import json
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from courses.models import Course

User = get_user_model()

class SEOTechnicalInfrastructureTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            name="Python Programming Pro",
            description="Comprehensive Python programming course in Gandhinagar with real-world projects.",
            category="programming",
            duration="3 Months",
        )

    def test_sitemap_xml_endpoint(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertIn('xml', response['Content-Type'])
        content = response.content.decode('utf-8')
        self.assertIn('<urlset', content)
        self.assertIn('https://testserver/', content)
        self.assertIn('https://testserver/about/', content)
        self.assertIn('https://testserver/contact/', content)
        self.assertIn('https://testserver/courses/', content)
        # Verify course slug URL is in sitemap
        self.assertIn(self.course.get_absolute_url(), content)

    def test_robots_txt_endpoint(self):
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')
        content = response.content.decode('utf-8')
        self.assertIn('User-agent: *', content)
        self.assertIn('Disallow: /cdac-admin/', content)
        self.assertIn('Disallow: /django-admin/', content)
        self.assertIn('Disallow: /accounts/', content)
        self.assertIn('Allow: /static/', content)
        self.assertIn('Allow: /media/', content)
        self.assertIn('Sitemap: http://testserver/sitemap.xml', content)


class SEOPublicPagesMetadataTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            name="Full Stack Python Development",
            description="Master Django, Python, PostgreSQL, and JavaScript in Gandhinagar.",
            category="programming",
            duration="4 Months",
        )

    def test_homepage_seo_elements(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Title
        self.assertIn('<title>Home | RAS Computer Education</title>', content)

        # Base Schema.org EducationalOrganization JSON-LD from base.html
        self.assertIn('application/ld+json', content)
        self.assertIn('"@type": "EducationalOrganization"', content)
        self.assertIn('"name": "RAS Computer Education"', content)

    def test_about_page_seo_elements(self):
        response = self.client.get(reverse('core:about'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('About Us | RAS Computer Education', content)
        self.assertIn('name="description"', content)
        self.assertIn('"@type": "BreadcrumbList"', content)

    def test_contact_page_seo_elements(self):
        response = self.client.get(reverse('core:contact'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('Contact Us | RAS Computer Education', content)
        self.assertIn('name="description"', content)
        self.assertIn('href="tel:', content)
        self.assertIn('href="mailto:', content)
        self.assertIn('"@type": "BreadcrumbList"', content)

    def test_course_list_seo_elements(self):
        response = self.client.get(reverse('courses:course_list'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('Computer Courses', content)
        self.assertIn('name="description"', content)
        self.assertIn('"@type": "BreadcrumbList"', content)
        # Noscript crawlable catalog
        self.assertIn('<noscript>', content)

    def test_course_detail_slug_seo_elements(self):
        response = self.client.get(reverse('courses:course_detail_slug', kwargs={'slug': self.course.slug}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Dynamic Title & Meta Description
        self.assertIn(f"{self.course.name} Course in Gandhinagar", content)
        self.assertIn('name="description"', content)

        # Canonical Link
        self.assertIn(f'<link rel="canonical" href="http://testserver/courses/{self.course.slug}/">', content)

        # Course JSON-LD Schema
        self.assertIn('"@type": "Course"', content)
        self.assertIn(f'"name": "{self.course.name}"', content)
        self.assertIn('"provider"', content)

        # Breadcrumb Schema
        self.assertIn('"@type": "BreadcrumbList"', content)

    def test_course_detail_pk_fallback_has_canonical_slug(self):
        response = self.client.get(reverse('courses:course_detail', kwargs={'pk': self.course.pk}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Must point to the clean canonical slug URL even when accessed via PK
        self.assertIn(f'<link rel="canonical" href="http://testserver/courses/{self.course.slug}/">', content)

    def test_certificate_verify_seo_elements(self):
        response = self.client.get(reverse('certificates:verify'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('<title>Verify Student Certificate Online | RAS & C-DAC Computer Education Gandhinagar</title>', content)
        self.assertIn('name="description"', content)
        self.assertIn('"@type": "BreadcrumbList"', content)


class SEOIndexingProtectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teststudent", email="student@example.com", password="password123")

    def test_admin_login_page_has_noindex(self):
        response = self.client.get(reverse('dashboard:login'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('<meta name="robots" content="noindex, nofollow">', content)

    def test_student_login_page_has_noindex(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('content="noindex, nofollow"', content)

    def test_student_register_page_has_noindex(self):
        response = self.client.get(reverse('accounts:register'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('content="noindex, nofollow"', content)

    def test_student_dashboard_has_noindex(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('content="noindex, nofollow"', content)

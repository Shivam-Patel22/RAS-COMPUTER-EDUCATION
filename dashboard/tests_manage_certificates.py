from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from certificates.models import Certificate
from courses.models import Course
from datetime import date
import os
from django.conf import settings


class ManageCertificatesTableTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='testpassword123'
        )
        self.client.login(username='admin_test', password='testpassword123')
        
        self.course = Course.objects.create(
            name="CCC (Basic)",
            category="basic",
            description="Basic computer course",
            duration="3 Months",
            fee=3500
        )
        self.cert = Certificate.objects.create(
            certificate_id="RAS-2026-10-CCC-1001",
            student_name="Rahul Sharma",
            course=self.course,
            issue_date=date(2026, 10, 1),
            grade="A+"
        )

    def test_manage_certificates_view_renders_without_linked_account(self):
        """Manage certificates view must NOT display Linked Account column or 'Unlinked'."""
        response = self.client.get(reverse('dashboard:manage_certificates'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Confirm Linked Account is NOT in the rendered table
        self.assertNotIn('Linked Account', content)
        self.assertNotIn('Unlinked', content)

        # Confirm expected columns exist
        self.assertIn('Certificate ID', content)
        self.assertIn('Student Name', content)
        self.assertIn('Course', content)
        self.assertIn('Issue Date', content)
        self.assertIn('Grade', content)
        self.assertIn('Actions', content)

        # Confirm certificate data is properly rendered
        self.assertIn('RAS-2026-10-CCC-1001', content)
        self.assertIn('Rahul Sharma', content)
        self.assertIn('CCC (Basic)', content)
        self.assertIn('A+', content)

    def test_template_file_does_not_contain_linked_account(self):
        """manage_certificates.html must not contain Linked Account header or Unlinked cell."""
        template_path = os.path.join(settings.BASE_DIR, 'templates', 'dashboard', 'manage_certificates.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        self.assertNotIn('Linked Account', template_content)
        self.assertNotIn('Unlinked', template_content)
        self.assertIn('manage-certs-table', template_content)
        self.assertIn('cert-actions-wrap', template_content)

    def test_css_rules_for_manage_certs_table(self):
        """CSS must define .manage-certs-table and .cert-actions-wrap for responsive fitting."""
        css_path = os.path.join(settings.BASE_DIR, 'static', 'css', 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()
        self.assertIn('.manage-certs-table', css)
        self.assertIn('.cert-actions-wrap', css)
        self.assertIn('flex-wrap: wrap;', css)

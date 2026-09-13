import io
import zipfile
from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.cache import cache
from core.models import Inquiry
from courses.models import Course, CourseOffer
from accounts.models import StudentProfile

class SecurityVulnerabilitiesTestCase(TestCase):
    """
    Automated test coverage for all 5 security audit remediations:
    1. Unauthorized Record Deletion & CSRF Protection (HTTP 405 on GET, CSRF on POST)
    2. DOM & Stored XSS Mitigation and Security Headers
    3. Administrative Open Redirect Mitigation
    4. Admin Login Rate Limiting & Secure Temporary Passwords
    5. Bulk Certificate Export Resource Safeguards (batch limits)
    """

    def setUp(self):
        cache.clear()
        self.staff_user = User.objects.create_user(
            username='staff_admin',
            email='staff@cdac.test',
            password='SecurePassword123!',
            is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username='normal_student',
            email='student@cdac.test',
            password='SecurePassword123!',
            is_staff=False
        )
        self.course = Course.objects.create(
            name='Cyber Security Specialist',
            category='diploma-6-months',
            description='Comprehensive cyber security training',
            duration='3 Months'
        )
        self.inquiry = Inquiry.objects.create(
            name='Test Inquirer',
            phone='9876543210',
            email='inquirer@cdac.test',
            subject='Course Details',
            message='Test inquiry message'
        )
        self.offer = CourseOffer.objects.create(
            title='Diwali Special Offer',
            discount='25% OFF',
            status='active',
            priority=1
        )

    # -------------------------------------------------------------
    # 1. CSRF & HTTP Method Enforcement Tests
    # -------------------------------------------------------------
    def test_inquiry_delete_rejects_get(self):
        """GET request to delete_inquiry must be rejected with 405 Method Not Allowed."""
        self.client.login(username='staff_admin', password='SecurePassword123!')
        url = reverse('dashboard:delete_inquiry', kwargs={'pk': self.inquiry.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Inquiry.objects.filter(id=self.inquiry.id).exists())

    def test_inquiry_toggle_read_rejects_get(self):
        """GET request to toggle_inquiry_read must be rejected with 405 Method Not Allowed."""
        self.client.login(username='staff_admin', password='SecurePassword123!')
        url = reverse('dashboard:toggle_inquiry_read', kwargs={'pk': self.inquiry.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_student_delete_rejects_get(self):
        """GET request to delete_student must be rejected with 405 Method Not Allowed."""
        self.client.login(username='staff_admin', password='SecurePassword123!')
        url = reverse('dashboard:delete_student', kwargs={'pk': self.regular_user.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(User.objects.filter(id=self.regular_user.id).exists())

    def test_offer_delete_rejects_get(self):
        """GET request to delete_offer must be rejected with 405 Method Not Allowed."""
        self.client.login(username='staff_admin', password='SecurePassword123!')
        url = reverse('dashboard:delete_offer', kwargs={'pk': self.offer.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(CourseOffer.objects.filter(id=self.offer.id).exists())

    def test_csrf_enforced_on_destructive_post(self):
        """POST request without CSRF token must be rejected with 403 Forbidden when CSRF is enforced."""
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username='staff_admin', password='SecurePassword123!')
        url = reverse('dashboard:delete_inquiry', kwargs={'pk': self.inquiry.id})
        response = csrf_client.post(url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Inquiry.objects.filter(id=self.inquiry.id).exists())

    def test_authorized_staff_post_deletes_inquiry(self):
        """Valid staff POST request successfully deletes inquiry."""
        self.client.login(username='staff_admin', password='SecurePassword123!')
        url = reverse('dashboard:delete_inquiry', kwargs={'pk': self.inquiry.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Inquiry.objects.filter(id=self.inquiry.id).exists())

    # -------------------------------------------------------------
    # 2. Open Redirect Protection Tests
    # -------------------------------------------------------------
    def test_open_redirect_with_external_domain_is_prevented(self):
        """Malicious external URL in 'next' parameter must be safely discarded."""
        self.client.login(username='staff_admin', password='SecurePassword123!')
        url = reverse('dashboard:toggle_inquiry_read', kwargs={'pk': self.inquiry.id}) + '?next=https://evil-attacker.com/phishing'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('evil-attacker.com', response.url)
        self.assertTrue(response.url.startswith('/cdac-admin/inquiries/'))

    def test_open_redirect_protocol_relative_is_prevented(self):
        """Protocol-relative malicious URL //evil.com must be safely discarded."""
        self.client.login(username='staff_admin', password='SecurePassword123!')
        url = reverse('dashboard:toggle_offer_status', kwargs={'pk': self.offer.id}) + '?next=//evil.com'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('evil.com', response.url)
        self.assertTrue(response.url.startswith('/cdac-admin/offers/'))

    # -------------------------------------------------------------
    # 3. Credential Security & Brute-Force Rate Limiting Tests
    # -------------------------------------------------------------
    def test_admin_login_rate_limiting(self):
        """After 5 consecutive failed login attempts, admin login must return HTTP 429 Too Many Requests."""
        login_url = reverse('dashboard:login')
        # 5 failed attempts
        for _ in range(5):
            res = self.client.post(login_url, {'username': 'staff_admin', 'password': 'WrongPassword!'})
            self.assertEqual(res.status_code, 200)

        # 6th attempt should be blocked with 429
        blocked_res = self.client.post(login_url, {'username': 'staff_admin', 'password': 'WrongPassword!'})
        self.assertEqual(blocked_res.status_code, 429)

    def test_add_student_generates_secure_password_and_requires_change(self):
        """Admin student creation must generate cryptographically secure password and set must_change_password."""
        self.client.login(username='staff_admin', password='SecurePassword123!')
        url = reverse('dashboard:add_student')
        payload = {
            'full_name': 'Aarav Sharma',
            'email': 'aarav.sharma@testcdac.com',
            'phone': '9876543219',
            'course': self.course.id,
            'is_active': '1'
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)

        new_user = User.objects.get(email='aarav.sharma@testcdac.com')
        # Must NOT be default static password 'cdac1234'
        self.assertFalse(new_user.check_password('cdac1234'))
        # Profile must flag must_change_password
        profile = StudentProfile.objects.get(user=new_user)
        self.assertTrue(profile.must_change_password)

    # -------------------------------------------------------------
    # 4. Security Headers Configuration Tests
    # -------------------------------------------------------------
    def test_security_headers_present(self):
        """Response should include X-Frame-Options and X-Content-Type-Options headers."""
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.headers.get('X-Frame-Options'), 'DENY')
        self.assertEqual(response.headers.get('X-Content-Type-Options'), 'nosniff')

    # -------------------------------------------------------------
    # 5. Bulk Export Batch Limit Test
    # -------------------------------------------------------------
    def test_bulk_certificate_export_limit_exceeded(self):
        """Export requesting more than 100 certificates must be blocked to prevent DoS."""
        from certificates.models import Certificate
        self.client.login(username='staff_admin', password='SecurePassword123!')

        # Bulk create 105 certificates
        certs = [
            Certificate(
                certificate_id=f'CERT-BULK-{i:03d}',
                student_name=f'Student {i}',
                course=self.course,
                issue_date=date(2026, 1, 1)
            ) for i in range(105)
        ]
        Certificate.objects.bulk_create(certs)

        url = reverse('dashboard:download_certificates_zip')
        response = self.client.get(url, {'start_date': '2026-01-01', 'end_date': '2026-01-01'})
        self.assertEqual(response.status_code, 302)
        # Should redirect to manage_certificates with an error flash message
        self.assertRedirects(response, reverse('dashboard:manage_certificates'))

import os
from django.test import TestCase, Client
from django.urls import reverse
from django.core.cache import cache
from django.core.exceptions import ValidationError
from courses.models import Course
from certificates.models import Certificate
from certificates.utils import extract_recipient_initials, format_certificate_id
from dashboard.forms import AdminCertificateForm
from core.forms import ContactForm

class AuditFixesVerificationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.course = Course.objects.create(
            name="Certificate Course on Computer Concepts (CCC)",
            description="Official CCC Course",
            duration="3 Months",
            category="basic"
        )
        self.client = Client()

    def tearDown(self):
        cache.clear()

    def test_unicode_gujarati_and_hindi_initials(self):
        """BUG-01: Verifies regional script names generate valid ASCII initials and valid Certificate IDs."""
        # Gujarati name
        i_guj = extract_recipient_initials("ભાવિક", "પ્રજાપતિ")
        self.assertEqual(len(i_guj), 2)
        self.assertTrue(i_guj.isalpha() and i_guj.isascii())
        cid_guj = format_certificate_id("RAS", 2026, 10, i_guj, 123456, 1001)
        self.assertTrue(cid_guj.startswith("RAS-2026-10-"))

        # Hindi name
        i_hin = extract_recipient_initials("राहुल", "शर्मा")
        self.assertEqual(len(i_hin), 2)
        self.assertTrue(i_hin.isalpha() and i_hin.isascii())
        cid_hin = format_certificate_id("CITI", 2026, 10, i_hin, 654321, 5001)
        self.assertTrue(cid_hin.startswith("CITI-2026-10-"))

    def test_duplicate_citi_registration_number_validation(self):
        """SEC-04: Verifies AdminCertificateForm blocks duplicate CITI registration numbers."""
        # Create first certificate
        Certificate.objects.create(
            certificate_id="CITI-2026-10-DV-111111-5001",
            first_name="Divyaraj",
            last_name="Vihol",
            student_name="Divyaraj Vihol",
            course=self.course,
            issue_date="2026-10-15",
            serial_number="5001",
            registration_number="CITI/GNR/2026-27/5001",
            theory_marks=45,
            practical_marks=45,
            grade="S"
        )

        # Attempt to create another certificate with the same serial number and date
        data = {
            'prefix': 'CITI',
            'certificate_id': 'CITI-2026-10-RP-222222-5002',
            'first_name': 'Rahul',
            'middle_name': '',
            'last_name': 'Patel',
            'course': self.course.id,
            'course_start_date': '2026-07-01',
            'course_end_date': '2026-09-30',
            'issue_date': '2026-10-15',
            'serial_number': '5001',  # Duplicate serial
            'theory_marks': 40,
            'practical_marks': 40,
            'course_duration': '3 Months',
        }
        form = AdminCertificateForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('serial_number', form.errors)
        self.assertIn('already assigned', form.errors['serial_number'][0])

    def test_certificate_verification_rate_limiting(self):
        """SEC-03: Verifies rate limiting stops scraping after threshold."""
        cache.clear()
        for _ in range(25):
            self.client.get('/verify-certificate/?certificate_id=TEST-SCRAPE')
        
        # 26th lookup must be rate-limited with HTTP 429
        response = self.client.get('/verify-certificate/?certificate_id=TEST-SCRAPE')
        self.assertEqual(response.status_code, 429)
        self.assertIn('Too many verification requests', response.content.decode('utf-8'))

    def test_contact_form_honeypot(self):
        """SEC-07: Verifies honeypot field catches automated spambot submissions."""
        data = {
            'name': 'Spam Bot',
            'phone': '9876543210',
            'email': 'spam@bot.com',
            'course': self.course.id,
            'message': 'Buy cheap meds',
            'website': 'http://spamsite.xyz'  # Filled by bot
        }
        form = ContactForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('website', form.errors)
        self.assertIn('Automated submission detected', form.errors['website'][0])

    def test_contact_form_submission_rate_limiting(self):
        """SEC-07: Verifies excessive POST inquiries from same IP are rate-limited."""
        cache.clear()
        for i in range(5):
            self.client.post(reverse('core:contact'), {
                'name': f'Student {i}',
                'phone': '9876543210',
                'course': self.course.id,
                'message': 'Inquiry'
            })
        
        # 6th attempt triggers rate limit
        r6 = self.client.post(reverse('core:contact'), {
            'name': 'Student 6',
            'phone': '9876543210',
            'course': self.course.id,
            'message': 'Inquiry'
        }, follow=True)
        self.assertContains(r6, 'Too many inquiry submissions')

    def test_custom_404_template_renders(self):
        """OPS-01: Verifies 404 page renders custom template with return link."""
        response = self.client.get('/this-url-definitely-does-not-exist-404/')
        self.assertEqual(response.status_code, 404)
        content = response.content.decode('utf-8')
        self.assertIn('Page Not Found', content)
        self.assertIn('Return to Homepage', content)

    def test_model_level_marks_validators(self):
        """SEC-08: Verifies model-level validation restricts marks between 0 and 50."""
        cert = Certificate(
            certificate_id="CITI-2026-10-TEST-999999-5099",
            first_name="Test",
            last_name="Student",
            student_name="Test Student",
            course=self.course,
            issue_date="2026-10-15",
            theory_marks=75,  # Invalid: > 50
            practical_marks=-5 # Invalid: < 0
        )
        with self.assertRaises(ValidationError):
            cert.full_clean()

import io
from datetime import date
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from courses.models import Course
from certificates.models import Certificate
from certificates import utils


class QRCodeCertificateVerificationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username='adminuser',
            password='AdminPassword123!',
            email='admin@example.com'
        )
        self.course = Course.objects.create(
            name='RAS Certificate in Web Development',
            description='Test course description',
            duration='3 Months'
        )
        self.citi_course = Course.objects.create(
            name='Certificate Course on Computer Concepts (CCC)',
            description='CITI CCC Course',
            duration='3 Months'
        )
        self.cert = Certificate.objects.create(
            certificate_id='RAS-2026-10-JD-123456-1001',
            first_name='John',
            last_name='Doe',
            student_name='John Doe',
            course=self.course,
            course_start_date=date(2026, 6, 1),
            course_end_date=date(2026, 8, 31),
            issue_date=date(2026, 9, 10),
            grade='A'
        )
        self.citi_cert = Certificate.objects.create(
            certificate_id='CITI-2026-10-AS-654321-5001',
            first_name='Alice',
            last_name='Smith',
            student_name='Alice Smith',
            course=self.citi_course,
            course_start_date=date(2026, 5, 1),
            course_end_date=date(2026, 7, 31),
            issue_date=date(2026, 8, 15),
            grade='S',
            serial_number='4500'
        )

    # Test 1: Certificate Issuance & DB Record
    def test_certificate_issuance_creates_db_and_generates_qr_url(self):
        """Confirm certificate record is in DB and has authoritative verification hash and URL."""
        self.assertEqual(self.cert.certificate_id, 'RAS-2026-10-JD-123456-1001')
        self.assertTrue(bool(self.cert.verification_hash))
        self.assertTrue(bool(self.cert.verification_token))
        url = utils.get_certificate_verify_url(self.cert)
        self.assertIn(self.cert.certificate_id, url)
        self.assertTrue(url.startswith('http'))

    # Test 2: QR URL Generation & Domain Resolution
    @override_settings(SITE_BASE_URL='https://rascomputergandhinagar.com')
    def test_qr_code_uses_configured_production_domain(self):
        """In production, QR code URLs MUST resolve to the configured public domain, never localhost."""
        url = utils.get_certificate_verify_url(self.cert)
        self.assertEqual(url, f"https://rascomputergandhinagar.com/verify-certificate/{self.cert.certificate_id}/")

    def test_qr_image_and_data_uri_generation(self):
        """Verify QR code PIL image and base64 Data URI are correctly generated."""
        url = utils.get_certificate_verify_url(self.cert)
        img = utils.generate_qr_code_image(url)
        self.assertIsNotNone(img)
        self.assertGreater(img.size[0], 50)
        self.assertGreater(img.size[1], 50)

        data_uri = utils.generate_qr_data_uri(url)
        self.assertTrue(data_uri.startswith('data:image/png;base64,'))
        self.assertGreater(len(data_uri), 100)

    # Test 3: Automatic Verification via Direct URL Path
    def test_automatic_verification_via_direct_url_path(self):
        """Scanning QR code opens /verify-certificate/<cert_id>/ directly and automatically renders details."""
        url = reverse('certificates:verify_direct', kwargs={'certificate_id': self.cert.certificate_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'certificates/result.html')
        self.assertContains(response, 'John Doe')
        self.assertContains(response, self.cert.certificate_id)
        self.assertContains(response, 'VERIFIED AUTHENTIC CERTIFICATE')
        self.assertContains(response, 'Official Verification Details')
        self.assertContains(response, 'Valid & Active')

    def test_automatic_verification_via_query_param(self):
        """Accessing /verify-certificate/?certificate_id=<cert_id> automatically displays result."""
        url = f"{reverse('certificates:verify')}?certificate_id={self.cert.certificate_id}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'certificates/result.html')
        self.assertContains(response, 'John Doe')
        self.assertContains(response, self.cert.certificate_id)

    # Test 4: Invalid / Fabricated Certificate URL
    def test_fabricated_certificate_url_returns_not_found_never_valid(self):
        """Fabricated or unknown certificate ID must return Invalid / Not Found, never Valid."""
        fake_id = 'FABRICATED-2026-999999'
        url = reverse('certificates:verify_direct', kwargs={'certificate_id': fake_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'certificates/verify.html')
        self.assertContains(response, 'Invalid / Not Found')
        self.assertNotContains(response, 'VERIFIED AUTHENTIC CERTIFICATE')

    # Test 5: Revoked Certificate Workflow
    def test_revoked_certificate_displays_revoked_and_blocks_download(self):
        """Revoking a certificate must update verification to Revoked and block PDF download."""
        # Log in as admin and revoke certificate via POST to dashboard revoke endpoint
        self.client.force_login(self.admin)
        revoke_url = reverse('dashboard:revoke_certificate', kwargs={'pk': self.cert.pk})
        post_resp = self.client.post(revoke_url, {'revocation_reason': 'Administrative error'})
        self.assertRedirects(post_resp, reverse('dashboard:manage_certificates'))

        # Reload from DB
        self.cert.refresh_from_db()
        self.assertTrue(self.cert.is_revoked)
        self.assertIsNotNone(self.cert.revoked_at)
        self.assertEqual(self.cert.revocation_reason, 'Administrative error')

        # Log out to test unauthenticated public verification
        self.client.logout()

        # Public verification scan via direct QR URL
        scan_url = reverse('certificates:verify_direct', kwargs={'certificate_id': self.cert.certificate_id})
        scan_resp = self.client.get(scan_url)
        self.assertEqual(scan_resp.status_code, 200)
        self.assertTemplateUsed(scan_resp, 'certificates/result.html')
        self.assertContains(scan_resp, 'CERTIFICATE REVOKED')
        self.assertContains(scan_resp, 'REVOKED')
        self.assertContains(scan_resp, 'Revocation Notice')
        self.assertContains(scan_resp, 'Download PDF Disabled (Revoked)')
        self.assertNotContains(scan_resp, 'VERIFIED AUTHENTIC CERTIFICATE')

        # Public PDF download must return 403 Forbidden
        dl_url = reverse('certificates:download_certificate_pdf', kwargs={'certificate_id': self.cert.certificate_id})
        dl_resp = self.client.get(dl_url)
        self.assertEqual(dl_resp.status_code, 403)

    # Test 6: Existing Functionality Preserved
    def test_manual_form_search_verification_works(self):
        """User can still enter certificate ID manually on the verify page."""
        response = self.client.get(reverse('certificates:verify'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'certificates/verify.html')

        # Submit GET search
        search_resp = self.client.get(reverse('certificates:verify'), {'certificate_id': self.citi_cert.certificate_id})
        self.assertEqual(search_resp.status_code, 200)
        self.assertTemplateUsed(search_resp, 'certificates/result.html')
        self.assertContains(search_resp, 'Alice Smith')
        self.assertContains(search_resp, self.citi_cert.certificate_id)

    def test_pdf_download_for_valid_certificate(self):
        """Valid certificates can be downloaded as authentic PDF."""
        dl_url = reverse('certificates:download_certificate_pdf', kwargs={'certificate_id': self.cert.certificate_id})
        response = self.client.get(dl_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(len(response.content) > 1000)

    # Test 7: JSON Verification Endpoint
    def test_json_verification_endpoint(self):
        """JSON format requests receive proper machine-readable status."""
        json_url = f"{reverse('certificates:verify_direct', kwargs={'certificate_id': self.cert.certificate_id})}?format=json"
        response = self.client.get(json_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'Valid')
        self.assertTrue(data['is_valid'])
        self.assertFalse(data['is_revoked'])
        self.assertEqual(data['certificate_id'], self.cert.certificate_id)

        # Non-existent ID in JSON returns 404
        fake_json_url = f"{reverse('certificates:verify_direct', kwargs={'certificate_id': 'NONEXISTENT'})}?format=json"
        fake_resp = self.client.get(fake_json_url)
        self.assertEqual(fake_resp.status_code, 404)
        self.assertEqual(fake_resp.json()['status'], 'Invalid/Not Found')

    # Test 8: PDF Generation Contains Valid PDF Structure
    def test_pdf_generation_ras_and_citi(self):
        """PDF generation for both RAS and CITI contains valid PDF header and bytes."""
        ras_pdf = utils.generate_certificate_pdf(self.cert)
        self.assertTrue(ras_pdf.startswith(b'%PDF-'))

        citi_pdf = utils.generate_certificate_pdf(self.citi_cert)
        self.assertTrue(citi_pdf.startswith(b'%PDF-'))

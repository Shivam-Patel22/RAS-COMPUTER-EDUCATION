from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from certificates.models import Certificate
from courses.models import Course


class RevokedCertificateNavigationTestCase(TestCase):
    """
    Test suite verifying that:
    1. Verifying an admin-revoked certificate stays in the existing verification flow and does NOT redirect to /about/.
    2. The custom revoked popup modal ('Certificate Revoked') is displayed with the required text.
    3. The user panel (navbar: Dashboard, About, Courses, Contact, verify field, theme toggle) is preserved.
    4. Valid certificates show successful verification.
    5. Invalid certificates retain standard error handling.
    6. QR code verification identifies revoked certificates and never marks them valid.
    7. Admin panel verify search handles revoked certificates securely without showing them as valid.
    """

    def setUp(self):
        # Create course
        self.course = Course.objects.create(
            name="Python Web Development",
            duration="3 Months",
            fee=5000.00
        )
        # Create staff admin user
        self.staff_admin = User.objects.create_user(
            username="test_admin",
            email="admin@rascomputer.com",
            password="AdminPassword123!",
            is_staff=True,
            is_superuser=True
        )
        # Create regular student user
        self.student = User.objects.create_user(
            username="test_student",
            email="student@rascomputer.com",
            password="StudentPassword123!"
        )
        # Create a valid certificate
        self.valid_cert = Certificate.objects.create(
            certificate_id="RAS-2026-10-JD-100000-100001",
            student_name="John Doe",
            course=self.course,
            issue_date=timezone.now().date(),
            grade="A",
            is_revoked=False
        )
        # Create a revoked certificate
        self.revoked_cert = Certificate.objects.create(
            certificate_id="RAS-2026-10-JD-100000-100002",
            student_name="Jane Doe",
            course=self.course,
            issue_date=timezone.now().date(),
            grade="A+",
            is_revoked=True,
            revoked_at=timezone.now(),
            revocation_reason="Administrative Revocation"
        )

    # -------------------------------------------------------------------------
    # Case 1: Verify a valid certificate
    # -------------------------------------------------------------------------
    def test_verify_valid_certificate(self):
        """Valid certificates must show successful verification result without error or revoked popup."""
        self.client.login(username="test_admin", password="AdminPassword123!")
        url = f"{reverse('certificates:verify')}?certificate_id={self.valid_cert.certificate_id}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'certificates/result.html')
        self.assertContains(response, 'VERIFIED AUTHENTIC CERTIFICATE')
        self.assertContains(response, self.valid_cert.student_name)
        self.assertNotContains(response, 'revokedCertificateModal')
        self.assertNotContains(response, 'CERTIFICATE REVOKED')

    # -------------------------------------------------------------------------
    # Case 2: Verify an admin-revoked certificate in user panel
    # -------------------------------------------------------------------------
    def test_verify_revoked_certificate_no_redirect_to_about(self):
        """Verifying a revoked certificate must remain on verification page and NOT redirect to /about/."""
        self.client.login(username="test_admin", password="AdminPassword123!")
        url = f"{reverse('certificates:verify')}?certificate_id={self.revoked_cert.certificate_id}"
        response = self.client.get(url)

        # Must not redirect to /about/ or any other page
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'certificates/result.html')

        # Must display the custom revoked certificate popup modal
        self.assertContains(response, 'id="revokedCertificateModal"')
        self.assertContains(response, 'Certificate Revoked')
        self.assertContains(response, 'This certificate has been revoked by the administrator and is no longer valid.')

        # Must show revocation notice box and status badge
        self.assertContains(response, 'CERTIFICATE REVOKED')
        self.assertContains(response, 'revocation-notice-box')
        self.assertNotContains(response, 'VERIFIED AUTHENTIC CERTIFICATE')

        # Must preserve the normal user panel navbar for authenticated staff
        self.assertContains(response, 'Dashboard')
        self.assertContains(response, 'About')
        self.assertContains(response, 'Courses')
        self.assertContains(response, 'Contact')
        self.assertContains(response, 'header-verify-form')
        self.assertContains(response, 'toggleTheme()')

    # -------------------------------------------------------------------------
    # Case 3: Close the popup - verify layout and elements stay accessible
    # -------------------------------------------------------------------------
    def test_close_popup_and_layout_elements(self):
        """Closing the popup must keep user on verification page with layout preserved."""
        self.client.login(username="test_admin", password="AdminPassword123!")
        url = f"{reverse('certificates:verify')}?certificate_id={self.revoked_cert.certificate_id}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Verify close function exists
        self.assertIn('function closeRevokedModal()', content)
        self.assertIn("modal.style.display = 'none'", content)
        self.assertIn('onclick="closeRevokedModal()"', content)

        # Verify header form points to certificates:verify
        self.assertIn('action="/verify-certificate/"', content)

    # -------------------------------------------------------------------------
    # Case 4: Verify an invalid certificate
    # -------------------------------------------------------------------------
    def test_verify_invalid_certificate(self):
        """Invalid certificate IDs must display standard error handling on verify page."""
        self.client.login(username="test_admin", password="AdminPassword123!")
        invalid_id = "INVALID-2026-FAKE-000000"
        url = f"{reverse('certificates:verify')}?certificate_id={invalid_id}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'certificates/verify.html')
        self.assertContains(response, f"No valid certificate found matching Certificate ID / Registration No &#x27;{invalid_id}&#x27;.")
        self.assertNotContains(response, 'revokedCertificateModal')

    # -------------------------------------------------------------------------
    # Case 5: Verify a revoked certificate through QR code
    # -------------------------------------------------------------------------
    def test_qr_code_verification_of_revoked_certificate(self):
        """Scanning a revoked certificate QR code must display revoked status and not mark valid."""
        # Direct URL as encoded in QR code: /verify-certificate/<certificate_id>/
        qr_url = reverse('certificates:verify_direct', kwargs={'certificate_id': self.revoked_cert.certificate_id})
        response = self.client.get(qr_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'certificates/result.html')
        self.assertContains(response, 'Certificate Revoked')
        self.assertContains(response, 'CERTIFICATE REVOKED')
        self.assertNotContains(response, 'VERIFIED AUTHENTIC CERTIFICATE')

        # JSON endpoint check (e.g. scanner apps / API lookups)
        json_resp = self.client.get(f"{qr_url}?format=json")
        self.assertEqual(json_resp.status_code, 200)
        data = json_resp.json()
        self.assertEqual(data['status'], 'Revoked')
        self.assertFalse(data['is_valid'])
        self.assertTrue(data['is_revoked'])
        self.assertEqual(
            data['revocation_message'],
            "This certificate has been revoked by the administrator and is no longer valid."
        )

    # -------------------------------------------------------------------------
    # Case 6: Admin Panel verify search handles revocation properly
    # -------------------------------------------------------------------------
    def test_admin_verify_search_revocation_handling(self):
        """Looking up a revoked certificate inside admin panel must not show it as valid."""
        self.client.login(username="test_admin", password="AdminPassword123!")
        admin_search_url = reverse('dashboard:admin_verify_search')

        response = self.client.post(admin_search_url, {'certificate_id': self.revoked_cert.certificate_id})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/admin_verify_certificate.html')
        self.assertContains(response, 'CERTIFICATE REVOKED')
        self.assertContains(response, 'Certificate Revoked')
        self.assertContains(response, 'Printing Disabled (Revoked)')
        self.assertNotContains(response, 'VERIFIED AUTHENTIC CERTIFICATE RECORD')

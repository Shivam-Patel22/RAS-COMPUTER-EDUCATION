from datetime import date
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from courses.models import Course
from certificates.models import Certificate

class CertificatesTestCase(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            name='Python Web Development',
            description='Learn Django & Python',
            duration='12 Weeks',
            fee=499.00
        )
        self.student_user = User.objects.create_user(
            username='student@test.com',
            email='student@test.com',
            password='Password123!'
        )
        self.valid_cert = Certificate.objects.create(
            certificate_id='CERT-2026-TEST01',
            student_name='Jane Student',
            student=self.student_user,
            course=self.course,
            issue_date=date(2026, 1, 15),
            grade='A+'
        )
        self.admin = User.objects.create_superuser(
            username='certadmin',
            email='certadmin@cdac.in',
            password='adminpassword123'
        )

    def test_valid_certificate_id_returns_match(self):
        url = reverse('certificates:verify')
        response = self.client.post(url, {'certificate_id': 'CERT-2026-TEST01'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'certificates/result.html')
        self.assertContains(response, 'Jane Student')
        self.assertContains(response, 'Python Web Development')

    def test_invalid_certificate_id_shows_error(self):
        url = reverse('certificates:verify')
        response = self.client.post(url, {'certificate_id': 'CERT-9999-INVALID'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'certificates/verify.html')
        self.assertContains(response, "No valid certificate found")

    def test_custom_certificate_id_issue(self):
        self.client.login(username='certadmin', password='adminpassword123')

        add_url = reverse('dashboard:add_certificate')
        data = {
            'certificate_id': 'CERT-2026-HARSHAL01',
            'first_name': 'Harshal',
            'middle_name': 'Narendrasinh',
            'last_name': 'Chauhan',
            'course': self.course.id,
            'course_start_date': '2026-01-10',
            'course_end_date': '2026-07-10',
            'issue_date': '2026-08-02',
            'grade': 'A+',
        }
        response = self.client.post(add_url, data)
        self.assertRedirects(response, reverse('dashboard:manage_certificates'))
        cert = Certificate.objects.get(certificate_id='CERT-2026-HARSHAL01')
        self.assertEqual(cert.student_name, 'Harshal Narendrasinh Chauhan')
        self.assertEqual(str(cert.course_start_date), '2026-01-10')
        self.assertEqual(str(cert.course_end_date), '2026-07-10')

    def test_middle_name_compulsory_validation(self):
        from dashboard.forms import AdminCertificateForm
        form = AdminCertificateForm(data={
            'certificate_id': 'CERT-2026-TEST02',
            'first_name': 'Harshal',
            'middle_name': '',  # Empty compulsory middle name
            'last_name': 'Chauhan',
            'course': self.course.id,
            'course_start_date': '2026-01-10',
            'course_end_date': '2026-07-10',
            'issue_date': '2026-08-02',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('middle_name', form.errors)

    def test_course_dates_validation(self):
        from dashboard.forms import AdminCertificateForm
        # End date earlier than start date
        form = AdminCertificateForm(data={
            'certificate_id': 'CERT-2026-TEST03',
            'first_name': 'Harshal',
            'middle_name': 'Narendrasinh',
            'last_name': 'Chauhan',
            'course': self.course.id,
            'course_start_date': '2026-07-10',
            'course_end_date': '2026-01-10', # Invalid: earlier than start date
            'issue_date': '2026-08-02',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('course_end_date', form.errors)
        self.assertIn('Course End Date cannot be earlier than Course Start Date.', form.errors['course_end_date'])

    def test_auto_generate_certificate_id_format(self):
        from certificates.utils import generate_certificate_id
        cert_id = generate_certificate_id('Harshal', 'Chauhan')
        # Format: CERT-2026-HC-XXXX-XX
        parts = cert_id.split('-')
        self.assertEqual(len(parts), 5)
        self.assertEqual(parts[0], 'CERT')
        self.assertEqual(parts[2], 'HC')
        self.assertEqual(len(parts[3]), 4)
        self.assertEqual(len(parts[4]), 2)

    def test_admin_verify_certificate_endpoint(self):
        self.client.login(username='certadmin', password='adminpassword123')
        verify_url = reverse('dashboard:verify_certificate', kwargs={'pk': self.valid_cert.pk})
        
        response = self.client.get(verify_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertTrue(json_data['success'])
        self.assertEqual(json_data['certificate_id'], 'CERT-2026-TEST01')
        self.assertEqual(json_data['student_name'], 'Jane Student')
        self.assertIn('✓ Certificate Verified Successfully', json_data['message'])

        # Verify timestamp was recorded
        self.valid_cert.refresh_from_db()
        self.assertIsNotNone(self.valid_cert.last_verified_at)

    def test_admin_print_certificate_endpoint(self):
        self.client.login(username='certadmin', password='adminpassword123')
        print_url = reverse('dashboard:print_certificate', kwargs={'pk': self.valid_cert.pk})

        response = self.client.get(print_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/print_certificate.html')
        self.assertContains(response, 'Jane Student')
        self.assertContains(response, 'CERT-2026-TEST01')
        self.assertContains(response, 'Python Web Development')

        # Verify printed_at was recorded
        self.valid_cert.refresh_from_db()
        self.assertIsNotNone(self.valid_cert.printed_at)

    def test_admin_verify_search_page(self):
        self.client.login(username='certadmin', password='adminpassword123')
        admin_verify_url = reverse('dashboard:admin_verify_search')

        # GET request to load input form
        response = self.client.get(admin_verify_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/admin_verify_certificate.html')

        # POST lookup for valid Certificate ID
        response = self.client.post(admin_verify_url, {'certificate_id': 'CERT-2026-TEST01'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Jane Student')
        self.assertContains(response, 'VERIFIED AUTHENTIC CERTIFICATE RECORD')

    def test_issue_date_year_validation(self):
        from dashboard.forms import AdminCertificateForm
        # Valid 4-digit years (1999, 2007, 2025, 2026, 2038, 2099)
        for valid_date in ['1999-05-12', '2007-11-20', '2025-01-01', '2026-08-04', '2038-12-31', '2099-09-09']:
            form = AdminCertificateForm(data={
                'certificate_id': f'CERT-{valid_date[:4]}-TEST',
                'first_name': 'Test',
                'middle_name': 'User',
                'last_name': 'Student',
                'course': self.course.id,
                'course_start_date': '2025-01-01',
                'course_end_date': '2025-06-01',
                'issue_date': valid_date,
            })
            self.assertTrue(form.is_valid(), f"Expected year in {valid_date} to be valid, errors: {form.errors}")

        # Invalid years (year < 1000 or year > 9999)
        form_invalid = AdminCertificateForm(data={
            'certificate_id': 'CERT-999-TEST',
            'first_name': 'Test',
            'middle_name': 'User',
            'last_name': 'Student',
            'course': self.course.id,
            'course_start_date': '2025-01-01',
            'course_end_date': '2025-06-01',
            'issue_date': '0999-01-01',
        })
        self.assertFalse(form_invalid.is_valid())
        self.assertIn('issue_date', form_invalid.errors)

    def test_certificate_date_filter_admin(self):
        """Test filtering certificates by date range on Manage Certificates page."""
        self.client.login(username='certadmin', password='adminpassword123')

        # Create certificates on different dates
        cert_aug8 = Certificate.objects.create(
            certificate_id='CERT-2026-AUG08',
            student_name='Shivam Patel',
            course=self.course,
            issue_date=date(2026, 8, 8),
            grade='A+'
        )
        cert_aug9 = Certificate.objects.create(
            certificate_id='CERT-2026-AUG09',
            student_name='Rohan Sharma',
            course=self.course,
            issue_date=date(2026, 8, 9),
            grade='A'
        )
        cert_aug15 = Certificate.objects.create(
            certificate_id='CERT-2026-AUG15',
            student_name='Priya Singh',
            course=self.course,
            issue_date=date(2026, 8, 15),
            grade='B+'
        )

        url = reverse('dashboard:manage_certificates')
        # Filter for 2026-08-08 to 2026-08-09
        response = self.client.get(url, {'start_date': '2026-08-08', 'end_date': '2026-08-09'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Shivam Patel')
        self.assertContains(response, 'Rohan Sharma')
        self.assertNotContains(response, 'Priya Singh')

    def test_download_certificates_zip_success(self):
        """Test downloading ZIP file containing filtered certificates."""
        import zipfile
        import io

        self.client.login(username='certadmin', password='adminpassword123')

        cert1 = Certificate.objects.create(
            certificate_id='CERT-ZIP-01',
            student_name='Shivam Patel',
            course=self.course,
            issue_date=date(2026, 8, 8)
        )
        cert2 = Certificate.objects.create(
            certificate_id='CERT-ZIP-02',
            student_name='Aarav Mehta',
            course=self.course,
            issue_date=date(2026, 8, 9)
        )

        url = reverse('dashboard:download_certificates_zip')
        response = self.client.get(url, {'start_date': '2026-08-08', 'end_date': '2026-08-09'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertIn('certificates_08-08-2026_to_09-08-2026.zip', response['Content-Disposition'])

        zip_data = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_data, 'r') as zf:
            namelist = zf.namelist()
            self.assertEqual(len(namelist), 2)
            self.assertIn('Shivampatel-Python-Web-Development.pdf', namelist)
            self.assertIn('Aaravmehta-Python-Web-Development.pdf', namelist)

    def test_download_certificates_zip_duplicate_filenames(self):
        """Test safe duplicate filename handling in ZIP archive."""
        import zipfile
        import io

        self.client.login(username='certadmin', password='adminpassword123')

        # Two certificates with exact same student name and course
        cert1 = Certificate.objects.create(
            certificate_id='CERT-DUP-01',
            student_name='Shivam Patel',
            course=self.course,
            issue_date=date(2026, 8, 8)
        )
        cert2 = Certificate.objects.create(
            certificate_id='CERT-DUP-02',
            student_name='Shivam Patel',
            course=self.course,
            issue_date=date(2026, 8, 8)
        )

        url = reverse('dashboard:download_certificates_zip')
        response = self.client.get(url, {'start_date': '2026-08-08', 'end_date': '2026-08-08'})
        self.assertEqual(response.status_code, 200)

        zip_data = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_data, 'r') as zf:
            namelist = zf.namelist()
            self.assertEqual(len(namelist), 2)
            self.assertIn('Shivampatel-Python-Web-Development.pdf', namelist)
            self.assertIn('Shivampatel-Python-Web-Development-2.pdf', namelist)

    def test_download_certificates_zip_invalid_date_range(self):
        """Test start date > end date validation."""
        self.client.login(username='certadmin', password='adminpassword123')
        url = reverse('dashboard:manage_certificates')
        response = self.client.get(url, {'start_date': '2026-08-10', 'end_date': '2026-08-08'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Starting date cannot be later than ending date.')

    def test_download_certificates_zip_unauthorized_access(self):
        """Test that non-staff or unauthenticated users cannot access zip download."""
        url = reverse('dashboard:download_certificates_zip')
        response = self.client.get(url, {'start_date': '2026-08-08', 'end_date': '2026-08-09'})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('dashboard:login'), response.url)

    def test_download_certificates_zip_all_without_dates(self):
        """Test downloading ALL certificates when no date filter parameters are provided."""
        import zipfile
        import io

        self.client.login(username='certadmin', password='adminpassword123')
        url = reverse('dashboard:download_certificates_zip')

        response = self.client.get(url)  # No start_date or end_date GET parameters
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertIn('certificates_all.zip', response['Content-Disposition'])

    def test_ccc_certificate_property_and_detection(self):
        """Test is_ccc property and is_ccc_certificate helper function."""
        from certificates.utils import is_ccc_certificate

        ccc_course = Course.objects.create(
            name='CCC',
            description='Course on Computer Concepts',
            duration='3 Months',
            fee=2500.00
        )
        ccc_cert = Certificate.objects.create(
            certificate_id='CERT-2026-CCC01',
            student_name='Shivam Patel',
            course=ccc_course,
            issue_date=date(2026, 8, 24),
            grade='A'
        )

        self.assertTrue(ccc_cert.is_ccc)
        self.assertTrue(is_ccc_certificate(ccc_cert))

        # Standard non-CCC certificate should return False
        self.assertFalse(self.valid_cert.is_ccc)
        self.assertFalse(is_ccc_certificate(self.valid_cert))

    def test_ccc_certificate_pdf_generation(self):
        """Test PDF byte generation for both CCC and non-CCC certificates."""
        from certificates.utils import generate_certificate_pdf

        ccc_course = Course.objects.create(
            name='CCC',
            description='Course on Computer Concepts',
            duration='3 Months',
            fee=2500.00
        )
        ccc_cert = Certificate.objects.create(
            certificate_id='CERT-2026-CCC02',
            student_name='Shivam Patel',
            course=ccc_course,
            course_start_date=date(2026, 5, 1),
            course_end_date=date(2026, 7, 31),
            issue_date=date(2026, 8, 24),
            grade='S'
        )

        # CCC PDF generation
        ccc_pdf = generate_certificate_pdf(ccc_cert)
        self.assertIsInstance(ccc_pdf, bytes)
        self.assertTrue(ccc_pdf.startswith(b'%PDF'))
        self.assertGreater(len(ccc_pdf), 1000)

        # Non-CCC PDF generation
        std_pdf = generate_certificate_pdf(self.valid_cert)
        self.assertIsInstance(std_pdf, bytes)
        self.assertTrue(std_pdf.startswith(b'%PDF'))
        self.assertGreater(len(std_pdf), 1000)

    def test_ccc_print_certificate_view(self):
        """Test print view renders CCC template for CCC and standard for other courses."""
        self.client.login(username='certadmin', password='adminpassword123')

        ccc_course = Course.objects.create(
            name='CCC',
            description='Course on Computer Concepts',
            duration='3 Months',
            fee=2500.00
        )
        ccc_cert = Certificate.objects.create(
            certificate_id='CERT-2026-CCC03',
            student_name='Aarav Shah',
            course=ccc_course,
            issue_date=date(2026, 8, 24),
            grade='A'
        )

        # Print CCC certificate
        response_ccc = self.client.get(reverse('dashboard:print_certificate', kwargs={'pk': ccc_cert.pk}))
        self.assertEqual(response_ccc.status_code, 200)
        self.assertContains(response_ccc, 'CCCCerty')
        self.assertContains(response_ccc, 'ccc-certificate-card')
        self.assertContains(response_ccc, 'Course on Computer Concepts (CCC)')

        # Print standard certificate
        response_std = self.client.get(reverse('dashboard:print_certificate', kwargs={'pk': self.valid_cert.pk}))
        self.assertEqual(response_std.status_code, 200)
        self.assertContains(response_std, 'certificate-card-printable')
        self.assertNotContains(response_std, 'CCCCerty')


    def test_ccc_public_verification_view(self):
        """Test public verify result page shows CCC branding for CCC certificate."""
        ccc_course = Course.objects.create(
            name='CCC',
            description='Course on Computer Concepts',
            duration='3 Months',
            fee=2500.00
        )
        ccc_cert = Certificate.objects.create(
            certificate_id='CERT-2026-CCC04',
            student_name='Aarav Shah',
            course=ccc_course,
            issue_date=date(2026, 8, 24),
            grade='A'
        )

        url = reverse('certificates:verify')
        response = self.client.post(url, {'certificate_id': 'CERT-2026-CCC04'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'COMPUTER &amp; INDUSTRIAL TRAINING INSTITUTION')
        self.assertContains(response, 'OFFICIAL GOVERNMENT RECOGNIZED PROGRAM (CCC)')
        self.assertContains(response, 'Aarav Shah')







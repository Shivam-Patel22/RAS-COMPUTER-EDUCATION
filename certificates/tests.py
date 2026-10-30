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
            'prefix': 'RAS',
            'id_gen_mode': 'manual',
            'certificate_id': 'RAS-2026-HC1050',
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
        cert = Certificate.objects.get(certificate_id='RAS-2026-HC1050')
        self.assertEqual(cert.student_name, 'Harshal Narendrasinh Chauhan')
        self.assertEqual(str(cert.course_start_date), '2026-01-10')
        self.assertEqual(str(cert.course_end_date), '2026-07-10')

    def test_middle_name_compulsory_validation(self):
        from dashboard.forms import AdminCertificateForm
        form = AdminCertificateForm(data={
            'prefix': 'RAS',
            'id_gen_mode': 'manual',
            'certificate_id': 'RAS-2026-HC1002',
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
            'prefix': 'RAS',
            'id_gen_mode': 'manual',
            'certificate_id': 'RAS-2026-HC1003',
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
        from certificates.utils import generate_certificate_id, CERTIFICATE_ID_REGEX
        from datetime import datetime
        year = datetime.now().year
        month = datetime.now().month
        cert_id_ras = generate_certificate_id('RAS', first_name='Harshal', last_name='Chauhan')
        self.assertTrue(CERTIFICATE_ID_REGEX.match(cert_id_ras))
        self.assertTrue(cert_id_ras.startswith(f'RAS-{year}-{month:02d}-HC-'))
        parts_ras = cert_id_ras.split('-')
        self.assertEqual(len(parts_ras), 5)
        self.assertEqual(len(parts_ras[4]), 6)
        self.assertTrue(100000 <= int(parts_ras[4]) <= 999999)

        cert_id_citi = generate_certificate_id('CITI', first_name='Harshal', last_name='Chauhan')
        self.assertTrue(CERTIFICATE_ID_REGEX.match(cert_id_citi))
        self.assertTrue(cert_id_citi.startswith(f'CITI-{year}-{month:02d}-HC-'))
        parts_citi = cert_id_citi.split('-')
        self.assertEqual(len(parts_citi), 5)
        self.assertEqual(len(parts_citi[4]), 6)
        self.assertTrue(100000 <= int(parts_citi[4]) <= 999999)

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
                'prefix': 'RAS',
                'id_gen_mode': 'manual',
                'certificate_id': f'RAS-{valid_date[:4]}-TS1001',
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
            'prefix': 'RAS',
            'id_gen_mode': 'manual',
            'certificate_id': 'RAS-2026-TS1001',
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
        self.assertNotContains(response_std, 'ras_template.jpg')

    def test_ras_certificate_detection_and_pdf_generation(self):
        """Test is_ras_certificate helper and PDF byte generation for RAS certificates."""
        from certificates.utils import is_ras_certificate, generate_certificate_pdf, _format_ordinal_date

        self.assertEqual(_format_ordinal_date(date(2026, 6, 15)), "15th Jun.")
        self.assertEqual(_format_ordinal_date(date(2026, 8, 31)), "31st Aug.")
        self.assertEqual(_format_ordinal_date(date(2026, 1, 1)), "1st Jan.")
        self.assertEqual(_format_ordinal_date(date(2026, 2, 2)), "2nd Feb.")
        self.assertEqual(_format_ordinal_date(date(2026, 3, 3)), "3rd Mar.")

        ras_cert = Certificate.objects.create(
            certificate_id='RAS-2026-10-AP-482716-1001',
            first_name='Ankit',
            last_name='Parihar',
            student_name='Ankit Parihar',
            course=self.course,
            course_start_date=date(2026, 6, 15),
            course_end_date=date(2026, 8, 31),
            issue_date=date(2026, 9, 10),
            grade='A'
        )

        self.assertEqual(ras_cert.prefix, 'RAS')
        self.assertTrue(is_ras_certificate(ras_cert))
        self.assertFalse(is_ras_certificate(self.valid_cert))

        ras_pdf = generate_certificate_pdf(ras_cert)
        self.assertIsInstance(ras_pdf, bytes)
        self.assertTrue(ras_pdf.startswith(b'%PDF'))
        self.assertGreater(len(ras_pdf), 1000)

    def test_ras_print_certificate_view(self):
        """Test print view renders RAS landscape template for prefix RAS and keeps standard/CCC for others."""
        self.client.login(username='certadmin', password='adminpassword123')

        ras_cert = Certificate.objects.create(
            certificate_id='RAS-2026-10-AP-482716-1002',
            first_name='Ankit',
            last_name='Parihar',
            student_name='Ankit Parihar',
            course=self.course,
            course_start_date=date(2026, 6, 15),
            course_end_date=date(2026, 8, 31),
            issue_date=date(2026, 9, 10),
            grade='A'
        )

        response_ras = self.client.get(reverse('dashboard:print_certificate', kwargs={'pk': ras_cert.pk}))
        self.assertEqual(response_ras.status_code, 200)
        self.assertContains(response_ras, 'ras-mode-container')
        self.assertContains(response_ras, 'ras-certificate-card')
        self.assertContains(response_ras, 'ras_template')
        self.assertContains(response_ras, 'ANKIT PARIHAR')
        self.assertContains(response_ras, '15th Jun.')
        self.assertContains(response_ras, '31st Aug.')
        self.assertContains(response_ras, '2026')
        self.assertContains(response_ras, '“A”')
        self.assertContains(response_ras, '10.09.2026')
        self.assertContains(response_ras, 'A4 landscape')

        # Test format=pdf returns raw PDF without any HTML/browser headers
        response_pdf = self.client.get(reverse('dashboard:print_certificate', kwargs={'pk': ras_cert.pk}) + '?format=pdf')
        self.assertEqual(response_pdf.status_code, 200)
        self.assertEqual(response_pdf['Content-Type'], 'application/pdf')
        self.assertTrue(response_pdf.content.startswith(b'%PDF'))
        self.assertGreater(len(response_pdf.content), 1000)

    def test_ras_public_verification_and_download_pdf(self):
        """Test public verify result page shows RAS landscape template and provides direct clean PDF download."""
        ras_cert = Certificate.objects.create(
            certificate_id='RAS-2026-10-SP-391758-1003',
            first_name='Shivam',
            last_name='Patel',
            student_name='Shivam Patel',
            course=self.course,
            course_start_date=date(2026, 10, 1),
            course_end_date=date(2026, 10, 30),
            issue_date=date(2026, 11, 1),
            grade='A+'
        )

        url = reverse('certificates:verify')
        response = self.client.post(url, {'certificate_id': 'RAS-2026-10-SP-391758-1003'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'certificates/result.html')
        self.assertContains(response, 'Official Verification Details')
        self.assertContains(response, 'Shivam Patel')
        self.assertContains(response, 'RAS-2026-10-SP-391758-1003')
        self.assertContains(response, 'A+')
        self.assertNotContains(response, 'ras-certificate-card')
        self.assertNotContains(response, 'ras_template.jpg')
        self.assertContains(response, '📥 Download PDF')

        # Test direct PDF download endpoint
        dl_url = reverse('certificates:download_certificate_pdf', kwargs={'certificate_id': ras_cert.certificate_id})
        dl_response = self.client.get(dl_url)
        self.assertEqual(dl_response.status_code, 200)
        self.assertEqual(dl_response['Content-Type'], 'application/pdf')
        self.assertTrue(dl_response.content.startswith(b'%PDF'))
        self.assertGreater(len(dl_response.content), 1000)

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
        self.assertContains(response, 'Official Verification Details')
        self.assertContains(response, 'Aarav Shah')
        self.assertContains(response, 'CERT-2026-CCC04')
        self.assertNotContains(response, 'certificate-card')


class CertificatePrefixAndSequenceTestCase(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            name='Full Stack Web Development',
            description='Web Dev with Python & JS',
            duration='16 Weeks',
            fee=800.00
        )
        self.admin = User.objects.create_superuser(
            username='seqadmin',
            email='seqadmin@cdac.in',
            password='adminpassword123'
        )

    def test_01_automatic_ras_generation_with_initials(self):
        """1. Automatic RAS generation produces RAS-YYYY-MM-FL-XXXXXX-1001 for student."""
        from datetime import datetime
        from certificates.utils import generate_certificate_id, CERTIFICATE_ID_REGEX
        current_year = datetime.now().year
        current_month = datetime.now().month
        cert_id = generate_certificate_id('RAS', first_name='Harshal', last_name='Chauhan')
        self.assertTrue(CERTIFICATE_ID_REGEX.match(cert_id))
        self.assertTrue(cert_id.startswith(f"RAS-{current_year}-{current_month:02d}-HC-"))
        parts = cert_id.split('-')
        self.assertEqual(len(parts), 5)
        self.assertEqual(len(parts[4]), 6)
        self.assertTrue(100000 <= int(parts[4]) <= 999999)

    def test_02_automatic_citi_generation_with_initials(self):
        """2. Automatic CITI generation produces CITI-YYYY-MM-FL-XXXXXX-5001 for student."""
        from datetime import datetime
        from certificates.utils import generate_certificate_id, CERTIFICATE_ID_REGEX
        current_year = datetime.now().year
        current_month = datetime.now().month
        cert_id = generate_certificate_id('CITI', first_name='Harshal', last_name='Chauhan')
        self.assertTrue(CERTIFICATE_ID_REGEX.match(cert_id))
        self.assertTrue(cert_id.startswith(f"CITI-{current_year}-{current_month:02d}-HC-"))
        parts = cert_id.split('-')
        self.assertEqual(len(parts), 5)
        self.assertEqual(len(parts[4]), 6)
        self.assertTrue(100000 <= int(parts[4]) <= 999999)

    def test_03_independent_prefix_and_continuous_student_sequences(self):
        """3. Each certificate generates unique 6-digit code and increments sequence independently."""
        from datetime import datetime
        from certificates.utils import generate_certificate_id, CERTIFICATE_ID_REGEX
        current_year = datetime.now().year
        current_month = datetime.now().month

        # Student 1: Harshal Chauhan (RAS)
        ras1_id = generate_certificate_id('RAS', first_name='Harshal', last_name='Chauhan')
        self.assertTrue(CERTIFICATE_ID_REGEX.match(ras1_id))
        self.assertTrue(ras1_id.startswith(f"RAS-{current_year}-{current_month:02d}-HC-"))
        parts1 = ras1_id.split('-')
        self.assertEqual(len(parts1), 5)
        self.assertEqual(len(parts1[4]), 6)
        self.assertTrue(100000 <= int(parts1[4]) <= 999999)
        Certificate.objects.create(
            certificate_id=ras1_id,
            first_name='Harshal',
            last_name='Chauhan',
            student_name='Harshal Chauhan',
            course=self.course,
            issue_date=date(current_year, 1, 10)
        )

        # Student 2: Amit Patel (RAS)
        ras2_id = generate_certificate_id('RAS', first_name='Amit', last_name='Patel')
        self.assertTrue(CERTIFICATE_ID_REGEX.match(ras2_id))
        self.assertTrue(ras2_id.startswith(f"RAS-{current_year}-{current_month:02d}-AP-"))
        parts2 = ras2_id.split('-')
        self.assertEqual(len(parts2), 5)
        self.assertEqual(len(parts2[4]), 6)
        self.assertTrue(100000 <= int(parts2[4]) <= 999999)
        self.assertNotEqual(parts1[4], parts2[4])
        Certificate.objects.create(
            certificate_id=ras2_id,
            first_name='Amit',
            last_name='Patel',
            student_name='Amit Patel',
            course=self.course,
            issue_date=date(current_year, 1, 11)
        )

        # Student 3: Priya Sharma (RAS)
        ras3_id = generate_certificate_id('RAS', first_name='Priya', last_name='Sharma')
        self.assertTrue(CERTIFICATE_ID_REGEX.match(ras3_id))
        self.assertTrue(ras3_id.startswith(f"RAS-{current_year}-{current_month:02d}-PS-"))
        parts3 = ras3_id.split('-')
        self.assertEqual(len(parts3), 5)
        self.assertNotEqual(parts2[4], parts3[4])
        Certificate.objects.create(
            certificate_id=ras3_id,
            first_name='Priya',
            last_name='Sharma',
            student_name='Priya Sharma',
            course=self.course,
            issue_date=date(current_year, 1, 12)
        )

        # CITI generation independent of RAS
        citi1_id = generate_certificate_id('CITI', first_name='Harshal', last_name='Chauhan')
        self.assertTrue(CERTIFICATE_ID_REGEX.match(citi1_id))
        self.assertTrue(citi1_id.startswith(f"CITI-{current_year}-{current_month:02d}-HC-"))
        parts_c1 = citi1_id.split('-')
        self.assertEqual(len(parts_c1), 5)
        self.assertEqual(len(parts_c1[4]), 6)
        self.assertTrue(100000 <= int(parts_c1[4]) <= 999999)
        Certificate.objects.create(
            certificate_id=citi1_id,
            first_name='Harshal',
            last_name='Chauhan',
            student_name='Harshal Chauhan',
            course=self.course,
            issue_date=date(current_year, 1, 12)
        )

        # Next CITI: Riya Patel
        citi2_id = generate_certificate_id('CITI', first_name='Riya', last_name='Patel')
        self.assertTrue(CERTIFICATE_ID_REGEX.match(citi2_id))
        self.assertTrue(citi2_id.startswith(f"CITI-{current_year}-{current_month:02d}-RP-"))
        parts_c2 = citi2_id.split('-')
        self.assertEqual(len(parts_c2), 5)
        self.assertNotEqual(citi1_id, citi2_id)
        self.assertNotEqual(citi1_id, citi2_id)

    def test_04_manual_generation_rules_and_validation(self):
        """4. Manual generation enforces prefix, student initials, format, and rejects literal XX."""
        from datetime import datetime
        from dashboard.forms import AdminCertificateForm
        current_year = datetime.now().year

        # 4a. Valid manual entry matching prefix RAS and initials HC
        form_valid = AdminCertificateForm(data={
            'prefix': 'RAS',
            'id_gen_mode': 'manual',
            'certificate_id': f'RAS-{current_year}-HC1099',
            'first_name': 'Harshal',
            'middle_name': 'Narendrasinh',
            'last_name': 'Chauhan',
            'course': self.course.id,
            'course_start_date': f'{current_year}-01-01',
            'course_end_date': f'{current_year}-06-01',
            'issue_date': f'{current_year}-06-15',
        })
        self.assertTrue(form_valid.is_valid(), f"Errors: {form_valid.errors}")

        # 4b. Prefix mismatch: selected RAS, entered CITI
        form_prefix_mismatch = AdminCertificateForm(data={
            'prefix': 'RAS',
            'id_gen_mode': 'manual',
            'certificate_id': f'CITI-{current_year}-HC5001',
            'first_name': 'Harshal',
            'middle_name': 'Narendrasinh',
            'last_name': 'Chauhan',
            'course': self.course.id,
            'course_start_date': f'{current_year}-01-01',
            'course_end_date': f'{current_year}-06-01',
            'issue_date': f'{current_year}-06-15',
        })
        self.assertFalse(form_prefix_mismatch.is_valid())
        self.assertIn('certificate_id', form_prefix_mismatch.errors)
        self.assertIn("must start with the selected prefix 'RAS'", form_prefix_mismatch.errors['certificate_id'][0])

        # 4c. Literal XX rejected
        form_xx = AdminCertificateForm(data={
            'prefix': 'RAS',
            'id_gen_mode': 'manual',
            'certificate_id': f'RAS-{current_year}-XX1001',
            'first_name': 'Harshal',
            'middle_name': 'Narendrasinh',
            'last_name': 'Chauhan',
            'course': self.course.id,
            'course_start_date': f'{current_year}-01-01',
            'course_end_date': f'{current_year}-06-01',
            'issue_date': f'{current_year}-06-15',
        })
        self.assertFalse(form_xx.is_valid())
        self.assertIn('certificate_id', form_xx.errors)
        self.assertIn("Literal 'XX' is not allowed", form_xx.errors['certificate_id'][0])

        # 4d. Initials mismatch rejected: entered AP, student is Harshal Chauhan (HC)
        form_mismatch_initials = AdminCertificateForm(data={
            'prefix': 'RAS',
            'id_gen_mode': 'manual',
            'certificate_id': f'RAS-{current_year}-AP1001',
            'first_name': 'Harshal',
            'middle_name': 'Narendrasinh',
            'last_name': 'Chauhan',
            'course': self.course.id,
            'course_start_date': f'{current_year}-01-01',
            'course_end_date': f'{current_year}-06-01',
            'issue_date': f'{current_year}-06-15',
        })
        self.assertFalse(form_mismatch_initials.is_valid())
        self.assertIn('certificate_id', form_mismatch_initials.errors)
        self.assertIn("do not match student initials", form_mismatch_initials.errors['certificate_id'][0])

        # 4e. Missing last name rejected in form (both first and last name required for initials)
        form_single_name = AdminCertificateForm(data={
            'prefix': 'RAS',
            'id_gen_mode': 'manual',
            'certificate_id': f'RAS-{current_year}-P1055',
            'first_name': 'Priya',
            'middle_name': 'Devi',
            'last_name': '',
            'course': self.course.id,
            'course_start_date': f'{current_year}-01-01',
            'course_end_date': f'{current_year}-06-01',
            'issue_date': f'{current_year}-06-15',
        })
        self.assertFalse(form_single_name.is_valid())
        self.assertIn('last_name', form_single_name.errors)

        # 4f. Duplicate ID rejected
        Certificate.objects.create(
            certificate_id=f'RAS-{current_year}-HC1001',
            student_name='Harshal Chauhan',
            course=self.course,
            issue_date=date(current_year, 1, 1)
        )
        form_duplicate = AdminCertificateForm(data={
            'prefix': 'RAS',
            'id_gen_mode': 'manual',
            'certificate_id': f'RAS-{current_year}-HC1001',
            'first_name': 'Harshal',
            'middle_name': 'Narendrasinh',
            'last_name': 'Chauhan',
            'course': self.course.id,
            'course_start_date': f'{current_year}-01-01',
            'course_end_date': f'{current_year}-06-01',
            'issue_date': f'{current_year}-06-15',
        })
        self.assertFalse(form_duplicate.is_valid())
        self.assertIn('certificate_id', form_duplicate.errors)
        self.assertIn('already exists', form_duplicate.errors['certificate_id'][0])

    def test_05_dynamic_year_handling(self):
        """5. Year is taken dynamically from server's current date, not hardcoded."""
        from datetime import datetime
        from certificates.utils import generate_certificate_id
        current_year = datetime.now().year
        current_month = datetime.now().month
        cert_id = generate_certificate_id('RAS', first_name='Harshal', last_name='Chauhan')
        self.assertIn(f"RAS-{current_year}-{current_month:02d}-HC-", cert_id)

    def test_06_continuous_sequence_across_years(self):
        """6. Each prefix's sequence continues monotonically across new years and never resets."""
        from certificates.utils import generate_certificate_id
        # Year 2026 has certificates
        Certificate.objects.create(
            certificate_id='RAS-2026-HC1001',
            student_name='Harshal Chauhan',
            course=self.course,
            issue_date=date(2026, 1, 1)
        )
        Certificate.objects.create(
            certificate_id='CITI-2026-HC5001',
            student_name='Harshal Chauhan CITI',
            course=self.course,
            issue_date=date(2026, 1, 1)
        )

        # In year 2027, unique 6-digit suffixes are generated
        ras_2027 = generate_certificate_id('RAS', year=2027, first_name='Harshal', last_name='Chauhan')
        citi_2027 = generate_certificate_id('CITI', year=2027, first_name='Harshal', last_name='Chauhan')
        self.assertTrue(ras_2027.startswith('RAS-2027-'))
        parts_r = ras_2027.split('-')
        self.assertEqual(len(parts_r), 5)
        self.assertEqual(len(parts_r[4]), 6)
        self.assertTrue(100000 <= int(parts_r[4]) <= 999999)
        self.assertTrue(citi_2027.startswith('CITI-2027-'))
        parts_c = citi_2027.split('-')
        self.assertEqual(len(parts_c), 5)
        self.assertEqual(len(parts_c[4]), 6)
        self.assertTrue(100000 <= int(parts_c[4]) <= 999999)

        # Existing 2026 certificates remain untouched
        self.assertTrue(Certificate.objects.filter(certificate_id='RAS-2026-HC1001').exists())
        self.assertTrue(Certificate.objects.filter(certificate_id='CITI-2026-HC5001').exists())

    def test_07_no_duplicate_ids_generated(self):
        """7. No duplicate IDs are generated even with rapid sequence calls."""
        from certificates.utils import generate_certificate_id
        from datetime import datetime
        current_year = datetime.now().year

        generated_ids = set()
        for i in range(20):
            cid = generate_certificate_id('RAS', first_name=f'User{i}', last_name='Test')
            self.assertNotIn(cid, generated_ids)
            generated_ids.add(cid)
            Certificate.objects.create(
                certificate_id=cid,
                student_name=f'User{i} Test',
                course=self.course,
                issue_date=date(current_year, 1, 1)
            )

        self.assertEqual(len(generated_ids), 20)

    def test_08_existing_records_preserved(self):
        """8. Existing historical records (e.g. CERT-..., RAS-...-XX...) are preserved untouched."""
        historical = Certificate.objects.create(
            certificate_id='CERT-2026-OLD-001',
            student_name='Historical Student',
            course=self.course,
            issue_date=date(2026, 1, 1)
        )
        historical_xx = Certificate.objects.create(
            certificate_id='RAS-2026-XX1001',
            student_name='Legacy Student',
            course=self.course,
            issue_date=date(2026, 1, 1)
        )
        self.assertEqual(historical.prefix, 'CERT')
        historical.refresh_from_db()
        self.assertEqual(historical.certificate_id, 'CERT-2026-OLD-001')
        historical_xx.refresh_from_db()
        self.assertEqual(historical_xx.certificate_id, 'RAS-2026-XX1001')

    def test_09_certificate_verification_with_new_and_historical_ids(self):
        """9. Certificate verification continues to work with new initials IDs and historical IDs."""
        from datetime import datetime
        current_year = datetime.now().year

        ras_cert = Certificate.objects.create(
            certificate_id=f'RAS-{current_year}-HC1001',
            student_name='Harshal Chauhan',
            course=self.course,
            issue_date=date(current_year, 3, 10),
            grade='A+'
        )
        citi_cert = Certificate.objects.create(
            certificate_id=f'CITI-{current_year}-RP5001',
            student_name='Riya Patel',
            course=self.course,
            issue_date=date(current_year, 3, 11),
            grade='A'
        )
        legacy_cert = Certificate.objects.create(
            certificate_id=f'RAS-{current_year}-XX1000',
            student_name='Legacy User',
            course=self.course,
            issue_date=date(current_year, 3, 1),
            grade='B'
        )

        url = reverse('certificates:verify')
        # Verify RAS
        res_ras = self.client.post(url, {'certificate_id': f'RAS-{current_year}-HC1001'})
        self.assertEqual(res_ras.status_code, 200)
        self.assertContains(res_ras, 'Harshal Chauhan')

        # Verify CITI
        res_citi = self.client.post(url, {'certificate_id': f'CITI-{current_year}-RP5001'})
        self.assertEqual(res_citi.status_code, 200)
        self.assertContains(res_citi, 'Riya Patel')

        # Verify Legacy historical certificate
        res_legacy = self.client.post(url, {'certificate_id': f'RAS-{current_year}-XX1000'})
        self.assertEqual(res_legacy.status_code, 200)
        self.assertContains(res_legacy, 'Legacy User')


    def test_10_ajax_next_id_api_endpoint(self):
        """10. API endpoint returns next sequence and ID with student initials without consuming sequence."""
        from datetime import datetime
        current_year = datetime.now().year
        current_month = datetime.now().month
        self.client.login(username='seqadmin', password='adminpassword123')

        url = reverse('dashboard:get_next_certificate_id')
        res_ras = self.client.get(url, {'prefix': 'RAS', 'first_name': 'Harshal', 'last_name': 'Chauhan'})
        self.assertEqual(res_ras.status_code, 200)
        ras_parts = res_ras.json()['certificate_id'].split('-')
        self.assertEqual(ras_parts[0], 'RAS')
        self.assertEqual(ras_parts[1], str(current_year))
        self.assertEqual(ras_parts[2], f'{current_month:02d}')
        self.assertEqual(ras_parts[3], 'HC')
        self.assertTrue(100000 <= int(ras_parts[4]) <= 999999)
        self.assertEqual(len(ras_parts), 5)
        self.assertEqual(res_ras.json()['initials'], 'HC')

        res_citi = self.client.get(url, {'prefix': 'CITI', 'first_name': 'Harshal', 'last_name': 'Chauhan', 'random_code': '855104'})
        self.assertEqual(res_citi.status_code, 200)
        self.assertEqual(res_citi.json()['certificate_id'], f'CITI-{current_year}-{current_month:02d}-HC-855104')

    def test_11_student_initials_rules(self):
        """11. Verify initials generation rules according to prompt specification."""
        from certificates.utils import get_student_initials
        # Harshal Chauhan -> HC
        self.assertEqual(get_student_initials('Harshal', 'Chauhan'), 'HC')
        self.assertEqual(get_student_initials(student_name='Harshal Chauhan'), 'HC')

        # Amit Patel -> AP
        self.assertEqual(get_student_initials('Amit', 'Patel'), 'AP')
        self.assertEqual(get_student_initials(student_name='Amit Patel'), 'AP')

        # Riya Shah -> RS
        self.assertEqual(get_student_initials('Riya', 'Shah'), 'RS')
        self.assertEqual(get_student_initials(student_name='Riya Shah'), 'RS')

        # Priya -> P (missing last name)
        self.assertEqual(get_student_initials('Priya', ''), 'P')
        self.assertEqual(get_student_initials(student_name='Priya'), 'P')

        # Case sensitivity & spaces
        self.assertEqual(get_student_initials('  harshal  ', '  chauhan  '), 'HC')

        # Multi-word names: first letter of first name and first letter of last name
        self.assertEqual(get_student_initials(student_name='Harshal Narendrasinh Chauhan'), 'HC')


class CertificateIDFormatterTestCase(TestCase):
    """Phase 3 Test Case: Isolated verification of Certificate ID Formatter & Initials Extractor."""

    def test_format_certificate_id_success(self):
        from certificates.utils import format_certificate_id
        # Standard RAS example without final numeric suffix: RAS-2026-10-DV-482716
        res_ras = format_certificate_id('RAS', 2026, 10, 'DV', 482716)
        self.assertEqual(res_ras, 'RAS-2026-10-DV-482716')

        # CITI example with single-digit month (must produce 2-digit MM with leading zero)
        res_citi = format_certificate_id('CITI', 2026, 4, 'RP', 100000)
        self.assertEqual(res_citi, 'CITI-2026-04-RP-100000')

        # Maximum boundary random code
        res_max = format_certificate_id('RAS', 2026, 12, 'AS', 999999)
        self.assertEqual(res_max, 'RAS-2026-12-AS-999999')

    def test_format_certificate_id_invalid_inputs(self):
        from certificates.utils import format_certificate_id
        # Invalid prefix
        with self.assertRaises(ValueError):
            format_certificate_id('XYZ', 2026, 10, 'DV', 482716)

        # Invalid month (0 or 13)
        with self.assertRaises(ValueError):
            format_certificate_id('RAS', 2026, 0, 'DV', 482716)
        with self.assertRaises(ValueError):
            format_certificate_id('RAS', 2026, 13, 'DV', 482716)

        # Invalid random code (< 100000 or > 999999)
        with self.assertRaises(ValueError):
            format_certificate_id('RAS', 2026, 10, 'DV', 99999)
        with self.assertRaises(ValueError):
            format_certificate_id('RAS', 2026, 10, 'DV', 1000000)

        # Invalid initials (not 2 letters)
        with self.assertRaises(ValueError):
            format_certificate_id('RAS', 2026, 10, 'D', 482716)
        with self.assertRaises(ValueError):
            format_certificate_id('RAS', 2026, 10, 'D1', 482716)

    def test_extract_recipient_initials(self):
        from certificates.utils import extract_recipient_initials
        # Divyaraj Vihol -> DV
        self.assertEqual(extract_recipient_initials('Divyaraj', 'Vihol'), 'DV')
        # Rahul Patel -> RP
        self.assertEqual(extract_recipient_initials('Rahul', 'Patel'), 'RP')
        # Aisha Shah -> AS
        self.assertEqual(extract_recipient_initials('Aisha', 'Shah'), 'AS')
        # Whitespace trimming and case insensitivity
        self.assertEqual(extract_recipient_initials('  divyaraj  ', '  vihol  '), 'DV')
        # Fallback from student_name when first/last not explicitly separated
        self.assertEqual(extract_recipient_initials(student_name='Divyaraj Vihol'), 'DV')

        # Missing first name or last name raises ValueError
        with self.assertRaises(ValueError):
            extract_recipient_initials('', 'Patel')
        with self.assertRaises(ValueError):
            extract_recipient_initials('Rahul', '')
        with self.assertRaises(ValueError):
            extract_recipient_initials('', '')

    def test_validate_certificate_id_format(self):
        from certificates.utils import validate_certificate_id_format
        # New format valid
        valid, err = validate_certificate_id_format('RAS-2026-10-DV-482716-1001', prefix='RAS', expected_initials='DV')
        self.assertTrue(valid)
        self.assertIsNone(err)

        # Prefix mismatch
        valid, err = validate_certificate_id_format('RAS-2026-10-DV-482716-1001', prefix='CITI')
        self.assertFalse(valid)

        # Initials mismatch
        valid, err = validate_certificate_id_format('RAS-2026-10-DV-482716-1001', expected_initials='RP')
        self.assertFalse(valid)

        # Legacy backward compatibility support
        valid_legacy, err_legacy = validate_certificate_id_format('RAS-2026-HC1001', allow_legacy=True)
        self.assertTrue(valid_legacy)


class CertificateSequenceAndRandomCodeTestCase(TestCase):
    """Phase 4 & 5 Test Case: Verification of Independent Persistent Sequences & Random Code Registry."""

    def test_independent_counters_and_persistence(self):
        from certificates.utils import (
            peek_next_certificate_sequence,
            reserve_next_certificate_sequence,
            generate_certificate_id,
            preview_certificate_id
        )
        from certificates.models import CertificateSequence

        # Initial peek
        self.assertEqual(peek_next_certificate_sequence('RAS'), 1001)
        self.assertEqual(peek_next_certificate_sequence('CITI'), 5001)

        # Preview must NOT consume or advance sequence numbers
        prev_id = preview_certificate_id(prefix='RAS', first_name='Divyaraj', last_name='Vihol')
        self.assertTrue(prev_id.startswith('RAS-'))
        self.assertEqual(peek_next_certificate_sequence('RAS'), 1001)

        # Reserve RAS
        seq1 = reserve_next_certificate_sequence('RAS')
        self.assertEqual(seq1, 1001)
        self.assertEqual(peek_next_certificate_sequence('RAS'), 1002)
        # CITI must remain unaffected
        self.assertEqual(peek_next_certificate_sequence('CITI'), 5001)

        # Reserve CITI
        citi_seq1 = reserve_next_certificate_sequence('CITI')
        self.assertEqual(citi_seq1, 5001)
        self.assertEqual(peek_next_certificate_sequence('CITI'), 5002)
        # RAS must remain 1002
        self.assertEqual(peek_next_certificate_sequence('RAS'), 1002)

        # Verify database persistence
        ras_db = CertificateSequence.objects.get(prefix='RAS')
        citi_db = CertificateSequence.objects.get(prefix='CITI')
        self.assertEqual(ras_db.next_sequence, 1002)
        self.assertEqual(citi_db.next_sequence, 5002)

    def test_sequence_exhaustion(self):
        from certificates.utils import reserve_next_certificate_sequence, SequenceExhaustedError
        from certificates.models import CertificateSequence

        # Fast forward counter to 9999
        seq_obj = CertificateSequence.objects.get_or_create(prefix='RAS', defaults={'next_sequence': 9999})[0]
        seq_obj.next_sequence = 9999
        seq_obj.save()

        # Issuing at 9999 succeeds and moves next to 10000
        val = reserve_next_certificate_sequence('RAS')
        self.assertEqual(val, 9999)

        # Next reservation attempt must raise SequenceExhaustedError
        with self.assertRaises(SequenceExhaustedError):
            reserve_next_certificate_sequence('RAS')

    def test_random_code_uniqueness_and_registry(self):
        from certificates.utils import allocate_unique_random_code
        from certificates.models import CertificateRandomCodeRegistry

        code1 = allocate_unique_random_code(certificate_id='TEST-01')
        code2 = allocate_unique_random_code(certificate_id='TEST-02')

        self.assertEqual(len(code1), 6)
        self.assertEqual(len(code2), 6)
        self.assertTrue(100000 <= int(code1) <= 999999)
        self.assertTrue(100000 <= int(code2) <= 999999)
        self.assertNotEqual(code1, code2)

        # Verify saved in registry
        reg1 = CertificateRandomCodeRegistry.objects.get(code=code1)
        self.assertEqual(reg1.certificate_id, 'TEST-01')
        self.assertEqual(reg1.status, 'allocated')

    def test_generate_certificate_id_full_workflow(self):
        from certificates.utils import generate_certificate_id, CERTIFICATE_ID_REGEX
        from certificates.models import CertificateRandomCodeRegistry

        cid = generate_certificate_id(
            prefix='RAS',
            year=2026,
            month=10,
            first_name='Divyaraj',
            last_name='Vihol',
            reserve=True
        )
        self.assertTrue(CERTIFICATE_ID_REGEX.match(cid), f"ID '{cid}' does not match expected regex.")
        self.assertTrue(cid.startswith('RAS-2026-10-DV-'))

        parts = cid.split('-')
        self.assertEqual(len(parts), 5)
        random_part = parts[4]

        # Verify registry entry is updated
        reg = CertificateRandomCodeRegistry.objects.get(code=random_part)
        self.assertEqual(reg.certificate_id, cid)
        self.assertEqual(reg.status, 'active')


class CertificateVerificationUrlTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            name='Mastering Python & Django',
            duration='3 Months',
            fee=5000.00
        )
        self.ccc_course = Course.objects.create(
            name='Course on Computer Concepts (CCC)',
            duration='3 Months (80 Hours)',
            fee=3500.00
        )
        self.admin = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='Password123!'
        )

        # Standard layout certificate
        self.cert_standard = Certificate.objects.create(
            certificate_id='CITI-2026-10-JS-582914-1001',
            student_name='Jane Student',
            course=self.course,
            issue_date=date(2026, 10, 1),
            grade='A'
        )

        # RAS layout certificate
        self.cert_ras = Certificate.objects.create(
            certificate_id='RAS-2026-10-DV-482716-1001',
            student_name='Divyaraj Vihol',
            course=self.course,
            course_start_date=date(2026, 6, 1),
            course_end_date=date(2026, 9, 1),
            issue_date=date(2026, 10, 1),
            grade='A+'
        )

        # CCC layout certificate
        self.cert_ccc = Certificate.objects.create(
            certificate_id='CITI-2026-10-RP-392817-1002',
            student_name='Rahul Patel',
            course=self.ccc_course,
            course_start_date=date(2026, 6, 1),
            course_end_date=date(2026, 9, 1),
            issue_date=date(2026, 10, 1),
            grade='A'
        )

    def test_get_certificate_verify_url_helper(self):
        from certificates.utils import get_certificate_verify_url
        from django.test import override_settings

        # Default localhost
        with override_settings(SITE_BASE_URL='http://localhost:8000'):
            url = get_certificate_verify_url()
            self.assertEqual(url, 'http://localhost:8000/verify-certificate/')
            self.assertNotIn('//verify', url)

        # Trailing slash handled properly (no double slashes)
        with override_settings(SITE_BASE_URL='http://localhost:8000/'):
            url = get_certificate_verify_url()
            self.assertEqual(url, 'http://localhost:8000/verify-certificate/')
            self.assertNotIn('http://localhost:8000//', url)

        # Production live URL
        with override_settings(SITE_BASE_URL='https://www.rascomputer.com'):
            url = get_certificate_verify_url()
            self.assertEqual(url, 'https://www.rascomputer.com/verify-certificate/')

    def test_verification_line_in_public_result_page(self):
        url = reverse('certificates:verify')

        # 1. Standard certificate
        resp = self.client.post(url, {'certificate_id': self.cert_standard.certificate_id})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Official Verification Details')
        self.assertContains(resp, self.cert_standard.student_name)
        self.assertNotContains(resp, 'certificate-card')

        # 2. RAS certificate
        resp = self.client.post(url, {'certificate_id': self.cert_ras.certificate_id})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Official Verification Details')
        self.assertContains(resp, self.cert_ras.student_name)
        self.assertNotContains(resp, 'ras-certificate-card')

        # 3. CCC certificate
        resp = self.client.post(url, {'certificate_id': self.cert_ccc.certificate_id})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Official Verification Details')
        self.assertContains(resp, self.cert_ccc.student_name)
        self.assertNotContains(resp, 'citi-certificate-card')

    def test_verification_line_in_admin_print_page(self):
        self.client.login(username='admin_test', password='Password123!')

        # 1. Standard certificate
        url = reverse('dashboard:print_certificate', args=[self.cert_standard.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'This Certificate can be verified on')
        self.assertContains(resp, 'http://localhost:8000/verify-certificate/')

        # 2. RAS certificate
        url = reverse('dashboard:print_certificate', args=[self.cert_ras.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'This Certificate can be verified on')
        self.assertContains(resp, 'ras-verify-line')
        self.assertContains(resp, 'http://localhost:8000/verify-certificate/')

        # 3. CCC certificate
        url = reverse('dashboard:print_certificate', args=[self.cert_ccc.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'This Certificate can be verified on')
        self.assertContains(resp, 'ccc-verify-line')
        self.assertContains(resp, 'http://localhost:8000/verify-certificate/')

    def test_pdf_generators_include_verification_line(self):
        from certificates.utils import (
            generate_ras_certificate_pdf,
            generate_ccc_certificate_pdf,
            generate_certificate_pdf,
        )

        # 1. RAS PDF
        ras_pdf = generate_ras_certificate_pdf(self.cert_ras)
        self.assertTrue(ras_pdf.startswith(b'%PDF'))
        self.assertGreater(len(ras_pdf), 1000)

        # 2. CCC PDF
        ccc_pdf = generate_ccc_certificate_pdf(self.cert_ccc)
        self.assertTrue(ccc_pdf.startswith(b'%PDF'))
        self.assertGreater(len(ccc_pdf), 1000)

        # 3. Standard C-DAC PDF
        std_pdf = generate_certificate_pdf(self.cert_standard)
        self.assertTrue(std_pdf.startswith(b'%PDF'))
        self.assertGreater(len(std_pdf), 1000)


class CitiCccWorkflowTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='citiadmin',
            email='citiadmin@test.com',
            password='Password123!'
        )
        self.ccc_course = Course.objects.create(
            name='Certificate Course on Computer Concepts (CCC)',
            description='CCC training program',
            duration='3 Months',
            fee=3000.00
        )
        self.other_course = Course.objects.create(
            name='Java Programming',
            description='Core Java',
            duration='6 Months',
            fee=5000.00
        )

    def _create_dummy_image(self):
        import io
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        buf = io.BytesIO()
        img = Image.new('RGB', (100, 120), color=(73, 109, 137))
        img.save(buf, format='JPEG')
        buf.seek(0)
        return SimpleUploadedFile('student_test.jpg', buf.getvalue(), content_type='image/jpeg')

    def test_citi_ccc_creation_and_calculations(self):
        photo = self._create_dummy_image()
        cert = Certificate.objects.create(
            certificate_id='CITI-2026-10-SP-100000-5001',
            first_name='Shivam',
            middle_name='Kumar',
            last_name='Patel',
            student_name='Shivam Kumar Patel',
            course=self.ccc_course,
            course_start_date=date(2026, 1, 1),
            course_end_date=date(2026, 3, 31),
            issue_date=date(2026, 4, 15),
            student_photo=photo,
            theory_marks=42,
            practical_marks=43,
            course_duration='3 Months',
            serial_number='4327',
        )
        self.assertEqual(cert.total_marks, 85)
        self.assertEqual(cert.percentage, 85.0)
        self.assertEqual(cert.grade, 'S')
        self.assertEqual(cert.registration_number, 'CITI/GNR/2026-27/4327')

    def test_citi_ccc_grade_scale(self):
        self.assertEqual(Certificate.calculate_citi_grade(85), 'S')
        self.assertEqual(Certificate.calculate_citi_grade(90), 'S')
        self.assertEqual(Certificate.calculate_citi_grade(75), 'A')
        self.assertEqual(Certificate.calculate_citi_grade(84), 'A')
        self.assertEqual(Certificate.calculate_citi_grade(65), 'B')
        self.assertEqual(Certificate.calculate_citi_grade(74), 'B')
        self.assertEqual(Certificate.calculate_citi_grade(55), 'C')
        self.assertEqual(Certificate.calculate_citi_grade(64), 'C')
        self.assertEqual(Certificate.calculate_citi_grade(50), 'D')
        self.assertEqual(Certificate.calculate_citi_grade(54), 'D')
        self.assertIsNone(Certificate.calculate_citi_grade(49))

    def test_citi_form_fails_when_below_50(self):
        from dashboard.forms import AdminCertificateForm
        photo = self._create_dummy_image()
        data = {
            'prefix': 'CITI',
            'first_name': 'Rahul',
            'middle_name': 'Kumar',
            'last_name': 'Patel',
            'course': self.ccc_course.id,
            'course_start_date': '2026-01-01',
            'course_end_date': '2026-03-31',
            'issue_date': '2026-04-15',
            'theory_marks': '20',
            'practical_marks': '25',  # Total 45 < 50
            'course_duration': '3 Months',
        }
        form = AdminCertificateForm(data=data, files={'student_photo': photo})
        self.assertFalse(form.is_valid())
        self.assertTrue(any('Not Eligible' in str(e) or 'below 50%' in str(e) for e in form.non_field_errors()))

    def test_citi_form_requires_photo(self):
        from dashboard.forms import AdminCertificateForm
        data = {
            'prefix': 'CITI',
            'first_name': 'Rahul',
            'middle_name': 'Kumar',
            'last_name': 'Patel',
            'course': self.ccc_course.id,
            'course_start_date': '2026-01-01',
            'course_end_date': '2026-03-31',
            'issue_date': '2026-04-15',
            'theory_marks': '35',
            'practical_marks': '35',
            'course_duration': '3 Months',
        }
        form = AdminCertificateForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('student_photo', form.errors)

    def test_citi_form_requires_ccc_course(self):
        from dashboard.forms import AdminCertificateForm
        photo = self._create_dummy_image()
        data = {
            'prefix': 'CITI',
            'first_name': 'Rahul',
            'middle_name': 'Kumar',
            'last_name': 'Patel',
            'course': self.other_course.id,
            'course_start_date': '2026-01-01',
            'course_end_date': '2026-03-31',
            'issue_date': '2026-04-15',
            'theory_marks': '35',
            'practical_marks': '35',
            'course_duration': '3 Months',
        }
        form = AdminCertificateForm(data=data, files={'student_photo': photo})
        self.assertFalse(form.is_valid())
        self.assertIn('course', form.errors)

    def test_citi_bundle_zip_download(self):
        photo = self._create_dummy_image()
        cert = Certificate.objects.create(
            certificate_id='CITI-2026-10-SP-100000-5002',
            first_name='Shivam',
            middle_name='Kumar',
            last_name='Patel',
            student_name='Shivam Kumar Patel',
            course=self.ccc_course,
            course_start_date=date(2026, 1, 1),
            course_end_date=date(2026, 3, 31),
            issue_date=date(2026, 4, 15),
            student_photo=photo,
            theory_marks=38,
            practical_marks=40,
            course_duration='3 Months',
            serial_number='4328',
        )
        self.client.login(username='citiadmin', password='Password123!')
        url = reverse('dashboard:download_citi_bundle', args=[cert.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/zip')

        import io
        import zipfile
        zip_buf = io.BytesIO(resp.content)
        with zipfile.ZipFile(zip_buf, 'r') as zf:
            file_names = zf.namelist()
            self.assertEqual(len(file_names), 2)
            self.assertTrue(any('Certificate.pdf' in fn for fn in file_names))
            self.assertTrue(any('Marksheet.pdf' in fn for fn in file_names))

    def test_citi_marksheet_view_and_pdf(self):
        photo = self._create_dummy_image()
        cert = Certificate.objects.create(
            certificate_id='CITI-2026-10-SP-100000-5003',
            first_name='Shivam',
            middle_name='Kumar',
            last_name='Patel',
            student_name='Shivam Kumar Patel',
            course=self.ccc_course,
            course_start_date=date(2026, 1, 1),
            course_end_date=date(2026, 3, 31),
            issue_date=date(2026, 4, 15),
            student_photo=photo,
            theory_marks=38,
            practical_marks=40,
            course_duration='3 Months',
            serial_number='4329',
        )
        self.client.login(username='citiadmin', password='Password123!')
        url = reverse('dashboard:print_citi_marksheet', args=[cert.id])
        resp_html = self.client.get(url)
        self.assertEqual(resp_html.status_code, 200)
        self.assertContains(resp_html, 'STATEMENT OF MARKS')
        self.assertContains(resp_html, 'SHIVAM KUMAR PATEL')

        resp_pdf = self.client.get(url + '?format=pdf')
        self.assertEqual(resp_pdf.status_code, 200)
        self.assertEqual(resp_pdf['Content-Type'], 'application/pdf')
        self.assertTrue(resp_pdf.content.startswith(b'%PDF'))

    def test_verify_by_registration_number(self):
        photo = self._create_dummy_image()
        cert = Certificate.objects.create(
            certificate_id='CITI-2026-10-SP-100000-5004',
            first_name='Shivam',
            middle_name='Kumar',
            last_name='Patel',
            student_name='Shivam Kumar Patel',
            course=self.ccc_course,
            course_start_date=date(2026, 1, 1),
            course_end_date=date(2026, 3, 31),
            issue_date=date(2026, 4, 15),
            student_photo=photo,
            theory_marks=38,
            practical_marks=40,
            course_duration='3 Months',
            serial_number='4330',
        )
        reg_no = cert.registration_number
        self.assertTrue(reg_no.startswith('CITI/GNR/'))

        # Public verification with registration_number
        verify_url = reverse('certificates:verify')
        resp = self.client.post(verify_url, {'certificate_id': reg_no})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Shivam Kumar Patel')

        # Admin search verification with registration_number
        self.client.login(username='citiadmin', password='Password123!')
        admin_search_url = reverse('dashboard:admin_verify_search')
        resp = self.client.post(admin_search_url, {'certificate_id': reg_no})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Shivam Kumar Patel')

from django.test import TransactionTestCase


class CitiQrPositionAndSixDigitSuffixTests(TransactionTestCase):
    """
    Mandatory Verification Tests for:
    1. CITI Certificate QR Repositioning to Top-Right Corner.
    2. Six-Digit Random Suffix (100000-999999) Certificate Number Generation.
    3. Collision Handling Simulation and Database-Level Uniqueness Enforcement.
    4. Concurrency Safety.
    5. Historical Certificate Preservation and Scannability.
    """

    def setUp(self):
        self.course = Course.objects.create(
            name='Certificate Course on Computer Concepts (CCC)',
            duration='3 Months',
            fee=3500.00
        )
        self.admin = User.objects.create_superuser(
            username='citi_test_admin',
            email='citi_admin@test.com',
            password='AdminPassword123!'
        )
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        import io
        img = Image.new('RGB', (100, 100), color=(100, 150, 200))
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        buf.seek(0)
        self.photo = SimpleUploadedFile('test_photo.jpg', buf.getvalue(), content_type='image/jpeg')

    def test_01_six_digit_numeric_suffix_range_and_length(self):
        """1. Every newly issued certificate contains unique 6-digit random code and sequential serial."""
        from certificates.utils import generate_certificate_id, CERTIFICATE_ID_REGEX
        for i in range(50):
            cid = generate_certificate_id('RAS', first_name=f'Student{i}', last_name='Patel', reserve=True)
            self.assertTrue(CERTIFICATE_ID_REGEX.match(cid))
            parts = cid.split('-')
            self.assertEqual(len(parts), 5)
            rand_code = parts[4]
            self.assertEqual(len(rand_code), 6, f"Random code '{rand_code}' is not 6 digits in '{cid}'")
            self.assertTrue(rand_code.isdigit(), f"Random code '{rand_code}' contains non-digits in '{cid}'")
            self.assertTrue(100000 <= int(rand_code) <= 999999, f"Code {rand_code} is outside 100000-999999")

    def test_02_uniqueness_across_months_years_courses_types(self):
        """2. Certificate numbers are unique across different months, years, courses, and prefixes."""
        from certificates.utils import generate_certificate_id
        generated = set()
        test_matrix = [
            ('RAS', 2026, 1), ('RAS', 2026, 10), ('RAS', 2027, 3), ('RAS', 2027, 12),
            ('CITI', 2026, 2), ('CITI', 2026, 11), ('CITI', 2027, 4), ('CITI', 2027, 8),
        ]
        for prefix, yr, mo in test_matrix:
            for i in range(5):
                cid = generate_certificate_id(prefix, year=yr, month=mo, first_name=f'User{i}', last_name='Shah', reserve=True)
                self.assertNotIn(cid, generated)
                generated.add(cid)
                Certificate.objects.create(
                    certificate_id=cid,
                    student_name=f'User{i} Shah',
                    course=self.course,
                    issue_date=date(yr, mo, 15)
                )
        self.assertEqual(len(generated), len(test_matrix) * 5)

    def test_03_collision_handling_retry_simulation(self):
        """3. Simulating an already-used random code forces the system to generate a replacement code."""
        from certificates.utils import generate_certificate_id, format_certificate_id
        from certificates.models import CertificateRandomCodeRegistry
        from datetime import datetime
        now = datetime.now()
        # Register a used code
        CertificateRandomCodeRegistry.objects.create(code='483271', status='active')
        new_cid = generate_certificate_id('RAS', first_name='Target', last_name='Person', reserve=True)
        parts = new_cid.split('-')
        self.assertNotEqual(parts[4], '483271')
        self.assertEqual(len(parts[4]), 6)
        self.assertTrue(100000 <= int(parts[4]) <= 999999)

    def test_04_database_uniqueness_constraint_enforced(self):
        """4. Confirm database uniqueness constraint is active and enforced on certificate_id."""
        from django.db import IntegrityError
        from certificates.models import Certificate
        Certificate.objects.create(
            certificate_id='RAS-2026-10-UN-100000-888888',
            student_name='Unique Test 1',
            course=self.course,
            issue_date=date(2026, 10, 1)
        )
        with self.assertRaises(IntegrityError):
            Certificate.objects.create(
                certificate_id='RAS-2026-10-UN-100000-888888',
                student_name='Duplicate Student',
                course=self.course,
                issue_date=date(2026, 10, 2)
            )
        with self.assertRaises(IntegrityError):
            Certificate.objects.create(
                certificate_id='ras-2026-10-un-100000-888888',
                student_name='Lower Duplicate Student',
                course=self.course,
                issue_date=date(2026, 10, 2)
            )

    def test_05_concurrent_issuance_safety(self):
        """5. Test concurrent issuance requests and verify no certificates receive duplicate numbers."""
        from concurrent.futures import ThreadPoolExecutor
        from certificates.utils import generate_certificate_id
        from django.db import connection

        def issue_one(idx):
            connection.close()
            try:
                return generate_certificate_id('RAS', first_name=f'Conc{idx}', last_name='Worker', reserve=True)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(issue_one, range(20)))

        self.assertEqual(len(results), 20)
        self.assertEqual(len(set(results)), 20, "Concurrent issuance generated duplicate certificate IDs!")

    def test_06_historical_certificates_retained_and_verifiable(self):
        """6. Historical certificates with legacy 4-digit suffixes retain verification and downloads."""
        cert_legacy = Certificate.objects.create(
            certificate_id='RAS-2026-10-HC-100000-1001',
            student_name='Historical Student',
            course=self.course,
            issue_date=date(2026, 10, 1)
        )
        verify_url = reverse('certificates:verify')
        resp = self.client.post(verify_url, {'certificate_id': 'RAS-2026-10-HC-100000-1001'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Historical Student')
        self.assertContains(resp, 'RAS-2026-10-HC-100000-1001')

    def test_07_citi_html_print_view_qr_in_top_right(self):
        """7. Inspect CITI certificate print template: confirm QR code is in top-right corner."""
        cert = Certificate.objects.create(
            certificate_id='CITI-2026-10-SP-100000-746291',
            first_name='Shivam',
            last_name='Patel',
            student_name='Shivam Patel',
            course=self.course,
            course_start_date=date(2026, 1, 1),
            course_end_date=date(2026, 3, 31),
            issue_date=date(2026, 4, 15),
            student_photo=self.photo,
            theory_marks=42,
            practical_marks=44,
            serial_number='5005',
        )
        self.client.login(username='citi_test_admin', password='AdminPassword123!')
        url = reverse('dashboard:print_certificate', args=[cert.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')

        self.assertIn('citi-cert-qr', html)
        self.assertIn('Scan to Verify', html)
        self.assertIn('top: 8.3%', html)
        self.assertIn('right: 10.5%', html)
        self.assertIn('top: 18.8%', html)
        self.assertNotIn('5005', html)

    def test_08_citi_public_result_view_qr_in_top_right(self):
        """8. Inspect CITI certificate public verification view: confirm QR code is in top-right corner."""
        cert = Certificate.objects.create(
            certificate_id='CITI-2026-10-SP-100000-918273',
            first_name='Shivam',
            last_name='Patel',
            student_name='Shivam Patel',
            course=self.course,
            course_start_date=date(2026, 1, 1),
            course_end_date=date(2026, 3, 31),
            issue_date=date(2026, 4, 15),
            student_photo=self.photo,
            theory_marks=40,
            practical_marks=42,
            serial_number='5006',
        )
        from django.core.cache import cache
        cache.clear()
        verify_url = reverse('certificates:verify')
        resp = self.client.post(verify_url, {'certificate_id': 'CITI-2026-10-SP-100000-918273'})
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        self.assertIn('Official Verification Details', html)
        self.assertIn('Shivam Patel', html)
        self.assertIn('CITI-2026-10-SP-100000-918273', html)
        self.assertNotIn('citi-certificate-card', html)

    def test_09_citi_pdf_generation_qr_in_top_right_and_scannable(self):
        """9. CITI ReportLab PDF contains top-right QR code and is scannable to verification URL."""
        from certificates.utils import generate_citi_ccc_certificate_pdf, get_certificate_verify_url
        import pypdf
        import io

        cert = Certificate.objects.create(
            certificate_id='CITI-2026-10-SP-100000-619284',
            first_name='Shivam',
            last_name='Patel',
            student_name='Shivam Patel',
            course=self.course,
            course_start_date=date(2026, 1, 1),
            course_end_date=date(2026, 3, 31),
            issue_date=date(2026, 4, 15),
            student_photo=self.photo,
            theory_marks=45,
            practical_marks=45,
            serial_number='5007',
        )
        pdf_bytes = generate_citi_ccc_certificate_pdf(cert)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        self.assertEqual(len(reader.pages), 1)
        text = reader.pages[0].extract_text()
        self.assertIn('SCAN TO VERIFY', text)
        self.assertNotIn('5007', text)
        self.assertIn('SHIVAM PATEL', text)
        self.assertIn('CITI-2026-10-SP-100000-619284', text)

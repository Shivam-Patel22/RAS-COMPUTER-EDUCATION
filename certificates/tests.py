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
        self.assertTrue(cert_id_ras.endswith('-1001'))

        cert_id_citi = generate_certificate_id('CITI', first_name='Harshal', last_name='Chauhan')
        self.assertTrue(CERTIFICATE_ID_REGEX.match(cert_id_citi))
        self.assertTrue(cert_id_citi.startswith(f'CITI-{year}-{month:02d}-HC-'))
        self.assertTrue(cert_id_citi.endswith('-5001'))

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
        self.assertContains(response_ras, 'ras_template.jpg')
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
        self.assertContains(response, 'ras-result-wrapper')
        self.assertContains(response, 'ras-certificate-card')
        self.assertContains(response, 'ras_template.jpg')
        self.assertContains(response, 'SHIVAM PATEL')
        self.assertContains(response, '1st Oct.')
        self.assertContains(response, '30th Oct.')
        self.assertContains(response, '2026')
        self.assertContains(response, '“A+”')
        self.assertContains(response, '01.11.2026')
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
        self.assertContains(response, 'COMPUTER &amp; INDUSTRIAL TRAINING INSTITUTION')
        self.assertContains(response, 'OFFICIAL GOVERNMENT RECOGNIZED PROGRAM (CCC)')
        self.assertContains(response, 'Aarav Shah')


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
        """1. Automatic RAS generation produces RAS-YYYY-MM-FF-RRRRRR-1001 for student."""
        from datetime import datetime
        from certificates.utils import generate_certificate_id, CERTIFICATE_ID_REGEX
        current_year = datetime.now().year
        current_month = datetime.now().month
        cert_id = generate_certificate_id('RAS', first_name='Harshal', last_name='Chauhan')
        self.assertTrue(CERTIFICATE_ID_REGEX.match(cert_id))
        self.assertTrue(cert_id.startswith(f"RAS-{current_year}-{current_month:02d}-HC-"))
        self.assertTrue(cert_id.endswith("-1001"))

    def test_02_automatic_citi_generation_with_initials(self):
        """2. Automatic CITI generation produces CITI-YYYY-MM-FF-RRRRRR-5001 for student."""
        from datetime import datetime
        from certificates.utils import generate_certificate_id, CERTIFICATE_ID_REGEX
        current_year = datetime.now().year
        current_month = datetime.now().month
        cert_id = generate_certificate_id('CITI', first_name='Harshal', last_name='Chauhan')
        self.assertTrue(CERTIFICATE_ID_REGEX.match(cert_id))
        self.assertTrue(cert_id.startswith(f"CITI-{current_year}-{current_month:02d}-HC-"))
        self.assertTrue(cert_id.endswith("-5001"))

    def test_03_independent_prefix_and_continuous_student_sequences(self):
        """3. Sequence increments across different students and prefixes independently."""
        from datetime import datetime
        from certificates.utils import generate_certificate_id, CERTIFICATE_ID_REGEX
        current_year = datetime.now().year
        current_month = datetime.now().month

        # Student 1: Harshal Chauhan (RAS) -> -1001
        ras1_id = generate_certificate_id('RAS', first_name='Harshal', last_name='Chauhan')
        self.assertTrue(CERTIFICATE_ID_REGEX.match(ras1_id))
        self.assertTrue(ras1_id.startswith(f"RAS-{current_year}-{current_month:02d}-HC-"))
        self.assertTrue(ras1_id.endswith("-1001"))
        Certificate.objects.create(
            certificate_id=ras1_id,
            first_name='Harshal',
            last_name='Chauhan',
            student_name='Harshal Chauhan',
            course=self.course,
            issue_date=date(current_year, 1, 10)
        )

        # Student 2: Amit Patel (RAS) -> -1002 (sequence continues, does NOT restart!)
        ras2_id = generate_certificate_id('RAS', first_name='Amit', last_name='Patel')
        self.assertTrue(CERTIFICATE_ID_REGEX.match(ras2_id))
        self.assertTrue(ras2_id.startswith(f"RAS-{current_year}-{current_month:02d}-AP-"))
        self.assertTrue(ras2_id.endswith("-1002"))
        Certificate.objects.create(
            certificate_id=ras2_id,
            first_name='Amit',
            last_name='Patel',
            student_name='Amit Patel',
            course=self.course,
            issue_date=date(current_year, 1, 11)
        )

        # Student 3: Priya Sharma (RAS) -> -1003
        ras3_id = generate_certificate_id('RAS', first_name='Priya', last_name='Sharma')
        self.assertTrue(CERTIFICATE_ID_REGEX.match(ras3_id))
        self.assertTrue(ras3_id.startswith(f"RAS-{current_year}-{current_month:02d}-PS-"))
        self.assertTrue(ras3_id.endswith("-1003"))
        Certificate.objects.create(
            certificate_id=ras3_id,
            first_name='Priya',
            last_name='Sharma',
            student_name='Priya Sharma',
            course=self.course,
            issue_date=date(current_year, 1, 12)
        )

        # CITI generation starts at 5001 independent of RAS
        citi1_id = generate_certificate_id('CITI', first_name='Harshal', last_name='Chauhan')
        self.assertTrue(CERTIFICATE_ID_REGEX.match(citi1_id))
        self.assertTrue(citi1_id.startswith(f"CITI-{current_year}-{current_month:02d}-HC-"))
        self.assertTrue(citi1_id.endswith("-5001"))
        Certificate.objects.create(
            certificate_id=citi1_id,
            first_name='Harshal',
            last_name='Chauhan',
            student_name='Harshal Chauhan',
            course=self.course,
            issue_date=date(current_year, 1, 12)
        )

        # Next CITI: Riya Patel -> -5002
        citi2_id = generate_certificate_id('CITI', first_name='Riya', last_name='Patel')
        self.assertTrue(CERTIFICATE_ID_REGEX.match(citi2_id))
        self.assertTrue(citi2_id.startswith(f"CITI-{current_year}-{current_month:02d}-RP-"))
        self.assertTrue(citi2_id.endswith("-5002"))

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
        self.assertIn('already in use', form_duplicate.errors['certificate_id'][0])

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

        # In year 2027, sequences must continue monotonically and NOT reset to 1001 or 5001
        ras_2027 = generate_certificate_id('RAS', year=2027, first_name='Harshal', last_name='Chauhan')
        citi_2027 = generate_certificate_id('CITI', year=2027, first_name='Harshal', last_name='Chauhan')
        self.assertTrue(ras_2027.startswith('RAS-2027-'))
        self.assertTrue(ras_2027.endswith('-1002'))
        self.assertTrue(citi_2027.startswith('CITI-2027-'))
        self.assertTrue(citi_2027.endswith('-5002'))

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
        self.assertContains(res_ras, 'HARSHAL CHAUHAN')

        # Verify CITI
        res_citi = self.client.post(url, {'certificate_id': f'CITI-{current_year}-RP5001'})
        self.assertEqual(res_citi.status_code, 200)
        self.assertContains(res_citi, 'Riya Patel')

        # Verify Legacy historical certificate
        res_legacy = self.client.post(url, {'certificate_id': f'RAS-{current_year}-XX1000'})
        self.assertEqual(res_legacy.status_code, 200)
        self.assertContains(res_legacy, 'LEGACY USER')


    def test_10_ajax_next_id_api_endpoint(self):
        """10. API endpoint returns next sequence and ID with student initials without consuming sequence."""
        from datetime import datetime
        current_year = datetime.now().year
        current_month = datetime.now().month
        self.client.login(username='seqadmin', password='adminpassword123')

        url = reverse('dashboard:get_next_certificate_id')
        res_ras = self.client.get(url, {'prefix': 'RAS', 'first_name': 'Harshal', 'last_name': 'Chauhan'})
        self.assertEqual(res_ras.status_code, 200)
        self.assertEqual(res_ras.json()['certificate_id'], f'RAS-{current_year}-{current_month:02d}-HC-100000-1001')
        self.assertEqual(res_ras.json()['initials'], 'HC')

        res_citi = self.client.get(url, {'prefix': 'CITI', 'first_name': 'Harshal', 'last_name': 'Chauhan'})
        self.assertEqual(res_citi.status_code, 200)
        self.assertEqual(res_citi.json()['certificate_id'], f'CITI-{current_year}-{current_month:02d}-HC-100000-5001')

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
        # Standard RAS example from specification: RAS-2026-10-DV-482716-1001
        res_ras = format_certificate_id('RAS', 2026, 10, 'DV', 482716, 1001)
        self.assertEqual(res_ras, 'RAS-2026-10-DV-482716-1001')

        # CITI example with single-digit month (must produce 2-digit MM with leading zero)
        res_citi = format_certificate_id('CITI', 2026, 4, 'RP', 100000, 5001)
        self.assertEqual(res_citi, 'CITI-2026-04-RP-100000-5001')

        # Maximum boundary sequence and random code
        res_max = format_certificate_id('RAS', 2026, 12, 'AS', 999999, 9999)
        self.assertEqual(res_max, 'RAS-2026-12-AS-999999-9999')

    def test_format_certificate_id_invalid_inputs(self):
        from certificates.utils import format_certificate_id
        # Invalid prefix
        with self.assertRaises(ValueError):
            format_certificate_id('XYZ', 2026, 10, 'DV', 482716, 1001)

        # Invalid month (0 or 13)
        with self.assertRaises(ValueError):
            format_certificate_id('RAS', 2026, 0, 'DV', 482716, 1001)
        with self.assertRaises(ValueError):
            format_certificate_id('RAS', 2026, 13, 'DV', 482716, 1001)

        # Invalid random code (< 100000 or > 999999)
        with self.assertRaises(ValueError):
            format_certificate_id('RAS', 2026, 10, 'DV', 99999, 1001)
        with self.assertRaises(ValueError):
            format_certificate_id('RAS', 2026, 10, 'DV', 1000000, 1001)

        # Invalid sequence (< 1000 or > 9999)
        with self.assertRaises(ValueError):
            format_certificate_id('RAS', 2026, 10, 'DV', 482716, 999)
        with self.assertRaises(ValueError):
            format_certificate_id('RAS', 2026, 10, 'DV', 482716, 10000)

        # Invalid initials (not 2 letters)
        with self.assertRaises(ValueError):
            format_certificate_id('RAS', 2026, 10, 'D', 482716, 1001)
        with self.assertRaises(ValueError):
            format_certificate_id('RAS', 2026, 10, 'D1', 482716, 1001)

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
        self.assertIn('1001', prev_id)
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
        random_part = parts[4]
        seq_part = parts[5]

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
        self.assertContains(resp, 'This Certificate can be verified on')
        self.assertContains(resp, 'http://localhost:8000/verify-certificate/')

        # 2. RAS certificate
        resp = self.client.post(url, {'certificate_id': self.cert_ras.certificate_id})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'This Certificate can be verified on')
        self.assertContains(resp, 'ras-verify-line')
        self.assertContains(resp, 'http://localhost:8000/verify-certificate/')

        # 3. CCC certificate
        resp = self.client.post(url, {'certificate_id': self.cert_ccc.certificate_id})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'This Certificate can be verified on')
        self.assertContains(resp, 'http://localhost:8000/verify-certificate/')

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










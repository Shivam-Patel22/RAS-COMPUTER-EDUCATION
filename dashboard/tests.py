from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

class DashboardTestCase(TestCase):
    def setUp(self):
        # Create non-staff student user
        self.student_user = User.objects.create_user(
            username='student@test.com',
            email='student@test.com',
            password='Password123!',
            is_staff=False
        )
        # Create staff admin user
        self.staff_user = User.objects.create_user(
            username='admin@test.com',
            email='admin@test.com',
            password='Password123!',
            is_staff=True
        )

    def test_unauthenticated_request_redirects_to_login(self):
        url = reverse('dashboard:index')
        response = self.client.get(url)
        self.assertRedirects(response, reverse('dashboard:login'))

    def test_non_staff_student_is_rejected(self):
        # Log in as non-staff student
        self.client.login(username='student@test.com', password='Password123!')
        url = reverse('dashboard:index')
        response = self.client.get(url)
        # Staff required decorator redirects non-staff user to dashboard:login with error message
        self.assertRedirects(response, reverse('dashboard:login'))

    def test_staff_admin_can_access_dashboard(self):
        self.client.login(username='admin@test.com', password='Password123!')
        url = reverse('dashboard:index')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/index.html')


class AdminAccountSettingsTestCase(TestCase):
    def setUp(self):
        self.staff_admin = User.objects.create_user(
            username='admin_boss',
            email='admin@cdac.test',
            password='CurrentStrongPassword123!',
            is_staff=True
        )
        self.other_user = User.objects.create_user(
            username='existing_user',
            email='existing@cdac.test',
            password='SomePassword123!',
            is_staff=False
        )

    def test_unauthenticated_access_redirects(self):
        for route_name in ['account_settings', 'change_username', 'change_password']:
            url = reverse(f'dashboard:{route_name}')
            response = self.client.get(url)
            self.assertRedirects(response, reverse('dashboard:login'))

    def test_non_staff_access_rejected(self):
        self.client.login(username='existing_user', password='SomePassword123!')
        url = reverse('dashboard:account_settings')
        response = self.client.get(url)
        self.assertRedirects(response, reverse('dashboard:login'))

    def test_staff_can_view_account_settings_page(self):
        self.client.login(username='admin_boss', password='CurrentStrongPassword123!')
        url = reverse('dashboard:account_settings')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/account_settings.html')
        self.assertContains(response, 'admin_boss')
        self.assertContains(response, 'Change Username')
        self.assertContains(response, 'Change Password')

    def test_change_username_success(self):
        self.client.login(username='admin_boss', password='CurrentStrongPassword123!')
        url = reverse('dashboard:change_username')
        response = self.client.post(url, {
            'action': 'change_username',
            'new_username': 'super_admin_new',
            'current_password': 'CurrentStrongPassword123!'
        })
        self.assertRedirects(response, reverse('dashboard:account_settings'))

        # Verify DB updated
        self.staff_admin.refresh_from_db()
        self.assertEqual(self.staff_admin.username, 'super_admin_new')

        # Verify can log in with new username
        self.client.logout()
        login_success = self.client.login(username='super_admin_new', password='CurrentStrongPassword123!')
        self.assertTrue(login_success)

    def test_change_username_wrong_password(self):
        self.client.login(username='admin_boss', password='CurrentStrongPassword123!')
        url = reverse('dashboard:change_username')
        response = self.client.post(url, {
            'action': 'change_username',
            'new_username': 'new_boss',
            'current_password': 'WrongPassword123!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['username_form'], 'current_password', 'Incorrect current password.')
        self.staff_admin.refresh_from_db()
        self.assertEqual(self.staff_admin.username, 'admin_boss')

    def test_change_username_duplicate_rejected(self):
        self.client.login(username='admin_boss', password='CurrentStrongPassword123!')
        url = reverse('dashboard:change_username')
        response = self.client.post(url, {
            'action': 'change_username',
            'new_username': 'existing_user',
            'current_password': 'CurrentStrongPassword123!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['username_form'], 'new_username', 'This username is already taken. Please choose another.')
        self.staff_admin.refresh_from_db()
        self.assertEqual(self.staff_admin.username, 'admin_boss')

    def test_change_username_same_as_current_rejected(self):
        self.client.login(username='admin_boss', password='CurrentStrongPassword123!')
        url = reverse('dashboard:change_username')
        response = self.client.post(url, {
            'action': 'change_username',
            'new_username': 'admin_boss',
            'current_password': 'CurrentStrongPassword123!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['username_form'], 'new_username', 'New username must be different from your current username.')

    def test_change_password_success_and_session_preserved(self):
        self.client.login(username='admin_boss', password='CurrentStrongPassword123!')
        url = reverse('dashboard:change_password')
        response = self.client.post(url, {
            'action': 'change_password',
            'current_password': 'CurrentStrongPassword123!',
            'new_password': 'BrandNewSecurePassword456!',
            'confirm_password': 'BrandNewSecurePassword456!'
        })
        self.assertRedirects(response, reverse('dashboard:account_settings'))

        # Check session is still authenticated without needing to re-login
        dashboard_url = reverse('dashboard:index')
        dash_response = self.client.get(dashboard_url)
        self.assertEqual(dash_response.status_code, 200)

        # Verify old password no longer works
        self.client.logout()
        old_login_success = self.client.login(username='admin_boss', password='CurrentStrongPassword123!')
        self.assertFalse(old_login_success)

        # Verify new password works
        new_login_success = self.client.login(username='admin_boss', password='BrandNewSecurePassword456!')
        self.assertTrue(new_login_success)

    def test_change_password_wrong_current_password(self):
        self.client.login(username='admin_boss', password='CurrentStrongPassword123!')
        url = reverse('dashboard:change_password')
        response = self.client.post(url, {
            'action': 'change_password',
            'current_password': 'WrongPassword!',
            'new_password': 'BrandNewSecurePassword456!',
            'confirm_password': 'BrandNewSecurePassword456!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['password_form'], 'current_password', 'Incorrect current password.')

    def test_change_password_mismatch(self):
        self.client.login(username='admin_boss', password='CurrentStrongPassword123!')
        url = reverse('dashboard:change_password')
        response = self.client.post(url, {
            'action': 'change_password',
            'current_password': 'CurrentStrongPassword123!',
            'new_password': 'BrandNewSecurePassword456!',
            'confirm_password': 'DifferentPassword456!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['password_form'], 'confirm_password', "The two password fields didn't match.")

    def test_change_password_too_short_validation(self):
        self.client.login(username='admin_boss', password='CurrentStrongPassword123!')
        url = reverse('dashboard:change_password')
        response = self.client.post(url, {
            'action': 'change_password',
            'current_password': 'CurrentStrongPassword123!',
            'new_password': '123',
            'confirm_password': '123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['password_form'].has_error('new_password'))


import time
from django.conf import settings

class AdminAutoLogoutSecurityTestCase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin_security_test',
            email='security@cdac.test',
            password='StrongSecurityPassword123!',
            is_staff=True
        )

    def test_security_settings_configured(self):
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        self.assertEqual(settings.SESSION_COOKIE_AGE, 3600)
        self.assertFalse(settings.SESSION_SAVE_EVERY_REQUEST)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')

    def test_no_cache_headers_on_admin_pages(self):
        self.client.login(username='admin_security_test', password='StrongSecurityPassword123!')
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))
        self.assertIn('no-cache', response.headers.get('Cache-Control', ''))
        self.assertEqual(response.headers.get('Pragma'), 'no-cache')
        self.assertEqual(response.headers.get('Expires'), '0')

    def test_no_cache_headers_not_on_public_pages(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        cache_control = response.headers.get('Cache-Control', '')
        self.assertNotIn('no-store', cache_control)

    def test_beacon_logout_endpoint(self):
        self.client.login(username='admin_security_test', password='StrongSecurityPassword123!')
        url = reverse('dashboard:beacon_logout')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 204)

        # Subsequent dashboard request must be redirected to login
        dash_response = self.client.get(reverse('dashboard:index'))
        self.assertRedirects(dash_response, reverse('dashboard:login'))

    def test_absolute_one_hour_timeout(self):
        self.client.login(username='admin_security_test', password='StrongSecurityPassword123!')
        
        # Set session admin_login_time to 3601 seconds ago (exceeded 1 hour)
        session = self.client.session
        session['admin_login_time'] = time.time() - 3601
        session.save()

        # Next request must be logged out and redirected to login
        response = self.client.get(reverse('dashboard:index'))
        self.assertRedirects(response, reverse('dashboard:login'))

        # Check session was invalidated
        dash_response = self.client.get(reverse('dashboard:index'))
        self.assertRedirects(dash_response, reverse('dashboard:login'))

    def test_active_session_under_one_hour_not_logged_out(self):
        self.client.login(username='admin_security_test', password='StrongSecurityPassword123!')
        
        # Set session admin_login_time to 1800 seconds ago (30 minutes)
        session = self.client.session
        session['admin_login_time'] = time.time() - 1800
        session.save()

        # Request succeeds
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)



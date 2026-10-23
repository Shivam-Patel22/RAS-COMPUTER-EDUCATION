import json
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import AboutContent, ContactContent

class RoleBasedNavigationAndLiveSyncTestCase(TestCase):
    def setUp(self):
        # Create regular student user
        self.student = User.objects.create_user(
            username='student_user',
            email='student@example.com',
            password='StudentPassword123!',
            is_staff=False,
            is_superuser=False
        )
        # Create staff administrator user
        self.staff_admin = User.objects.create_user(
            username='staff_admin_user',
            email='staff@example.com',
            password='AdminPassword123!',
            is_staff=True,
            is_superuser=False
        )

    # =========================================================================
    # 1. Regular User Role & Navigation Tests
    # =========================================================================
    def test_regular_user_accesses_user_panel_about_and_contact(self):
        self.client.login(username='student_user', password='StudentPassword123!')

        # About page renders in User Panel
        response_about = self.client.get(reverse('core:about'))
        self.assertEqual(response_about.status_code, 200)
        self.assertTemplateUsed(response_about, 'core/about.html')

        # Contact page renders in User Panel
        response_contact = self.client.get(reverse('core:contact'))
        self.assertEqual(response_contact.status_code, 200)
        self.assertTemplateUsed(response_contact, 'core/contact.html')

        # Student dashboard renders
        response_dash = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response_dash.status_code, 200)
        self.assertTemplateUsed(response_dash, 'accounts/dashboard.html')

    def test_regular_user_blocked_from_admin_panel(self):
        self.client.login(username='student_user', password='StudentPassword123!')

        # Admin index
        response_idx = self.client.get(reverse('dashboard:index'))
        self.assertRedirects(response_idx, reverse('dashboard:login'))

        # Admin edit about
        response_about = self.client.get(reverse('dashboard:edit_about'))
        self.assertRedirects(response_about, reverse('dashboard:login'))

        # Admin edit contact
        response_contact = self.client.get(reverse('dashboard:edit_contact'))
        self.assertRedirects(response_contact, reverse('dashboard:login'))

    def test_unauthenticated_user_redirected_to_student_login(self):
        url = reverse('accounts:dashboard')
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={url}")

    # =========================================================================
    # 2. Administrator Role & Navigation Tests
    # =========================================================================
    def test_admin_saves_about_remains_in_admin_panel(self):
        self.client.login(username='staff_admin_user', password='AdminPassword123!')

        post_data = {
            'heading': 'Updated Institute Heading',
            'subtitle': 'Updated Subtitle Text',
            'mission_title': 'Updated Mission',
            'description': 'Updated Description Content for C-DAC.',
            'feature_1_title': 'Feature 1',
            'feature_1_desc': 'Desc 1',
            'feature_2_title': 'Feature 2',
            'feature_2_desc': 'Desc 2',
            'feature_3_title': 'Feature 3',
            'feature_3_desc': 'Desc 3',
        }
        response = self.client.post(reverse('dashboard:edit_about'), post_data)
        # MUST redirect to dashboard:edit_about, NOT core:about!
        self.assertRedirects(response, reverse('dashboard:edit_about'))

        # Verify DB persisted
        about_obj = AboutContent.get_solo()
        self.assertEqual(about_obj.heading, 'Updated Institute Heading')

    def test_admin_saves_contact_remains_in_admin_panel(self):
        self.client.login(username='staff_admin_user', password='AdminPassword123!')

        post_data = {
            'phone': '+91 98765 00000',
            'whatsapp_number': '+91 98765 00001',
            'email': 'admin_contact@cdac.in',
            'address': 'Gandhinagar Sector 22',
            'working_hours': 'Mon-Fri: 9am-6pm',
            'map_embed_url': 'https://www.google.com/maps/embed?pb=test',
            'instagram_username': 'cdac_test',
            'instagram_url': 'https://www.instagram.com/cdac_test/',
            'facebook_name': 'CDAC Test Page',
            'facebook_url': 'https://www.facebook.com/cdactest/',
        }
        response = self.client.post(reverse('dashboard:edit_contact'), post_data)
        # MUST redirect to dashboard:edit_contact, NOT core:contact!
        self.assertRedirects(response, reverse('dashboard:edit_contact'))

        # Verify DB persisted
        contact_obj = ContactContent.get_solo()
        self.assertEqual(contact_obj.phone, '+91 98765 00000')

    def test_admin_visiting_student_routes_redirected_to_admin_panel(self):
        self.client.login(username='staff_admin_user', password='AdminPassword123!')

        # Student dashboard -> redirected to admin dashboard
        response_dash = self.client.get(reverse('accounts:dashboard'))
        self.assertRedirects(response_dash, reverse('dashboard:index'))

        # Student login -> redirected to admin dashboard
        response_login = self.client.get(reverse('accounts:login'))
        self.assertRedirects(response_login, reverse('dashboard:index'))

        # Student register -> redirected to admin dashboard
        response_reg = self.client.get(reverse('accounts:register'))
        self.assertRedirects(response_reg, reverse('dashboard:index'))

    # =========================================================================
    # 3. Live Sync API Tests
    # =========================================================================
    def test_live_sync_about_api_requires_staff(self):
        # Anonymous
        resp1 = self.client.post(reverse('dashboard:sync_about_api'), {'heading': 'Test'})
        self.assertRedirects(resp1, reverse('dashboard:login'))

        # Non-staff student
        self.client.login(username='student_user', password='StudentPassword123!')
        resp2 = self.client.post(reverse('dashboard:sync_about_api'), {'heading': 'Test'})
        self.assertRedirects(resp2, reverse('dashboard:login'))

    def test_live_sync_about_api_persists_changes(self):
        self.client.login(username='staff_admin_user', password='AdminPassword123!')

        sync_data = {
            'heading': 'Live Synced Heading',
            'subtitle': 'Live Synced Subtitle',
            'mission_title': 'Live Mission Title',
            'description': 'Real-time synchronized description text.',
            'feature_1_title': 'Sync Card 1',
            'feature_1_desc': 'Sync Desc 1',
            'feature_2_title': 'Sync Card 2',
            'feature_2_desc': 'Sync Desc 2',
            'feature_3_title': 'Sync Card 3',
            'feature_3_desc': 'Sync Desc 3',
        }
        response = self.client.post(
            reverse('dashboard:sync_about_api'),
            sync_data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['data']['heading'], 'Live Synced Heading')
        self.assertTrue('updated_at' in data)

        # Confirm persisted in database
        about_obj = AboutContent.get_solo()
        self.assertEqual(about_obj.heading, 'Live Synced Heading')
        self.assertEqual(about_obj.feature_1_title, 'Sync Card 1')

    def test_live_sync_about_api_validation_error(self):
        self.client.login(username='staff_admin_user', password='AdminPassword123!')

        # Empty heading (required field)
        sync_data = {
            'heading': '',
            'subtitle': 'Some Subtitle',
        }
        response = self.client.post(
            reverse('dashboard:sync_about_api'),
            sync_data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['status'], 'error')
        self.assertIn('heading', data['errors'])

    def test_live_sync_contact_api_persists_changes(self):
        self.client.login(username='staff_admin_user', password='AdminPassword123!')

        sync_data = {
            'phone': '+91 91234 56789',
            'whatsapp_number': '+91 91234 56780',
            'email': 'sync_contact@cdac.in',
            'address': 'Gandhinagar Campus, Sector 22',
            'working_hours': 'Mon - Sat: 8:00 AM - 8:00 PM',
            'map_embed_url': 'https://www.google.com/maps/embed?pb=live_sync_test',
            'instagram_username': 'cdac_live_sync',
            'instagram_url': 'https://www.instagram.com/cdac_live_sync/',
            'facebook_name': 'CDAC Live Sync Page',
            'facebook_url': 'https://www.facebook.com/cdaclivesync/',
        }
        response = self.client.post(
            reverse('dashboard:sync_contact_api'),
            sync_data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['data']['phone'], '+91 91234 56789')
        self.assertEqual(data['data']['display_instagram'], 'cdac_live_sync')

        # Confirm persisted in database
        contact_obj = ContactContent.get_solo()
        self.assertEqual(contact_obj.phone, '+91 91234 56789')
        self.assertEqual(contact_obj.email, 'sync_contact@cdac.in')

    def test_live_sync_contact_api_validation_error(self):
        self.client.login(username='staff_admin_user', password='AdminPassword123!')

        # Invalid email and empty phone
        sync_data = {
            'phone': '',
            'email': 'not-an-email',
            'address': 'Gandhinagar',
        }
        response = self.client.post(
            reverse('dashboard:sync_contact_api'),
            sync_data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['status'], 'error')
        self.assertIn('phone', data['errors'])
        self.assertIn('email', data['errors'])

    def test_status_apis(self):
        about_status_resp = self.client.get(reverse('dashboard:about_content_status_api'))
        self.assertEqual(about_status_resp.status_code, 200)
        self.assertIn('updated_at', about_status_resp.json())

        contact_status_resp = self.client.get(reverse('dashboard:contact_content_status_api'))
        self.assertEqual(contact_status_resp.status_code, 200)
        self.assertIn('updated_at', contact_status_resp.json())

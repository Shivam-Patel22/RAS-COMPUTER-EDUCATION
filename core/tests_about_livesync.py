import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import (
    AboutContent,
    DEFAULT_LEGACY_CARDS,
    DEFAULT_WHY_BENEFITS,
    DEFAULT_SPECS_CARDS,
    DEFAULT_TESTIMONIALS
)

class AboutSectionLiveSyncTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username='about_staff_admin',
            password='AdminPassword123!',
            is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username='about_regular_student',
            password='StudentPassword123!',
            is_staff=False
        )
        self.about_obj = AboutContent.get_solo()

    def test_admin_about_navigation_links_present(self):
        self.client.login(username='about_staff_admin', password='AdminPassword123!')
        
        # Admin dashboard overview
        res_dash = self.client.get(reverse('dashboard:index'))
        self.assertEqual(res_dash.status_code, 200)
        self.assertContains(res_dash, 'About Section Management')

        # Admin about edit page
        res_edit = self.client.get(reverse('dashboard:edit_about'))
        self.assertEqual(res_edit.status_code, 200)
        self.assertContains(res_edit, 'About Section Management')
        self.assertContains(res_edit, 'Section 1: Introduction')
        self.assertContains(res_edit, 'Section 2: Our Legacy of Excellence')
        self.assertContains(res_edit, 'Section 3: Why We Are the Best Computer Class')
        self.assertContains(res_edit, 'Section 4: Our Core Specializations')
        self.assertContains(res_edit, 'Section 5: Our Mission &amp; Vision')
        self.assertContains(res_edit, 'Section 6: Student Testimonials')
        self.assertContains(res_edit, 'Section 7: Bottom CTA Bar')

    def test_public_about_page_renders_all_six_sections(self):
        res = self.client.get(reverse('core:about'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        # Section 1: Intro
        self.assertIn('Premier Computer Institute in Gandhinagar', content)
        self.assertIn('Welcome to RAS Computer Education', content)

        # Section 2: Legacy
        self.assertIn('Our Legacy of Excellence', content)
        self.assertIn('20+ Years of Establishment', content)
        self.assertIn('15,000+ Students Trained', content)

        # Section 3: Why Choose Us
        self.assertIn('Why We Are the Best Computer Class in Gandhinagar', content)
        self.assertIn('What Sets Us Apart?', content)
        self.assertIn('Industry-Aligned Curriculum', content)

        # Section 4: Specializations
        self.assertIn('Our Core Specializations', content)
        self.assertIn('Best Tally Training Institute in Gandhinagar', content)
        self.assertIn('Best Coding Languages Institute in Gandhinagar', content)
        self.assertIn('Best CCC Training Institute', content)
        self.assertIn('Advanced Office &amp; Data Analysis Skills', content)

        # Section 5: Mission & Vision
        self.assertIn('Our Mission &amp; Vision', content)
        self.assertIn('Our Mission', content)
        self.assertIn('Our Vision', content)

        # Section 6: Testimonials
        self.assertIn('What Our Students Say', content)
        self.assertIn('Alumni Student', content)

        # Bottom CTA (removed from public page)

    def test_admin_can_update_all_six_sections_via_post(self):
        self.client.login(username='about_staff_admin', password='AdminPassword123!')
        v_init = self.about_obj.sync_version

        post_data = {
            'intro_badge': 'Award-Winning Tech Academy',
            'intro_heading': 'Welcome to Premier RAS Computer Education',
            'intro_lead': 'Updated custom lead paragraph.',
            'intro_text': 'Updated custom secondary paragraph.',
            'legacy_title': 'Decades of Tech Leadership',
            'legacy_desc': 'Our custom legacy description.',
            'legacy_cards_data': json.dumps([
                {
                    'id': 1,
                    'stat': '22+',
                    'title': '22+ Years of Impact',
                    'desc': 'Leading since inception.',
                    'color': 'orange',
                    'icon': 'clock'
                }
            ]),
            'why_title': 'Why Choose RAS Today',
            'why_desc': 'Unique advantages for modern careers.',
            'why_subheading': 'Our Core Distinctions',
            'why_benefits_data': json.dumps([
                {
                    'id': 1,
                    'title': 'Hands-on Projects',
                    'desc': 'Build live industry projects.',
                    'icon': 'book'
                }
            ]),
            'specs_title': 'Industry Career Programs',
            'specs_desc': 'Advanced technical curriculum.',
            'specs_cards_data': json.dumps([
                {
                    'id': 1,
                    'badge': 'Data & AI',
                    'badge_color': 'cyan',
                    'title': 'Advanced Python & Data Science',
                    'desc': 'Data analysis, pandas and machine learning.',
                    'desc2': 'Hands-on lab experiments.',
                    'highlights': [{'label': 'NumPy & Pandas:', 'text': 'Data structures and analysis'}],
                    'tags': ['Python', 'Data Science', 'Pandas']
                }
            ]),
            'mv_title': 'Guiding Principles',
            'mission_title': 'Dedicated Mission',
            'mission_text': 'Transform careers with modern tech.',
            'vision_title': 'Strategic Vision',
            'vision_text': 'Be the global benchmark.',
            'testimonials_title': 'Graduate Reviews',
            'testimonials_desc': 'Stories from placed graduates.',
            'testimonials_data': json.dumps([
                {
                    'id': 1,
                    'stars': 5,
                    'quote': 'The best learning experience ever!',
                    'author': 'Priya Sharma',
                    'tag': 'Software Engineer at TCS',
                    'avatar': 'PS'
                }
            ]),
            'cta_title': 'Start Your Journey Today',
            'cta_desc': 'Batches filling up fast.',
            'cta_btn1_text': 'Browse Courses',
            'cta_btn1_url': '/courses/',
            'cta_btn2_text': 'Get In Touch',
            'cta_btn2_url': '/contact/',
        }

        res = self.client.post(reverse('dashboard:edit_about'), post_data)
        self.assertRedirects(res, reverse('dashboard:edit_about'))

        # Check DB persistence
        updated_obj = AboutContent.get_solo()
        self.assertEqual(updated_obj.intro_heading, 'Welcome to Premier RAS Computer Education')
        self.assertEqual(updated_obj.legacy_title, 'Decades of Tech Leadership')
        self.assertEqual(len(updated_obj.get_legacy_cards()), 1)
        self.assertEqual(updated_obj.get_legacy_cards()[0]['stat'], '22+')
        self.assertEqual(len(updated_obj.get_why_benefits()), 1)
        self.assertEqual(len(updated_obj.get_specs_cards()), 1)
        self.assertEqual(len(updated_obj.get_testimonials()), 1)
        self.assertEqual(updated_obj.get_testimonials()[0]['author'], 'Priya Sharma')
        self.assertGreater(updated_obj.sync_version, v_init)

    def test_live_sync_api_updates_and_broadcasts_version(self):
        self.client.login(username='about_staff_admin', password='AdminPassword123!')
        v_init = self.about_obj.sync_version

        sync_payload = {
            'heading': 'Sync Test Heading',
            'intro_badge': 'Top Rated',
            'intro_heading': 'Sync Test Heading',
            'intro_lead': 'Lead paragraph synced in real time.',
            'legacy_title': 'Sync Legacy Title',
            'legacy_cards_data': json.dumps([
                {'id': 99, 'stat': '99%', 'title': '99% Placement', 'desc': 'Track record.', 'color': 'green', 'icon': 'award'}
            ]),
        }

        res = self.client.post(
            reverse('dashboard:sync_about_api'),
            sync_payload,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'success')
        self.assertGreater(data['version'], v_init)
        self.assertEqual(data['data']['intro_heading'], 'Sync Test Heading')
        self.assertEqual(data['data']['legacy_cards'][0]['stat'], '99%')

        # Public endpoint check with old version -> returns updated: True
        res_live_old = self.client.get(f"{reverse('core:about_live_sync')}?v={v_init}")
        self.assertEqual(res_live_old.status_code, 200)
        live_data = res_live_old.json()
        self.assertTrue(live_data['updated'])
        self.assertEqual(live_data['version'], data['version'])
        self.assertEqual(live_data['data']['intro_heading'], 'Sync Test Heading')

        # Public endpoint check with current version -> returns updated: False (no wasted payload)
        res_live_current = self.client.get(f"{reverse('core:about_live_sync')}?v={data['version']}")
        self.assertEqual(res_live_current.status_code, 200)
        current_data = res_live_current.json()
        self.assertFalse(current_data['updated'])

    def test_unauthenticated_and_regular_user_security(self):
        # 1. Anonymous user cannot edit
        res_anon_edit = self.client.get(reverse('dashboard:edit_about'))
        self.assertRedirects(res_anon_edit, reverse('dashboard:login'))

        res_anon_sync = self.client.post(reverse('dashboard:sync_about_api'), {'heading': 'Hack'})
        self.assertRedirects(res_anon_sync, reverse('dashboard:login'))

        # 2. Regular user (non-staff) cannot edit
        self.client.login(username='about_regular_student', password='StudentPassword123!')
        res_student_edit = self.client.get(reverse('dashboard:edit_about'))
        self.assertRedirects(res_student_edit, reverse('dashboard:login'))

        res_student_sync = self.client.post(reverse('dashboard:sync_about_api'), {'heading': 'Hack'})
        self.assertRedirects(res_student_sync, reverse('dashboard:login'))

        # 3. Public endpoints are accessible read-only
        self.client.logout()
        res_public_about = self.client.get(reverse('core:about'))
        self.assertEqual(res_public_about.status_code, 200)

        res_public_sync = self.client.get(reverse('core:about_live_sync'))
        self.assertEqual(res_public_sync.status_code, 200)

    def test_empty_state_and_defaults_fallback(self):
        # Even if legacy_cards is empty list in DB, get_legacy_cards() falls back to DEFAULT_LEGACY_CARDS
        obj = AboutContent.objects.create(
            heading='Blank Test',
            legacy_cards=[],
            why_benefits=[],
            specs_cards=[],
            testimonials=[]
        )
        self.assertEqual(len(obj.get_legacy_cards()), len(DEFAULT_LEGACY_CARDS))
        self.assertEqual(len(obj.get_why_benefits()), len(DEFAULT_WHY_BENEFITS))
        self.assertEqual(len(obj.get_specs_cards()), len(DEFAULT_SPECS_CARDS))
        self.assertEqual(len(obj.get_testimonials()), len(DEFAULT_TESTIMONIALS))

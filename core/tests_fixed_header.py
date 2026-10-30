from django.test import TestCase, Client
from django.urls import reverse
import os
from django.conf import settings


class FixedHeaderTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_user_panel_has_fixed_header_markup(self):
        """User panel base template must have .has-fixed-header on body and #site-header-fixed wrapper."""
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Check body class
        self.assertIn('class="has-fixed-header"', content)
        
        # Check container presence
        self.assertIn('id="site-header-fixed"', content)
        self.assertIn('class="site-header-fixed"', content)
        
        # Check ordering: navbar header is inside and before offers ticker
        navbar_pos = content.find('class="navbar-header"')
        site_header_pos = content.find('id="site-header-fixed"')
        self.assertTrue(site_header_pos != -1 and navbar_pos != -1)
        self.assertGreater(navbar_pos, site_header_pos)

    def test_admin_panel_does_not_have_user_fixed_header(self):
        """Admin panel base template must not have .site-header-fixed or .has-fixed-header."""
        admin_base_path = os.path.join(settings.BASE_DIR, 'templates', 'dashboard', 'admin_base.html')
        with open(admin_base_path, 'r', encoding='utf-8') as f:
            admin_content = f.read()
        self.assertNotIn('site-header-fixed', admin_content)
        self.assertNotIn('has-fixed-header', admin_content)

    def test_css_rules_for_fixed_header(self):
        """CSS must define .site-header-fixed, body.has-fixed-header, and scroll-padding-top."""
        css_path = os.path.join(settings.BASE_DIR, 'static', 'css', 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        # Check .site-header-fixed rules
        self.assertIn('.site-header-fixed', css)
        self.assertIn('position: fixed;', css)
        self.assertIn('body.has-fixed-header', css)
        self.assertIn('padding-top: var(--header-height);', css)
        self.assertIn('scroll-padding-top: var(--header-height);', css)
        
        # Check print styles
        self.assertIn('.site-header-fixed', css[css.find('@media print'):])

    def test_js_header_height_measures_fixed_header(self):
        """JavaScript must reference site-header-fixed to update --header-height."""
        js_path = os.path.join(settings.BASE_DIR, 'static', 'js', 'main.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            js = f.read()
        self.assertIn('site-header-fixed', js)

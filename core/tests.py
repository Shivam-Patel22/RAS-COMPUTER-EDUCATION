from django.test import TestCase
from django.urls import reverse
from courses.models import Course
from core.models import ContactContent, Inquiry

class CoreTestCase(TestCase):
    def setUp(self):
        self.course1 = Course.objects.create(name="Python Web Development", description="Learn Django & Python", duration="3 Months")
        self.course2 = Course.objects.create(name="Data Science Fundamentals", description="Learn Data Science", duration="6 Months")

    def test_contact_page_renders_with_courses(self):
        response = self.client.get(reverse('core:contact'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Full Name *")
        self.assertContains(response, "Phone Number *")
        self.assertContains(response, "Interested in Course")
        self.assertContains(response, "Python Web Development")
        self.assertContains(response, "Data Science Fundamentals")

    def test_contact_page_preselects_course_from_query_param(self):
        response = self.client.get(f"{reverse('core:contact')}?course={self.course1.id}")
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(form.initial.get('course'), str(self.course1.id))

    def test_contact_form_submission(self):
        from core.models import Inquiry
        data = {
            'name': 'Jane Student',
            'phone': '9876543210',
            'course': self.course1.id,
            'message': 'I would like to inquire about course fees and batch timings.',
        }
        response = self.client.post(reverse('core:contact'), data)
        self.assertRedirects(response, reverse('core:contact'))

        # Verify inquiry saved in database
        self.assertEqual(Inquiry.objects.count(), 1)
        inquiry = Inquiry.objects.first()
        self.assertEqual(inquiry.name, 'Jane Student')
        self.assertEqual(inquiry.phone, '9876543210')
        self.assertEqual(inquiry.course, self.course1)
        self.assertFalse(inquiry.is_read)

    def test_contact_form_submission_without_message(self):
        from core.models import Inquiry
        data = {
            'name': 'Bob Student',
            'phone': '9876543211',
            'course': self.course1.id,
            'message': '',
        }
        response = self.client.post(reverse('core:contact'), data)
        self.assertRedirects(response, reverse('core:contact'))

        self.assertEqual(Inquiry.objects.count(), 1)
        inquiry = Inquiry.objects.first()
        self.assertEqual(inquiry.name, 'Bob Student')
        self.assertEqual(inquiry.message, '')

    def test_contact_content_social_defaults(self):
        contact = ContactContent.get_solo()
        self.assertEqual(contact.instagram_username, "")
        self.assertEqual(contact.instagram_url, "")
        self.assertEqual(contact.facebook_name, "")
        self.assertEqual(contact.facebook_url, "")
        self.assertFalse(contact.has_instagram)
        self.assertFalse(contact.has_facebook)

    def test_contact_page_hides_unconfigured_social_media(self):
        contact = ContactContent.get_solo()
        contact.instagram_username = ""
        contact.instagram_url = ""
        contact.facebook_name = ""
        contact.facebook_url = ""
        contact.save()

        response = self.client.get(reverse('core:contact'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="contact-instagram-link"')
        self.assertNotContains(response, 'id="contact-facebook-link"')
        self.assertNotContains(response, 'id="footer-instagram-link"')
        self.assertNotContains(response, 'id="footer-facebook-link"')
        self.assertNotContains(response, '<strong>Instagram:</strong>')
        self.assertNotContains(response, '<strong>Facebook:</strong>')

    def test_contact_page_renders_configured_social_media(self):
        contact = ContactContent.get_solo()
        contact.instagram_username = "@cdac_official"
        contact.instagram_url = "https://www.instagram.com/cdac_official/"
        contact.facebook_name = "CDAC Computer Education"
        contact.facebook_url = "https://www.facebook.com/cdacclasses/"
        contact.save()

        response = self.client.get(reverse('core:contact'))
        self.assertEqual(response.status_code, 200)
        # Check Instagram presence in contact card
        self.assertContains(response, '<strong>Instagram:</strong>')
        self.assertContains(response, 'id="contact-instagram-link"')
        self.assertContains(response, 'href="https://www.instagram.com/cdac_official/"')
        self.assertContains(response, '@cdac_official')
        self.assertContains(response, 'target="_blank"')
        self.assertContains(response, 'rel="noopener noreferrer"')

        # Check Facebook presence in contact card
        self.assertContains(response, '<strong>Facebook:</strong>')
        self.assertContains(response, 'id="contact-facebook-link"')
        self.assertContains(response, 'href="https://www.facebook.com/cdacclasses/"')
        self.assertContains(response, 'CDAC Computer Education')

        # Check footer presence (global base.html)
        self.assertContains(response, 'id="footer-instagram-link"')
        self.assertContains(response, 'id="footer-facebook-link"')

    def test_contact_content_helper_properties(self):
        contact = ContactContent.get_solo()
        # Missing https scheme auto-cleanup
        contact.instagram_url = "instagram.com/cdac_official"
        contact.instagram_username = "cdac_official"
        self.assertEqual(contact.clean_instagram_url, "https://instagram.com/cdac_official")
        self.assertTrue(contact.has_instagram)

        # Fallback to username from URL if username blank
        contact.instagram_username = ""
        self.assertEqual(contact.display_instagram, "@cdac_official")

        contact.facebook_url = "facebook.com/cdac-pune"
        contact.facebook_name = ""
        self.assertEqual(contact.clean_facebook_url, "https://facebook.com/cdac-pune")
        self.assertEqual(contact.display_facebook, "Cdac Pune")
        self.assertTrue(contact.has_facebook)

    def test_admin_contact_form_social_validation(self):
        from dashboard.forms import AdminContactForm
        # Test valid submission
        valid_data = {
            'phone': '+91 (020) 2570-4100',
            'whatsapp_number': '919876543210',
            'email': 'contact@cdac.in',
            'address': 'Pune, Maharashtra',
            'working_hours': 'Mon - Sat: 9:00 AM - 6:00 PM',
            'map_embed_url': 'https://www.google.com/maps/embed?pb=1',
            'instagram_username': '@cdac_classes',
            'instagram_url': 'https://www.instagram.com/cdac_classes/',
            'facebook_name': 'CDAC Classes',
            'facebook_url': 'https://www.facebook.com/cdacclasses/',
        }
        form = AdminContactForm(data=valid_data)
        self.assertTrue(form.is_valid(), form.errors)

        # Test invalid Instagram URL (wrong domain)
        invalid_ig_data = valid_data.copy()
        invalid_ig_data['instagram_url'] = 'https://twitter.com/cdac'
        form = AdminContactForm(data=invalid_ig_data)
        self.assertFalse(form.is_valid())
        self.assertIn('instagram_url', form.errors)

        # Test invalid Facebook URL (wrong domain)
        invalid_fb_data = valid_data.copy()
        invalid_fb_data['facebook_url'] = 'https://linkedin.com/in/cdac'
        form = AdminContactForm(data=invalid_fb_data)
        self.assertFalse(form.is_valid())
        self.assertIn('facebook_url', form.errors)

    def test_admin_can_update_social_links_via_dashboard(self):
        from django.contrib.auth.models import User
        admin_user = User.objects.create_user(
            username='admin_test',
            email='admin_test@cdac.in',
            password='Password123!',
            is_staff=True
        )
        self.client.login(username='admin_test', password='Password123!')

        post_data = {
            'phone': '+91 99999 88888',
            'whatsapp_number': '919999988888',
            'email': 'info@cdac.in',
            'address': 'Pune Campus',
            'working_hours': '9am - 5pm',
            'map_embed_url': 'https://www.google.com/maps/embed?pb=2',
            'instagram_username': '@cdac_institute',
            'instagram_url': 'https://www.instagram.com/cdac_institute/',
            'facebook_name': 'CDAC Institute Official',
            'facebook_url': 'https://www.facebook.com/cdacinstitute/',
        }
        response = self.client.post(reverse('dashboard:edit_contact'), post_data)
        self.assertEqual(response.status_code, 302)

        contact = ContactContent.get_solo()
        self.assertEqual(contact.instagram_username, '@cdac_institute')
        self.assertEqual(contact.instagram_url, 'https://www.instagram.com/cdac_institute/')
        self.assertEqual(contact.facebook_name, 'CDAC Institute Official')
        self.assertEqual(contact.facebook_url, 'https://www.facebook.com/cdacinstitute/')

        # Verify reflected immediately on public contact page
        contact_page_resp = self.client.get(reverse('core:contact'))
        self.assertContains(contact_page_resp, '@cdac_institute')
        self.assertContains(contact_page_resp, 'CDAC Institute Official')
        self.assertContains(contact_page_resp, 'https://www.instagram.com/cdac_institute/')
        self.assertContains(contact_page_resp, 'https://www.facebook.com/cdacinstitute/')

    def test_google_review_button_rendered(self):
        response = self.client.get(reverse('core:contact'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="google-review-btn"')
        self.assertContains(response, 'Write a Google Review')
        self.assertContains(response, 'target="_blank"')
        self.assertContains(response, 'rel="noopener noreferrer"')
        self.assertContains(response, '4.9')
        self.assertContains(response, '400+')

    def test_justdial_reviews_display_active(self):
        from core.models import JustdialReview
        import datetime
        JustdialReview.objects.all().delete()
        JustdialReview.objects.create(
            reviewer_name="Rajesh Kumar",
            rating=5,
            review_text="Best training institute for accounting and GST.",
            review_date=datetime.date(2026, 1, 15),
            is_active=True,
            display_order=1
        )
        response = self.client.get(reverse('core:contact'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reviews from Justdial")
        self.assertContains(response, "Rajesh Kumar")
        self.assertContains(response, "Best training institute for accounting and GST.")
        self.assertContains(response, "via Justdial")
        self.assertContains(response, "★★★★★")
        self.assertContains(response, 'id="justdial-all-reviews-link"')

    def test_justdial_inactive_reviews_hidden(self):
        from core.models import JustdialReview
        JustdialReview.objects.all().delete()
        JustdialReview.objects.create(
            reviewer_name="Hidden Reviewer",
            rating=4,
            review_text="This should not be seen on public site.",
            is_active=False
        )
        response = self.client.get(reverse('core:contact'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Hidden Reviewer")
        self.assertNotContains(response, "ras-reviews-section")

    def test_justdial_review_xss_escaped(self):
        from core.models import JustdialReview
        JustdialReview.objects.all().delete()
        JustdialReview.objects.create(
            reviewer_name="Security Tester",
            rating=5,
            review_text="<script>alert('xss')</script><b>Bold Text</b>",
            is_active=True
        )
        response = self.client.get(reverse('core:contact'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<script>alert('xss')</script>")
        self.assertContains(response, "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;")

    def test_navbar_reviews_link(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/#reviews"')
        self.assertContains(response, '>Reviews<')

    def test_homepage_reviews_section_renders(self):
        from core.models import JustdialReview
        import datetime
        JustdialReview.objects.all().delete()
        JustdialReview.objects.create(
            reviewer_name="Bhavik Prajapati",
            rating=5,
            review_text="One of the best computer coaching institutes in Gandhinagar Sector 22.",
            review_date=datetime.date(2026, 1, 12),
            is_active=True,
            display_order=1
        )
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="reviews"')
        self.assertContains(response, 'Reviews from')
        self.assertContains(response, 'Bhavik Prajapati')
        self.assertContains(response, 'One of the best computer coaching institutes in Gandhinagar Sector 22.')
        self.assertContains(response, 'via Justdial')

    def test_homepage_reviews_section_hidden_when_no_active_reviews(self):
        from core.models import JustdialReview
        JustdialReview.objects.all().delete()
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="reviews"')





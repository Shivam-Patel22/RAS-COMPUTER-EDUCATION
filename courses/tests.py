import json
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from courses.models import Course, CourseOffer, CourseCategory
from dashboard.forms import AdminCourseForm

class CourseOfferTestCase(TestCase):
    def setUp(self):
        self.course = Course.objects.create(name="Python Masterclass", description="Python basics", duration="2 Months")
        self.today = timezone.now().date()

        self.active_offer = CourseOffer.objects.create(
            title="30% OFF on Python",
            badge="🎉 SPECIAL OFFER",
            discount="30% OFF",
            course=self.course,
            status="active"
        )
        self.scheduled_offer = CourseOffer.objects.create(
            title="Future Batch Discount",
            start_date=self.today + timedelta(days=5),
            status="active"
        )
        self.expired_offer = CourseOffer.objects.create(
            title="Old Summer Sale",
            end_date=self.today - timedelta(days=2),
            status="active"
        )
        self.inactive_offer = CourseOffer.objects.create(
            title="Draft Offer",
            status="inactive"
        )

    def test_offer_computed_statuses(self):
        self.assertEqual(self.active_offer.computed_status, "Active")
        self.assertEqual(self.scheduled_offer.computed_status, "Scheduled")
        self.assertEqual(self.expired_offer.computed_status, "Expired")
        self.assertEqual(self.inactive_offer.computed_status, "Inactive")

    def test_is_currently_active(self):
        self.assertTrue(self.active_offer.is_currently_active)
        self.assertFalse(self.scheduled_offer.is_currently_active)
        self.assertFalse(self.expired_offer.is_currently_active)
        self.assertFalse(self.inactive_offer.is_currently_active)

    def test_ticker_context_processor_filters_only_active_offers(self):
        session = self.client.session
        session['is_guest'] = True
        session.save()
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        ticker_offers = response.context['latest_offers']
        self.assertIn(self.active_offer, ticker_offers)
        self.assertNotIn(self.scheduled_offer, ticker_offers)
        self.assertNotIn(self.expired_offer, ticker_offers)
        self.assertNotIn(self.inactive_offer, ticker_offers)


class CourseImageDisplayTestCase(TestCase):
    def setUp(self):
        # Create 1x1 GIF as a valid image
        self.test_image = SimpleUploadedFile(
            name='test_course.gif',
            content=b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;',
            content_type='image/gif'
        )
        self.course_with_img = Course.objects.create(
            name="Django Web Development",
            category="programming",
            description="Complete Django backend course",
            duration="3 Months",
            image=self.test_image
        )
        self.course_no_img = Course.objects.create(
            name="Data Entry Basics",
            category="basic",
            description="Data entry fundamentals",
            duration="1 Month"
        )

    def tearDown(self):
        if self.course_with_img.image:
            self.course_with_img.image.delete(save=False)

    def test_image_url_or_default(self):
        self.assertTrue(self.course_with_img.image_url_or_default.startswith('/media/courses/test_course'))
        self.assertEqual(self.course_no_img.image_url_or_default, '')

    def test_course_list_includes_image_urls(self):
        session = self.client.session
        session['is_guest'] = True
        session.save()
        response = self.client.get(reverse('courses:course_list'))
        self.assertEqual(response.status_code, 200)

        courses_data = json.loads(response.context['courses_json'])
        programming_cat = next((c for c in courses_data if c['id'] == 'programming'), None)
        self.assertIsNotNone(programming_cat)

        django_sub = next((s for s in programming_cat['subCourses'] if s['id'] == self.course_with_img.id), None)
        self.assertIsNotNone(django_sub)
        self.assertTrue(django_sub['image_url'].startswith('/media/courses/test_course'))

        basic_cat = next((c for c in courses_data if c['id'] == 'basic'), None)
        self.assertIsNotNone(basic_cat)
        basic_sub = next((s for s in basic_cat['subCourses'] if s['id'] == self.course_no_img.id), None)
        self.assertIsNotNone(basic_sub)
        self.assertEqual(basic_sub['image_url'], '')

    def test_course_detail_view_renders_image(self):
        session = self.client.session
        session['is_guest'] = True
        session.save()

        # Course with image
        res1 = self.client.get(reverse('courses:course_detail', args=[self.course_with_img.id]))
        self.assertEqual(res1.status_code, 200)
        self.assertContains(res1, self.course_with_img.image.url)

        # Course without image
        res2 = self.client.get(reverse('courses:course_detail', args=[self.course_no_img.id]))
        self.assertEqual(res2.status_code, 200)
        self.assertContains(res2, '🖥️')

    def test_admin_course_form_validation_and_removal(self):
        # Invalid file type test
        text_file = SimpleUploadedFile("fake.txt", b"not an image", content_type="text/plain")
        form_invalid = AdminCourseForm(
            data={
                'name': 'Test Invalid',
                'category': 'basic',
                'duration': '1 Month',
                'description': 'Testing invalid file'
            },
            files={'image': text_file}
        )
        self.assertFalse(form_invalid.is_valid())
        self.assertIn('image', form_invalid.errors)

        # Image removal test
        form_remove = AdminCourseForm(
            data={
                'name': self.course_with_img.name,
                'category': self.course_with_img.category,
                'duration': self.course_with_img.duration,
                'description': self.course_with_img.description,
                'remove_image': True
            },
            instance=self.course_with_img
        )
        self.assertTrue(form_remove.is_valid())
        saved_course = form_remove.save()
        self.assertFalse(bool(saved_course.image))


class CourseDescriptionAndDetailsTestCase(TestCase):
    def setUp(self):
        self.long_c_description = (
            "# C Programming Course\n\n"
            "## Course Description\n"
            "The C Programming Course is designed to help students build a strong foundation in programming "
            "and problem-solving. Students will learn the fundamentals of C programming, including variables, "
            "data types, operators, conditional statements, loops, arrays, strings, functions, pointers, "
            "structures, and file handling.\n\n"
            "## Course Syllabus\n\n"
            "**Module 1: Introduction to C Programming**\n"
            "- Introduction to programming and the C language\n"
            "- Structure of a C program\n"
            "- Installing and using a C compiler\n\n"
            "**Module 2: Fundamentals of C**\n"
            "- Data types and type conversion\n"
            "- Input and output functions (`printf()` and `scanf()`)\n\n"
            "## Learning Outcomes\n"
            "- Write, compile, debug, and execute C programs.\n\n"
            "**Prerequisites:** Basic computer knowledge."
        )
        self.c_course = Course.objects.create(
            name="C Programming",
            category="programming",
            description=self.long_c_description,
            duration="2 Months",
            fee=8500.00
        )

    def test_clean_preview_description_removes_headings_and_syllabus(self):
        preview = self.c_course.clean_preview_description
        # Headings should not be in preview
        self.assertNotIn("#", preview)
        self.assertNotIn("Course Syllabus", preview)
        self.assertNotIn("Module 1", preview)
        # Should start with the actual description text
        self.assertTrue(preview.startswith("The C Programming Course is designed to help students"))

    def test_formatted_description_html_renders_markdown_elements(self):
        html_out = self.c_course.formatted_description_html
        # Headings
        self.assertIn('<h2 class="course-h2">C Programming Course</h2>', html_out)
        self.assertIn('<h3 class="course-h3">Course Description</h3>', html_out)
        self.assertIn('<h3 class="course-h3">Course Syllabus</h3>', html_out)
        # Bold
        self.assertIn('<strong>Module 1: Introduction to C Programming</strong>', html_out)
        # Bullet list
        self.assertIn('<ul class="course-bullet-list">', html_out)
        self.assertIn('<li>Introduction to programming and the C language</li>', html_out)
        # Code
        self.assertIn('<code class="course-inline-code">printf()</code>', html_out)
        # Paragraph
        self.assertIn('class="course-text-para"', html_out)

    def test_course_detail_view_renders_full_content_and_fee(self):
        session = self.client.session
        session['is_guest'] = True
        session.save()
        res = self.client.get(reverse('courses:course_detail', args=[self.c_course.id]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "C Programming")
        self.assertContains(res, "₹8500")
        self.assertContains(res, "Course Syllabus")
        self.assertContains(res, "Module 1: Introduction to C Programming")
        self.assertContains(res, "printf()")

    def test_course_list_includes_preview_and_full_description(self):
        session = self.client.session
        session['is_guest'] = True
        session.save()
        res = self.client.get(reverse('courses:course_list'))
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.context['courses_json'])
        programming_cat = next((c for c in data if c['id'] == 'programming'), None)
        self.assertIsNotNone(programming_cat)
        sub = next((s for s in programming_cat['subCourses'] if s['id'] == self.c_course.id), None)
        self.assertIsNotNone(sub)
        self.assertIn('preview_description', sub)
        self.assertNotIn('## Course Syllabus', sub['preview_description'])
        self.assertIn('## Course Syllabus', sub['description'])
        self.assertEqual(sub['fee'], '₹8,500')



class DynamicCourseCategoryTestCase(TestCase):
    def setUp(self):
        self.cat1 = CourseCategory.objects.create(
            name="Cloud Computing",
            slug="cloud-computing",
            icon="☁️",
            description="AWS, Azure and DevOps cloud engineering",
            duration="6 Months",
            display_order=10,
            is_active=True
        )

    def test_new_category_appears_dynamically_in_user_panel(self):
        """Newly created category should automatically appear in course_list without template changes."""
        response = self.client.get(reverse('courses:course_list'))
        self.assertEqual(response.status_code, 200)
        courses_json = response.context['courses_json']
        data = json.loads(courses_json)
        cat_ids = [c['id'] for c in data]
        self.assertIn('cloud-computing', cat_ids)

        cloud_cat = next(c for c in data if c['id'] == 'cloud-computing')
        self.assertEqual(cloud_cat['name'], 'Cloud Computing')
        self.assertEqual(cloud_cat['icon'], '☁️')
        self.assertEqual(cloud_cat['description'], 'AWS, Azure and DevOps cloud engineering')
        self.assertEqual(len(cloud_cat['subCourses']), 0)

    def test_subcourse_count_calculated_from_database(self):
        """Adding sub-courses dynamically increases the sub-courses count for that category."""
        Course.objects.create(
            name="AWS Certified Solutions Architect",
            category_ref=self.cat1,
            duration="3 Months"
        )
        Course.objects.create(
            name="Azure Cloud Fundamentals",
            category_ref=self.cat1,
            duration="2 Months"
        )

        response = self.client.get(reverse('courses:course_list'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.context['courses_json'])
        cloud_cat = next(c for c in data if c['id'] == 'cloud-computing')
        self.assertEqual(len(cloud_cat['subCourses']), 2)
        sub_names = [s['name'] for s in cloud_cat['subCourses']]
        self.assertIn("AWS Certified Solutions Architect", sub_names)
        self.assertIn("Azure Cloud Fundamentals", sub_names)

    def test_edit_category_updates_card_automatically(self):
        """Editing category in admin/DB automatically updates the user panel card."""
        self.cat1.name = "Cloud & DevOps Architecture"
        self.cat1.icon = "⚡"
        self.cat1.description = "Updated DevOps syllabus with Kubernetes"
        self.cat1.save()

        response = self.client.get(reverse('courses:course_list'))
        data = json.loads(response.context['courses_json'])
        cloud_cat = next(c for c in data if c['id'] == self.cat1.slug)
        self.assertEqual(cloud_cat['name'], "Cloud & DevOps Architecture")
        self.assertEqual(cloud_cat['icon'], "⚡")
        self.assertEqual(cloud_cat['description'], "Updated DevOps syllabus with Kubernetes")

    def test_deactivated_category_hidden_from_user_panel(self):
        """Deactivating category removes its card from user panel without breaking courses."""
        course = Course.objects.create(
            name="DevOps CI/CD",
            category_ref=self.cat1,
            duration="1 Month"
        )

        self.cat1.is_active = False
        self.cat1.save()

        response = self.client.get(reverse('courses:course_list'))
        data = json.loads(response.context['courses_json'])
        cat_ids = [c['id'] for c in data]
        self.assertNotIn('cloud-computing', cat_ids)

        # Confirm course record still intact in database
        course.refresh_from_db()
        self.assertEqual(course.category_ref, self.cat1)

    def test_deleted_category_preserves_courses_safely(self):
        """Deleting a category unlinks category_ref without deleting the course."""
        course = Course.objects.create(
            name="Kubernetes Administration",
            category_ref=self.cat1,
            duration="2 Months"
        )
        course_id = course.id
        self.cat1.delete()

        # Course should still exist
        course_after = Course.objects.get(id=course_id)
        self.assertIsNone(course_after.category_ref)

        # Category should no longer be in user panel
        response = self.client.get(reverse('courses:course_list'))
        data = json.loads(response.context['courses_json'])
        cat_ids = [c['id'] for c in data]
        self.assertNotIn('cloud-computing', cat_ids)

    def test_category_ordering_by_display_order(self):
        """Categories are displayed in order of display_order."""
        cat_early = CourseCategory.objects.create(
            name="Cyber Security",
            slug="cyber-security",
            display_order=0,
            is_active=True
        )
        response = self.client.get(reverse('courses:course_list'))
        data = json.loads(response.context['courses_json'])
        self.assertEqual(data[0]['id'], 'cyber-security')

    def test_admin_panel_crud_and_user_panel_appearance(self):
        """Admin can create a category via Django admin, add sub-courses, and see it in user panel."""
        from django.contrib.auth.models import User
        admin_user = User.objects.create_superuser(username='admin_test', email='admin@test.com', password='password123')
        self.client.login(username='admin_test', password='password123')

        # 1. Admin adds a new category
        response = self.client.post(reverse('admin:courses_coursecategory_add'), {
            'name': 'Data Analytics',
            'slug': 'data-analytics',
            'icon': '📈',
            'description': 'Advanced Data Analysis with Power BI, Excel & SQL',
            'duration': '4 Months',
            'display_order': 8,
            'is_active': True,
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        new_cat = CourseCategory.objects.filter(slug='data-analytics').first()
        self.assertIsNotNone(new_cat)
        self.assertEqual(new_cat.name, 'Data Analytics')

        # 2. Admin adds a course under this category
        response = self.client.post(reverse('admin:courses_course_add'), {
            'name': 'Power BI for Business Analytics',
            'category_ref': new_cat.pk,
            'description': 'Master Power BI dashboards and DAX',
            'duration': '2 Months',
            'fee': 6000,
            'slug': 'power-bi-business-analytics',
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        # 3. User Panel automatically reflects this category card and sub-course
        self.client.logout()
        user_response = self.client.get(reverse('courses:course_list'))
        self.assertEqual(user_response.status_code, 200)
        data = json.loads(user_response.context['courses_json'])

        matched_cat = next((c for c in data if c['id'] == 'data-analytics'), None)
        self.assertIsNotNone(matched_cat)
        self.assertEqual(matched_cat['name'], 'Data Analytics')
        self.assertEqual(matched_cat['icon'], '📈')
        self.assertEqual(len(matched_cat['subCourses']), 1)
        self.assertEqual(matched_cat['subCourses'][0]['name'], 'Power BI for Business Analytics')

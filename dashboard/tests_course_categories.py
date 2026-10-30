from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from courses.models import Course, CourseCategory


class CourseCategoryAdminTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='admin_cat_test',
            email='admin_cat@test.com',
            password='AdminPassword123!'
        )
        self.client.login(username='admin_cat_test', password='AdminPassword123!')

        self.cat1 = CourseCategory.objects.create(name='Programming & Development', slug='programming-development')
        self.cat2 = CourseCategory.objects.create(name='Basic Literacy', slug='basic-literacy')

    def test_manage_course_categories_view(self):
        url = reverse('dashboard:manage_course_categories')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Programming &amp; Development')
        self.assertContains(response, 'Basic Literacy')
        self.assertContains(response, 'Manage Course Categories')

    def test_add_course_category_success_and_duplicate_prevention(self):
        add_url = reverse('dashboard:add_course_category')
        
        # Duplicate name should fail
        res_dup = self.client.post(add_url, {'name': 'Programming & Development'})
        self.assertEqual(res_dup.status_code, 200)
        self.assertContains(res_dup, 'already exists')

        # New name should succeed
        res_ok = self.client.post(add_url, {'name': 'Cyber Security', 'description': 'Security tracks'})
        self.assertEqual(res_ok.status_code, 302)
        self.assertTrue(CourseCategory.objects.filter(name='Cyber Security').exists())

    def test_edit_course_category(self):
        edit_url = reverse('dashboard:edit_course_category', kwargs={'pk': self.cat2.pk})
        res = self.client.post(edit_url, {'name': 'Updated Basic Category'})
        self.assertEqual(res.status_code, 302)
        self.cat2.refresh_from_db()
        self.assertEqual(self.cat2.name, 'Updated Basic Category')

    def test_create_and_edit_course_with_category(self):
        add_course_url = reverse('dashboard:add_course')
        res = self.client.post(add_course_url, {
            'name': 'Python for Beginners',
            'category': self.cat1.pk,
            'duration': '2 Months',
            'description': 'Beginner python course',
        })
        self.assertEqual(res.status_code, 302)
        course = Course.objects.get(name='Python for Beginners')
        self.assertEqual(course.category_ref, self.cat1)
        self.assertEqual(course.category, self.cat1.slug)
        self.assertEqual(course.get_category_display(), 'Programming & Development')

        # Edit course and change category
        edit_course_url = reverse('dashboard:edit_course', kwargs={'pk': course.pk})
        res_edit = self.client.post(edit_course_url, {
            'name': 'Python for Beginners',
            'category': self.cat2.pk,
            'duration': '2 Months',
            'description': 'Beginner python course',
        })
        self.assertEqual(res_edit.status_code, 302)
        course.refresh_from_db()
        self.assertEqual(course.category_ref, self.cat2)

    def test_course_without_category_works(self):
        add_course_url = reverse('dashboard:add_course')
        res = self.client.post(add_course_url, {
            'name': 'General Course Without Cat',
            'category': '',
            'duration': '1 Month',
            'description': 'General overview',
        })
        self.assertEqual(res.status_code, 302)
        course = Course.objects.get(name='General Course Without Cat')
        self.assertIsNone(course.category_ref)
        self.assertEqual(course.category, '')
        self.assertEqual(course.get_category_display(), 'Uncategorized')

    def test_delete_course_category_unlinks_courses_without_deleting_them(self):
        course = Course.objects.create(
            name='Java Masterclass',
            category_ref=self.cat1,
            category=self.cat1.slug,
            duration='3 Months',
            description='Java'
        )
        delete_url = reverse('dashboard:delete_course_category', kwargs={'pk': self.cat1.pk})
        res = self.client.post(delete_url)
        self.assertEqual(res.status_code, 302)
        self.assertFalse(CourseCategory.objects.filter(pk=self.cat1.pk).exists())
        # Course still exists!
        course.refresh_from_db()
        self.assertIsNone(course.category_ref)
        self.assertEqual(course.category, '')

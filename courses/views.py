import json
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Course, CourseCategory

CATEGORY_METADATA = {
    'basic': {
        'id': 'basic',
        'name': 'Basic',
        'icon': '💻',
        'description': 'Essential computer fundamentals, office productivity software, data entry, desktop publishing, and CAD basics.',
        'duration': 'Basic Skills'
    },
    'accounting': {
        'id': 'accounting',
        'name': 'Accounting',
        'icon': '📊',
        'description': 'Professional computerized financial accounting, Tally Prime modules, GST compliance, and inventory management.',
        'duration': 'Specialized'
    },
    'programming': {
        'name': 'Programming',
        'id': 'programming',
        'icon': '⚙️',
        'description': 'Core and object-oriented programming languages, web scripting, backend technology, and database management.',
        'duration': 'Modular Tracks'
    },
    'diploma-6-months': {
        'id': 'diploma-6-months',
        'name': 'Diploma (6 Months)',
        'icon': '🎓',
        'description': 'Structured 6-month career diploma programs designed for specialized technical employment readiness.',
        'duration': '6 Months'
    },
    'advance-diploma-12-months': {
        'id': 'advance-diploma-12-months',
        'name': 'Advance Diploma (12 Months)',
        'icon': '🏆',
        'description': 'Comprehensive 12-month master diploma programs offering extensive practical training and domain mastery.',
        'duration': '12 Months'
    },
    'frontend-full-stack-development': {
        'id': 'frontend-full-stack-development',
        'name': 'Frontend / Full Stack Development',
        'icon': '🚀',
        'description': 'Modern web stack specializations, full stack frameworks, mobile app engineering, and UI/UX design.',
        'duration': 'Career Track'
    },
    'modular-courses': {
        'id': 'modular-courses',
        'name': 'Modular Courses',
        'icon': '🧩',
        'description': 'Focused standalone technical skill modules for specialized creative, analytical, and technical software.',
        'duration': 'Flexible'
    }
}

def course_list(request):
    # Fetch all active categories dynamically from the database
    active_categories = CourseCategory.objects.filter(is_active=True).order_by('display_order', 'id')
    all_cat_names = set(CourseCategory.objects.values_list('name', flat=True))

    categories_dict = {}
    for cat in active_categories:
        cat_key = cat.slug or str(cat.id)
        categories_dict[cat_key] = {
            'id': cat_key,
            'pk': cat.pk,
            'name': cat.name,
            'icon': cat.icon or '💻',
            'description': cat.description,
            'duration': cat.duration,
            'subCourses': []
        }

    # Group database courses dynamically
    db_courses = Course.objects.all().select_related('category_ref').order_by('created_at')

    for course in db_courses:
        image_url = course.image_url_or_default

        # Category cover placeholder course handling
        if course.name in all_cat_names:
            for c_id, c_data in categories_dict.items():
                if c_data['name'] == course.name and image_url:
                    c_data['image_url'] = image_url
            continue

        cat_key = None
        if course.category_ref and course.category_ref.slug in categories_dict:
            cat_key = course.category_ref.slug
        elif course.category and course.category in categories_dict:
            cat_key = course.category

        if cat_key:
            categories_dict[cat_key]['subCourses'].append({
                'id': course.id,
                'name': course.name,
                'description': course.description or f"Professional {course.name} course program tailored with practical lab training and certification.",
                'preview_description': course.clean_preview_description,
                'duration': course.duration or categories_dict[cat_key]['duration'],
                'fee': f"₹{course.fee:,.0f}" if course.fee else '',
                'image_url': image_url,
            })

    courses_data_list = list(categories_dict.values())

    return render(request, 'courses/course_list.html', {
        'courses_json': json.dumps(courses_data_list),
        'courses': db_courses
    })

def course_detail(request, pk=None, slug=None):
    if pk is not None:
        course = get_object_or_404(Course, pk=pk)
    else:
        course = get_object_or_404(Course, slug=slug)

    # Contextual related courses within same category for SEO internal linking
    if course.category_ref:
        cat_query = Q(category_ref=course.category_ref) | Q(category=course.category_ref.slug)
    elif course.category:
        cat_query = Q(category=course.category)
    else:
        cat_query = Q(pk=course.pk)

    related_courses = Course.objects.filter(cat_query).exclude(pk=course.pk).order_by('name')[:4]

    return render(request, 'courses/course_detail.html', {
        'course': course,
        'related_courses': related_courses,
    })

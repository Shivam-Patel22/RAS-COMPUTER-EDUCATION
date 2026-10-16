import json
from django.shortcuts import render, get_object_or_404
from .models import Course

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
        'id': 'programming',
        'name': 'Programming',
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
    db_courses = Course.objects.all().order_by('created_at')

    # Prepare categories dictionary
    categories_dict = {}
    for cat_id, cat_info in CATEGORY_METADATA.items():
        categories_dict[cat_id] = {
            'id': cat_info['id'],
            'name': cat_info['name'],
            'icon': cat_info['icon'],
            'description': cat_info['description'],
            'duration': cat_info['duration'],
            'subCourses': []
        }

    # Group database courses dynamically
    for course in db_courses:
        image_url = course.image_url_or_default

        if course.name in [c['name'] for c in CATEGORY_METADATA.values()]:
            for c_id, c_data in CATEGORY_METADATA.items():
                if c_data['name'] == course.name and image_url:
                    categories_dict[c_id]['image_url'] = image_url
            continue

        cat_key = course.category if course.category in categories_dict else 'basic'
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

def course_detail(request, pk):
    course = get_object_or_404(Course, pk=pk)
    return render(request, 'courses/course_detail.html', {'course': course})

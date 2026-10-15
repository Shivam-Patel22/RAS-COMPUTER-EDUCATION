from datetime import date, datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone as tz
from django.contrib.auth.models import User
from courses.models import Course, CourseOffer
from certificates.models import Certificate
from accounts.models import StudentProfile
from core.models import Inquiry, InquiryFollowUp, AboutContent, ContactContent

class Command(BaseCommand):
    help = 'Seeds initial sample data for all models in the database'

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write("Starting comprehensive database seeding...")
        self.stdout.write("=" * 60)

        # 1. Create Superuser and Staff User
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@cdac.in',
                'first_name': 'System',
                'last_name': 'Administrator',
                'is_staff': True,
                'is_superuser': True
            }
        )
        admin_user.set_password('adminpassword123')
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()
        self.stdout.write(self.style.SUCCESS(f"[OK] Admin User: '{admin_user.username}' (Password: adminpassword123)"))

        instructor_user, created = User.objects.get_or_create(
            username='instructor',
            defaults={
                'email': 'instructor@cdac.in',
                'first_name': 'Vikram',
                'last_name': 'Sharma',
                'is_staff': True,
                'is_superuser': False
            }
        )
        instructor_user.set_password('staffpassword123')
        instructor_user.is_staff = True
        instructor_user.save()
        self.stdout.write(self.style.SUCCESS(f"[OK] Staff Instructor: '{instructor_user.username}' (Password: staffpassword123)"))

        # 2. Seed Courses
        from django.core.management import call_command
        call_command('sync_courses')

        courses_data = [
            {
                'name': 'Python Web Development (Django & FastAPI)',
                'description': 'Master backend web development using Python, Django, REST APIs, and PostgreSQL. Build scalable real-world applications with modern deployment patterns.',
                'duration': '3 Months',
                'fee': 15000.00,
                'is_featured': True
            },
            {
                'name': 'Full Stack Web Development (MERN Stack)',
                'description': 'Comprehensive training in React.js, Node.js, Express, and MongoDB with modern frontend design, JWT authentication, and full-stack API integration.',
                'duration': '6 Months',
                'fee': 25000.00,
                'is_featured': True
            },
            {
                'name': 'Data Science & Machine Learning',
                'description': 'Hands-on course covering Python for Data Analysis, Pandas, NumPy, Scikit-Learn, TensorFlow, and statistical machine learning models.',
                'duration': '4 Months',
                'fee': 20000.00,
                'is_featured': True
            },
            {
                'name': 'Certificate Course in Financial Accounting (Tally Prime & GST)',
                'description': 'Practical accounting training on Tally Prime, GST filing, inventory management, taxation compliance, and computerized bookkeeping.',
                'duration': '2 Months',
                'fee': 8000.00,
                'is_featured': False
            },
            {
                'name': 'Cyber Security & Ethical Hacking',
                'description': 'Learn network security, vulnerability assessment, penetration testing fundamentals, web application security, and ethical hacking protocols.',
                'duration': '3 Months',
                'fee': 18000.00,
                'is_featured': False
            },
            {
                'name': 'Java Full Stack Software Engineering',
                'description': 'Enterprise application development with Java 17+, Spring Boot, Hibernate, microservices architecture, and Angular frontend integration.',
                'duration': '6 Months',
                'fee': 24000.00,
                'is_featured': False
            },
            {
                'name': 'Cloud Computing & DevOps (AWS & Docker)',
                'description': 'Hands-on containerization with Docker, Kubernetes orchestration, CI/CD pipelines, and cloud architecture deployment on Amazon Web Services.',
                'duration': '3 Months',
                'fee': 22000.00,
                'is_featured': False
            },
            {
                'name': 'C/C++ Programming & Data Structures',
                'description': 'Foundational programming in C and C++, object-oriented programming, memory management, pointers, and fundamental algorithms & data structures.',
                'duration': '2 Months',
                'fee': 7500.00,
                'is_featured': False
            }
        ]

        created_courses = []
        for cdata in courses_data:
            course, created = Course.objects.get_or_create(
                name=cdata['name'],
                defaults={
                    'description': cdata['description'],
                    'duration': cdata['duration'],
                    'fee': cdata['fee'],
                    'is_featured': cdata['is_featured']
                }
            )
            if not created:
                course.description = cdata['description']
                course.duration = cdata['duration']
                course.fee = cdata['fee']
                course.is_featured = cdata['is_featured']
                course.save()
            created_courses.append(course)
            status = "Created" if created else "Updated"
            self.stdout.write(f"  Course [{status}]: {course.name}")

        # 3. Seed Course Offers
        offers_data = [
            {
                'title': '30% OFF on Python Web Development Course',
                'badge': 'LIMITED OFFER',
                'discount': '30% OFF',
                'course': created_courses[0],
                'priority': 10,
                'status': 'active'
            },
            {
                'title': 'New Data Science & ML Advanced Batch Starts Soon',
                'badge': 'NEW BATCH',
                'discount': 'Enroll Now',
                'course': created_courses[2],
                'priority': 8,
                'status': 'active'
            },
            {
                'title': 'Free Verified Certificate with MERN Stack Web Development',
                'badge': 'FREE CERTIFICATE',
                'discount': 'Free Certification',
                'course': created_courses[1],
                'priority': 5,
                'status': 'active'
            },
            {
                'title': 'Early Bird Special Discount on Financial Accounting',
                'badge': 'LIMITED TIME',
                'discount': '20% OFF',
                'course': created_courses[3],
                'priority': 3,
                'status': 'active'
            },
            {
                'title': 'DevOps & AWS Cloud Certification Bundle Discount',
                'badge': 'CLOUD SPECIAL',
                'discount': 'RS 5000 OFF',
                'course': created_courses[6],
                'priority': 7,
                'status': 'active'
            }
        ]

        for offer_item in offers_data:
            offer, created = CourseOffer.objects.get_or_create(
                title=offer_item['title'],
                defaults={
                    'badge': offer_item['badge'],
                    'discount': offer_item['discount'],
                    'course': offer_item['course'],
                    'priority': offer_item['priority'],
                    'status': offer_item['status'],
                    'created_by': admin_user
                }
            )
            status_str = "Created" if created else "Updated"
            self.stdout.write(f"  Offer [{status_str}]: {offer.title}")

        # 4. Seed Student Accounts & Profiles
        students_data = [
            {'username': 'rahul_sharma',   'first_name': 'Rahul',    'last_name': 'Sharma',    'email': 'rahul.sharma@gmail.com',    'phone': '+91 9876543210', 'joined': date(2026, 1, 10), 'course_idx': 0, 'notes': 'Top performer in Django backend modules.'},
            {'username': 'priya_patel',    'first_name': 'Priya',    'last_name': 'Patel',     'email': 'priya.patel@gmail.com',     'phone': '+91 9876543211', 'joined': date(2026, 1, 15), 'course_idx': 1, 'notes': 'Working on final year React project.'},
            {'username': 'amit_verma',     'first_name': 'Amit',     'last_name': 'Verma',     'email': 'amit.verma@yahoo.com',      'phone': '+91 9876543212', 'joined': date(2026, 1, 20), 'course_idx': 2, 'notes': 'Completed Machine Learning capstone project.'},
            {'username': 'sneha_gupta',    'first_name': 'Sneha',    'last_name': 'Gupta',     'email': 'sneha.gupta@outlook.com',   'phone': '+91 9876543213', 'joined': date(2026, 2, 1),  'course_idx': 3, 'notes': 'Passed Tally Prime assessment with distinction.'},
            {'username': 'arjun_singh',    'first_name': 'Arjun',    'last_name': 'Singh',     'email': 'arjun.singh@gmail.com',     'phone': '+91 9876543214', 'joined': date(2026, 2, 8),  'course_idx': 4, 'notes': 'Interested in ethical hacking lab sessions.'},
            {'username': 'kavya_nair',     'first_name': 'Kavya',    'last_name': 'Nair',      'email': 'kavya.nair@gmail.com',      'phone': '+91 9876543215', 'joined': date(2026, 2, 14), 'course_idx': 5, 'notes': 'Enrolled in Spring Boot microservices batch.'},
            {'username': 'rohan_mehta',    'first_name': 'Rohan',    'last_name': 'Mehta',     'email': 'rohan.mehta@hotmail.com',   'phone': '+91 9876543216', 'joined': date(2026, 2, 20), 'course_idx': 6, 'notes': 'Preparing for AWS Certified Solutions Architect.'},
            {'username': 'ananya_iyer',    'first_name': 'Ananya',   'last_name': 'Iyer',      'email': 'ananya.iyer@gmail.com',     'phone': '+91 9876543217', 'joined': date(2026, 3, 3),  'course_idx': 7, 'notes': 'Enrolled for fundamentals algorithms review.'},
            {'username': 'kiran_joshi',    'first_name': 'Kiran',    'last_name': 'Joshi',     'email': 'kiran.joshi@gmail.com',     'phone': '+91 9876543218', 'joined': date(2026, 3, 10), 'course_idx': 0, 'notes': 'Attending FastAPI weekend workshop.'},
            {'username': 'pooja_desai',    'first_name': 'Pooja',    'last_name': 'Desai',     'email': 'pooja.desai@rediffmail.com','phone': '+91 9876543219', 'joined': date(2026, 3, 18), 'course_idx': 1, 'notes': 'Submitted Node.js REST API assignment.'},
            {'username': 'varun_kapoor',   'first_name': 'Varun',    'last_name': 'Kapoor',    'email': 'varun.kapoor@gmail.com',    'phone': '+91 9876543220', 'joined': date(2026, 4, 2),  'course_idx': 2, 'notes': 'Regular participant in Data Science seminars.'},
            {'username': 'divya_reddy',    'first_name': 'Divya',    'last_name': 'Reddy',     'email': 'divya.reddy@gmail.com',     'phone': '+91 9876543221', 'joined': date(2026, 4, 9),  'course_idx': 4, 'notes': 'Completed network security assignment.'},
            {'username': 'nikhil_kumar',   'first_name': 'Nikhil',   'last_name': 'Kumar',     'email': 'nikhil.kumar@outlook.com',  'phone': '+91 9876543222', 'joined': date(2026, 4, 20), 'course_idx': 5, 'notes': 'Java enterprise batch student.'},
            {'username': 'meera_pillai',   'first_name': 'Meera',    'last_name': 'Pillai',    'email': 'meera.pillai@gmail.com',    'phone': '+91 9876543223', 'joined': date(2026, 5, 5),  'course_idx': 6, 'notes': 'Docker and Kubernetes labs completed.'},
            {'username': 'suresh_bhat',    'first_name': 'Suresh',   'last_name': 'Bhat',      'email': 'suresh.bhat@gmail.com',     'phone': '+91 9876543224', 'joined': date(2026, 5, 14), 'course_idx': 3, 'notes': 'GST filing practical session completed.'},
        ]

        student_users_map = {}
        for sdata in students_data:
            user, created = User.objects.get_or_create(
                username=sdata['username'],
                defaults={
                    'first_name': sdata['first_name'],
                    'last_name':  sdata['last_name'],
                    'email':      sdata['email'],
                    'is_staff':   False,
                    'is_active':  True,
                }
            )
            user.set_password('student@123')
            user.date_joined = tz.make_aware(
                datetime(sdata['joined'].year, sdata['joined'].month, sdata['joined'].day)
            )
            user.save()

            profile, _ = StudentProfile.objects.get_or_create(user=user)
            profile.phone = sdata['phone']
            profile.enrolled_course = created_courses[sdata['course_idx']]
            profile.notes = sdata['notes']
            profile.save()

            student_users_map[sdata['username']] = user
            status = "Created" if created else "Updated"
            self.stdout.write(f"  Student [{status}]: {user.get_full_name()} ({user.username})")

        # 5. Seed Certificates
        certificates_data = [
            {
                'certificate_id': 'CERT-2026-PY0001',
                'first_name': 'Rahul',
                'last_name': 'Sharma',
                'student_username': 'rahul_sharma',
                'course': created_courses[0],
                'course_start_date': date(2025, 11, 1),
                'course_end_date': date(2026, 1, 31),
                'issue_date': date(2026, 2, 15),
                'grade': 'A+'
            },
            {
                'certificate_id': 'CERT-2026-FS0002',
                'first_name': 'Priya',
                'last_name': 'Patel',
                'student_username': 'priya_patel',
                'course': created_courses[1],
                'course_start_date': date(2025, 9, 1),
                'course_end_date': date(2026, 3, 1),
                'issue_date': date(2026, 3, 20),
                'grade': 'A'
            },
            {
                'certificate_id': 'CERT-2026-DS0003',
                'first_name': 'Amit',
                'last_name': 'Verma',
                'student_username': 'amit_verma',
                'course': created_courses[2],
                'course_start_date': date(2025, 12, 1),
                'course_end_date': date(2026, 3, 31),
                'issue_date': date(2026, 4, 10),
                'grade': 'A+'
            },
            {
                'certificate_id': 'CERT-2026-AC0004',
                'first_name': 'Sneha',
                'last_name': 'Gupta',
                'student_username': 'sneha_gupta',
                'course': created_courses[3],
                'course_start_date': date(2026, 2, 1),
                'course_end_date': date(2026, 3, 31),
                'issue_date': date(2026, 5, 1),
                'grade': 'O (Outstanding)'
            },
            {
                'certificate_id': 'CERT-2026-CS0005',
                'first_name': 'Arjun',
                'last_name': 'Singh',
                'student_username': 'arjun_singh',
                'course': created_courses[4],
                'course_start_date': date(2026, 2, 1),
                'course_end_date': date(2026, 4, 30),
                'issue_date': date(2026, 5, 15),
                'grade': 'A+'
            },
            {
                'certificate_id': 'CERT-2026-JV0006',
                'first_name': 'Kavya',
                'last_name': 'Nair',
                'student_username': 'kavya_nair',
                'course': created_courses[5],
                'course_start_date': date(2025, 11, 15),
                'course_end_date': date(2026, 5, 15),
                'issue_date': date(2026, 6, 1),
                'grade': 'A'
            }
        ]

        for cert_data in certificates_data:
            student_user = student_users_map.get(cert_data['student_username'])
            cert, created = Certificate.objects.get_or_create(
                certificate_id=cert_data['certificate_id'],
                defaults={
                    'first_name': cert_data['first_name'],
                    'last_name': cert_data['last_name'],
                    'student_name': f"{cert_data['first_name']} {cert_data['last_name']}",
                    'student': student_user,
                    'course': cert_data['course'],
                    'course_start_date': cert_data['course_start_date'],
                    'course_end_date': cert_data['course_end_date'],
                    'issue_date': cert_data['issue_date'],
                    'grade': cert_data['grade']
                }
            )
            if not created:
                cert.first_name = cert_data['first_name']
                cert.last_name = cert_data['last_name']
                cert.student_name = f"{cert_data['first_name']} {cert_data['last_name']}"
                cert.student = student_user
                cert.course = cert_data['course']
                cert.course_start_date = cert_data['course_start_date']
                cert.course_end_date = cert_data['course_end_date']
                cert.issue_date = cert_data['issue_date']
                cert.grade = cert_data['grade']
                cert.save()

            status = "Created" if created else "Updated"
            self.stdout.write(f"  Certificate [{status}]: {cert.certificate_id} - {cert.student_name}")

        # 6. Seed Inquiries & Inquiry Follow-ups
        inquiries_data = [
            {
                'name': 'Rajesh Kumar',
                'phone': '+91 9825012345',
                'email': 'rajesh.k@gmail.com',
                'course': created_courses[0],
                'subject': 'Inquiry regarding Python Django weekend batch timings',
                'message': 'Hello, I am a working professional interested in taking the Python Web Development course. Do you offer weekend or evening batches?',
                'is_read': True,
                'followups': [
                    {'status': 'contacted', 'message': 'Called Rajesh. Informed him about the Saturday-Sunday 10 AM to 1 PM weekend batch options.'},
                    {'status': 'interested', 'message': 'Rajesh confirmed interest. Requested syllabus PDF on WhatsApp.'}
                ]
            },
            {
                'name': 'Neha Shah',
                'phone': '+91 9712345678',
                'email': 'neha.shah99@yahoo.com',
                'course': created_courses[1],
                'subject': 'MERN Stack course fees and installment payment options',
                'message': 'Hi, I want to join the MERN stack course starting next month. Is there any installment payment plan available for students?',
                'is_read': True,
                'followups': [
                    {'status': 'contacted', 'message': 'Explained 2-part installment scheme for 6-month MERN course.'},
                    {'status': 'converted', 'message': 'Student enrolled in MERN batch and paid initial fee.'}
                ]
            },
            {
                'name': 'Manish Chawla',
                'phone': '+91 9909988776',
                'email': 'manish.chawla@gmail.com',
                'course': created_courses[2],
                'subject': 'Prerequisites for Data Science & Machine Learning',
                'message': 'I have a background in Commerce. Can I learn Data Science and Machine Learning without prior coding experience?',
                'is_read': False,
                'followups': []
            },
            {
                'name': 'Bhavna Patel',
                'phone': '+91 9426011223',
                'email': 'bhavna.p@outlook.com',
                'course': created_courses[3],
                'subject': 'Tally Prime & GST Certification Batch Start Date',
                'message': 'When does the next Tally Prime & GST training batch begin? Please share class schedules.',
                'is_read': True,
                'followups': [
                    {'status': 'callback_later', 'message': 'Requested callback after 5 PM on Monday.'}
                ]
            },
            {
                'name': 'Vikram Solanki',
                'phone': '+91 9898012345',
                'email': 'vsolanki@gmail.com',
                'course': created_courses[4],
                'subject': 'Ethical Hacking Lab Facilities',
                'message': 'Does the Cyber Security course include hands-on penetration testing labs and Linux environments?',
                'is_read': True,
                'followups': [
                    {'status': 'contacted', 'message': 'Demonstrated online lab setup via demo call.'},
                    {'status': 'interested', 'message': 'Planning to join upcoming batch on 15th.'}
                ]
            },
            {
                'name': 'Siddharth Trivedi',
                'phone': '+91 9601234567',
                'email': 'sid.trivedi@gmail.com',
                'course': created_courses[6],
                'subject': 'AWS DevOps Certification voucher details',
                'message': 'Do you provide guidance for AWS Certified Cloud Practitioner / Solutions Architect exams?',
                'is_read': False,
                'followups': []
            }
        ]

        for inq_data in inquiries_data:
            inquiry, created = Inquiry.objects.get_or_create(
                name=inq_data['name'],
                phone=inq_data['phone'],
                defaults={
                    'email': inq_data['email'],
                    'course': inq_data['course'],
                    'subject': inq_data['subject'],
                    'message': inq_data['message'],
                    'is_read': inq_data['is_read']
                }
            )
            status = "Created" if created else "Updated"
            self.stdout.write(f"  Inquiry [{status}]: {inquiry.name} ({inquiry.subject})")

            for f_data in inq_data.get('followups', []):
                InquiryFollowUp.objects.get_or_create(
                    inquiry=inquiry,
                    message=f_data['message'],
                    defaults={
                        'admin_user': admin_user,
                        'status': f_data['status'],
                        'callback_at': tz.now() + timedelta(days=2) if f_data['status'] == 'callback_later' else None
                    }
                )

        # 7. Seed About & Contact Singleton Content
        about_content = AboutContent.get_solo()
        about_content.heading = "About C-DAC Class Gandhinagar"
        about_content.subtitle = "Empowering Students & IT Professionals with Practical Computer Education & Industry Skills."
        about_content.mission_title = "Our Mission & Vision"
        about_content.description = (
            "At the Centre for Development of Advanced Computing (C-DAC) Class, our mission is to deliver high-quality, "
            "practical computer education across Web Development, Data Science, Cyber Security, Accounting, and Cloud Computing. "
            "Our hands-on curriculum is designed to make students industry-ready with cryptographically verifiable certificates."
        )
        about_content.feature_1_title = "Practical Learning"
        about_content.feature_1_desc = "Hands-on coding, live project building, and practical lab assignments tailored for real industry demands."
        about_content.feature_2_title = "Authentic Certification"
        about_content.feature_2_desc = "Certificates featuring unique SHA-256 hashes and instant online verification for employers."
        about_content.feature_3_title = "Community Support"
        about_content.feature_3_desc = "1-on-1 mentor guidance, interview preparation, resume building, and active job placement assistance."
        about_content.save()
        self.stdout.write(self.style.SUCCESS("[OK] About Page Content seeded/updated."))

        contact_content = ContactContent.get_solo()
        contact_content.phone = "+91 98765 43210 / +91 (079) 2326-1000"
        contact_content.email = "info@cdac-class.in"
        contact_content.address = "C-DAC Computer Class, Sector 11, Gandhinagar, Gujarat 382011, India"
        contact_content.working_hours = "Monday - Saturday: 8:00 AM - 8:00 PM (Sunday Closed)"
        contact_content.map_embed_url = "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d471.09!2d72.6320823!3d23.1852315!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x395c2b921555555d%3A0x50e94504c763b697!2sCDAC%20Computer%20Class!5e0!3m2!1sen!2sin!4v1722593000000!5m2!1sen!2sin"
        if not contact_content.instagram_url:
            contact_content.instagram_url = "https://www.instagram.com/ras_computer_education/"
            contact_content.instagram_username = "ras_computer_education"
        if not contact_content.facebook_url:
            contact_content.facebook_url = "https://www.facebook.com/RASeducationgnr/"
            contact_content.facebook_name = "RASeducationgnr"
        contact_content.save()
        self.stdout.write(self.style.SUCCESS("[OK] Contact Details Content seeded/updated."))

        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("Successfully seeded data for all models in the database!"))
        self.stdout.write("=" * 60)



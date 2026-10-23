from django.db import models
from courses.models import Course

class Inquiry(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField(max_length=254, blank=True, null=True)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='inquiries')
    subject = models.CharField(max_length=200, default="General Inquiry")
    message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Customer Inquiry'
        verbose_name_plural = 'Customer Inquiries'

    def __str__(self):
        return f"Inquiry from {self.name} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

    @property
    def followup_count(self):
        return self.followups.count()

    @property
    def whatsapp_url(self):
        if not self.phone:
            return None
        digits = ''.join(c for c in str(self.phone) if c.isdigit())
        if not digits:
            return None
        return f"https://wa.me/{digits}"

    @property
    def latest_followup(self):
        return self.followups.first()


class InquiryFollowUp(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('contacted', 'Contacted'),
        ('interested', 'Interested'),
        ('not_interested', 'Not Interested'),
        ('callback_later', 'Callback Later'),
        ('converted', 'Converted'),
    ]

    inquiry = models.ForeignKey(Inquiry, on_delete=models.CASCADE, related_name='followups')
    admin_user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='contacted')
    message = models.TextField()
    callback_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Inquiry Follow-Up'
        verbose_name_plural = 'Inquiry Follow-Ups'

    def __str__(self):
        admin_name = self.admin_user.get_full_name() or self.admin_user.username if self.admin_user else 'Admin'
        return f"Follow-up for {self.inquiry.name} by {admin_name} ({self.get_status_display()})"


DEFAULT_LEGACY_CARDS = [
    {
        "id": 1,
        "stat": "20+",
        "title": "20+ Years of Establishment",
        "desc": "Over two decades of proven excellence, trust, and leadership in computer training.",
        "color": "orange",
        "icon": "clock"
    },
    {
        "id": 2,
        "stat": "15,000+",
        "title": "15,000+ Students Trained",
        "desc": "A vast alumni network working successfully in top companies, MNCs, and government sectors across Gujarat and beyond.",
        "color": "blue",
        "icon": "users"
    },
    {
        "id": 3,
        "stat": "100%",
        "title": "100% Practical Training",
        "desc": "Hands-on experience with modern software, real-world projects, and dedicated lab sessions.",
        "color": "primary",
        "icon": "desktop"
    },
    {
        "id": 4,
        "stat": "Certified",
        "title": "Certified & Experienced Instructors",
        "desc": "Learn directly from industry experts with deep domain knowledge and personalized teaching approaches.",
        "color": "green",
        "icon": "award"
    }
]

DEFAULT_WHY_BENEFITS = [
    {
        "id": 1,
        "title": "Industry-Aligned Curriculum",
        "desc": "Updated regularly to keep pace with evolving technological standards.",
        "icon": "book"
    },
    {
        "id": 2,
        "title": "Small Batch Sizes",
        "desc": "Ensures individual focus and personal attention for every student.",
        "icon": "users"
    },
    {
        "id": 3,
        "title": "Flexible Timings",
        "desc": "Morning, evening, and weekend batches tailored for convenience.",
        "icon": "clock"
    },
    {
        "id": 4,
        "title": "Affordable Fees Structure",
        "desc": "Quality computer education accessible to everyone.",
        "icon": "dollar"
    },
    {
        "id": 5,
        "title": "Career Guidance & Placement Support",
        "desc": "Assistance with resume building, interview preparation, and job placement.",
        "icon": "briefcase"
    }
]

DEFAULT_SPECS_CARDS = [
    {
        "id": 1,
        "badge": "Accounting & Taxation",
        "badge_color": "orange",
        "title": "1. Best Tally Training Institute in Gandhinagar",
        "desc": "Master accounting and GST with our specialized Tally Prime & GST Certification Course. Designed for commerce students, job seekers, and business owners, our course covers Tally with real-time financial accounting, inventory management, taxation, and GST compliance. Gain practical bookkeeping skills to pursue roles in accounting and finance.",
        "desc2": "",
        "highlights": [],
        "tags": ["Tally Prime", "GST Compliance", "Inventory", "Bookkeeping"]
    },
    {
        "id": 2,
        "badge": "Software Development & IT",
        "badge_color": "default",
        "title": "2. Best Coding Languages Institute in Gandhinagar",
        "desc": "Kickstart your career in software development and IT. We offer comprehensive training in core and advanced programming languages:",
        "desc2": "",
        "highlights": [
            {"label": "Python Programming:", "text": "From Python basics to advanced OOPs and data manipulation."},
            {"label": "C & C++ Fundamentals:", "text": "Build strong logic, algorithm, and object-oriented programming concepts."},
            {"label": "Web Development (HTML, CSS, JavaScript):", "text": "Learn full-stack skills to build modern, responsive websites."},
            {"label": "Java & Data Structures:", "text": "Master core logic and enterprise-level development."}
        ],
        "tags": ["Python", "C / C++", "Full-Stack Web", "Java & DSA"]
    },
    {
        "id": 3,
        "badge": "Government Certification",
        "badge_color": "cyan",
        "title": "3. Best CCC Training Institute",
        "desc": "Prepare for government job requirements and administrative skill certifications with our CCC (Course on Computer Concepts) training program.",
        "desc2": "We offer expert guidance on fundamental computer skills, MS Office (Word, Excel, PowerPoint), internet basics, email management, and government portal navigation, ensuring a high pass rate for all aspirants.",
        "highlights": [],
        "tags": ["CCC Exam Prep", "MS Office", "Internet & Email", "Govt Portals"]
    },
    {
        "id": 4,
        "badge": "Productivity & Analytics",
        "badge_color": "default",
        "title": "4. Advanced Office & Data Analysis Skills",
        "desc": "Become an expert in office productivity tools. Master Advanced Excel for Data Analysis, formula creation, data visualization, pivot tables, and database management through hands-on practice.",
        "desc2": "",
        "highlights": [],
        "tags": ["Advanced Excel", "Data Analysis", "Pivot Tables", "Data Visualization"]
    }
]

DEFAULT_TESTIMONIALS = [
    {
        "id": 1,
        "stars": 5,
        "quote": "Joining RAS Computer Education was the best decision for my career. The practical exposure in Python and Advanced Excel gave me the confidence to clear my interviews easily.",
        "author": "Alumni Student",
        "tag": "RAS Computer Education Alum",
        "avatar": "AS"
    },
    {
        "id": 2,
        "stars": 5,
        "quote": "The best Tally training institute in Gandhinagar! The faculty explains complex GST concepts with real-world examples.",
        "author": "Commerce Graduate",
        "tag": "Tally Prime & GST Graduate",
        "avatar": "CG"
    }
]


class AboutContent(models.Model):
    # Backward compatibility fields
    heading = models.CharField(max_length=200, default="About C-DAC")
    subtitle = models.CharField(max_length=300, default="Dedicated to excellence in practical computer education, advanced computing research, and skills training.")
    mission_title = models.CharField(max_length=150, default="Our Mission")
    description = models.TextField(default="At the Centre for Development of Advanced Computing (C-DAC), our mission is to carry out R&D in IT, Electronics and associated areas, empowering students and professionals with high-end IT education. Whether you are looking to start a career in software development, web engineering, database administration, or advanced computing, our hands-on curriculum is designed to get you industry-ready.")
    
    feature_1_title = models.CharField(max_length=150, default="🎯 Practical Learning")
    feature_1_desc = models.TextField(default="Every course emphasizes real-world projects and coding exercises over passive lecture theory.")
    feature_2_title = models.CharField(max_length=150, default="🏆 Authentic Certification")
    feature_2_desc = models.TextField(default="Certificates issued by C-DAC feature unique cryptographic IDs verifiable by employers globally.")
    feature_3_title = models.CharField(max_length=150, default="👥 Community Support")
    feature_3_desc = models.TextField(default="Dedicated lab assistants, mentor hours, and career placement assistance for all active students.")

    # Section 1: Introduction
    intro_badge = models.CharField(max_length=150, default="Premier Computer Institute in Gandhinagar", blank=True)
    intro_heading = models.CharField(max_length=300, default="Welcome to RAS Computer Education – Empowering Futures Through Technology", blank=True)
    intro_lead = models.TextField(default="Welcome to RAS Computer Education, Gandhinagar’s premier destination for comprehensive computer training, skill development, and professional IT education. For over two decades, we have been dedicated to bridging the gap between traditional learning and modern industry demands.", blank=True)
    intro_text = models.TextField(default="Whether you are a student aiming to build a career in technology, a job seeker preparing for government examinations, or a professional looking to upskill, RAS Computer Education is the best students' choice for learning computer skills in Gandhinagar, Gujarat.", blank=True)

    # Section 2: Our Legacy of Excellence
    legacy_title = models.CharField(max_length=200, default="Our Legacy of Excellence", blank=True)
    legacy_desc = models.TextField(default="Since our inception, we have maintained an unwavering commitment to quality education, practical learning, and student success.", blank=True)
    legacy_cards = models.JSONField(default=list, blank=True)

    # Section 3: Why We Are the Best Computer Class in Gandhinagar, Gujarat
    why_title = models.CharField(max_length=250, default="Why We Are the Best Computer Class in Gandhinagar, Gujarat", blank=True)
    why_desc = models.TextField(default="At RAS Computer Education, we believe that quality education should be practical, affordable, and career-oriented. Located strategically in Gandhinagar, our institute provides a state-of-the-art learning environment equipped with modern infrastructure and flexible batch timings to accommodate students, working professionals, and job seekers.", blank=True)
    why_subheading = models.CharField(max_length=200, default="What Sets Us Apart?", blank=True)
    why_benefits = models.JSONField(default=list, blank=True)

    # Section 4: Our Core Specializations
    specs_title = models.CharField(max_length=200, default="Our Core Specializations", blank=True)
    specs_desc = models.TextField(default="Comprehensive training programs designed to develop in-demand technical expertise, professional competence, and career readiness.", blank=True)
    specs_cards = models.JSONField(default=list, blank=True)

    # Section 5: Our Mission & Vision
    mv_title = models.CharField(max_length=200, default="Our Mission & Vision", blank=True)
    mission_text = models.TextField(default="To empower individuals with cutting-edge computer skills, practical knowledge, and technical confidence required to excel in today’s digital world.", blank=True)
    vision_title = models.CharField(max_length=150, default="Our Vision", blank=True)
    vision_text = models.TextField(default="To remain the most trusted, innovative, and student-centric computer training institute in Gandhinagar, continuously raising the standard of IT education.", blank=True)

    # Section 6: Student Testimonials
    testimonials_title = models.CharField(max_length=200, default="What Our Students Say", blank=True)
    testimonials_desc = models.TextField(default="Genuine feedback from our students on their learning journeys and career milestones.", blank=True)
    testimonials = models.JSONField(default=list, blank=True)

    # Bottom CTA Bar
    cta_title = models.CharField(max_length=200, default="Ready to Build In-Demand Computer Skills?", blank=True)
    cta_desc = models.TextField(default="Join thousands of successful students and professionals in Gandhinagar.", blank=True)
    cta_btn1_text = models.CharField(max_length=100, default="View All Courses →", blank=True)
    cta_btn1_url = models.CharField(max_length=255, default="/courses/", blank=True)
    cta_btn2_text = models.CharField(max_length=100, default="Contact Us", blank=True)
    cta_btn2_url = models.CharField(max_length=255, default="/contact/", blank=True)

    # Synchronization versioning & timestamp
    sync_version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'About Page Content'
        verbose_name_plural = 'About Page Content'

    def __str__(self):
        return f"About Content v{self.sync_version} (Last updated: {self.updated_at.strftime('%Y-%m-%d %H:%M')})"

    def get_legacy_cards(self):
        return self.legacy_cards if self.legacy_cards else DEFAULT_LEGACY_CARDS

    def get_why_benefits(self):
        return self.why_benefits if self.why_benefits else DEFAULT_WHY_BENEFITS

    def get_specs_cards(self):
        return self.specs_cards if self.specs_cards else DEFAULT_SPECS_CARDS

    def get_testimonials(self):
        return self.testimonials if self.testimonials else DEFAULT_TESTIMONIALS

    def populate_defaults(self, save=True):
        updated = False
        if not self.legacy_cards:
            self.legacy_cards = DEFAULT_LEGACY_CARDS
            updated = True
        if not self.why_benefits:
            self.why_benefits = DEFAULT_WHY_BENEFITS
            updated = True
        if not self.specs_cards:
            self.specs_cards = DEFAULT_SPECS_CARDS
            updated = True
        if not self.testimonials:
            self.testimonials = DEFAULT_TESTIMONIALS
            updated = True
        if save and updated:
            self.save()

    def to_dict(self):
        return {
            "sync_version": self.sync_version,
            "updated_at": self.updated_at.strftime('%I:%M:%S %p'),
            "updated_at_iso": self.updated_at.isoformat(),
            # Section A
            "intro_badge": self.intro_badge or "Premier Computer Institute in Gandhinagar",
            "intro_heading": self.intro_heading or self.heading or "Welcome to RAS Computer Education – Empowering Futures Through Technology",
            "intro_lead": self.intro_lead or "",
            "intro_text": self.intro_text or "",
            # Section B
            "legacy_title": self.legacy_title or "Our Legacy of Excellence",
            "legacy_desc": self.legacy_desc or "",
            "legacy_cards": self.get_legacy_cards(),
            # Section C
            "why_title": self.why_title or "Why We Are the Best Computer Class in Gandhinagar, Gujarat",
            "why_desc": self.why_desc or "",
            "why_subheading": self.why_subheading or "What Sets Us Apart?",
            "why_benefits": self.get_why_benefits(),
            # Section D
            "specs_title": self.specs_title or "Our Core Specializations",
            "specs_desc": self.specs_desc or "",
            "specs_cards": self.get_specs_cards(),
            # Section E
            "mv_title": self.mv_title or "Our Mission & Vision",
            "mission_title": self.mission_title or "Our Mission",
            "mission_text": self.mission_text or self.description or "",
            "vision_title": self.vision_title or "Our Vision",
            "vision_text": self.vision_text or "",
            # Section F
            "testimonials_title": self.testimonials_title or "What Our Students Say",
            "testimonials_desc": self.testimonials_desc or "",
            "testimonials": self.get_testimonials(),
            # CTA
            "cta_title": self.cta_title or "Ready to Build In-Demand Computer Skills?",
            "cta_desc": self.cta_desc or "",
            "cta_btn1_text": self.cta_btn1_text or "View All Courses →",
            "cta_btn1_url": self.cta_btn1_url or "/courses/",
            "cta_btn2_text": self.cta_btn2_text or "Contact Us",
            "cta_btn2_url": self.cta_btn2_url or "/contact/",
            # Backward compatibility
            "heading": self.heading,
            "subtitle": self.subtitle,
            "description": self.description,
            "feature_1_title": self.feature_1_title,
            "feature_1_desc": self.feature_1_desc,
            "feature_2_title": self.feature_2_title,
            "feature_2_desc": self.feature_2_desc,
            "feature_3_title": self.feature_3_title,
            "feature_3_desc": self.feature_3_desc,
        }

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(id=1)
        if not obj.legacy_cards or not obj.why_benefits or not obj.specs_cards or not obj.testimonials:
            obj.populate_defaults(save=True)
        return obj


class ContactContent(models.Model):
    phone = models.CharField(max_length=100, default="+91 (020) 2570-4100")
    whatsapp_number = models.CharField(max_length=30, default="919876543210", help_text="WhatsApp number with country code (e.g. 919876543210)")
    email = models.EmailField(default="contact@cdac.in")
    address = models.TextField(default="Surbhi complex, F-5, 2nd Floor, Above Bharat Library. Gh-5, Circle, GH Rd, Sector 22, Gandhinagar, Gujarat 382021")
    working_hours = models.CharField(max_length=150, default="Mon - Sat: 9:00 AM - 6:00 PM")
    map_embed_url = models.URLField(blank=True, null=True, max_length=500, default="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3667.432845625442!2d72.6502271!3d23.2344055!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x395c2b98680613c5%3A0xe36f138dbac2da1a!2sRas%20Computer%20Education%20%26%20Spoken%20English!5e0!3m2!1sen!2sin!4v1729668000000!5m2!1sen!2sin")
    
    # Social Media Links
    instagram_username = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Instagram Username",
        help_text="Instagram username or handle (e.g. @cdac_classes or cdac_official)"
    )
    instagram_url = models.URLField(
        max_length=300,
        blank=True,
        default="",
        verbose_name="Instagram Profile URL",
        help_text="Full Instagram profile URL (e.g. https://www.instagram.com/username/)"
    )
    facebook_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Facebook Page Name",
        help_text="Facebook page name or display name (e.g. CDAC Computer Education)"
    )
    facebook_url = models.URLField(
        max_length=300,
        blank=True,
        default="",
        verbose_name="Facebook Page URL",
        help_text="Full Facebook page URL (e.g. https://www.facebook.com/pagename/)"
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Contact Details Content'
        verbose_name_plural = 'Contact Details Content'

    def __str__(self):
        return f"Contact Content (Last updated: {self.updated_at.strftime('%Y-%m-%d %H:%M')})"

    @property
    def formatted_whatsapp_number(self):
        target = self.whatsapp_number or self.phone
        if target:
            digits = ''.join(c for c in str(target) if c.isdigit())
            if digits:
                return digits
        return "919876543210"

    @property
    def whatsapp_url(self):
        num = self.formatted_whatsapp_number
        return f"https://wa.me/{num}"

    @property
    def clean_instagram_url(self):
        if not self.instagram_url:
            return ""
        url = self.instagram_url.strip()
        if not url.startswith(('http://', 'https://')):
            return f"https://{url}"
        return url

    @property
    def display_instagram(self):
        if self.instagram_username and self.instagram_username.strip():
            return self.instagram_username.strip()
        if self.instagram_url:
            cleaned = self.instagram_url.strip().rstrip('/').split('/')[-1]
            return f"@{cleaned}" if cleaned else "Instagram"
        return ""

    @property
    def has_instagram(self):
        return bool(self.clean_instagram_url and self.display_instagram)

    @property
    def clean_facebook_url(self):
        if not self.facebook_url:
            return ""
        url = self.facebook_url.strip()
        if not url.startswith(('http://', 'https://')):
            return f"https://{url}"
        return url

    @property
    def display_facebook(self):
        if self.facebook_name and self.facebook_name.strip():
            return self.facebook_name.strip()
        if self.facebook_url:
            cleaned = self.facebook_url.strip().rstrip('/').split('/')[-1]
            return cleaned.replace('-', ' ').title() if cleaned else "Facebook"
        return ""

    @property
    def has_facebook(self):
        return bool(self.clean_facebook_url and self.display_facebook)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class JustdialReview(models.Model):
    reviewer_name = models.CharField(max_length=150)
    rating = models.PositiveSmallIntegerField(
        default=5,
        choices=[(i, f"{i} Stars") for i in range(1, 6)],
        help_text="Rating between 1 and 5 stars"
    )
    review_text = models.TextField(help_text="Text of the review from Justdial")
    review_date = models.DateField(blank=True, null=True, help_text="Date of review on Justdial (optional)")
    is_active = models.BooleanField(default=True, help_text="Toggle whether to display this review on the Contact page")
    display_order = models.PositiveIntegerField(default=0, help_text="Display order (lower numbers appear first)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', '-created_at']
        verbose_name = 'Justdial Review'
        verbose_name_plural = 'Justdial Reviews'

    @property
    def stars(self):
        r = max(1, min(int(self.rating or 5), 5))
        return '★' * r + '☆' * (5 - r)

    def __str__(self):
        return f"{self.reviewer_name} ({self.rating}★)"


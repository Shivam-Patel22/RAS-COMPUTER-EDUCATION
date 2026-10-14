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


class AboutContent(models.Model):
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
    
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'About Page Content'
        verbose_name_plural = 'About Page Content'

    def __str__(self):
        return f"About Content (Last updated: {self.updated_at.strftime('%Y-%m-%d %H:%M')})"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class ContactContent(models.Model):
    phone = models.CharField(max_length=100, default="+91 (020) 2570-4100")
    whatsapp_number = models.CharField(max_length=30, default="919876543210", help_text="WhatsApp number with country code (e.g. 919876543210)")
    email = models.EmailField(default="contact@cdac.in")
    address = models.TextField(default="Gandhinagar, Gujarat, India")
    working_hours = models.CharField(max_length=150, default="Mon - Sat: 9:00 AM - 6:00 PM")
    map_embed_url = models.URLField(blank=True, null=True, max_length=500, default="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d471.09!2d72.6320823!3d23.1852315!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x395c2b921555555d%3A0x50e94504c763b697!2sCDAC%20Computer%20Class!5e0!3m2!1sen!2sin!4v1722593000000!5m2!1sen!2sin")
    
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

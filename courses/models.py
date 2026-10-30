from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class CourseCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="Category name, e.g. Basic, Programming, Accounting")
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, default='', help_text="Short summary of this category")
    icon = models.CharField(max_length=50, blank=True, default='💻', help_text="Icon or emoji, e.g. 💻, 📊, ⚙️, 🎓, 🏆, 🚀, 🧩")
    duration = models.CharField(max_length=50, blank=True, default='', help_text="Default duration or track tag (e.g. 6 Months, Flexible)")
    display_order = models.PositiveIntegerField(default=0, help_text="Order in which category appears (lower numbers first)")
    is_active = models.BooleanField(default=True, help_text="Designates whether this category is active and visible in the user panel")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Course Category'
        verbose_name_plural = 'Course Categories'
        ordering = ['display_order', 'id']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.name) or 'category'
            candidate = base_slug
            idx = 1
            while CourseCategory.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_slug}-{idx}"
                idx += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def subcourses_count(self):
        try:
            return self.get_subcourses().count()
        except Exception:
            return 0

    def get_subcourses(self):
        try:
            all_cat_names = set(CourseCategory.objects.values_list('name', flat=True))
            return Course.objects.filter(
                models.Q(category_ref=self) | models.Q(category=self.slug)
            ).exclude(name__in=all_cat_names)
        except Exception:
            try:
                return Course.objects.filter(category=self.slug)
            except Exception:
                return Course.objects.none()


class Course(models.Model):
    CATEGORY_CHOICES = [
        ('basic', 'Basic'),
        ('accounting', 'Accounting'),
        ('programming', 'Programming'),
        ('diploma-6-months', 'Diploma (6 Months)'),
        ('advance-diploma-12-months', 'Advance Diploma (12 Months)'),
        ('frontend-full-stack-development', 'Frontend / Full Stack Development'),
        ('modular-courses', 'Modular Courses'),
    ]

    name = models.CharField(max_length=200)
    category = models.CharField(
        max_length=100,
        default='basic',
        blank=True,
        null=True,
        help_text="Select the main Course Category"
    )
    category_ref = models.ForeignKey(
        CourseCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses',
        help_text="Assigned Course Category"
    )
    description = models.TextField()
    duration = models.CharField(max_length=50)
    fee = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    image = models.ImageField(upload_to='courses/', blank=True, null=True)
    is_featured = models.BooleanField(default=False, help_text="Display as featured course on homepage")
    slug = models.SlugField(max_length=220, unique=True, blank=True, null=True, help_text="SEO-friendly URL identifier")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.category_ref:
            self.category = self.category_ref.slug
        elif self.category:
            cat = CourseCategory.objects.filter(
                models.Q(slug=self.category) | models.Q(name__iexact=self.category)
            ).first()
            if cat:
                self.category_ref = cat
                self.category = cat.slug

        if not self.slug:
            from .utils import generate_course_slug
            base_slug = generate_course_slug(self.name)
            candidate = base_slug
            idx = 1
            while Course.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_slug}-{idx}"
                idx += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        if self.slug:
            return reverse('courses:course_detail_slug', kwargs={'slug': self.slug})
        return reverse('courses:course_detail', kwargs={'pk': self.pk})

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    def get_category_display(self):
        if self.category_ref:
            return self.category_ref.name
        choices_dict = dict(self.CATEGORY_CHOICES)
        if self.category in choices_dict:
            return choices_dict[self.category]
        if self.category:
            cat = CourseCategory.objects.filter(
                models.Q(slug=self.category) | models.Q(name__iexact=self.category)
            ).first()
            if cat:
                return cat.name
            return self.category.replace('-', ' ').title()
        return "Uncategorized"

    @property
    def image_url_or_default(self):
        if self.image:
            try:
                return self.image.url
            except Exception:
                return ''
        return ''

    @property
    def clean_preview_description(self):
        from .utils import get_clean_preview
        return get_clean_preview(self.description)

    @property
    def formatted_description_html(self):
        from .utils import format_markdown_to_html
        return format_markdown_to_html(self.description)



class CourseOffer(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('draft', 'Draft'),
    ]

    title = models.CharField(max_length=200, help_text="Short offer title for ticker, e.g., 30% OFF on Python Course")
    description = models.TextField(blank=True, null=True, help_text="Detailed description of offer")
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='offers')
    discount = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., 30% OFF, ₹999 Only, Free Certificate")
    badge = models.CharField(max_length=50, default="🎉 SPECIAL OFFER", help_text="Ticker badge icon/text")
    start_date = models.DateField(blank=True, null=True, help_text="Start date for offer schedule")
    end_date = models.DateField(blank=True, null=True, help_text="End date for offer expiry")
    priority = models.IntegerField(default=0, help_text="Higher priority offers appear first in ticker")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_offers')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', '-created_at']
        verbose_name = 'Course Offer'
        verbose_name_plural = 'Course Offers'

    def __str__(self):
        return f"{self.badge} - {self.title}"

    @property
    def computed_status(self):
        today = timezone.now().date()
        if self.status == 'inactive':
            return 'Inactive'
        if self.status == 'draft':
            return 'Draft'
        if self.start_date and self.start_date > today:
            return 'Scheduled'
        if self.end_date and self.end_date < today:
            return 'Expired'
        return 'Active'

    @property
    def is_currently_active(self):
        today = timezone.now().date()
        if self.status != 'active':
            return False
        if self.start_date and self.start_date > today:
            return False
        if self.end_date and self.end_date < today:
            return False
        return True

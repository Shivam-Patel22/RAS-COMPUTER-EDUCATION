import hashlib
from django.db import models
from django.db.models.functions import Lower
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db import IntegrityError

class Certificate(models.Model):
    certificate_id = models.CharField(max_length=50, unique=True, db_index=True)
    first_name = models.CharField(max_length=100, blank=True, default='')
    middle_name = models.CharField(max_length=100, blank=True, default='')
    last_name = models.CharField(max_length=100, blank=True, default='')
    student_name = models.CharField(max_length=200)
    student = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='certificates')
    course = models.ForeignKey('courses.Course', on_delete=models.PROTECT)
    course_start_date = models.DateField(null=True, blank=True)
    course_end_date = models.DateField(null=True, blank=True)
    issue_date = models.DateField(db_index=True)
    grade = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verification_token = models.CharField(max_length=64, blank=True, null=True)
    verification_hash = models.CharField(max_length=64, blank=True, null=True)
    printed_at = models.DateTimeField(blank=True, null=True)
    last_verified_at = models.DateTimeField(blank=True, null=True)
    is_revoked = models.BooleanField(default=False, db_index=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    revocation_reason = models.CharField(max_length=255, blank=True, default='')

    # CITI CCC Specific Fields (Optional & Nullable for non-CITI certificates)
    student_photo = models.ImageField(upload_to='student_photos/', null=True, blank=True)
    theory_marks = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(50)]
    )
    practical_marks = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(50)]
    )
    course_duration = models.CharField(max_length=50, blank=True, default='3 Months')
    serial_number = models.CharField(max_length=20, blank=True, default='')
    registration_number = models.CharField(max_length=100, blank=True, default='', db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower('certificate_id'),
                name='unique_lower_certificate_id'
            ),
        ]

    def clean(self):
        super().clean()
        if self.certificate_id:
            self.certificate_id = self.certificate_id.strip().upper()
            qs = Certificate.objects.filter(certificate_id__iexact=self.certificate_id)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({'certificate_id': "⚠ Certificate ID already exists. Please enter a unique ID."})

    def generate_verification_hash(self):
        """Generates a SHA-256 hash for certificate data verification."""
        data_str = f"{self.certificate_id}|{self.student_name}|{self.course_id}|{self.issue_date}|{self.grade or ''}"
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

    def save(self, *args, **kwargs):
        if self.certificate_id:
            self.certificate_id = self.certificate_id.strip().upper()
            qs = Certificate.objects.filter(certificate_id__iexact=self.certificate_id)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise IntegrityError("⚠ Certificate ID already exists. Please enter a unique ID.")

        fn = self.first_name.strip() if self.first_name else ""
        mn = self.middle_name.strip() if self.middle_name else ""
        ln = self.last_name.strip() if self.last_name else ""
        
        if fn or ln:
            if mn:
                self.student_name = f"{fn} {mn} {ln}"
            else:
                self.student_name = f"{fn} {ln}"

        if self.prefix == 'CITI':
            if self.serial_number and not self.registration_number:
                self.registration_number = self.format_citi_registration_number(self.serial_number, self.issue_date)
            if self.theory_marks is not None and self.practical_marks is not None:
                calc_grade = self.calculate_citi_grade(self.theory_marks + self.practical_marks)
                if calc_grade:
                    self.grade = calc_grade
                
        if not self.verification_hash:
            self.verification_hash = self.generate_verification_hash()
        if not self.verification_token:
            self.verification_token = self.verification_hash[:16].upper()
        super().save(*args, **kwargs)

    @property
    def total_marks(self):
        if self.theory_marks is not None and self.practical_marks is not None:
            return self.theory_marks + self.practical_marks
        return None

    @property
    def percentage(self):
        return self.total_marks

    @classmethod
    def calculate_citi_grade(cls, total):
        """
        Grade scale (from CCC marksheet):
        S: 85% and above
        A: 75% to 84%
        B: 65% to 74%
        C: 55% to 64%
        D: 50% to 54%
        Below 50%: None (Not Eligible)
        """
        if total is None:
            return None
        if total >= 85:
            return 'S'
        elif total >= 75:
            return 'A'
        elif total >= 65:
            return 'B'
        elif total >= 55:
            return 'C'
        elif total >= 50:
            return 'D'
        return None

    @classmethod
    def compute_financial_year(cls, d=None):
        if d is None:
            import datetime
            d = datetime.date.today()
        year = d.year
        if d.month >= 4:
            next_yr_short = str(year + 1)[-2:]
            return f"{year}-{next_yr_short}"
        else:
            prev_yr = year - 1
            yr_short = str(year)[-2:]
            return f"{prev_yr}-{yr_short}"

    @classmethod
    def format_citi_registration_number(cls, serial, d=None):
        fy = cls.compute_financial_year(d)
        return f"CITI/GNR/{fy}/{serial}"

    @property
    def is_ccc(self):
        """Returns True if the certificate belongs to Course on Computer Concepts (CCC)."""
        if not self.course:
            return False
        course_name = (self.course.name or '').strip().lower()
        return (
            course_name == 'ccc' or
            'course on computer concepts' in course_name or
            course_name.startswith('ccc ') or
            course_name.endswith(' ccc') or
            '(ccc)' in course_name
        )

    @property
    def prefix(self):
        """Returns the certificate prefix (RAS, CITI, etc.) from certificate_id."""
        if self.certificate_id and '-' in self.certificate_id:
            return self.certificate_id.split('-')[0].upper()
        return ''

    def __str__(self):
        return f"{self.certificate_id} - {self.student_name} ({self.course.name})"


class CertificateSequence(models.Model):
    """
    Independent persistent sequence counters per certificate prefix (RAS, CITI).
    - RAS counter starts at 1001.
    - CITI counter starts at 5001.
    - Persistent across restarts, redeployments, month/year changes.
    - Concurrency-safe atomic reservation via database-level row locking.
    - Never decremented, reused, or reset upon deletion/cancellation.
    - Upper limit: 9999.
    """
    prefix = models.CharField(max_length=20, unique=True, db_index=True)
    next_sequence = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Certificate Sequence'
        verbose_name_plural = 'Certificate Sequences'

    def __str__(self):
        return f"{self.prefix}: {self.next_sequence}"


class CertificateRandomCodeRegistry(models.Model):
    """
    Permanent database registry for globally unique six-digit numeric codes (100000-999999).
    - Database-level unique constraint on code.
    - Cryptographically secure random allocation with atomic insert.
    - Never released or reused, including after certificate deletion or cancellation.
    - Safe collision retry with exhaustion protection (maximum 900,000 allocations).
    """
    STATUS_CHOICES = [
        ('allocated', 'Allocated'),
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
    ]
    code = models.CharField(max_length=6, unique=True, db_index=True)
    certificate_id = models.CharField(max_length=50, blank=True, default='', db_index=True)
    allocated_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='allocated')

    class Meta:
        verbose_name = 'Certificate Random Code Allocation'
        verbose_name_plural = 'Certificate Random Code Allocations'

    def __str__(self):
        return f"{self.code} -> {self.certificate_id or 'reserved'} ({self.status})"




import hashlib
from django.db import models
from django.contrib.auth.models import User

class Certificate(models.Model):
    certificate_id = models.CharField(max_length=30, unique=True, db_index=True)
    first_name = models.CharField(max_length=100, blank=True, default='')
    middle_name = models.CharField(max_length=100, blank=True, default='')
    last_name = models.CharField(max_length=100, blank=True, default='')
    student_name = models.CharField(max_length=200)
    student = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='certificates')
    course = models.ForeignKey('courses.Course', on_delete=models.PROTECT)
    course_start_date = models.DateField(null=True, blank=True)
    course_end_date = models.DateField(null=True, blank=True)
    issue_date = models.DateField()
    grade = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verification_token = models.CharField(max_length=64, blank=True, null=True)
    verification_hash = models.CharField(max_length=64, blank=True, null=True)
    printed_at = models.DateTimeField(blank=True, null=True)
    last_verified_at = models.DateTimeField(blank=True, null=True)

    def generate_verification_hash(self):
        """Generates a SHA-256 hash for certificate data verification."""
        data_str = f"{self.certificate_id}|{self.student_name}|{self.course_id}|{self.issue_date}|{self.grade or ''}"
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

    def save(self, *args, **kwargs):
        fn = self.first_name.strip() if self.first_name else ""
        mn = self.middle_name.strip() if self.middle_name else ""
        ln = self.last_name.strip() if self.last_name else ""
        
        if fn or ln:
            if mn:
                self.student_name = f"{fn} {mn} {ln}"
            else:
                self.student_name = f"{fn} {ln}"
                
        if not self.verification_hash:
            self.verification_hash = self.generate_verification_hash()
        if not self.verification_token:
            self.verification_token = self.verification_hash[:16].upper()
        super().save(*args, **kwargs)

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

    def __str__(self):
        return f"{self.certificate_id} - {self.student_name} ({self.course.name})"



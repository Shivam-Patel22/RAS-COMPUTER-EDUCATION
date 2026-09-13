from django.db import models
from django.contrib.auth.models import User
from courses.models import Course

class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    phone = models.CharField(max_length=20, blank=True, null=True)
    enrolled_course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='enrolled_students')
    notes = models.TextField(blank=True, null=True)
    must_change_password = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"StudentProfile for {self.user.username}"

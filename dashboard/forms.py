from django import forms
from django.contrib.auth.models import User
from courses.models import Course, CourseCategory
from certificates.models import Certificate
from certificates.utils import (
    generate_certificate_id,
    validate_certificate_id_format,
    get_student_initials,
    extract_recipient_initials,
    preview_certificate_id,
    get_next_citi_serial,
    SequenceExhaustedError,
    RandomCodeExhaustedError,
)
import os
from datetime import datetime

class AdminLoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Staff Username or Email', 'required': 'required'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password', 'required': 'required'})
    )

class TwoFactorVerifyForm(forms.Form):
    otp_token = forms.CharField(
        max_length=16,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '6-digit code or 16-character backup code',
            'required': 'required',
            'autocomplete': 'one-time-code',
            'autofocus': 'autofocus',
        }),
        label="Two-Factor Authentication Code",
    )

class TwoFactorSetupForm(forms.Form):
    token = forms.CharField(
        max_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter 6-digit code from authenticator app',
            'required': 'required',
            'autocomplete': 'one-time-code',
            'autofocus': 'autofocus',
            'inputmode': 'numeric',
            'pattern': '[0-9]{6}',
        }),
        label="Verification Code",
    )

class AdminCourseCategoryForm(forms.ModelForm):
    class Meta:
        model = CourseCategory
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category Name (e.g. Data Science, Web Design)', 'required': 'required'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Brief description of this category (optional)', 'rows': 3}),
        }
        labels = {
            'name': 'Category Name *',
            'description': 'Description',
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Category name cannot be empty.")
        qs = CourseCategory.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f"A category with name '{name}' already exists.")
        return name


class FlexibleCategoryChoiceField(forms.ModelChoiceField):
    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            return super().to_python(value)
        except forms.ValidationError:
            from django.db.models import Q
            from django.utils.text import slugify
            str_val = str(value).strip()
            if not str_val:
                return None
            cat = CourseCategory.objects.filter(Q(slug=str_val) | Q(name__iexact=str_val)).first()
            if not cat:
                slug_cand = slugify(str_val) or str_val.lower()
                name_cand = str_val.replace('-', ' ').title()
                cat, _ = CourseCategory.objects.get_or_create(slug=slug_cand, defaults={'name': name_cand})
            return cat


class AdminCourseForm(forms.ModelForm):
    category = FlexibleCategoryChoiceField(
        queryset=CourseCategory.objects.all().order_by('name'),
        required=False,
        empty_label="-- Select Category (Optional) --",
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Course Category"
    )
    remove_image = forms.BooleanField(
        required=False,
        label="Remove current image",
        widget=forms.CheckboxInput(attrs={'style': 'width: 16px; height: 16px; cursor: pointer;'})
    )

    class Meta:
        model = Course
        fields = ['name', 'category', 'duration', 'description', 'image', 'is_featured']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Course Name', 'required': 'required'}),
            'duration': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 8 Weeks / 3 Months', 'required': 'required'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Detailed syllabus and overview', 'rows': 5, 'required': 'required'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'is_featured': forms.CheckboxInput(attrs={'style': 'width: 20px; height: 20px; cursor: pointer;'}),
        }
        labels = {
            'category': 'Course Category',
            'is_featured': '⭐ Feature this course on homepage',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = CourseCategory.objects.all().order_by('name')
        if self.instance and self.instance.pk:
            if self.instance.category_ref:
                self.initial['category'] = self.instance.category_ref.pk
            elif self.instance.category:
                from django.db.models import Q
                cat = CourseCategory.objects.filter(
                    Q(slug=self.instance.category) | Q(name__iexact=self.instance.category)
                ).first()
                if cat:
                    self.initial['category'] = cat.pk

    def clean_category(self):
        cat_obj = self.cleaned_data.get('category')
        # Return slug string so CharField validation passes
        return cat_obj.slug if cat_obj else ''

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'content_type'):
            if not image.content_type.startswith('image/'):
                raise forms.ValidationError("Please upload a valid image file (e.g., JPG, PNG, WEBP).")
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Image file size must not exceed 5MB.")
        return image

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Note: self.cleaned_data['category'] is slug string
        slug_val = self.cleaned_data.get('category')
        if slug_val:
            instance.category = slug_val
            instance.category_ref = CourseCategory.objects.filter(slug=slug_val).first()
        else:
            instance.category = ''
            instance.category_ref = None
        remove_image = self.cleaned_data.get('remove_image', False)
        has_new_image = bool(self.files and self.files.get('image'))

        old_image_name = None
        if instance.pk:
            try:
                current_db_instance = Course.objects.get(pk=instance.pk)
                if current_db_instance.image:
                    old_image_name = current_db_instance.image.name
            except Course.DoesNotExist:
                pass

        if has_new_image:
            # Newly uploaded image takes priority over remove_image
            if old_image_name:
                self._delete_old_image_if_not_shared(instance, old_image_name)
        elif remove_image:
            # Clear image reference from course
            instance.image = None
            if old_image_name:
                self._delete_old_image_if_not_shared(instance, old_image_name)

        if commit:
            instance.save()
            self.save_m2m()
        return instance

    def _delete_old_image_if_not_shared(self, instance, old_image_name):
        if not old_image_name:
            return
        is_shared = Course.objects.filter(image=old_image_name).exclude(pk=instance.pk).exists()
        if not is_shared:
            try:
                storage = instance._meta.get_field('image').storage
                if storage.exists(old_image_name):
                    storage.delete(old_image_name)
            except Exception:
                pass


PREFIX_CHOICES = [
    ('RAS', 'RAS'),
    ('CITI', 'CITI'),
]


class AdminCertificateForm(forms.ModelForm):
    prefix = forms.ChoiceField(
        choices=PREFIX_CHOICES,
        initial='RAS',
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_prefix'})
    )
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name *', 'required': 'required'})
    )
    middle_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Middle Name *', 'required': 'required'})
    )
    last_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'})
    )
    student_photo = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'id': 'id_student_photo', 'accept': 'image/jpeg,image/png,image/jpg'})
    )
    theory_marks = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=50,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_theory_marks', 'placeholder': 'Theory Marks (0–50)', 'min': '0', 'max': '50'})
    )
    practical_marks = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=50,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_practical_marks', 'placeholder': 'Practical Marks (0–50)', 'min': '0', 'max': '50'})
    )
    course_duration = forms.CharField(
        max_length=50,
        required=False,
        initial='3 Months',
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_course_duration', 'placeholder': 'Course Duration (e.g. 3 Months)'})
    )
    serial_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_serial_number', 'placeholder': 'Serial No. (e.g. 4327)'})
    )

    class Meta:
        model = Certificate
        fields = [
            'prefix', 'certificate_id', 'first_name', 'middle_name', 'last_name',
            'course', 'course_start_date', 'course_end_date', 'issue_date', 'grade',
            'student_photo', 'theory_marks', 'practical_marks', 'course_duration', 'serial_number'
        ]
        widgets = {
            'certificate_id': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_certificate_id', 'readonly': 'readonly'}),
            'course': forms.Select(attrs={'class': 'form-control', 'required': 'required'}),
            'course_start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'min': '1000-01-01', 'max': '9999-12-31', 'required': 'required'}),
            'course_end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'min': '1000-01-01', 'max': '9999-12-31', 'required': 'required'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'min': '1000-01-01', 'max': '9999-12-31', 'required': 'required'}),
            'grade': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Grade A / Pass'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.certificate_id:
                cert_id_upper = self.instance.certificate_id.strip().upper()
                if cert_id_upper.startswith('CITI'):
                    self.initial['prefix'] = 'CITI'
                elif cert_id_upper.startswith('RAS'):
                    self.initial['prefix'] = 'RAS'
            if self.instance.serial_number:
                self.initial['serial_number'] = self.instance.serial_number
            if self.instance.course_duration:
                self.initial['course_duration'] = self.instance.course_duration
            if self.instance.theory_marks is not None:
                self.initial['theory_marks'] = self.instance.theory_marks
            if self.instance.practical_marks is not None:
                self.initial['practical_marks'] = self.instance.practical_marks
            if not self.initial.get('first_name'):
                if self.instance.first_name:
                    self.initial['first_name'] = self.instance.first_name
                    self.initial['middle_name'] = self.instance.middle_name
                    self.initial['last_name'] = self.instance.last_name
                elif self.instance.student_name:
                    parts = self.instance.student_name.strip().split()
                    if len(parts) >= 3:
                        self.initial['first_name'] = parts[0]
                        self.initial['middle_name'] = " ".join(parts[1:-1])
                        self.initial['last_name'] = parts[-1]
                    elif len(parts) == 2:
                        self.initial['first_name'] = parts[0]
                        self.initial['middle_name'] = ""
                        self.initial['last_name'] = parts[1]
                    elif len(parts) == 1:
                        self.initial['first_name'] = parts[0]
                        self.initial['middle_name'] = ""
                        self.initial['last_name'] = ""
        else:
            self.initial.setdefault('serial_number', get_next_citi_serial())
            self.initial.setdefault('course_duration', '3 Months')
            current_prefix = self.initial.get('prefix', 'RAS')
            fn = self.initial.get('first_name', '')
            ln = self.initial.get('last_name', '')
            if not self.initial.get('certificate_id'):
                self.initial['certificate_id'] = preview_certificate_id(prefix=current_prefix, first_name=fn, last_name=ln)

    def clean_course_start_date(self):
        start_date = self.cleaned_data.get('course_start_date')
        if start_date:
            if start_date.year < 1000 or start_date.year > 9999:
                raise forms.ValidationError("Please enter a valid 4-digit year (1000–9999).")
        return start_date

    def clean_course_end_date(self):
        end_date = self.cleaned_data.get('course_end_date')
        if end_date:
            if end_date.year < 1000 or end_date.year > 9999:
                raise forms.ValidationError("Please enter a valid 4-digit year (1000–9999).")
        return end_date

    def clean_issue_date(self):
        issue_date = self.cleaned_data.get('issue_date')
        if issue_date:
            if issue_date.year < 1000 or issue_date.year > 9999:
                raise forms.ValidationError("Please enter a valid 4-digit year (1000–9999).")
        return issue_date

    def clean_certificate_id(self):
        cert_id = self.cleaned_data.get('certificate_id', '').strip().upper()
        if cert_id and self.data.get('id_gen_mode') == 'manual':
            qs = Certificate.objects.filter(certificate_id__iexact=cert_id)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("⚠ Certificate ID already exists. Please enter a unique ID.")
        return cert_id

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('course_start_date')
        end_date = cleaned_data.get('course_end_date')
        if start_date and end_date:
            if end_date < start_date:
                self.add_error('course_end_date', "Course End Date cannot be earlier than Course Start Date.")

        prefix = cleaned_data.get('prefix', 'RAS')
        fn = cleaned_data.get('first_name', '').strip()
        ln = cleaned_data.get('last_name', '').strip()
        cert_id = cleaned_data.get('certificate_id', '').strip().upper()
        id_gen_mode = self.data.get('id_gen_mode', 'auto')

        # Preserve historical or unchanged existing certificate IDs on edit
        if self.instance and self.instance.pk and self.instance.certificate_id and cert_id == self.instance.certificate_id.upper():
            return cleaned_data

        if not fn:
            self.add_error('first_name', "First Name is required.")
        if not ln:
            self.add_error('last_name', "Last Name is required.")

        initials = None
        if fn and ln:
            try:
                initials = extract_recipient_initials(first_name=fn, last_name=ln)
            except ValueError as e:
                self.add_error('first_name', str(e))

        if id_gen_mode == 'manual':
            # Manual Mode: strictly validate prefix, format, student initials, and uniqueness
            is_valid, error_msg = validate_certificate_id_format(cert_id, prefix=prefix, expected_initials=initials, allow_legacy=True)
            if not is_valid:
                self.add_error('certificate_id', error_msg)
            else:
                qs = Certificate.objects.filter(certificate_id__iexact=cert_id)
                if self.instance and self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    self.add_error('certificate_id', "⚠ Certificate ID already exists. Please enter a unique ID.")
                else:
                    # Register manual random code if it matches standard pattern
                    parts = cert_id.split('-')
                    if (len(parts) == 5 or len(parts) == 6) and len(parts[4]) == 6 and parts[4].isdigit():
                        from certificates.models import CertificateRandomCodeRegistry
                        CertificateRandomCodeRegistry.objects.get_or_create(
                            code=parts[4],
                            defaults={'certificate_id': cert_id, 'status': 'active'}
                        )


        if prefix == 'CITI':
            # 1. Course validation - must be CCC
            course = cleaned_data.get('course')
            if course:
                c_name = (course.name or '').strip().lower()
                if not ('ccc' in c_name or 'computer concepts' in c_name):
                    self.add_error('course', "For CITI certificates, course must be 'Certificate Course on Computer Concepts (CCC)'.")

            # 2. Student photo validation
            photo = cleaned_data.get('student_photo')
            has_photo = bool(photo or (self.instance and self.instance.pk and self.instance.student_photo))
            if not has_photo:
                self.add_error('student_photo', "Student photo is required for CITI certificates.")
            elif photo and hasattr(photo, 'file'):
                if photo.size > 2 * 1024 * 1024:
                    self.add_error('student_photo', "Photo file size exceeds 2 MB. Please upload an image under 2 MB.")
                else:
                    try:
                        from PIL import Image
                        import io
                        from django.core.files.uploadedfile import InMemoryUploadedFile

                        photo.seek(0)
                        img = Image.open(photo)
                        img.verify()

                        photo.seek(0)
                        img = Image.open(photo)
                        if img.mode not in ('RGB', 'L'):
                            img = img.convert('RGB')

                        # Resize to ~400px wide
                        target_w = 400
                        if img.width > target_w:
                            target_h = int(img.height * (target_w / img.width))
                            img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

                        out_io = io.BytesIO()
                        img.save(out_io, format='JPEG', quality=88, optimize=True)
                        out_io.seek(0)

                        file_name = os.path.splitext(photo.name)[0] + '.jpg'
                        cleaned_data['student_photo'] = InMemoryUploadedFile(
                            out_io, 'student_photo', file_name, 'image/jpeg', out_io.getbuffer().nbytes, None
                        )
                    except Exception as e:
                        self.add_error('student_photo', f"Invalid image file: {str(e)}")

            # 3. Marks validation (0-50 each)
            tm = cleaned_data.get('theory_marks')
            pm = cleaned_data.get('practical_marks')
            if tm is None:
                self.add_error('theory_marks', "Theory marks (0–50) are required for CITI CCC.")
            elif not (0 <= tm <= 50):
                self.add_error('theory_marks', "Theory marks must be between 0 and 50.")

            if pm is None:
                self.add_error('practical_marks', "Practical marks (0–50) are required for CITI CCC.")
            elif not (0 <= pm <= 50):
                self.add_error('practical_marks', "Practical marks must be between 0 and 50.")

            if tm is not None and pm is not None and 0 <= tm <= 50 and 0 <= pm <= 50:
                total = tm + pm
                if total < 50:
                    self.add_error(None, f"Candidate obtained {total}/100 ({total}%), which is below 50%. Status: Not Eligible. Certificate generation blocked.")
                else:
                    grade = Certificate.calculate_citi_grade(total)
                    cleaned_data['grade'] = grade

            # 4. Serial & registration number
            serial = cleaned_data.get('serial_number', '').strip()
            if not serial:
                serial = get_next_citi_serial()
                cleaned_data['serial_number'] = serial

            issue_d = cleaned_data.get('issue_date')
            reg_num = Certificate.format_citi_registration_number(serial, issue_d)
            cleaned_data['registration_number'] = reg_num

            # Check for duplicate registration numbers across CITI certificates
            if reg_num:
                existing_qs = Certificate.objects.filter(registration_number=reg_num)
                if self.instance and self.instance.pk:
                    existing_qs = existing_qs.exclude(pk=self.instance.pk)
                if existing_qs.exists():
                    self.add_error(
                        'serial_number',
                        f"Registration number '{reg_num}' is already assigned to another certificate. Please choose a unique serial number."
                    )

            if not cleaned_data.get('course_duration'):
                cleaned_data['course_duration'] = '3 Months'

        if id_gen_mode != 'manual' and not self.errors:
            if fn and ln and initials:
                try:
                    submitted_cert_id = self.cleaned_data.get('certificate_id', '').strip().upper()
                    extracted_code = None
                    if submitted_cert_id:
                        parts = submitted_cert_id.split('-')
                        if (len(parts) == 5 or len(parts) == 6) and parts[4].isdigit() and len(parts[4]) == 6:
                            extracted_code = int(parts[4])

                    cert_id = generate_certificate_id(
                        prefix=prefix,
                        first_name=fn,
                        last_name=ln,
                        initials=initials,
                        random_code=extracted_code,
                        reserve=True
                    )
                    cleaned_data['certificate_id'] = cert_id
                except (SequenceExhaustedError, RandomCodeExhaustedError) as e:
                    self.add_error('certificate_id', str(e))

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        cert_id = self.cleaned_data.get('certificate_id', '').strip().upper()
        if cert_id:
            instance.certificate_id = cert_id
        fn = self.cleaned_data.get('first_name', '').strip()
        mn = self.cleaned_data.get('middle_name', '').strip()
        ln = self.cleaned_data.get('last_name', '').strip()
        instance.first_name = fn
        instance.middle_name = mn
        instance.last_name = ln
        if mn:
            instance.student_name = f"{fn} {mn} {ln}"
        else:
            instance.student_name = f"{fn} {ln}"

        prefix = self.cleaned_data.get('prefix', 'RAS')
        if prefix == 'CITI':
            instance.course_duration = self.cleaned_data.get('course_duration', '3 Months')
            instance.serial_number = self.cleaned_data.get('serial_number', '')
            instance.registration_number = self.cleaned_data.get('registration_number', '')
            instance.theory_marks = self.cleaned_data.get('theory_marks')
            instance.practical_marks = self.cleaned_data.get('practical_marks')
            if 'student_photo' in self.cleaned_data and self.cleaned_data['student_photo']:
                instance.student_photo = self.cleaned_data['student_photo']

        if commit:
            instance.save()
        return instance

from courses.models import CourseOffer

class AdminOfferForm(forms.ModelForm):
    class Meta:
        model = CourseOffer
        fields = ['title', 'description', 'course', 'discount', 'badge', 'start_date', 'end_date', 'priority', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 30% OFF on Python Course', 'required': 'required', 'id': 'id_title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Offer overview & terms', 'rows': 3}),
            'course': forms.Select(attrs={'class': 'form-control'}),
            'discount': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 30% OFF / ₹999 Only', 'id': 'id_discount'}),
            'badge': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 🎉 SPECIAL OFFER', 'id': 'id_badge'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'min': '1000-01-01', 'max': '9999-12-31'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'min': '1000-01-01', 'max': '9999-12-31'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

class AdminStudentForm(forms.Form):
    full_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name (e.g. Rahul Sharma)', 'required': 'required'})
    )
    username = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username (Optional, auto-generated if blank)'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address', 'required': 'required'})
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number (Optional)'})
    )
    course = forms.ModelChoiceField(
        queryset=Course.objects.all().order_by('name'),
        required=False,
        empty_label="— Select Enrolled Course (Optional) —",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_joined = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'min': '1000-01-01', 'max': '9999-12-31'})
    )
    is_active = forms.ChoiceField(
        choices=[('1', 'Active'), ('0', 'Inactive')],
        initial='1',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Optional internal notes...', 'rows': 2})
    )

from core.models import AboutContent, ContactContent
import json

class AdminAboutForm(forms.ModelForm):
    legacy_cards_data = forms.CharField(required=False, widget=forms.HiddenInput())
    why_benefits_data = forms.CharField(required=False, widget=forms.HiddenInput())
    specs_cards_data = forms.CharField(required=False, widget=forms.HiddenInput())
    testimonials_data = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = AboutContent
        fields = [
            'heading', 'subtitle', 'mission_title', 'description',
            'feature_1_title', 'feature_1_desc', 'feature_2_title', 'feature_2_desc', 'feature_3_title', 'feature_3_desc',
            'intro_badge', 'intro_heading', 'intro_lead', 'intro_text',
            'legacy_title', 'legacy_desc',
            'why_title', 'why_desc', 'why_subheading',
            'specs_title', 'specs_desc',
            'mv_title', 'mission_text', 'vision_title', 'vision_text',
            'testimonials_title', 'testimonials_desc',
            'cta_title', 'cta_desc', 'cta_btn1_text', 'cta_btn1_url', 'cta_btn2_text', 'cta_btn2_url',
        ]
        widgets = {
            'heading': forms.TextInput(attrs={'class': 'form-control'}),
            'subtitle': forms.TextInput(attrs={'class': 'form-control'}),
            'mission_title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'feature_1_title': forms.TextInput(attrs={'class': 'form-control'}),
            'feature_1_desc': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'feature_2_title': forms.TextInput(attrs={'class': 'form-control'}),
            'feature_2_desc': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'feature_3_title': forms.TextInput(attrs={'class': 'form-control'}),
            'feature_3_desc': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            # Section A
            'intro_badge': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Premier Computer Institute in Gandhinagar'}),
            'intro_heading': forms.TextInput(attrs={'class': 'form-control'}),
            'intro_lead': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'intro_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            # Section B
            'legacy_title': forms.TextInput(attrs={'class': 'form-control'}),
            'legacy_desc': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            # Section C
            'why_title': forms.TextInput(attrs={'class': 'form-control'}),
            'why_desc': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'why_subheading': forms.TextInput(attrs={'class': 'form-control'}),
            # Section D
            'specs_title': forms.TextInput(attrs={'class': 'form-control'}),
            'specs_desc': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            # Section E
            'mv_title': forms.TextInput(attrs={'class': 'form-control'}),
            'mission_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'vision_title': forms.TextInput(attrs={'class': 'form-control'}),
            'vision_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            # Section F
            'testimonials_title': forms.TextInput(attrs={'class': 'form-control'}),
            'testimonials_desc': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            # CTA
            'cta_title': forms.TextInput(attrs={'class': 'form-control'}),
            'cta_desc': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'cta_btn1_text': forms.TextInput(attrs={'class': 'form-control'}),
            'cta_btn1_url': forms.TextInput(attrs={'class': 'form-control'}),
            'cta_btn2_text': forms.TextInput(attrs={'class': 'form-control'}),
            'cta_btn2_url': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.required = False

    def clean(self):
        cleaned_data = super().clean()

        # At least one heading is required
        heading = (cleaned_data.get('heading') or '').strip()
        intro_heading = (cleaned_data.get('intro_heading') or '').strip()

        # If heading was explicitly provided as empty in POST (e.g. testing validation error)
        if 'heading' in self.data and not heading and not intro_heading:
            self.add_error('heading', 'This field is required.')

        if not heading and intro_heading:
            cleaned_data['heading'] = intro_heading
        elif not intro_heading and heading:
            cleaned_data['intro_heading'] = heading

        # Preserve instance values for empty fields if available
        if self.instance and self.instance.pk:
            for field in ['subtitle', 'mission_title', 'description', 'feature_1_title', 'feature_1_desc', 'feature_2_title', 'feature_2_desc', 'feature_3_title', 'feature_3_desc']:
                if not cleaned_data.get(field) and field not in self.data:
                    cleaned_data[field] = getattr(self.instance, field, '')

        # Parse JSON fields if provided in data
        for data_key, model_field in [
            ('legacy_cards_data', 'legacy_cards'),
            ('why_benefits_data', 'why_benefits'),
            ('specs_cards_data', 'specs_cards'),
            ('testimonials_data', 'testimonials'),
            ('legacy_cards', 'legacy_cards'),
            ('why_benefits', 'why_benefits'),
            ('specs_cards', 'specs_cards'),
            ('testimonials', 'testimonials'),
        ]:
            raw_val = self.data.get(data_key)
            if raw_val is not None:
                if isinstance(raw_val, str) and raw_val.strip():
                    try:
                        parsed = json.loads(raw_val)
                        if isinstance(parsed, list):
                            cleaned_data[model_field] = parsed
                    except Exception:
                        pass
                elif isinstance(raw_val, list):
                    cleaned_data[model_field] = raw_val

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        cleaned_data = self.cleaned_data

        if 'legacy_cards' in cleaned_data:
            instance.legacy_cards = cleaned_data['legacy_cards']
        if 'why_benefits' in cleaned_data:
            instance.why_benefits = cleaned_data['why_benefits']
        if 'specs_cards' in cleaned_data:
            instance.specs_cards = cleaned_data['specs_cards']
        if 'testimonials' in cleaned_data:
            instance.testimonials = cleaned_data['testimonials']

        if cleaned_data.get('intro_heading') and not cleaned_data.get('heading'):
            instance.heading = cleaned_data['intro_heading']
        elif cleaned_data.get('heading') and not cleaned_data.get('intro_heading'):
            instance.intro_heading = cleaned_data['heading']

        instance.sync_version = (instance.sync_version or 0) + 1

        if commit:
            instance.save()
        return instance


class AdminContactForm(forms.ModelForm):
    class Meta:
        model = ContactContent
        fields = [
            'phone', 'whatsapp_number', 'email', 'address', 'working_hours', 'map_embed_url',
            'instagram_username', 'instagram_url', 'facebook_name', 'facebook_url'
        ]
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. +91 98765 43210', 'required': 'required'}),
            'whatsapp_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. +91 91049 94493'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'required': 'required'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'required': 'required'}),
            'working_hours': forms.TextInput(attrs={'class': 'form-control'}),
            'map_embed_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Google Maps Embed URL'}),
            'instagram_username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. @cdac_official or cdac_official'}),
            'instagram_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'e.g. https://www.instagram.com/cdac_official/'}),
            'facebook_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. CDAC Computer Education'}),
            'facebook_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'e.g. https://www.facebook.com/cdacclasses/'}),
        }
        labels = {
            'phone': 'Contact Phone Number *',
            'whatsapp_number': 'WhatsApp Contact Number',
            'email': 'Official Email Address *',
            'address': 'Campus Office Address *',
            'working_hours': 'Working / Office Hours',
            'map_embed_url': 'Google Maps Embed URL',
            'instagram_username': 'Instagram Username / Display Name',
            'instagram_url': 'Instagram Profile URL',
            'facebook_name': 'Facebook Page / Display Name',
            'facebook_url': 'Facebook Page URL',
        }

    def clean_instagram_url(self):
        url = self.cleaned_data.get('instagram_url', '')
        if not url:
            return ''
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        if not (url.startswith('http://') or url.startswith('https://')):
            raise forms.ValidationError("Please enter a valid HTTP/HTTPS URL.")
        lower_url = url.lower()
        if 'instagram.com' not in lower_url and 'instagr.am' not in lower_url:
            raise forms.ValidationError("Please enter a valid Instagram profile URL (e.g. https://www.instagram.com/username/).")
        return url

    def clean_facebook_url(self):
        url = self.cleaned_data.get('facebook_url', '')
        if not url:
            return ''
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        if not (url.startswith('http://') or url.startswith('https://')):
            raise forms.ValidationError("Please enter a valid HTTP/HTTPS URL.")
        lower_url = url.lower()
        if 'facebook.com' not in lower_url and 'fb.com' not in lower_url and 'fb.me' not in lower_url:
            raise forms.ValidationError("Please enter a valid Facebook page URL (e.g. https://www.facebook.com/pagename/).")
        return url


class AdminChangeUsernameForm(forms.Form):
    new_username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_new_username',
            'placeholder': 'Enter new username',
            'required': 'required',
            'autocomplete': 'username'
        }),
        label="New Username"
    )
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'id_username_current_password',
            'placeholder': 'Enter current password to confirm',
            'required': 'required',
            'autocomplete': 'current-password'
        }),
        label="Current Password"
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_new_username(self):
        new_username = self.cleaned_data.get('new_username', '').strip()
        if not new_username:
            raise forms.ValidationError("New username cannot be empty.")
        if new_username == self.user.username:
            raise forms.ValidationError("New username must be different from your current username.")

        # Run Django User model username validators (format, allowed characters)
        username_field = User._meta.get_field('username')
        for validator in username_field.validators:
            validator(new_username)

        # Ensure uniqueness across existing users
        if User.objects.filter(username__iexact=new_username).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("This username is already taken. Please choose another.")

        return new_username

    def clean_current_password(self):
        current_password = self.cleaned_data.get('current_password')
        if current_password and not self.user.check_password(current_password):
            raise forms.ValidationError("Incorrect current password.")
        return current_password

    def save(self):
        new_username = self.cleaned_data['new_username']
        self.user.username = new_username
        self.user.save(update_fields=['username'])
        return self.user


class AdminChangePasswordForm(forms.Form):
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'id_password_current_password',
            'placeholder': 'Enter current password',
            'required': 'required',
            'autocomplete': 'current-password'
        }),
        label="Current Password"
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'id_new_password',
            'placeholder': 'Enter new password',
            'required': 'required',
            'autocomplete': 'new-password'
        }),
        label="New Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'id_confirm_password',
            'placeholder': 'Confirm new password',
            'required': 'required',
            'autocomplete': 'new-password'
        }),
        label="Confirm New Password"
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        current_password = self.cleaned_data.get('current_password')
        if current_password and not self.user.check_password(current_password):
            raise forms.ValidationError("Incorrect current password.")
        return current_password

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')

        if new_password and confirm_password:
            if new_password != confirm_password:
                self.add_error('confirm_password', "The two password fields didn't match.")
            else:
                from django.contrib.auth.password_validation import validate_password
                try:
                    validate_password(new_password, user=self.user)
                except forms.ValidationError as error:
                    self.add_error('new_password', error)

        return cleaned_data

    def save(self):
        new_password = self.cleaned_data['new_password']
        self.user.set_password(new_password)
        self.user.save()
        return self.user





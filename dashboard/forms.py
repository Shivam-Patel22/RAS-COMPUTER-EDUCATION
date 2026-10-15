from django import forms
from django.contrib.auth.models import User
from courses.models import Course
from certificates.models import Certificate
from certificates.utils import generate_certificate_id, validate_certificate_id_format, get_student_initials
from datetime import datetime

class AdminLoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Staff Username or Email', 'required': 'required'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password', 'required': 'required'})
    )

class AdminCourseForm(forms.ModelForm):
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
            'category': forms.Select(attrs={'class': 'form-control', 'required': 'required'}),
            'duration': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 8 Weeks / 3 Months', 'required': 'required'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Detailed syllabus and overview', 'rows': 5, 'required': 'required'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'is_featured': forms.CheckboxInput(attrs={'style': 'width: 20px; height: 20px; cursor: pointer;'}),
        }
        labels = {
            'category': 'Course Category *',
            'is_featured': '⭐ Feature this course on homepage',
        }

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

    class Meta:
        model = Certificate
        fields = ['prefix', 'certificate_id', 'first_name', 'middle_name', 'last_name', 'course', 'course_start_date', 'course_end_date', 'issue_date', 'grade']
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
            current_prefix = self.initial.get('prefix', 'RAS')
            fn = self.initial.get('first_name', '')
            ln = self.initial.get('last_name', '')
            if not self.initial.get('certificate_id'):
                self.initial['certificate_id'] = generate_certificate_id(prefix=current_prefix, first_name=fn, last_name=ln)

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
        return self.cleaned_data.get('certificate_id', '').strip().upper()

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
        initials = get_student_initials(first_name=fn, last_name=ln)
        cert_id = cleaned_data.get('certificate_id', '').strip().upper()
        id_gen_mode = self.data.get('id_gen_mode', 'auto')

        # Auto-generate if blank
        if not cert_id:
            cert_id = generate_certificate_id(prefix=prefix, first_name=fn, last_name=ln)
            cleaned_data['certificate_id'] = cert_id

        # Preserve historical or unchanged existing certificate IDs on edit
        if self.instance and self.instance.pk and self.instance.certificate_id and cert_id == self.instance.certificate_id.upper():
            return cleaned_data

        if id_gen_mode == 'auto':
            # In auto mode, ensure the ID uses the selected prefix and correct student initials
            qs = Certificate.objects.filter(certificate_id__iexact=cert_id)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            expected_prefix_year = f"{prefix}-{datetime.now().year}-{initials}"
            if qs.exists() or not cert_id.startswith(expected_prefix_year):
                cert_id = generate_certificate_id(prefix=prefix, first_name=fn, last_name=ln)
                cleaned_data['certificate_id'] = cert_id
        else:
            # Manual Mode: strictly validate prefix, format, student initials, and uniqueness
            is_valid, error_msg = validate_certificate_id_format(cert_id, prefix=prefix, expected_initials=initials)
            if not is_valid:
                self.add_error('certificate_id', error_msg)
            else:
                qs = Certificate.objects.filter(certificate_id__iexact=cert_id)
                if self.instance and self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    self.add_error('certificate_id', f"Certificate ID '{cert_id}' is already in use. Please enter a unique Certificate ID.")

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

class AdminAboutForm(forms.ModelForm):
    class Meta:
        model = AboutContent
        fields = ['heading', 'subtitle', 'mission_title', 'description', 'feature_1_title', 'feature_1_desc', 'feature_2_title', 'feature_2_desc', 'feature_3_title', 'feature_3_desc']
        widgets = {
            'heading': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'subtitle': forms.TextInput(attrs={'class': 'form-control'}),
            'mission_title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'feature_1_title': forms.TextInput(attrs={'class': 'form-control'}),
            'feature_1_desc': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'feature_2_title': forms.TextInput(attrs={'class': 'form-control'}),
            'feature_2_desc': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'feature_3_title': forms.TextInput(attrs={'class': 'form-control'}),
            'feature_3_desc': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

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




from django import forms
from courses.models import Course

class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Full Name', 'required': 'required'})
    )
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Phone Number', 'required': 'required'})
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Your Email Address (Optional)'})
    )
    course = forms.ModelChoiceField(
        queryset=Course.objects.none(),
        empty_label="Select Interested Course",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Write your message or inquiry here...', 'rows': 5})
    )
    # Anti-bot honeypot field (hidden from real users, filled by automated spambots)
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'style': 'display:none !important;', 'tabindex': '-1', 'autocomplete': 'off'})
    )

    def clean_website(self):
        val = self.cleaned_data.get('website', '').strip()
        if val:
            raise forms.ValidationError("Automated submission detected.")
        return val

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['course'].queryset = Course.objects.all().order_by('name')


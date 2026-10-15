from django import forms

class CertificateVerificationForm(forms.Form):
    certificate_id = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter Certificate ID',
            'required': 'required'
        })
    )

    def clean_certificate_id(self):
        return self.cleaned_data.get('certificate_id', '').strip().lower()

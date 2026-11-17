import re

from django import forms
from django.conf import settings

from .models import Contact

E164_RE = re.compile(r'^\+[1-9]\d{7,14}$')


def normalize_phone_number(raw):
    """
    Turn user input into E.164 format (the format Twilio expects).

    Accepts:  +63 917 123 4567, +63-917-123-4567, 09171234567, (0917) 123-4567
    Returns:  +639171234567
    Raises:   forms.ValidationError with a readable message.
    """
    value = (raw or '').strip()
    if not value:
        raise forms.ValidationError("Please enter the recipient's phone number.")

    cleaned = re.sub(r'[\s\-().]', '', value)

    bad_chars = re.search(r'[^\d+]', cleaned)
    bad_plus = cleaned.count('+') > 1 or ('+' in cleaned and not cleaned.startswith('+'))
    if bad_chars or bad_plus:
        raise forms.ValidationError(
            'Phone number may only contain digits, spaces, dashes and a leading "+".'
        )

    if cleaned.startswith('00'):            # 00 63 917... -> +63 917...
        cleaned = '+' + cleaned[2:]
    elif cleaned.startswith('0'):           # local format 0917... -> +63917...
        cleaned = '+' + settings.SMS_DEFAULT_COUNTRY_CODE + cleaned[1:]
    elif not cleaned.startswith('+'):
        cleaned = '+' + cleaned

    if not E164_RE.match(cleaned):
        raise forms.ValidationError(
            'Invalid phone number. Use international format such as +639171234567 '
            '(country code + number, 8 to 15 digits).'
        )
    return cleaned


def count_segments(text):
    """Estimate how many SMS segments Twilio will bill (GSM: 160/153 chars, Unicode: 70/67)."""
    if not text:
        return 0
    try:
        text.encode('ascii')
        single, multi = 160, 153
    except UnicodeEncodeError:
        single, multi = 70, 67
    length = len(text)
    return 1 if length <= single else -(-length // multi)


class SMSForm(forms.Form):
    contact = forms.ModelChoiceField(
        queryset=Contact.objects.all(),
        required=False,
        empty_label='Choose a saved contact (optional)',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    to_number = forms.CharField(
        label='Recipient phone number',
        max_length=25,
        required=False,  # a friendlier "required" message is raised in clean_to_number
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+639171234567',
            'autocomplete': 'tel',
            'inputmode': 'tel',
        }),
        help_text='International format (+63...) or local PH format (09...).',
    )
    body = forms.CharField(
        label='Message',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Type your message here...',
            'maxlength': settings.SMS_MAX_LENGTH,
        }),
    )

    def clean_to_number(self):
        raw = self.cleaned_data.get('to_number', '')
        contact_id = self.data.get('contact')
        if not raw.strip() and contact_id:
            # Number left blank but a contact was picked: use the contact's number.
            try:
                return Contact.objects.get(pk=contact_id).phone_number
            except (Contact.DoesNotExist, ValueError):
                pass
        return normalize_phone_number(raw)

    def clean_body(self):
        body = (self.cleaned_data.get('body') or '').strip()
        if not body:
            raise forms.ValidationError('The message cannot be empty.')
        if len(body) > settings.SMS_MAX_LENGTH:
            raise forms.ValidationError(
                f'The message is too long ({len(body)} characters). '
                f'The maximum is {settings.SMS_MAX_LENGTH}.'
            )
        return body


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['name', 'phone_number']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Juan Dela Cruz'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+639171234567'}),
        }

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if not name:
            raise forms.ValidationError('Please enter a name.')
        return name

    def clean_phone_number(self):
        number = normalize_phone_number(self.cleaned_data.get('phone_number'))
        if Contact.objects.filter(phone_number=number).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('A contact with this phone number already exists.')
        return number

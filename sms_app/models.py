from django.core.validators import RegexValidator
from django.db import models

e164_validator = RegexValidator(
    regex=r'^\+[1-9]\d{7,14}$',
    message='Phone number must be in international format, e.g. +639171234567.',
)


class Contact(models.Model):
    """A saved recipient so users don't have to retype numbers (additional feature)."""

    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=16, unique=True, validators=[e164_validator])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.phone_number})'


class SMSMessage(models.Model):
    """One attempt to send an SMS. Used for history, the dashboard and status tracking."""

    # Statuses reported by Twilio, plus "not_sent" for attempts that never reached Twilio.
    STATUS_CHOICES = [
        ('not_sent', 'Not sent'),
        ('accepted', 'Accepted'),
        ('scheduled', 'Scheduled'),
        ('queued', 'Queued'),
        ('sending', 'Sending'),
        ('sent', 'Sent to carrier'),
        ('delivered', 'Delivered'),
        ('undelivered', 'Undelivered'),
        ('failed', 'Failed'),
        ('canceled', 'Canceled'),
    ]
    # Statuses that will not change any more.
    FINAL_STATUSES = {'not_sent', 'delivered', 'undelivered', 'failed', 'canceled'}
    # "The provider accepted it, but delivery is NOT confirmed yet."
    PENDING_STATUSES = {'accepted', 'scheduled', 'queued', 'sending', 'sent'}

    to_number = models.CharField(max_length=16)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_sent')
    provider_sid = models.CharField(max_length=64, blank=True)
    segments = models.PositiveSmallIntegerField(default=1)
    error_code = models.CharField(max_length=20, blank=True)
    error_message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'SMS message'

    def __str__(self):
        return f'To {self.to_number} - {self.status}'

    @property
    def is_final(self):
        return self.status in self.FINAL_STATUSES

    @property
    def is_pending(self):
        return self.status in self.PENDING_STATUSES

    @property
    def status_badge(self):
        """Bootstrap colour name used by the templates."""
        if self.status == 'delivered':
            return 'success'
        if self.status in self.PENDING_STATUSES:
            return 'info'
        return 'danger'

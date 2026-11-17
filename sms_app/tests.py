"""
Automated tests for the SMS app.

Twilio is always mocked, so running the tests never sends a real SMS and
never needs real credentials.   Run with:   python manage.py test
"""

from types import SimpleNamespace
from unittest import mock

import requests
from django.test import TestCase, override_settings
from django.urls import reverse
from twilio.base.exceptions import TwilioRestException

from . import services
from .forms import ContactForm, SMSForm, count_segments, normalize_phone_number
from .models import Contact, SMSMessage

FAKE_TWILIO = dict(
    TWILIO_ACCOUNT_SID='ACtest00000000000000000000000000',
    TWILIO_AUTH_TOKEN='test-token',
    TWILIO_FROM_NUMBER='+15005550006',
    TWILIO_MESSAGING_SERVICE_SID='',
)
NO_TWILIO = dict(
    TWILIO_ACCOUNT_SID='', TWILIO_AUTH_TOKEN='', TWILIO_FROM_NUMBER='', TWILIO_MESSAGING_SERVICE_SID='',
)


def rest_error(code, status=400):
    return TwilioRestException(status=status, uri='/Messages.json', msg='provider said no', code=code)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
class PhoneNumberValidationTests(TestCase):
    def test_accepts_international_format(self):
        self.assertEqual(normalize_phone_number('+639171234567'), '+639171234567')

    def test_strips_spaces_dashes_and_brackets(self):
        self.assertEqual(normalize_phone_number(' +63 (917) 123-4567 '), '+639171234567')

    def test_converts_local_ph_format(self):
        self.assertEqual(normalize_phone_number('09171234567'), '+639171234567')

    def test_converts_00_prefix(self):
        self.assertEqual(normalize_phone_number('00639171234567'), '+639171234567')

    def test_rejects_letters(self):
        with self.assertRaisesMessage(Exception, 'may only contain digits'):
            normalize_phone_number('0917-CALL-ME')

    def test_rejects_too_short(self):
        with self.assertRaisesMessage(Exception, 'Invalid phone number'):
            normalize_phone_number('+63123')

    def test_rejects_too_long(self):
        with self.assertRaisesMessage(Exception, 'Invalid phone number'):
            normalize_phone_number('+6391712345678901')

    def test_rejects_plus_in_middle(self):
        with self.assertRaises(Exception):
            normalize_phone_number('63+9171234567')


class SMSFormTests(TestCase):
    def test_valid_form(self):
        form = SMSForm(data={'to_number': '09171234567', 'body': 'Hello'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['to_number'], '+639171234567')

    def test_empty_phone_number(self):
        form = SMSForm(data={'to_number': '', 'body': 'Hello'})
        self.assertFalse(form.is_valid())
        self.assertIn("enter the recipient's phone number", form.errors['to_number'][0])

    def test_empty_message(self):
        form = SMSForm(data={'to_number': '+639171234567', 'body': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('cannot be empty', form.errors['body'][0])

    def test_whitespace_only_message(self):
        form = SMSForm(data={'to_number': '+639171234567', 'body': '   \n  '})
        self.assertFalse(form.is_valid())

    def test_message_too_long(self):
        form = SMSForm(data={'to_number': '+639171234567', 'body': 'x' * 1601})
        self.assertFalse(form.is_valid())
        self.assertIn('too long', form.errors['body'][0])

    def test_contact_used_when_number_blank(self):
        c = Contact.objects.create(name='Ana', phone_number='+639181112222')
        form = SMSForm(data={'contact': c.pk, 'to_number': '', 'body': 'Hi'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['to_number'], '+639181112222')


class SegmentCounterTests(TestCase):
    def test_counts(self):
        self.assertEqual(count_segments(''), 0)
        self.assertEqual(count_segments('a' * 160), 1)
        self.assertEqual(count_segments('a' * 161), 2)
        self.assertEqual(count_segments('ñ' * 70), 1)   # Unicode: 70 per single SMS
        self.assertEqual(count_segments('ñ' * 71), 2)


class ContactFormTests(TestCase):
    def test_duplicate_number_rejected(self):
        Contact.objects.create(name='Ana', phone_number='+639181112222')
        form = ContactForm(data={'name': 'Ben', 'phone_number': '0918 111 2222'})
        self.assertFalse(form.is_valid())
        self.assertIn('already exists', form.errors['phone_number'][0])


# ---------------------------------------------------------------------------
# Provider integration (services.py)
# ---------------------------------------------------------------------------
@override_settings(**FAKE_TWILIO)
class ServiceTests(TestCase):
    def _client_returning(self, **create_kwargs):
        client = mock.MagicMock()
        client.messages.create.return_value = SimpleNamespace(**create_kwargs)
        return client

    def test_send_success_uses_from_number(self):
        client = self._client_returning(sid='SM123', status='queued', num_segments='1')
        with mock.patch.object(services, 'Client', return_value=client):
            result = services.send_sms('+639171234567', 'Hello')
        self.assertEqual(result.sid, 'SM123')
        self.assertEqual(result.status, 'queued')
        client.messages.create.assert_called_once_with(to='+639171234567', body='Hello', from_='+15005550006')

    @override_settings(TWILIO_MESSAGING_SERVICE_SID='MG123')
    def test_send_uses_messaging_service_when_set(self):
        client = self._client_returning(sid='SM1', status='accepted', num_segments='1')
        with mock.patch.object(services, 'Client', return_value=client):
            services.send_sms('+639171234567', 'Hi')
        self.assertEqual(client.messages.create.call_args.kwargs['messaging_service_sid'], 'MG123')

    @override_settings(**NO_TWILIO)
    def test_missing_credentials(self):
        with self.assertRaises(services.SMSConfigurationError) as ctx:
            services.send_sms('+639171234567', 'Hi')
        self.assertIn('TWILIO_ACCOUNT_SID', ctx.exception.user_message)

    def test_wrong_credentials(self):
        client = mock.MagicMock()
        client.messages.create.side_effect = rest_error(20003, status=401)
        with mock.patch.object(services, 'Client', return_value=client):
            with self.assertRaises(services.SMSConfigurationError) as ctx:
                services.send_sms('+639171234567', 'Hi')
        self.assertNotIn('test-token', ctx.exception.user_message)  # never leak secrets

    def test_unverified_trial_number(self):
        client = mock.MagicMock()
        client.messages.create.side_effect = rest_error(21608)
        with mock.patch.object(services, 'Client', return_value=client):
            with self.assertRaises(services.SMSProviderError) as ctx:
                services.send_sms('+639171234567', 'Hi')
        self.assertIn('verified', ctx.exception.user_message)
        self.assertEqual(ctx.exception.code, '21608')

    def test_unknown_provider_error(self):
        client = mock.MagicMock()
        client.messages.create.side_effect = rest_error(99999)
        with mock.patch.object(services, 'Client', return_value=client):
            with self.assertRaises(services.SMSProviderError) as ctx:
                services.send_sms('+639171234567', 'Hi')
        self.assertIn('99999', ctx.exception.user_message)

    def test_network_error(self):
        client = mock.MagicMock()
        client.messages.create.side_effect = requests.exceptions.ConnectionError('no internet')
        with mock.patch.object(services, 'Client', return_value=client):
            with self.assertRaises(services.SMSNetworkError):
                services.send_sms('+639171234567', 'Hi')

    def test_timeout(self):
        client = mock.MagicMock()
        client.messages.create.side_effect = requests.exceptions.ReadTimeout()
        with mock.patch.object(services, 'Client', return_value=client):
            with self.assertRaises(services.SMSNetworkError):
                services.send_sms('+639171234567', 'Hi')

    def test_fetch_status(self):
        client = mock.MagicMock()
        client.messages.return_value.fetch.return_value = SimpleNamespace(
            status='undelivered', error_code=30007, error_message=None)
        with mock.patch.object(services, 'Client', return_value=client):
            result = services.fetch_status('SM123')
        self.assertEqual(result.status, 'undelivered')
        self.assertIn('spam', result.error_message)


# ---------------------------------------------------------------------------
# Views (end-to-end through Django's test client)
# ---------------------------------------------------------------------------
class ComposeViewTests(TestCase):
    url = reverse('sms_app:compose')

    def test_page_loads_with_form_and_csrf(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Send SMS')
        self.assertContains(response, 'csrfmiddlewaretoken')

    @mock.patch('sms_app.views.services.send_sms')
    def test_success_reports_submission_not_delivery(self, send):
        send.return_value = services.SendResult(sid='SM1', status='queued', segments=1)
        response = self.client.post(self.url, {'to_number': '09171234567', 'body': 'Hello'}, follow=True)
        send.assert_called_once_with('+639171234567', 'Hello')
        self.assertContains(response, 'submitted to the SMS provider')
        self.assertContains(response, 'Delivery is not confirmed yet')
        sms = SMSMessage.objects.get()
        self.assertEqual((sms.status, sms.provider_sid), ('queued', 'SM1'))

    @mock.patch('sms_app.views.services.send_sms')
    def test_empty_phone_is_rejected_and_nothing_sent(self, send):
        response = self.client.post(self.url, {'to_number': '', 'body': 'Hello'})
        self.assertContains(response, "enter the recipient&#x27;s phone number")
        send.assert_not_called()
        self.assertEqual(SMSMessage.objects.count(), 0)

    @mock.patch('sms_app.views.services.send_sms')
    def test_empty_message_is_rejected_and_nothing_sent(self, send):
        response = self.client.post(self.url, {'to_number': '+639171234567', 'body': ''})
        self.assertContains(response, 'cannot be empty')
        send.assert_not_called()

    @mock.patch('sms_app.views.services.send_sms')
    def test_invalid_phone_is_rejected(self, send):
        response = self.client.post(self.url, {'to_number': '12ab', 'body': 'Hello'})
        self.assertContains(response, 'may only contain digits')
        send.assert_not_called()

    @mock.patch('sms_app.views.services.send_sms')
    def test_provider_error_is_shown_and_logged(self, send):
        send.side_effect = services.SMSProviderError('Trial accounts can only send to verified numbers.', '21608')
        response = self.client.post(self.url, {'to_number': '+639171234567', 'body': 'Hello'})
        self.assertContains(response, 'SMS was not sent')
        self.assertContains(response, 'verified numbers')
        self.assertContains(response, 'value="+639171234567"')  # input kept for retry
        sms = SMSMessage.objects.get()
        self.assertEqual((sms.status, sms.error_code), ('not_sent', '21608'))

    @override_settings(**NO_TWILIO)
    def test_missing_credentials_end_to_end(self):
        response = self.client.post(self.url, {'to_number': '+639171234567', 'body': 'Hello'})
        self.assertContains(response, 'not configured')
        self.assertEqual(SMSMessage.objects.get().status, 'not_sent')

    @mock.patch('sms_app.views.services.send_sms')
    def test_network_error_message(self, send):
        send.side_effect = services.SMSNetworkError('Could not connect to the SMS provider.')
        response = self.client.post(self.url, {'to_number': '+639171234567', 'body': 'Hello'})
        self.assertContains(response, 'Could not connect')

    def test_csrf_is_enforced(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        response = client.post(self.url, {'to_number': '+639171234567', 'body': 'Hello'})
        self.assertEqual(response.status_code, 403)


class HistoryViewTests(TestCase):
    def setUp(self):
        self.pending = SMSMessage.objects.create(to_number='+639171234567', body='a', status='queued', provider_sid='SM1')
        SMSMessage.objects.create(to_number='+639171234567', body='b', status='delivered', provider_sid='SM2')
        SMSMessage.objects.create(to_number='+639171234567', body='c', status='not_sent')

    def test_dashboard_stats(self):
        response = self.client.get(reverse('sms_app:history'))
        self.assertEqual(response.context['stats'], {'total': 3, 'delivered': 1, 'pending': 1, 'failed': 1})

    def test_filter(self):
        response = self.client.get(reverse('sms_app:history') + '?status=failed')
        self.assertEqual([m.body for m in response.context['sms_list']], ['c'])

    @mock.patch('sms_app.views.services.fetch_status')
    def test_refresh_status_updates_record(self, fetch):
        fetch.return_value = services.StatusResult(status='delivered', error_code='', error_message='')
        response = self.client.post(reverse('sms_app:refresh_status', args=[self.pending.pk]), follow=True)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, 'delivered')
        self.assertContains(response, 'was delivered')

    def test_refresh_requires_post(self):
        response = self.client.get(reverse('sms_app:refresh_status', args=[self.pending.pk]))
        self.assertEqual(response.status_code, 405)


class ContactViewTests(TestCase):
    def test_add_and_delete_contact(self):
        self.client.post(reverse('sms_app:contacts'), {'name': 'Ana', 'phone_number': '09171234567'})
        contact = Contact.objects.get()
        self.assertEqual(contact.phone_number, '+639171234567')
        self.client.post(reverse('sms_app:delete_contact', args=[contact.pk]))
        self.assertFalse(Contact.objects.exists())

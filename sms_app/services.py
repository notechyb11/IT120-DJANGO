"""
SMS provider integration (Twilio).

All communication with Twilio lives in this module, so views never talk to the
provider directly. Every failure is converted into an `SMSError` whose
`user_message` is safe to show on screen (it never contains credentials or
raw provider responses). Technical details go to the server log only.
"""

import logging
from dataclasses import dataclass

import requests
from django.conf import settings
from twilio.base.exceptions import TwilioException, TwilioRestException
from twilio.http.http_client import TwilioHttpClient
from twilio.rest import Client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class SMSError(Exception):
    """Base class. `user_message` is safe to display; `code` is the provider error code if any."""

    def __init__(self, user_message, code=''):
        super().__init__(user_message)
        self.user_message = user_message
        self.code = str(code or '')


class SMSConfigurationError(SMSError):
    """Credentials or sender number are missing / wrong."""


class SMSNetworkError(SMSError):
    """Twilio could not be reached (no internet, DNS, timeout...)."""


class SMSProviderError(SMSError):
    """Twilio was reached but rejected the request."""


# Friendly explanations for the Twilio error codes students run into most often.
# Full list: https://www.twilio.com/docs/api/errors
TWILIO_ERROR_MESSAGES = {
    20003: ('config', 'The SMS provider rejected our credentials. Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN.'),
    20404: ('config', 'The SMS provider could not find the requested resource. Check the Account SID.'),
    21211: ('provider', 'The provider says the recipient phone number is not valid.'),
    21212: ('config', 'The sender number (TWILIO_FROM_NUMBER) is not valid.'),
    21606: ('config', 'The sender number cannot send SMS. Use an SMS-capable Twilio number.'),
    21608: ('provider', 'This Twilio trial account can only send to verified numbers. '
                        'Verify the recipient in the Twilio Console first.'),
    21408: ('provider', 'Sending SMS to this country is not enabled on the Twilio account '
                        '(Messaging > Settings > Geo permissions).'),
    21610: ('provider', 'The recipient has unsubscribed (replied STOP) and cannot receive messages.'),
    21614: ('provider', 'The recipient number is not a mobile number that can receive SMS.'),
    21617: ('provider', 'The message is too long for the provider.'),
    21602: ('provider', 'The message body is required.'),
    30007: ('provider', 'The carrier filtered this message as possible spam.'),
}


@dataclass
class SendResult:
    sid: str
    status: str
    segments: int


@dataclass
class StatusResult:
    status: str
    error_code: str
    error_message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def missing_settings():
    """Return the names of required Twilio settings that are empty."""
    missing = [
        name for name in ('TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN')
        if not getattr(settings, name, '')
    ]
    if not (settings.TWILIO_FROM_NUMBER or settings.TWILIO_MESSAGING_SERVICE_SID):
        missing.append('TWILIO_FROM_NUMBER or TWILIO_MESSAGING_SERVICE_SID')
    return missing


def is_configured():
    return not missing_settings()


def get_client():
    missing = missing_settings()
    if missing:
        raise SMSConfigurationError(
            'The SMS provider is not configured. Missing setting(s): ' + ', '.join(missing) + '. '
            'Add them to your .env file and restart the server.'
        )
    http_client = TwilioHttpClient(timeout=settings.TWILIO_TIMEOUT)
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, http_client=http_client)


def _translate_rest_error(exc):
    """Turn a TwilioRestException into one of our SMSError subclasses."""
    kind, message = TWILIO_ERROR_MESSAGES.get(exc.code, (None, None))
    if kind is None:
        if exc.status == 401:
            kind, message = 'config', TWILIO_ERROR_MESSAGES[20003][1]
        else:
            kind = 'provider'
            message = f'The SMS provider rejected the message (error {exc.code or exc.status}).'
    error_cls = SMSConfigurationError if kind == 'config' else SMSProviderError
    return error_cls(message, code=exc.code or exc.status)


def _call_twilio(func):
    """Run a Twilio call and convert every possible failure into an SMSError."""
    try:
        return func()
    except TwilioRestException as exc:
        logger.warning('Twilio REST error: status=%s code=%s', exc.status, exc.code)
        raise _translate_rest_error(exc) from exc
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
        logger.warning('Could not reach Twilio: %s', type(exc).__name__)
        raise SMSNetworkError(
            'Could not connect to the SMS provider. Check your internet connection and try again.'
        ) from exc
    except (requests.exceptions.RequestException, TwilioException) as exc:
        logger.exception('Unexpected Twilio error')
        raise SMSProviderError('The SMS provider returned an unexpected error. Please try again.') from exc


# ---------------------------------------------------------------------------
# Public API used by the views
# ---------------------------------------------------------------------------
def send_sms(to_number, body):
    """
    Submit a message to Twilio.

    A successful return means Twilio ACCEPTED the message (status usually "queued").
    It does NOT mean the phone received it - use `fetch_status` to check delivery.
    """
    client = get_client()
    params = {'to': to_number, 'body': body}
    if settings.TWILIO_MESSAGING_SERVICE_SID:
        params['messaging_service_sid'] = settings.TWILIO_MESSAGING_SERVICE_SID
    else:
        params['from_'] = settings.TWILIO_FROM_NUMBER

    message = _call_twilio(lambda: client.messages.create(**params))
    logger.info('SMS submitted to Twilio: sid=%s status=%s', message.sid, message.status)
    return SendResult(
        sid=message.sid,
        status=str(message.status or 'queued'),
        segments=int(message.num_segments or 1),
    )


def fetch_status(sid):
    """Ask Twilio for the latest status of a message we already submitted."""
    client = get_client()
    message = _call_twilio(lambda: client.messages(sid).fetch())
    code = message.error_code
    friendly = TWILIO_ERROR_MESSAGES.get(code, (None, ''))[1] if code else ''
    return StatusResult(
        status=str(message.status),
        error_code=str(code or ''),
        error_message=friendly or (message.error_message or ''),
    )

from . import services


def provider_status(request):
    """Lets every page show whether Twilio is configured (never shows the values themselves)."""
    return {'sms_provider_configured': services.is_configured()}

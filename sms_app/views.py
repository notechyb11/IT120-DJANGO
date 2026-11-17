from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .forms import ContactForm, SMSForm, count_segments
from .models import Contact, SMSMessage


def compose(request):
    """Show the SMS form (GET) and process it (POST)."""
    if request.method == 'POST':
        form = SMSForm(request.POST)
        if form.is_valid():
            to_number = form.cleaned_data['to_number']
            body = form.cleaned_data['body']
            record = SMSMessage(to_number=to_number, body=body, segments=count_segments(body))

            try:
                result = services.send_sms(to_number, body)
            except services.SMSError as exc:
                # Save the failed attempt so it shows in history, then tell the user why.
                record.status = 'not_sent'
                record.error_code = exc.code
                record.error_message = exc.user_message[:255]
                record.save()
                messages.error(request, f'SMS was not sent. {exc.user_message}')
                # Re-render with the user's input still filled in so they can fix and retry.
                return render(request, 'sms_app/compose.html', _compose_context(form))

            record.status = result.status
            record.provider_sid = result.sid
            record.segments = result.segments
            record.save()
            # IMPORTANT: Twilio accepting the request is NOT the same as delivery.
            messages.success(
                request,
                f'Message submitted to the SMS provider for {to_number} '
                f'(status: {record.get_status_display()}). '
                'Delivery is not confirmed yet - check the History page for updates.',
            )
            return redirect('sms_app:compose')  # Post/Redirect/Get: avoids double-send on refresh
        messages.warning(request, 'Please fix the errors below and try again.')
    else:
        form = SMSForm()

    return render(request, 'sms_app/compose.html', _compose_context(form))


def _compose_context(form):
    contacts = list(Contact.objects.all())
    return {
        'form': form,
        'recent': SMSMessage.objects.all()[:5],
        'contacts': contacts,
        'contact_numbers': {str(c.pk): c.phone_number for c in contacts},
        'missing_settings': services.missing_settings(),
    }


def history(request):
    """Dashboard of previous sending attempts with simple statistics and a status filter."""
    qs = SMSMessage.objects.all()
    stats = qs.aggregate(
        total=Count('id'),
        delivered=Count('id', filter=Q(status='delivered')),
        pending=Count('id', filter=Q(status__in=SMSMessage.PENDING_STATUSES)),
        failed=Count('id', filter=Q(status__in=['not_sent', 'failed', 'undelivered', 'canceled'])),
    )
    status_filter = request.GET.get('status', '')
    if status_filter == 'pending':
        qs = qs.filter(status__in=SMSMessage.PENDING_STATUSES)
    elif status_filter == 'failed':
        qs = qs.filter(status__in=['not_sent', 'failed', 'undelivered', 'canceled'])
    elif status_filter == 'delivered':
        qs = qs.filter(status='delivered')
    else:
        status_filter = ''
    return render(request, 'sms_app/history.html', {
        'sms_list': qs[:100],
        'stats': stats,
        'status_filter': status_filter,
    })


@require_POST
def refresh_status(request, pk):
    """Ask Twilio for the latest delivery status of one message (message status tracking)."""
    record = get_object_or_404(SMSMessage, pk=pk)
    if not record.provider_sid:
        messages.info(request, 'This message never reached the provider, so there is no status to check.')
        return redirect('sms_app:history')
    try:
        result = services.fetch_status(record.provider_sid)
    except services.SMSError as exc:
        messages.error(request, f'Could not check the status. {exc.user_message}')
        return redirect('sms_app:history')

    record.status = result.status
    record.error_code = result.error_code
    record.error_message = result.error_message[:255]
    record.save()
    if record.status == 'delivered':
        messages.success(request, f'Message to {record.to_number} was delivered.')
    elif record.is_pending:
        messages.info(request, f'Message to {record.to_number} is still "{record.get_status_display()}". '
                               'Delivery is not confirmed yet.')
    else:
        detail = f' {record.error_message}' if record.error_message else ''
        messages.error(request, f'Message to {record.to_number} was not delivered '
                                f'({record.get_status_display()}).{detail}')
    return redirect('sms_app:history')


def contacts(request):
    """List saved contacts and add new ones."""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            contact = form.save()
            messages.success(request, f'Contact "{contact.name}" saved.')
            return redirect('sms_app:contacts')
        messages.warning(request, 'Please fix the errors below.')
    else:
        form = ContactForm()
    return render(request, 'sms_app/contacts.html', {
        'form': form,
        'contacts': Contact.objects.all(),
    })


@require_POST
def delete_contact(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    name = contact.name
    contact.delete()
    messages.success(request, f'Contact "{name}" deleted.')
    return redirect('sms_app:contacts')

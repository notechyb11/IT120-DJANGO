from django.contrib import admin

from .models import Contact, SMSMessage


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'created_at')
    search_fields = ('name', 'phone_number')


@admin.register(SMSMessage)
class SMSMessageAdmin(admin.ModelAdmin):
    list_display = ('to_number', 'status', 'segments', 'error_code', 'created_at')
    list_filter = ('status',)
    search_fields = ('to_number', 'body', 'provider_sid')
    readonly_fields = ('provider_sid', 'created_at', 'updated_at')

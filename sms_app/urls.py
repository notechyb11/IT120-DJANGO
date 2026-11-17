from django.urls import path

from . import views

app_name = 'sms_app'

urlpatterns = [
    path('', views.compose, name='compose'),
    path('history/', views.history, name='history'),
    path('history/<int:pk>/refresh/', views.refresh_status, name='refresh_status'),
    path('contacts/', views.contacts, name='contacts'),
    path('contacts/<int:pk>/delete/', views.delete_contact, name='delete_contact'),
]

from django.contrib import admin
from .models import Notification, PreferenceNotification

admin.site.register(Notification)
admin.site.register(PreferenceNotification)
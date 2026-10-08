from django.contrib import admin
from .models import Notification, PreferenceNotification

# Notifications et préférences visibles dans l'interface d'administration.
admin.site.register(Notification)
admin.site.register(PreferenceNotification)
from django.contrib import admin
from .models import SalonDiscussion, Message

# Salons et messages dans l'interface d'administration.
admin.site.register(SalonDiscussion)
admin.site.register(Message)
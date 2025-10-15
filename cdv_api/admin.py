from django.contrib import admin
from .models import Estacao, Transmissor, Receptor

admin.site.register(Estacao)
admin.site.register(Transmissor)
admin.site.register(Receptor)
from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('cdv_api.urls')),  # Inclui as URLs de cdv_api na raiz
]

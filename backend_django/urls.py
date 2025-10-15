# backend_django/urls.py
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

@login_required
def ping(request):
    return HttpResponse("ok, logado")

@login_required
def home_ok(request):
    return HttpResponse("Home OK")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('ping/', ping),                 # ← agora existe /ping/
    path('', home_ok),                   # ← home temporária que NÃO quebra
    path('', include('cdv_api.urls')),   # deixa por último para não sobrescrever a home provisória
]

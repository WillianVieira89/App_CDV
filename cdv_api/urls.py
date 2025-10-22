# cdv_api/urls.py
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    
    path('salvar_dados_cdv/', views.salvar_dados_cdv, name='salvar_dados_cdv'),
    path('registrar_cdv/', views.registrar_cdv, name='registrar_cdv'),
    path('gerar_relatorio_excel/', views.gerar_relatorio_excel_page, name='gerar_relatorio_excel_page'),
    path('gerar_excel/', views.gerar_excel_estacao, name='gerar_excel_estacao'),
]

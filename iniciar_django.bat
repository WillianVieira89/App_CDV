@echo off
echo ===============================
echo  Iniciando ambiente Django
echo ===============================

echo Criando ambiente virtual...
python -m venv venv

echo Ativando ambiente virtual...
call venv\Scripts\activate

echo Instalando dependências...
IF EXIST requirements.txt (
    pip install -r requirements.txt
) ELSE (
    pip install django openpyxl
)

echo Iniciando servidor Django...
python manage.py runserver

pause

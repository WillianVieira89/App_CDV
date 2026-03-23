from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os

class Command(BaseCommand):
    help = "Cria superusuário automaticamente se não existir"

    def handle(self, *args, **kwargs):
        username = os.getenv("SU_USERNAME", "admin")
        email = os.getenv("SU_EMAIL", "admin@email.com")
        password = os.getenv("SU_PASSWORD", "admin123")

        # 🔥 CORREÇÃO: verifica qualquer superuser existente
        if User.objects.filter(is_superuser=True).exists():
            print("✅ Superusuário já existe. Pulando criação.")
            return

        print("🔥 Criando superusuário...")

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )

        print("✅ Superusuário criado com sucesso!")
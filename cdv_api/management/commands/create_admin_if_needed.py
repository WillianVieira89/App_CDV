from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os


class Command(BaseCommand):
    help = "Cria superusuário automaticamente se as variáveis existirem."

    def handle(self, *args, **options):
        username = os.getenv("SU_USERNAME")
        email = os.getenv("SU_EMAIL")
        password = os.getenv("SU_PASSWORD")

        if not username or not email or not password:
            self.stdout.write("Variáveis de superusuário não definidas. Nada a fazer.")
            return

        User = get_user_model()

        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Superusuário '{username}' já existe.")
            return

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(f"Superusuário '{username}' criado com sucesso."))
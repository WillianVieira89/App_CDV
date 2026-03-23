from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os

class Command(BaseCommand):
    help = "Cria ou atualiza superusuário automaticamente"

    def handle(self, *args, **kwargs):
        username = os.getenv("SU_USERNAME", "admin")
        email = os.getenv("SU_EMAIL", "admin@email.com")
        password = os.getenv("SU_PASSWORD", "admin123")

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email}
        )

        if created:
            print("🔥 Criando superusuário...")
            user.set_password(password)
            user.is_superuser = True
            user.is_staff = True
            user.save()
            print("✅ Superusuário criado!")
        else:
            print("🔁 Atualizando senha do superusuário...")
            user.set_password(password)
            user.save()
            print("✅ Senha atualizada com sucesso!")
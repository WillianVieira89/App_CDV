from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import connection
import os

class Command(BaseCommand):
    help = "Cria ou atualiza superusuário automaticamente"

    def handle(self, *args, **kwargs):

        # 🔥 CORRIGE SEQUENCE DO POSTGRES
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT setval(
                    pg_get_serial_sequence('auth_user', 'id'),
                    (SELECT MAX(id) FROM auth_user)
                );
            """)
        print("🔧 Sequence do banco corrigida!")

        username = os.getenv("SU_USERNAME", "admin")
        email = os.getenv("SU_EMAIL", "admin@email.com")
        password = os.getenv("SU_PASSWORD", "admin123")

        user, created = User.objects.get_or_create(username=username)

        user.email = email
        user.set_password(password)
        user.is_superuser = True
        user.is_staff = True
        user.save()

        if created:
            print("🔥 Superusuário criado!")
        else:
            print("🔁 Superusuário atualizado!")
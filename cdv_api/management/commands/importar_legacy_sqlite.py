from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Importa dados do banco SQLite legado (alias: legacy) para o PostgreSQL atual (alias: default)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limpar",
            action="store_true",
            help="Apaga os dados atuais do PostgreSQL antes de importar.",
        )
        parser.add_argument(
            "--incluir-auth",
            action="store_true",
            help="Inclui usuários e grupos do Django auth.",
        )

    def handle(self, *args, **options):
        limpar = options["limpar"]
        incluir_auth = options["incluir_auth"]

        # Ordem segura por dependência
        modelos_base = [
            ("cdv_api", "Estacao"),
            ("cdv_api", "Transmissor"),
            ("cdv_api", "Receptor"),
        ]

        modelos_auth = [
            ("auth", "Group"),
            ("auth", "User"),
        ]

        modelos = list(modelos_base)
        if incluir_auth:
            modelos = modelos_auth + modelos

        self.stdout.write(self.style.NOTICE("Iniciando importação do SQLite legado para PostgreSQL..."))

        # Verifica existência de dados no legado
        for app_label, model_name in modelos:
            Model = apps.get_model(app_label, model_name)
            total_legacy = Model.objects.using("legacy").count()
            self.stdout.write(f"[legacy] {app_label}.{model_name}: {total_legacy} registro(s)")

        if limpar:
            self.stdout.write(self.style.WARNING("Limpando dados atuais do PostgreSQL..."))
            # Ordem inversa por dependência
            for app_label, model_name in reversed(modelos):
                Model = apps.get_model(app_label, model_name)
                deleted, _ = Model.objects.using("default").all().delete()
                self.stdout.write(f"[default] {app_label}.{model_name}: {deleted} registro(s) removido(s)")

        with transaction.atomic(using="default"):
            for app_label, model_name in modelos:
                Model = apps.get_model(app_label, model_name)
                objetos_legacy = list(Model.objects.using("legacy").all())

                if not objetos_legacy:
                    self.stdout.write(self.style.WARNING(f"Nenhum dado em {app_label}.{model_name} no legado."))
                    continue

                campos_concretos = [
                    f for f in Model._meta.concrete_fields
                    if not f.auto_created and not f.primary_key
                ]

                criados = 0
                atualizados = 0

                for obj in objetos_legacy:
                    pk = obj.pk
                    defaults = {}

                    for campo in campos_concretos:
                        valor = getattr(obj, campo.attname)
                        defaults[campo.attname] = valor

                    novo_obj, created = Model.objects.using("default").update_or_create(
                        pk=pk,
                        defaults=defaults
                    )

                    if created:
                        criados += 1
                    else:
                        atualizados += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"{app_label}.{model_name}: {criados} criado(s), {atualizados} atualizado(s)"
                    )
                )

        self.stdout.write(self.style.SUCCESS("Importação concluída com sucesso."))
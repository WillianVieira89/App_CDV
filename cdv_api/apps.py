from django.apps import AppConfig
from django.db.backends.signals import connection_created

def _enable_sqlite_pragmas(sender, connection, **kwargs):
    if connection.vendor == 'sqlite':
        cur = connection.cursor()
        # Modo WAL: múltiplos leitores não bloqueiam escritor
        cur.execute('PRAGMA journal_mode=WAL;')
        # Compromisso seguro vs performance
        cur.execute('PRAGMA synchronous=NORMAL;')
        # Garantir FKs (por via das dúvidas)
        cur.execute('PRAGMA foreign_keys=ON;')

class CdvApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cdv_api'
    def ready(self):
        connection_created.connect(_enable_sqlite_pragmas)
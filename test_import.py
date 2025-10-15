import sys
import os

# Adiciona o diretório pai ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import backend_django.settings

print("Importação bem-sucedida!")
print(backend_django.settings.BASE_DIR)
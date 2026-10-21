"""Inicia o painel em http://localhost:8000 com o Waitress.

Para abrir junto com o Windows, crie um atalho para `pythonw run.py` na pasta Inicializar.
"""

import os

from waitress import serve

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.wsgi import application  # noqa: E402

if __name__ == "__main__":
    serve(application, host="127.0.0.1", port=8000)

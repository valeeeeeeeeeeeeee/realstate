"""Inicia o painel em http://localhost:8000 com o Waitress e agenda a rotina diária.

Para abrir junto com o Windows, crie um atalho para `pythonw run.py` na pasta Inicializar.
"""

import os

import django
from waitress import serve

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.staticfiles.handlers import StaticFilesHandler  # noqa: E402

from config.wsgi import application as django_app  # noqa: E402
from locacao import agendador  # noqa: E402

# O Waitress não serve arquivos estáticos (o CSS e o JS do painel). Este é o mesmo handler
# do runserver e funciona com DEBUG desligado. Como o painel só atende o próprio PC
# (localhost), não é preciso um servidor de estáticos à parte nem rodar collectstatic.
application = StaticFilesHandler(django_app)

if __name__ == "__main__":
    agendador.iniciar()
    serve(application, host="127.0.0.1", port=8000)

"""O run.py serve o painel com o CSS do admin, mesmo com DEBUG desligado."""

from wsgiref.util import setup_testing_defaults

import pytest

import run

# Toda requisição WSGI fecha as conexões ao final, então todos os testes precisam do banco.
pytestmark = pytest.mark.django_db


def requisitar(caminho):
    environ = {"PATH_INFO": caminho, "HTTP_HOST": "localhost"}
    setup_testing_defaults(environ)
    resposta = {}

    def start_response(status, headers, exc_info=None):
        resposta["status"] = int(status.split()[0])
        resposta["headers"] = dict(headers)

    corpo = b"".join(run.application(environ, start_response))
    return resposta["status"], resposta["headers"], corpo


@pytest.fixture(autouse=True)
def debug_desligado(settings):
    settings.DEBUG = False


def test_serve_o_css_do_admin():
    status, headers, corpo = requisitar("/static/admin/css/base.css")

    assert status == 200
    assert headers["Content-Type"].startswith("text/css")
    assert corpo


def test_arquivo_estatico_inexistente_da_404():
    status, _, _ = requisitar("/static/admin/css/nao-existe.css")

    assert status == 404


def test_demais_paginas_continuam_com_o_django():
    status, headers, _ = requisitar("/login/")

    assert status == 200
    assert headers["Content-Type"].startswith("text/html")

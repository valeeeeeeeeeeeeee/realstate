from datetime import date
from unittest import mock

import pytest
from django.core import mail
from django.urls import reverse

from locacao.models import IGPM, Aviso, Locacao, Locador, Locatario, Reajuste
from locacao.rotina import executar


def acao(client, modelo, nome, objetos, filtro="", **extra):
    url = reverse(f"admin:locacao_{modelo}_changelist") + filtro
    dados = {"action": nome, "_selected_action": [o.pk for o in objetos], **extra}
    return client.post(url, dados, follow=True)


class TestPaginaInicial:
    def test_mostra_o_igpm_e_os_quadros(self, admin_client, locacao, igpm_um_por_cento):
        resposta = admin_client.get(reverse("admin:index"))

        html = resposta.content.decode()
        assert "IGP-M acumulado em 12 meses" in html
        assert "12,68%" in html
        assert "outubro/2026" in html
        assert "Próximos vencimentos" in html
        assert "Próximos reajustes" in html

    def test_sem_igpm(self, admin_client, db):
        resposta = admin_client.get(reverse("admin:index"))
        assert "Ainda não há 12 meses seguidos de IGP-M" in resposta.content.decode()


class TestArquivar:
    def test_arquiva_e_some_da_lista(self, admin_client, db):
        locatario = Locatario.objects.create(nome="Carla", email="carla@exemplo.com")

        acao(admin_client, "locatario", "arquivar", [locatario])

        locatario.refresh_from_db()
        assert locatario.arquivado_em is not None
        lista = admin_client.get(reverse("admin:locacao_locatario_changelist"))
        assert "Carla" not in lista.content.decode()
        arquivados = admin_client.get(reverse("admin:locacao_locatario_changelist") + "?situacao=arquivados")
        assert "Carla" in arquivados.content.decode()

    @pytest.mark.parametrize("modelo", ["locador", "locatario", "imovel"])
    def test_bloqueado_com_locacao_ativa(self, admin_client, locacao, modelo):
        obj = {"locador": locacao.imovel.locador, "locatario": locacao.locatario, "imovel": locacao.imovel}[modelo]

        resposta = acao(admin_client, modelo, "arquivar", [obj])

        obj.refresh_from_db()
        assert obj.arquivado_em is None
        assert "têm locação ativa" in resposta.content.decode()

    def test_desarquivar(self, admin_client, db):
        locador = Locador.objects.create(nome="Davi", email="davi@exemplo.com", arquivado_em="2026-01-01T00:00Z")

        # A ação é feita a partir da lista de arquivados.
        acao(admin_client, "locador", "desarquivar", [locador], filtro="?situacao=arquivados")

        locador.refresh_from_db()
        assert locador.arquivado_em is None

    def test_nao_exclui(self, admin_client, db):
        locador = Locador.objects.create(nome="Davi", email="davi@exemplo.com")
        resposta = admin_client.get(reverse("admin:locacao_locador_delete", args=[locador.pk]))
        assert resposta.status_code == 403


class TestRescindirEncerrar:
    def test_pede_a_data_antes(self, admin_client, locacao):
        resposta = acao(admin_client, "locacao", "rescindir", [locacao])

        assert "Rescindir locação" in resposta.content.decode()
        locacao.refresh_from_db()
        assert locacao.status == Locacao.Status.ATIVA

    @pytest.mark.parametrize("nome, status", [("rescindir", "rescindida"), ("encerrar", "encerrada")])
    def test_marca_com_a_data(self, admin_client, locacao, nome, status):
        acao(admin_client, "locacao", nome, [locacao], confirmar="1", data="2026-10-20")

        locacao.refresh_from_db()
        assert (locacao.status, locacao.data_encerramento) == (status, date(2026, 10, 20))

    def test_data_antes_da_entrada(self, admin_client, locacao):
        resposta = acao(admin_client, "locacao", "encerrar", [locacao], confirmar="1", data="2025-01-01")

        assert "anterior à entrada" in resposta.content.decode()
        locacao.refresh_from_db()
        assert locacao.status == Locacao.Status.ATIVA

    def test_nao_mexe_em_locacao_ja_encerrada(self, admin_client, locacao):
        locacao.status, locacao.data_encerramento = Locacao.Status.ENCERRADA, date(2026, 1, 1)
        locacao.save()

        acao(admin_client, "locacao", "rescindir", [locacao], confirmar="1", data="2026-10-20")

        locacao.refresh_from_db()
        assert (locacao.status, locacao.data_encerramento) == (Locacao.Status.ENCERRADA, date(2026, 1, 1))


def _falha(*args, **kwargs):
    raise OSError("SMTP fora do ar")


class TestReenviar:
    def test_reenvia_pagamento_para_o_email_corrigido(self, admin_client, locacao, monkeypatch):
        monkeypatch.setattr("locacao.avisos.send_mail", _falha)
        executar(date(2026, 10, 15))
        monkeypatch.undo()
        locacao.locatario.email = "bruno.novo@exemplo.com"
        locacao.locatario.save()

        acao(admin_client, "aviso", "reenviar", Aviso.objects.all())

        aviso = Aviso.objects.get()
        assert (aviso.status, aviso.destino, aviso.erro) == (Aviso.Status.ENVIADO, "bruno.novo@exemplo.com", "")
        [email] = mail.outbox
        assert email.to == ["bruno.novo@exemplo.com"]
        assert "15/10/2026" in email.body

    def test_reenvia_reajuste(self, admin_client, locacao, igpm_um_por_cento, monkeypatch):
        monkeypatch.setattr("locacao.avisos.send_mail", _falha)
        executar(date(2026, 11, 15))
        monkeypatch.undo()

        acao(admin_client, "aviso", "reenviar", Aviso.objects.filter(destinatario_tipo="locador"))

        assert Aviso.objects.get(destinatario_tipo="locador").status == Aviso.Status.ENVIADO
        assert Aviso.objects.get(destinatario_tipo="locatario").status == Aviso.Status.FALHOU
        [email] = mail.outbox
        assert email.to == ["ana@exemplo.com"]
        assert "R$ 1.690,24" in email.body
        assert Reajuste.objects.count() == 1

    def test_falha_de_novo(self, admin_client, locacao, monkeypatch):
        monkeypatch.setattr("locacao.avisos.send_mail", _falha)
        executar(date(2026, 10, 15))

        resposta = acao(admin_client, "aviso", "reenviar", Aviso.objects.all())

        assert "Falhou de novo" in resposta.content.decode()

    def test_aviso_e_somente_leitura(self, admin_client, locacao):
        executar(date(2026, 10, 15))
        aviso = Aviso.objects.get()
        resposta = admin_client.post(reverse("admin:locacao_aviso_change", args=[aviso.pk]), {"status": "falhou"})
        assert resposta.status_code == 403


class TestAtualizarIGPM:
    def test_grava_os_meses_novos(self, admin_client, sem_internet):
        sem_internet.return_value = {date(2026, 9, 1): "0.5"}

        resposta = admin_client.post(reverse("admin:locacao_igpm_atualizar"), follow=True)

        assert IGPM.objects.get().mes == date(2026, 9, 1)
        assert "IGP-M atualizado: 09/2026" in resposta.content.decode()

    def test_volta_para_a_pagina_inicial(self, admin_client, db):
        resposta = admin_client.post(reverse("admin:locacao_igpm_atualizar"), {"next": reverse("admin:index")})
        assert resposta.url == reverse("admin:index")

    def test_ignora_next_externo(self, admin_client, db):
        resposta = admin_client.post(reverse("admin:locacao_igpm_atualizar"), {"next": "https://exemplo.com/"})
        assert resposta.url == reverse("admin:locacao_igpm_changelist")

    def test_api_fora_do_ar(self, admin_client, sem_internet):
        sem_internet.side_effect = OSError("sem internet")
        resposta = admin_client.post(reverse("admin:locacao_igpm_atualizar"), follow=True)
        assert "Não foi possível buscar o IGP-M" in resposta.content.decode()

    def test_so_aceita_post(self, admin_client, db):
        assert admin_client.get(reverse("admin:locacao_igpm_atualizar")).status_code == 405

from unittest import mock

import pytest
from django.core import mail
from django.db import IntegrityError
from django.utils import timezone

from locacao import avisos
from locacao.models import Aviso


def enviar_pagamento(locacao, referencia="2026-11"):
    return avisos.enviar(
        locacao,
        Aviso.Tipo.PAGAMENTO,
        Aviso.Destinatario.LOCATARIO,
        referencia,
        locacao.locatario.email,
        "Lembrete de aluguel",
        "Seu aluguel vence hoje.",
    )


def test_envia_e_registra(locacao):
    aviso = enviar_pagamento(locacao)

    assert aviso.status == Aviso.Status.ENVIADO
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["bruno@exemplo.com"]


def test_nao_envia_em_dobro(locacao):
    enviar_pagamento(locacao)

    assert enviar_pagamento(locacao) is None
    assert len(mail.outbox) == 1
    assert Aviso.objects.count() == 1


def test_outro_mes_e_outro_aviso(locacao):
    enviar_pagamento(locacao, "2026-11")
    enviar_pagamento(locacao, "2026-12")

    assert len(mail.outbox) == 2


def test_mesma_referencia_para_locador_e_locatario(locacao):
    for destinatario, email in [
        (Aviso.Destinatario.LOCATARIO, locacao.locatario.email),
        (Aviso.Destinatario.LOCADOR, locacao.imovel.locador.email),
    ]:
        avisos.enviar(locacao, Aviso.Tipo.REAJUSTE, destinatario, "7", email, "Reajuste", "...")

    assert len(mail.outbox) == 2


def test_falha_fica_no_log_e_nao_levanta(locacao):
    with mock.patch("locacao.avisos.send_mail", side_effect=OSError("SMTP recusou")):
        aviso = enviar_pagamento(locacao)

    assert aviso.status == Aviso.Status.FALHOU
    assert aviso.erro == "SMTP recusou"


def test_aviso_que_falhou_e_tentado_de_novo(locacao):
    with mock.patch("locacao.avisos.send_mail", side_effect=OSError("fora do ar")):
        falhou = enviar_pagamento(locacao)

    reenviado = enviar_pagamento(locacao)

    assert reenviado.pk == falhou.pk
    assert reenviado.status == Aviso.Status.ENVIADO
    assert reenviado.erro == ""
    assert len(mail.outbox) == 1
    assert Aviso.objects.count() == 1


def test_banco_recusa_aviso_duplicado(locacao):
    dados = dict(
        locacao=locacao,
        tipo=Aviso.Tipo.PAGAMENTO,
        destinatario_tipo=Aviso.Destinatario.LOCATARIO,
        referencia="2026-11",
        destino="bruno@exemplo.com",
        status=Aviso.Status.ENVIADO,
        enviado_em=timezone.now(),
    )
    Aviso.objects.create(**dados)

    with pytest.raises(IntegrityError):
        Aviso.objects.create(**dados)

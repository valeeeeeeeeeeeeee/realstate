from datetime import date
from decimal import Decimal

from locacao import mensagens
from locacao.models import IGPM, Aviso
from locacao.reajustes import preparar_reajuste
from locacao.regras import igpm


def test_reais():
    assert mensagens.reais(150000) == "R$ 1.500,00"
    assert mensagens.reais(169024) == "R$ 1.690,24"
    assert mensagens.reais(5) == "R$ 0,05"
    assert mensagens.reais(123456789) == "R$ 1.234.567,89"


def test_porcentagem():
    assert mensagens.porcentagem(Decimal("4.125")) == "4,13%"
    assert mensagens.porcentagem(Decimal("-0.22")) == "-0,22%"


def test_pagamento(locacao):
    assunto, corpo = mensagens.pagamento(locacao, date(2026, 11, 16))

    assert assunto == "Lembrete: aluguel de Rua das Flores, 10 vence hoje (16/11/2026)"
    assert "Olá, Bruno Locatário." in corpo
    assert "Valor: R$ 1.500,00" in corpo


def test_texto_nao_e_escapado_como_html(locacao):
    locacao.imovel.endereco = "Rua A & B, 1"

    assunto, corpo = mensagens.pagamento(locacao, date(2026, 11, 16))

    assert "Rua A & B, 1" in assunto
    assert "&amp;" not in corpo


def test_reajuste_para_locatario_e_locador(locacao, igpm_um_por_cento):
    reajuste = preparar_reajuste(locacao, date(2026, 12, 15), date(2026, 11, 15))

    assunto, corpo = mensagens.reajuste(reajuste, Aviso.Destinatario.LOCATARIO)
    assert assunto == "Reajuste anual do aluguel de Rua das Flores, 10 em 15/12/2026"
    assert "Olá, Bruno Locatário." in corpo
    assert "IGP-M mês a mês (11/2025 a 10/2026):" in corpo
    assert corpo.count(": 1,00%") == 12
    assert "IGP-M acumulado: 12,68%" in corpo
    assert "Cálculo: R$ 1.500,00 × (1 + 12,68%) = R$ 1.690,24" in corpo
    assert "Novo valor: R$ 1.690,24, a partir de 15/12/2026" in corpo
    assert "negativo" not in corpo

    _, corpo_locador = mensagens.reajuste(reajuste, Aviso.Destinatario.LOCADOR)
    assert "Olá, Ana Locadora." in corpo_locador


def test_reajuste_com_acumulado_negativo(locacao):
    for mes in igpm.meses(date(2025, 11, 1), date(2026, 10, 1)):
        IGPM.objects.create(mes=mes, variacao=Decimal("-0.5"))
    reajuste = preparar_reajuste(locacao, date(2026, 12, 15), date(2026, 11, 15))

    _, corpo = mensagens.reajuste(reajuste, Aviso.Destinatario.LOCATARIO)

    assert "IGP-M acumulado: -5,84%" in corpo
    assert "o reajuste fica em 0%" in corpo
    assert "Cálculo: R$ 1.500,00 × (1 + 0,00%) = R$ 1.500,00" in corpo

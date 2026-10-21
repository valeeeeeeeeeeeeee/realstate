from datetime import date
from decimal import Decimal

import pytest

from locacao.models import IGPM, Locacao, Reajuste
from locacao.reajustes import IGPMIncompleto, aplicar_reajustes, preparar_reajuste, reajuste_a_avisar
from locacao.regras import igpm

AVISO = date(2026, 11, 15)
ANIVERSARIO = date(2026, 12, 15)


def test_reajuste_a_avisar(locacao):
    assert reajuste_a_avisar(locacao, AVISO) == ANIVERSARIO
    assert reajuste_a_avisar(locacao, date(2026, 11, 14)) is None

    locacao.status = Locacao.Status.RESCINDIDA
    assert reajuste_a_avisar(locacao, AVISO) is None


def test_preparar_calcula_e_congela(locacao, igpm_um_por_cento):
    reajuste = preparar_reajuste(locacao, ANIVERSARIO, AVISO)

    assert reajuste.status == Reajuste.Status.CALCULADO
    assert (reajuste.periodo_inicio, reajuste.periodo_fim) == (date(2025, 11, 1), date(2026, 10, 1))
    assert reajuste.igpm_acumulado.quantize(Decimal("0.00000001")) == Decimal("0.12682503")
    assert reajuste.valor_anterior == 150000
    assert reajuste.valor_novo == 169024  # 150000 × 1,12682503 = 169023,75 → 169024


def test_preparar_de_novo_devolve_o_mesmo_valor(locacao, igpm_um_por_cento):
    primeiro = preparar_reajuste(locacao, ANIVERSARIO, AVISO)

    # Mesmo que o índice ou o aluguel mudem depois, o valor avisado não muda.
    IGPM.objects.update(variacao=Decimal("2"))
    locacao.valor_aluguel = 100000
    locacao.save()
    segundo = preparar_reajuste(locacao, ANIVERSARIO, AVISO)

    assert segundo.pk == primeiro.pk
    assert segundo.valor_novo == 169024
    assert Reajuste.objects.count() == 1


def test_igpm_incompleto_nao_calcula(locacao, igpm_um_por_cento):
    IGPM.objects.filter(mes=date(2026, 10, 1)).delete()

    with pytest.raises(IGPMIncompleto) as erro:
        preparar_reajuste(locacao, ANIVERSARIO, AVISO)

    assert erro.value.faltando == [date(2026, 10, 1)]
    assert Reajuste.objects.count() == 0


def test_acumulado_negativo_mantem_valor(locacao):
    for mes in igpm.meses(date(2025, 11, 1), date(2026, 10, 1)):
        IGPM.objects.create(mes=mes, variacao=Decimal("-0.5"))

    reajuste = preparar_reajuste(locacao, ANIVERSARIO, AVISO)

    assert reajuste.igpm_acumulado < 0
    assert reajuste.valor_novo == reajuste.valor_anterior == 150000


class TestAplicar:
    def test_aplica_na_data(self, locacao, igpm_um_por_cento):
        reajuste = preparar_reajuste(locacao, ANIVERSARIO, AVISO)

        assert aplicar_reajustes(date(2026, 12, 14)) == []  # ainda não chegou a data
        assert aplicar_reajustes(ANIVERSARIO) == [reajuste]

        locacao.refresh_from_db()
        reajuste.refresh_from_db()
        assert locacao.valor_aluguel == 169024
        assert reajuste.status == Reajuste.Status.APLICADO

    def test_aplicar_duas_vezes_nao_reaplica(self, locacao, igpm_um_por_cento):
        preparar_reajuste(locacao, ANIVERSARIO, AVISO)
        aplicar_reajustes(ANIVERSARIO)

        assert aplicar_reajustes(ANIVERSARIO) == []
        locacao.refresh_from_db()
        assert locacao.valor_aluguel == 169024

    def test_aplica_atrasado_se_o_pc_estava_desligado(self, locacao, igpm_um_por_cento):
        preparar_reajuste(locacao, ANIVERSARIO, AVISO)

        assert len(aplicar_reajustes(date(2026, 12, 20))) == 1

    def test_locacao_encerrada_nao_e_reajustada(self, locacao, igpm_um_por_cento):
        preparar_reajuste(locacao, ANIVERSARIO, AVISO)
        locacao.status = Locacao.Status.ENCERRADA
        locacao.data_encerramento = date(2026, 12, 1)
        locacao.save()

        assert aplicar_reajustes(ANIVERSARIO) == []
        locacao.refresh_from_db()
        assert locacao.valor_aluguel == 150000

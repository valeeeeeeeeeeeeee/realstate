from datetime import date

import pytest

from locacao.regras import datas


class TestDiaNoMes:
    def test_dia_existente(self):
        assert datas.dia_no_mes(2026, 10, 15) == date(2026, 10, 15)

    @pytest.mark.parametrize(
        "ano, mes, dia, esperado",
        [
            (2026, 11, 31, date(2026, 11, 30)),
            (2026, 2, 30, date(2026, 2, 28)),
            (2028, 2, 31, date(2028, 2, 29)),  # ano bissexto
        ],
    )
    def test_mes_sem_o_dia_usa_ultimo_dia(self, ano, mes, dia, esperado):
        assert datas.dia_no_mes(ano, mes, dia) == esperado


class TestDiaUtil:
    def test_dia_util_comum(self):
        assert datas.proximo_dia_util(date(2026, 10, 21)) == date(2026, 10, 21)  # quarta

    def test_fim_de_semana_vai_para_segunda(self):
        assert datas.proximo_dia_util(date(2026, 10, 24)) == date(2026, 10, 26)  # sábado

    def test_feriado_nacional(self):
        assert datas.proximo_dia_util(date(2026, 12, 25)) == date(2026, 12, 28)  # Natal, sexta

    def test_fim_de_semana_seguido_de_feriado(self):
        # 31/10/2026 é sábado e 02/11 (segunda) é Finados.
        assert datas.proximo_dia_util(date(2026, 10, 31)) == date(2026, 11, 3)

    def test_feriado_local(self):
        sao_sebastiao = date(2026, 1, 20)  # terça
        assert datas.proximo_dia_util(sao_sebastiao) == sao_sebastiao
        assert datas.proximo_dia_util(sao_sebastiao, {sao_sebastiao}) == date(2026, 1, 21)


class TestVencimento:
    def test_dia_31_em_novembro(self):
        assert datas.vencimento(2026, 11, 31) == date(2026, 11, 30)  # segunda

    def test_fim_de_mes_que_cai_no_sabado(self):
        # 30 → 28/02/2026, sábado → segunda 02/03.
        assert datas.vencimento(2026, 2, 30) == date(2026, 3, 2)

    def test_feriado_local_no_vencimento(self):
        assert datas.vencimento(2026, 1, 20, {date(2026, 1, 20)}) == date(2026, 1, 21)


class TestAniversario:
    def test_primeiro_e_segundo_reajuste(self):
        entrada = date(2025, 3, 10)
        assert datas.aniversario(entrada, 1) == date(2026, 3, 10)
        assert datas.aniversario(entrada, 2) == date(2027, 3, 10)

    def test_entrada_em_29_de_fevereiro(self):
        entrada = date(2024, 2, 29)
        assert datas.aniversario(entrada, 1) == date(2025, 2, 28)
        assert datas.aniversario(entrada, 4) == date(2028, 2, 29)

    def test_numero_invalido(self):
        with pytest.raises(ValueError):
            datas.aniversario(date(2025, 1, 1), 0)

    def test_eh_aniversario(self):
        entrada = date(2025, 3, 10)
        assert datas.eh_aniversario(entrada, date(2026, 3, 10))
        assert not datas.eh_aniversario(entrada, date(2025, 3, 10))  # a entrada não é reajuste
        assert not datas.eh_aniversario(entrada, date(2026, 3, 11))


class TestAvisoDeReajuste:
    def test_um_mes_antes(self):
        assert datas.data_aviso_reajuste(date(2026, 12, 15)) == date(2026, 11, 15)

    def test_mes_anterior_sem_o_dia(self):
        assert datas.data_aviso_reajuste(date(2026, 3, 31)) == date(2026, 2, 28)

    def test_proximo_aniversario(self):
        entrada = date(2025, 12, 15)
        assert datas.proximo_aniversario(entrada, date(2025, 12, 20)) == date(2026, 12, 15)
        assert datas.proximo_aniversario(entrada, date(2026, 12, 15)) == date(2026, 12, 15)
        assert datas.proximo_aniversario(entrada, date(2026, 12, 16)) == date(2027, 12, 15)

    def test_periodo_de_aviso_vai_do_aviso_ao_aniversario(self):
        entrada = date(2025, 12, 15)
        assert datas.reajuste_em_aviso(entrada, date(2026, 11, 14)) is None
        assert datas.reajuste_em_aviso(entrada, date(2026, 11, 15)) == date(2026, 12, 15)
        assert datas.reajuste_em_aviso(entrada, date(2026, 12, 15)) == date(2026, 12, 15)
        assert datas.reajuste_em_aviso(entrada, date(2026, 12, 16)) is None

    def test_nao_avisa_antes_do_primeiro_ano(self):
        # O aviso do 1º reajuste é 15/11/2026, não 15/11/2025 (antes da entrada).
        assert datas.reajuste_em_aviso(date(2025, 12, 15), date(2025, 11, 15)) is None

    def test_reajuste_em_janeiro_avisado_em_dezembro_do_ano_anterior(self):
        assert datas.reajuste_em_aviso(date(2025, 1, 15), date(2025, 12, 15)) == date(2026, 1, 15)

    def test_reajuste_em_31_de_marco(self):
        assert datas.reajuste_em_aviso(date(2025, 3, 31), date(2026, 2, 27)) is None
        assert datas.reajuste_em_aviso(date(2025, 3, 31), date(2026, 2, 28)) == date(2026, 3, 31)

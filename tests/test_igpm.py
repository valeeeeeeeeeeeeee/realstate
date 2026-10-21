from datetime import date
from decimal import Decimal

import pytest

from locacao.regras import igpm, reajuste


class TestPeriodo:
    def test_termina_no_mes_anterior_ao_aviso(self):
        # Reajuste em 15/12/2026 → aviso em 15/11/2026 → IGP-M de out/2025 a out/2026.
        assert igpm.periodo(date(2026, 11, 15)) == (date(2025, 11, 1), date(2026, 10, 1))

    def test_virada_de_ano(self):
        assert igpm.periodo(date(2027, 1, 10)) == (date(2026, 1, 1), date(2026, 12, 1))

    def test_tem_12_meses(self):
        assert len(igpm.meses(*igpm.periodo(date(2026, 11, 15)))) == 12

    def test_meses_faltando(self):
        inicio, fim = date(2025, 11, 1), date(2026, 10, 1)
        disponiveis = set(igpm.meses(inicio, fim)) - {date(2026, 10, 1)}
        assert igpm.meses_faltando(inicio, fim, disponiveis) == [date(2026, 10, 1)]


class TestAcumulado:
    def test_juros_compostos(self):
        resultado = igpm.acumulado([Decimal("1")] * 12)
        assert resultado.quantize(Decimal("0.00000001")) == Decimal("0.12682503")

    def test_meses_negativos_e_positivos(self):
        variacoes = [Decimal(v) for v in ["0.5", "-0.3", "1.2", "0", "-1", "0.8", "0.1", "0.2", "-0.4", "0.6", "0.3", "0.9"]]
        esperado = Decimal(1)
        for v in variacoes:
            esperado *= 1 + v / 100
        assert igpm.acumulado(variacoes) == esperado - 1

    def test_aceita_dicionario_por_mes(self):
        meses = igpm.meses(date(2025, 1, 1), date(2025, 12, 1))
        assert igpm.acumulado({m: Decimal("0") for m in meses}) == 0

    def test_exige_12_meses(self):
        with pytest.raises(ValueError):
            igpm.acumulado([Decimal("1")] * 11)


class TestValorNovo:
    def test_reajuste_positivo(self):
        # R$ 1.500,00 × 1,0412 = R$ 1.561,80
        assert reajuste.valor_novo(150000, Decimal("0.0412")) == 156180

    def test_arredonda_meio_para_cima(self):
        # 1012,5 centavos → 1013 (o arredondamento padrão do Python daria 1012).
        assert reajuste.valor_novo(1000, Decimal("0.0125")) == 1013

    def test_acumulado_negativo_mantem_valor(self):
        assert reajuste.valor_novo(150000, Decimal("-0.0350")) == 150000
        assert reajuste.percentual_aplicado(Decimal("-0.0350")) == 0

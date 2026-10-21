from datetime import date
from decimal import Decimal

from locacao import painel
from locacao.models import IGPM, Aviso, Locacao, Reajuste
from locacao.regras import igpm


class TestIGPM12Meses:
    def test_acumulado_dos_12_meses_ate_o_ultimo_obtido(self, igpm_um_por_cento):
        IGPM.objects.create(mes=date(2025, 10, 1), variacao=Decimal("50"))  # fora do período

        resultado = painel.igpm_12_meses()

        assert (resultado.inicio, resultado.fim) == (date(2025, 11, 1), date(2026, 10, 1))
        assert resultado.acumulado == igpm.acumulado([Decimal("1")] * 12)

    def test_sem_12_meses_seguidos(self, igpm_um_por_cento):
        IGPM.objects.filter(mes=date(2026, 3, 1)).delete()
        assert painel.igpm_12_meses() is None

    def test_sem_igpm(self, db):
        assert painel.igpm_12_meses() is None


class TestProximosVencimentos:
    def test_lista_os_vencimentos_do_periodo(self, locacao):
        [v] = painel.proximos_vencimentos(date(2026, 10, 21), dias=30)
        assert v.data == date(2026, 11, 16)  # 15/11/2026 é domingo

    def test_ignora_locacoes_encerradas(self, locacao):
        locacao.status = Locacao.Status.ENCERRADA
        locacao.save()
        assert painel.proximos_vencimentos(date(2026, 10, 21), dias=30) == []


class TestProximosReajustes:
    def test_reajuste_ainda_nao_calculado(self, locacao):
        [r] = painel.proximos_reajustes(date(2026, 10, 21))
        assert (r.data, r.reajuste) == (date(2026, 12, 15), None)

    def test_fora_do_periodo(self, locacao):
        assert painel.proximos_reajustes(date(2026, 10, 1), dias=30) == []


class TestPendenciasIGPM:
    def test_reajuste_esperando_igpm(self, locacao, igpm_um_por_cento):
        IGPM.objects.filter(mes=date(2026, 10, 1)).delete()

        [p] = painel.pendencias_igpm(date(2026, 11, 20))

        assert (p.data_reajuste, p.faltando) == (date(2026, 12, 15), [date(2026, 10, 1)])

    def test_sem_pendencia_quando_o_reajuste_ja_foi_calculado(self, locacao, igpm_um_por_cento):
        IGPM.objects.filter(mes=date(2026, 10, 1)).delete()
        Reajuste.objects.create(
            locacao=locacao,
            data_reajuste=date(2026, 12, 15),
            periodo_inicio=date(2025, 11, 1),
            periodo_fim=date(2026, 10, 1),
            igpm_acumulado=Decimal("0.1"),
            valor_anterior=150000,
            valor_novo=165000,
        )
        assert painel.pendencias_igpm(date(2026, 11, 20)) == []

    def test_fora_do_periodo_de_aviso(self, locacao):
        assert painel.pendencias_igpm(date(2026, 10, 21)) == []


def test_falhas_de_envio(locacao):
    comum = dict(locacao=locacao, tipo="pagamento", destinatario_tipo="locatario", destino="b@x.com")
    Aviso.objects.create(**comum, referencia="2026-09", status="enviado", enviado_em="2026-09-15T08:00Z")
    falha = Aviso.objects.create(**comum, referencia="2026-10", status="falhou", enviado_em="2026-10-15T08:00Z")

    assert list(painel.falhas_de_envio()) == [falha]

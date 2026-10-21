"""Cálculo e aplicação dos reajustes no banco (spec §4.2 a §4.4)."""

from datetime import date

from django.db import transaction

from .models import IGPM, Locacao, Reajuste
from .regras import datas, igpm
from .regras.reajuste import valor_novo


class IGPMIncompleto(Exception):
    """Falta algum mês de IGP-M do período. O aviso fica para o dia seguinte (spec §4.5)."""

    def __init__(self, faltando: list[date]):
        self.faltando = faltando
        meses = ", ".join(f"{m:%m/%Y}" for m in faltando)
        super().__init__(f"IGP-M ainda não disponível para: {meses}")


def preparar_reajuste(locacao: Locacao, data_reajuste: date, data_aviso: date) -> Reajuste:
    """Calcula e congela o reajuste com status `calculado`.

    Se ele já foi calculado antes, devolve o mesmo registro sem recalcular,
    para que o valor informado no aviso seja exatamente o aplicado.
    """
    existente = Reajuste.objects.filter(locacao=locacao, data_reajuste=data_reajuste).first()
    if existente:
        return existente

    inicio, fim = igpm.periodo(data_aviso)
    indices = dict(IGPM.objects.filter(mes__range=(inicio, fim)).values_list("mes", "variacao"))
    faltando = igpm.meses_faltando(inicio, fim, indices)
    if faltando:
        raise IGPMIncompleto(faltando)

    acumulado = igpm.acumulado(indices)
    return Reajuste.objects.create(
        locacao=locacao,
        data_reajuste=data_reajuste,
        periodo_inicio=inicio,
        periodo_fim=fim,
        igpm_acumulado=acumulado,
        valor_anterior=locacao.valor_aluguel,
        valor_novo=valor_novo(locacao.valor_aluguel, acumulado),
    )


def reajuste_a_avisar(locacao: Locacao, hoje: date) -> date | None:
    """Data do reajuste cujo período de aviso inclui hoje, se a locação estiver ativa."""
    if locacao.status != Locacao.Status.ATIVA:
        return None
    return datas.reajuste_em_aviso(locacao.data_entrada, hoje)


@transaction.atomic
def aplicar_reajustes(hoje: date) -> list[Reajuste]:
    """Aplica os reajustes calculados com data até hoje, só em locações ativas."""
    aplicados = []
    pendentes = Reajuste.objects.select_related("locacao").filter(
        status=Reajuste.Status.CALCULADO,
        data_reajuste__lte=hoje,
        locacao__status=Locacao.Status.ATIVA,
    )
    for reajuste in pendentes:
        locacao = reajuste.locacao
        locacao.valor_aluguel = reajuste.valor_novo
        locacao.save(update_fields=["valor_aluguel"])
        reajuste.status = Reajuste.Status.APLICADO
        reajuste.save(update_fields=["status"])
        aplicados.append(reajuste)
    return aplicados

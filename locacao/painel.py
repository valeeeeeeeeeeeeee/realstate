"""Dados da página inicial do painel (spec §7)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from .models import IGPM, Aviso, Feriado, Locacao, Reajuste
from .regras import datas, igpm

# Quanto à frente a página inicial olha.
DIAS_VENCIMENTOS = 15
DIAS_REAJUSTES = 60


@dataclass
class IGPM12Meses:
    acumulado: Decimal
    inicio: date
    fim: date


@dataclass
class Vencimento:
    locacao: Locacao
    data: date


@dataclass
class ProximoReajuste:
    locacao: Locacao
    data: date
    reajuste: Reajuste | None


@dataclass
class PendenciaIGPM:
    locacao: Locacao
    data_reajuste: date
    faltando: list[date]


def igpm_12_meses() -> IGPM12Meses | None:
    """Acumulado dos 12 meses que terminam no último IGP-M obtido, ou None se faltar algum mês."""
    fim = IGPM.objects.order_by("-mes").values_list("mes", flat=True).first()
    if not fim:
        return None
    inicio = fim - relativedelta(months=igpm.MESES_DO_PERIODO - 1)
    indices = dict(IGPM.objects.filter(mes__range=(inicio, fim)).values_list("mes", "variacao"))
    if igpm.meses_faltando(inicio, fim, indices):
        return None
    return IGPM12Meses(igpm.acumulado(indices), inicio, fim)


def _ativas():
    return Locacao.objects.select_related("imovel__locador", "locatario").filter(status=Locacao.Status.ATIVA)


def proximos_vencimentos(hoje: date, dias: int = DIAS_VENCIMENTOS) -> list[Vencimento]:
    feriados = set(Feriado.objects.values_list("data", flat=True))
    limite = hoje + relativedelta(days=dias)
    lista = []
    for locacao in _ativas():
        # O mês anterior entra porque o vencimento dele pode cair no início deste mês.
        for n in (-1, 0, 1):
            mes = hoje.replace(day=1) + relativedelta(months=n)
            if (mes.year, mes.month) < (locacao.data_entrada.year, locacao.data_entrada.month):
                continue
            data = datas.vencimento(mes.year, mes.month, locacao.dia_vencimento, feriados)
            if hoje <= data <= limite:
                lista.append(Vencimento(locacao, data))
    return sorted(lista, key=lambda v: v.data)


def proximos_reajustes(hoje: date, dias: int = DIAS_REAJUSTES) -> list[ProximoReajuste]:
    limite = hoje + relativedelta(days=dias)
    lista = []
    for locacao in _ativas():
        data = datas.proximo_aniversario(locacao.data_entrada, hoje)
        if data <= limite:
            reajuste = locacao.reajustes.filter(data_reajuste=data).first()
            lista.append(ProximoReajuste(locacao, data, reajuste))
    return sorted(lista, key=lambda r: r.data)


def pendencias_igpm(hoje: date) -> list[PendenciaIGPM]:
    """Reajustes que já deveriam ter sido avisados, mas esperam algum mês de IGP-M (spec §4.5)."""
    lista = []
    for locacao in _ativas():
        data_reajuste = datas.reajuste_em_aviso(locacao.data_entrada, hoje)
        if not data_reajuste or locacao.reajustes.filter(data_reajuste=data_reajuste).exists():
            continue
        inicio, fim = igpm.periodo(datas.data_aviso_reajuste(data_reajuste))
        disponiveis = set(IGPM.objects.filter(mes__range=(inicio, fim)).values_list("mes", flat=True))
        # Sem meses faltando, o aviso sai na próxima execução da rotina.
        if faltando := igpm.meses_faltando(inicio, fim, disponiveis):
            lista.append(PendenciaIGPM(locacao, data_reajuste, faltando))
    return lista


def falhas_de_envio():
    return Aviso.objects.select_related("locacao__imovel").filter(status=Aviso.Status.FALHOU)

"""IGP-M acumulado e período de 12 meses (spec §4.3)."""

from collections.abc import Collection, Mapping
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta

MESES_DO_PERIODO = 12


def periodo(data_aviso: date) -> tuple[date, date]:
    """Os 12 meses usados num aviso de reajuste, como (primeiro mês, último mês), sempre no dia 1.

    O período termina no mês anterior ao do aviso: é o último IGP-M já publicado nessa data,
    pois a FGV divulga o índice no fim do próprio mês. Como o aviso sai 1 mês antes do
    aniversário, o período termina 2 meses antes dele.
    """
    fim = data_aviso.replace(day=1) - relativedelta(months=1)
    inicio = fim - relativedelta(months=MESES_DO_PERIODO - 1)
    return inicio, fim


def meses(inicio: date, fim: date) -> list[date]:
    lista = []
    mes = inicio
    while mes <= fim:
        lista.append(mes)
        mes += relativedelta(months=1)
    return lista


def meses_faltando(inicio: date, fim: date, disponiveis: Collection[date]) -> list[date]:
    return [m for m in meses(inicio, fim) if m not in disponiveis]


def acumulado(variacoes: Mapping[date, Decimal] | Collection[Decimal]) -> Decimal:
    """Π(1 + variação/100) − 1. Ex.: retorna Decimal('0.0412') para 4,12%."""
    valores = variacoes.values() if isinstance(variacoes, Mapping) else variacoes
    if len(valores) != MESES_DO_PERIODO:
        raise ValueError(f"São necessários {MESES_DO_PERIODO} meses de IGP-M, recebidos {len(valores)}.")
    fator = Decimal(1)
    for v in valores:
        fator *= 1 + Decimal(v) / 100
    return fator - 1

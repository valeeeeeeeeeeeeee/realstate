"""Regras de datas: fim de mês, dia útil, vencimentos e aniversários (spec §4.1, §4.2, §4.4)."""

import calendar
from collections.abc import Collection
from datetime import date, timedelta

import holidays
from dateutil.relativedelta import relativedelta

_FERIADOS_NACIONAIS = holidays.Brazil()


def dia_no_mes(ano: int, mes: int, dia: int) -> date:
    """Data com o dia pedido; se o mês não tem esse dia, usa o último dia do mês."""
    ultimo = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, min(dia, ultimo))


def eh_dia_util(d: date, feriados_locais: Collection[date] = ()) -> bool:
    return d.weekday() < 5 and d not in _FERIADOS_NACIONAIS and d not in feriados_locais


def proximo_dia_util(d: date, feriados_locais: Collection[date] = ()) -> date:
    """A própria data, se for dia útil; senão, o próximo dia útil."""
    while not eh_dia_util(d, feriados_locais):
        d += timedelta(days=1)
    return d


def vencimento(ano: int, mes: int, dia_vencimento: int, feriados_locais: Collection[date] = ()) -> date:
    """Data em que sai o aviso de pagamento do mês, já ajustada para dia útil."""
    return proximo_dia_util(dia_no_mes(ano, mes, dia_vencimento), feriados_locais)


def aniversario(data_entrada: date, n: int) -> date:
    """Data do n-ésimo reajuste (n >= 1). 29/02 vira 28/02 nos anos não bissextos."""
    if n < 1:
        raise ValueError("O primeiro reajuste é o de número 1.")
    return data_entrada + relativedelta(years=n)


def data_aviso_reajuste(data_reajuste: date) -> date:
    """Um mês antes do aniversário, com a mesma regra de fim de mês."""
    return data_reajuste - relativedelta(months=1)


def proximo_aniversario(data_entrada: date, hoje: date) -> date:
    """Primeiro aniversário do contrato em `hoje` ou depois."""
    n = max(hoje.year - data_entrada.year, 1)
    while aniversario(data_entrada, n) < hoje:
        n += 1
    return aniversario(data_entrada, n)


def reajuste_em_aviso(data_entrada: date, hoje: date) -> date | None:
    """Aniversário cujo período de aviso inclui `hoje`, ou None.

    O período vai da data do aviso (1 mês antes) até o próprio aniversário. Assim, se o
    aviso não pôde sair no dia certo (IGP-M atrasado, PC desligado), ele sai depois.
    """
    proximo = proximo_aniversario(data_entrada, hoje)
    return proximo if data_aviso_reajuste(proximo) <= hoje else None


def eh_aniversario(data_entrada: date, hoje: date) -> bool:
    n = hoje.year - data_entrada.year
    return n >= 1 and aniversario(data_entrada, n) == hoje

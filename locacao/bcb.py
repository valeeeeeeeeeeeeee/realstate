"""Busca do IGP-M na API do Banco Central, série SGS 189 (spec §4.5)."""

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from urllib.error import HTTPError
from urllib.request import urlopen

from dateutil.relativedelta import relativedelta

from .models import IGPM

log = logging.getLogger(__name__)

URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.189/dados?formato=json&dataInicial={inicio:%d/%m/%Y}"

# Na primeira busca, traz meses suficientes para qualquer reajuste próximo.
MESES_INICIAIS = 24


def buscar(desde: date) -> dict[date, Decimal]:
    """Variações mensais publicadas a partir de `desde`, por mês (dia 1)."""
    try:
        with urlopen(URL.format(inicio=desde), timeout=30) as resposta:
            dados = json.load(resposta)
    except HTTPError as erro:
        # A API responde 404 quando ainda não há nenhum mês novo no período.
        if erro.code == 404:
            return {}
        raise
    return {datetime.strptime(item["data"], "%d/%m/%Y").date(): Decimal(item["valor"]) for item in dados}


def atualizar(hoje: date) -> list[date]:
    """Grava os meses que ainda não estão no banco e devolve quais foram gravados."""
    ultimo = IGPM.objects.order_by("-mes").values_list("mes", flat=True).first()
    desde = ultimo + relativedelta(months=1) if ultimo else hoje.replace(day=1) - relativedelta(months=MESES_INICIAIS)
    novos = []
    for mes, variacao in sorted(buscar(desde).items()):
        _, criado = IGPM.objects.get_or_create(mes=mes, defaults={"variacao": variacao})
        if criado:
            novos.append(mes)
    if novos:
        log.info("IGP-M: %d mês(es) novo(s) até %s", len(novos), f"{novos[-1]:%m/%Y}")
    return novos

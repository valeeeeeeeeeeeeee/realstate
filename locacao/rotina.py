"""Rotina diária: IGP-M, avisos de reajuste, aplicação dos reajustes e avisos de pagamento (spec §5)."""

import logging
import threading
from datetime import date, timedelta

from django.utils import timezone

from . import avisos, bcb, mensagens
from .models import Aviso, Execucao, Feriado, Locacao
from .reajustes import IGPMIncompleto, aplicar_reajustes, preparar_reajuste, reajuste_a_avisar
from .regras import datas

log = logging.getLogger(__name__)

# Impede que a execução da inicialização e a do horário marcado rodem ao mesmo tempo.
_trava = threading.Lock()


def executar(hoje: date | None = None) -> list[date]:
    """Atualiza o IGP-M e processa todos os dias pendentes desde a última execução, até hoje.

    Na primeira execução de todas, processa só o dia de hoje. Devolve os dias processados.
    """
    hoje = hoje or timezone.localdate()
    with _trava:
        try:
            bcb.atualizar(hoje)
        except Exception:
            # Sem IGP-M novo, os avisos de reajuste esperam; o resto da rotina segue.
            log.exception("Falha ao atualizar o IGP-M")

        execucao = Execucao.objects.first()
        dia = execucao.ultimo_dia + timedelta(days=1) if execucao else hoje
        processados = []
        while dia <= hoje:
            processar_dia(dia)
            Execucao.objects.update_or_create(pk=1, defaults={"ultimo_dia": dia})
            processados.append(dia)
            dia += timedelta(days=1)
        return processados


def processar_dia(dia: date) -> None:
    log.info("Processando %s", f"{dia:%d/%m/%Y}")
    ativas = list(
        Locacao.objects.select_related("imovel__locador", "locatario").filter(
            status=Locacao.Status.ATIVA, data_entrada__lte=dia
        )
    )
    # O reajuste é aplicado antes dos avisos de pagamento, para que o aviso do dia
    # do aniversário já saia com o valor novo.
    avisar_reajustes(ativas, dia)
    aplicar_reajustes(dia)
    for locacao in ativas:
        locacao.refresh_from_db(fields=["valor_aluguel"])
    avisar_pagamentos(ativas, dia)


def avisar_reajustes(locacoes: list[Locacao], dia: date) -> None:
    for locacao in locacoes:
        data_reajuste = reajuste_a_avisar(locacao, dia)
        if not data_reajuste:
            continue
        try:
            reajuste = preparar_reajuste(locacao, data_reajuste, datas.data_aviso_reajuste(data_reajuste))
        except IGPMIncompleto as pendencia:
            log.warning("Reajuste de %s aguardando IGP-M: %s", locacao, pendencia)
            continue
        destinos = [
            (Aviso.Destinatario.LOCATARIO, locacao.locatario.email),
            (Aviso.Destinatario.LOCADOR, locacao.imovel.locador.email),
        ]
        for destinatario, email in destinos:
            assunto, corpo = mensagens.reajuste(reajuste, destinatario)
            avisos.enviar(locacao, Aviso.Tipo.REAJUSTE, destinatario, str(reajuste.pk), email, assunto, corpo)


def avisar_pagamentos(locacoes: list[Locacao], dia: date) -> None:
    feriados = set(Feriado.objects.values_list("data", flat=True))
    mes_anterior = dia.replace(day=1) - timedelta(days=1)
    for locacao in locacoes:
        # O vencimento de um mês pode cair no início do mês seguinte (fim de semana + feriado).
        for ano, mes in [(mes_anterior.year, mes_anterior.month), (dia.year, dia.month)]:
            if (ano, mes) < (locacao.data_entrada.year, locacao.data_entrada.month):
                continue
            vencimento = datas.vencimento(ano, mes, locacao.dia_vencimento, feriados)
            if vencimento != dia:
                continue
            assunto, corpo = mensagens.pagamento(locacao, vencimento)
            avisos.enviar(
                locacao,
                Aviso.Tipo.PAGAMENTO,
                Aviso.Destinatario.LOCATARIO,
                f"{ano}-{mes:02d}",
                locacao.locatario.email,
                assunto,
                corpo,
            )

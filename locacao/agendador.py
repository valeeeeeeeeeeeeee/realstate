"""Agenda a rotina diária dentro da aplicação (spec §5)."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django.utils import timezone

from .rotina import executar

log = logging.getLogger(__name__)


def iniciar() -> BackgroundScheduler:
    """Roda a rotina agora, para recuperar os dias em que o PC estava desligado, e todo dia no horário."""
    hora, minuto = (int(parte) for parte in settings.ROTINA_HORARIO.split(":"))
    agendador = BackgroundScheduler(timezone=settings.TIME_ZONE)
    opcoes = dict(id="rotina", max_instances=1, coalesce=True, misfire_grace_time=None)
    agendador.add_job(executar, CronTrigger(hour=hora, minute=minuto), **opcoes)
    agendador.add_job(executar, next_run_time=timezone.now(), id="rotina-inicial", max_instances=1)
    agendador.start()
    log.info("Rotina diária agendada para %02d:%02d", hora, minuto)
    return agendador

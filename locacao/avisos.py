"""Envio de avisos com registro no log, sem nunca enviar o mesmo aviso em dobro (spec §3 e §6)."""

from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Aviso, Locacao


def enviar(
    locacao: Locacao,
    tipo: str,
    destinatario_tipo: str,
    referencia: str,
    destino: str,
    assunto: str,
    corpo: str,
) -> Aviso | None:
    """Envia o aviso e grava o resultado no log.

    Devolve None, sem enviar, se esse aviso já saiu com sucesso. Um aviso que falhou
    é tentado de novo e o mesmo registro é atualizado. Uma falha de envio fica no log
    e não levanta exceção, para não impedir os demais envios.
    """
    chave = dict(locacao=locacao, tipo=tipo, destinatario_tipo=destinatario_tipo, referencia=referencia)
    aviso = Aviso.objects.filter(**chave).first()
    if aviso and aviso.status == Aviso.Status.ENVIADO:
        return None

    try:
        send_mail(assunto, corpo, None, [destino])
        status, erro = Aviso.Status.ENVIADO, ""
    except Exception as exc:  # qualquer erro do servidor SMTP vai para o log
        status, erro = Aviso.Status.FALHOU, str(exc)

    dados = dict(destino=destino, status=status, erro=erro, enviado_em=timezone.now())
    if aviso:
        for campo, valor in dados.items():
            setattr(aviso, campo, valor)
        aviso.save()
        return aviso
    try:
        with transaction.atomic():
            return Aviso.objects.create(**chave, **dados)
    except IntegrityError:
        # Outra execução gravou o mesmo aviso ao mesmo tempo; o registro dela prevalece.
        return None

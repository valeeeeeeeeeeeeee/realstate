"""Formatos brasileiros para os templates do painel."""

from decimal import Decimal

from django import template

from .. import mensagens

register = template.Library()


@register.filter
def reais(centavos: int) -> str:
    return mensagens.reais(centavos)


@register.filter
def pct(fracao: Decimal) -> str:
    """Decimal('0.0412') → '4,12%'."""
    return mensagens.porcentagem(fracao * 100)

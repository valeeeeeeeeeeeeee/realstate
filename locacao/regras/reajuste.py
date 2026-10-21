"""Cálculo do novo valor do aluguel (spec §4.2 e §4.3)."""

from decimal import ROUND_HALF_UP, Decimal


def percentual_aplicado(igpm_acumulado: Decimal) -> Decimal:
    """Acumulado negativo não reduz o aluguel: o reajuste fica em 0%."""
    return max(igpm_acumulado, Decimal(0))


def valor_novo(valor_atual_centavos: int, igpm_acumulado: Decimal) -> int:
    """valor_atual × (1 + acumulado), arredondado para centavos (meio para cima)."""
    novo = Decimal(valor_atual_centavos) * (1 + percentual_aplicado(igpm_acumulado))
    return int(novo.quantize(Decimal(1), rounding=ROUND_HALF_UP))

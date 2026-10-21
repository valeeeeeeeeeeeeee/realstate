"""Monta o assunto e o corpo dos avisos a partir dos templates em templates/avisos/ (spec §6)."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.template.loader import render_to_string

from .models import IGPM, Aviso, Locacao, Reajuste
from .regras.reajuste import percentual_aplicado


def reais(centavos: int) -> str:
    """150000 → 'R$ 1.500,00'."""
    texto = f"{Decimal(centavos) / 100:,.2f}"
    return "R$ " + texto.replace(",", "_").replace(".", ",").replace("_", ".")


def porcentagem(valor_em_pct: Decimal) -> str:
    """Decimal('4.1234') → '4,12%'."""
    return f"{valor_em_pct.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}".replace(".", ",") + "%"


def _data(d: date) -> str:
    return f"{d:%d/%m/%Y}"


def _mes(d: date) -> str:
    return f"{d:%m/%Y}"


def _renderizar(nome: str, contexto: dict) -> tuple[str, str]:
    assunto = render_to_string(f"avisos/{nome}_assunto.txt", contexto).strip()
    corpo = render_to_string(f"avisos/{nome}.txt", contexto).strip() + "\n"
    return assunto, corpo


def pagamento(locacao: Locacao, vencimento: date) -> tuple[str, str]:
    return _renderizar(
        "pagamento",
        {
            "nome": locacao.locatario.nome,
            "endereco": locacao.imovel.endereco,
            "valor": reais(locacao.valor_aluguel),
            "vencimento": _data(vencimento),
        },
    )


def reajuste(reajuste: Reajuste, destinatario_tipo: str) -> tuple[str, str]:
    locacao = reajuste.locacao
    if destinatario_tipo == Aviso.Destinatario.LOCADOR:
        nome = locacao.imovel.locador.nome
    else:
        nome = locacao.locatario.nome
    indices = IGPM.objects.filter(mes__range=(reajuste.periodo_inicio, reajuste.periodo_fim)).order_by("mes")
    return _renderizar(
        "reajuste",
        {
            "nome": nome,
            "endereco": locacao.imovel.endereco,
            "data_reajuste": _data(reajuste.data_reajuste),
            "periodo": f"{_mes(reajuste.periodo_inicio)} a {_mes(reajuste.periodo_fim)}",
            "meses": [{"mes": _mes(i.mes), "variacao": porcentagem(i.variacao)} for i in indices],
            "acumulado": porcentagem(reajuste.igpm_acumulado * 100),
            "negativo": reajuste.igpm_acumulado < 0,
            "percentual_aplicado": porcentagem(percentual_aplicado(reajuste.igpm_acumulado) * 100),
            "valor_atual": reais(reajuste.valor_anterior),
            "valor_novo": reais(reajuste.valor_novo),
        },
    )

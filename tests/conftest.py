from datetime import date
from decimal import Decimal
from unittest import mock

import pytest

from locacao.models import IGPM, Imovel, Locacao, Locador, Locatario
from locacao.regras import igpm


@pytest.fixture(autouse=True)
def sem_internet():
    """Os testes nunca chamam a API do Banco Central de verdade."""
    with mock.patch("locacao.bcb.buscar", return_value={}) as buscar:
        yield buscar


@pytest.fixture
def locacao(db):
    locador = Locador.objects.create(nome="Ana Locadora", email="ana@exemplo.com")
    locatario = Locatario.objects.create(nome="Bruno Locatário", email="bruno@exemplo.com")
    imovel = Imovel.objects.create(locador=locador, endereco="Rua das Flores, 10")
    return Locacao.objects.create(
        imovel=imovel,
        locatario=locatario,
        data_entrada=date(2025, 12, 15),
        valor_aluguel=150000,
        dia_vencimento=15,
    )


@pytest.fixture
def igpm_um_por_cento(db):
    """IGP-M de 1% ao mês de nov/2025 a out/2026: período do aviso de 15/11/2026."""
    for mes in igpm.meses(date(2025, 11, 1), date(2026, 10, 1)):
        IGPM.objects.create(mes=mes, variacao=Decimal("1"))

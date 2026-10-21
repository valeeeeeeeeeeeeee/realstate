import io
import json
from datetime import date
from decimal import Decimal
from unittest import mock
from urllib.error import HTTPError

import pytest

from locacao import bcb
from locacao.models import IGPM

# Os testes deste arquivo usam a função buscar original, com a rede simulada.
buscar_original = bcb.buscar


def resposta(dados):
    return io.BytesIO(json.dumps(dados).encode())


class TestBuscar:
    def test_converte_datas_e_valores(self):
        dados = [{"data": "01/08/2026", "valor": "-0.22"}, {"data": "01/09/2026", "valor": "1.57"}]
        with mock.patch("locacao.bcb.urlopen", return_value=resposta(dados)) as urlopen:
            resultado = buscar_original(date(2026, 8, 1))

        assert resultado == {date(2026, 8, 1): Decimal("-0.22"), date(2026, 9, 1): Decimal("1.57")}
        assert "bcdata.sgs.189" in urlopen.call_args.args[0]
        assert "dataInicial=01/08/2026" in urlopen.call_args.args[0]

    def test_404_significa_nenhum_mes_novo(self):
        erro = HTTPError("url", 404, "Value(s) not found", {}, None)
        with mock.patch("locacao.bcb.urlopen", side_effect=erro):
            assert buscar_original(date(2026, 10, 1)) == {}

    def test_outros_erros_sobem(self):
        erro = HTTPError("url", 500, "erro", {}, None)
        with mock.patch("locacao.bcb.urlopen", side_effect=erro), pytest.raises(HTTPError):
            buscar_original(date(2026, 10, 1))


class TestAtualizar:
    def test_primeira_vez_busca_24_meses(self, db, sem_internet):
        sem_internet.return_value = {date(2024, 10, 1): Decimal("1.52")}

        assert bcb.atualizar(date(2026, 10, 21)) == [date(2024, 10, 1)]
        sem_internet.assert_called_once_with(date(2024, 10, 1))

    def test_depois_busca_a_partir_do_mes_seguinte_ao_ultimo(self, db, sem_internet):
        IGPM.objects.create(mes=date(2026, 8, 1), variacao=Decimal("-0.22"))
        sem_internet.return_value = {date(2026, 9, 1): Decimal("1.57")}

        assert bcb.atualizar(date(2026, 10, 21)) == [date(2026, 9, 1)]
        sem_internet.assert_called_once_with(date(2026, 9, 1))
        assert IGPM.objects.get(mes=date(2026, 9, 1)).variacao == Decimal("1.57")

    def test_nao_sobrescreve_mes_existente(self, db, sem_internet):
        IGPM.objects.create(mes=date(2026, 9, 1), variacao=Decimal("1.57"))
        sem_internet.return_value = {date(2026, 9, 1): Decimal("9.99")}

        assert bcb.atualizar(date(2026, 10, 21)) == []
        assert IGPM.objects.get(mes=date(2026, 9, 1)).variacao == Decimal("1.57")

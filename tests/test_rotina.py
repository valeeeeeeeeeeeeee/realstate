import threading
from datetime import date
from decimal import Decimal

import pytest
from django.core import mail
from django.core.management import call_command

from locacao import agendador
from locacao.models import IGPM, Aviso, Execucao, Feriado, Locacao, Reajuste
from locacao.rotina import executar


def ja_processado_ate(dia):
    Execucao.objects.create(pk=1, ultimo_dia=dia)


def avisos_de(tipo):
    return list(Aviso.objects.filter(tipo=tipo).order_by("destinatario_tipo"))


class TestRecuperacao:
    def test_primeira_execucao_processa_so_hoje(self, db):
        assert executar(date(2026, 10, 21)) == [date(2026, 10, 21)]
        assert Execucao.objects.get().ultimo_dia == date(2026, 10, 21)

    def test_processa_os_dias_em_que_o_pc_estava_desligado(self, db):
        ja_processado_ate(date(2026, 10, 18))

        assert executar(date(2026, 10, 21)) == [date(2026, 10, 19), date(2026, 10, 20), date(2026, 10, 21)]
        assert Execucao.objects.get().ultimo_dia == date(2026, 10, 21)

    def test_rodar_de_novo_no_mesmo_dia_nao_faz_nada(self, locacao):
        ja_processado_ate(date(2026, 10, 14))
        executar(date(2026, 10, 15))

        assert executar(date(2026, 10, 15)) == []
        assert len(mail.outbox) == 1

    def test_aviso_perdido_sai_na_recuperacao(self, locacao):
        # Vencimento em 15/10/2026 (quinta), mas o PC só ligou no dia 20.
        ja_processado_ate(date(2026, 10, 10))

        executar(date(2026, 10, 20))

        [aviso] = avisos_de(Aviso.Tipo.PAGAMENTO)
        assert aviso.referencia == "2026-10"

    def test_falha_no_igpm_nao_impede_a_rotina(self, locacao, sem_internet):
        sem_internet.side_effect = OSError("sem internet")
        ja_processado_ate(date(2026, 10, 14))

        executar(date(2026, 10, 15))

        assert len(avisos_de(Aviso.Tipo.PAGAMENTO)) == 1


class TestPagamento:
    def test_avisa_na_data_de_vencimento(self, locacao):
        ja_processado_ate(date(2026, 10, 13))

        executar(date(2026, 10, 14))
        assert mail.outbox == []
        executar(date(2026, 10, 15))

        [email] = mail.outbox
        assert email.to == ["bruno@exemplo.com"]
        assert "R$ 1.500,00" in email.body

    def test_vencimento_no_domingo_vai_para_segunda(self, locacao):
        ja_processado_ate(date(2026, 11, 14))

        executar(date(2026, 11, 15))  # domingo
        assert avisos_de(Aviso.Tipo.PAGAMENTO) == []
        executar(date(2026, 11, 16))
        assert avisos_de(Aviso.Tipo.PAGAMENTO)[0].referencia == "2026-11"

    def test_vencimento_que_passa_para_o_mes_seguinte(self, locacao):
        # Dia 31/10/2026 é sábado e 02/11 é Finados: o aviso de outubro sai em 03/11.
        locacao.dia_vencimento = 31
        locacao.save()
        ja_processado_ate(date(2026, 10, 30))

        executar(date(2026, 11, 3))

        [aviso] = avisos_de(Aviso.Tipo.PAGAMENTO)
        assert aviso.referencia == "2026-10"

    def test_feriado_local(self, locacao):
        Feriado.objects.create(data=date(2026, 10, 15), descricao="Feriado municipal")
        ja_processado_ate(date(2026, 10, 14))

        executar(date(2026, 10, 15))
        assert avisos_de(Aviso.Tipo.PAGAMENTO) == []
        executar(date(2026, 10, 16))
        assert len(avisos_de(Aviso.Tipo.PAGAMENTO)) == 1

    def test_locacao_rescindida_nao_recebe_aviso(self, locacao):
        locacao.status = Locacao.Status.RESCINDIDA
        locacao.data_encerramento = date(2026, 10, 1)
        locacao.save()
        ja_processado_ate(date(2026, 10, 14))

        executar(date(2026, 10, 15))

        assert mail.outbox == []

    def test_nao_avisa_meses_antes_da_entrada(self, locacao):
        locacao.data_entrada = date(2026, 11, 1)
        locacao.save()
        ja_processado_ate(date(2026, 10, 14))

        executar(date(2026, 10, 15))

        assert mail.outbox == []


class TestReajuste:
    def test_fluxo_completo(self, locacao, igpm_um_por_cento):
        ja_processado_ate(date(2026, 11, 13))

        executar(date(2026, 11, 14))
        assert avisos_de(Aviso.Tipo.REAJUSTE) == []

        # 15/11: aviso de reajuste para locatário e locador.
        executar(date(2026, 11, 15))
        locador, locatario = avisos_de(Aviso.Tipo.REAJUSTE)
        assert (locador.destino, locatario.destino) == ("ana@exemplo.com", "bruno@exemplo.com")
        reajuste = Reajuste.objects.get()
        assert locador.referencia == locatario.referencia == str(reajuste.pk)
        assert reajuste.status == Reajuste.Status.CALCULADO

        # Nos dias seguintes, não reenvia.
        executar(date(2026, 12, 14))
        assert len(avisos_de(Aviso.Tipo.REAJUSTE)) == 2

        # 15/12: aplica e o aviso de pagamento do dia já sai com o valor novo.
        executar(date(2026, 12, 15))
        locacao.refresh_from_db()
        reajuste.refresh_from_db()
        assert locacao.valor_aluguel == 169024
        assert reajuste.status == Reajuste.Status.APLICADO
        assert "R$ 1.690,24" in mail.outbox[-1].body
        assert mail.outbox[-1].subject.startswith("Lembrete")

    def test_igpm_atrasado_adia_o_aviso(self, locacao, igpm_um_por_cento):
        IGPM.objects.filter(mes=date(2026, 10, 1)).delete()
        ja_processado_ate(date(2026, 11, 14))

        executar(date(2026, 11, 15))
        assert avisos_de(Aviso.Tipo.REAJUSTE) == []
        assert Reajuste.objects.count() == 0

        IGPM.objects.create(mes=date(2026, 10, 1), variacao=Decimal("1"))
        executar(date(2026, 11, 16))
        assert len(avisos_de(Aviso.Tipo.REAJUSTE)) == 2
        # O período continua o do aviso original (out/2025 a out/2026).
        assert Reajuste.objects.get().periodo_fim == date(2026, 10, 1)

    def test_reajuste_preparado_no_proprio_aniversario_e_aplicado_no_dia(self, locacao, igpm_um_por_cento):
        ja_processado_ate(date(2026, 12, 14))

        executar(date(2026, 12, 15))

        locacao.refresh_from_db()
        assert locacao.valor_aluguel == 169024

    def test_aviso_de_reajuste_que_falhou_e_tentado_no_dia_seguinte(self, locacao, igpm_um_por_cento, monkeypatch):
        ja_processado_ate(date(2026, 11, 14))
        monkeypatch.setattr("locacao.avisos.send_mail", _falha)
        executar(date(2026, 11, 15))
        assert {a.status for a in avisos_de(Aviso.Tipo.REAJUSTE)} == {Aviso.Status.FALHOU}

        monkeypatch.undo()
        executar(date(2026, 11, 16))
        assert {a.status for a in avisos_de(Aviso.Tipo.REAJUSTE)} == {Aviso.Status.ENVIADO}


def _falha(*args, **kwargs):
    raise OSError("SMTP fora do ar")


def test_comando_rodar_rotina(locacao, capsys):
    ja_processado_ate(date(2026, 10, 13))

    call_command("rodar_rotina", "--ate", "2026-10-15")

    assert "Dias processados: 14/10/2026 a 15/10/2026" in capsys.readouterr().out
    assert Execucao.objects.get().ultimo_dia == date(2026, 10, 15)
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_agendador(settings, monkeypatch):
    executou = threading.Event()
    monkeypatch.setattr("locacao.agendador.executar", executou.set)
    settings.ROTINA_HORARIO = "07:30"

    sched = agendador.iniciar()
    try:
        rotina = sched.get_job("rotina")
        assert (str(rotina.trigger.fields[5]), str(rotina.trigger.fields[6])) == ("7", "30")
        # A execução de recuperação roda logo na inicialização.
        assert executou.wait(timeout=5)
    finally:
        sched.shutdown()

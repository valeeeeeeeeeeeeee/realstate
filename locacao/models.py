"""Modelo de dados (spec §3).

Valores em dinheiro são guardados em centavos inteiros, para não haver erro de arredondamento.
"""

from django.db import models
from django.db.models import Q


class Arquivavel(models.Model):
    """Base para cadastros que são arquivados em vez de excluídos (spec §7)."""

    arquivado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class Locador(Arquivavel):
    nome = models.CharField(max_length=200)
    email = models.EmailField()
    telefone = models.CharField(max_length=40, blank=True)

    class Meta:
        verbose_name_plural = "locadores"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Locatario(Arquivavel):
    nome = models.CharField(max_length=200)
    email = models.EmailField()
    telefone = models.CharField(max_length=40, blank=True)

    class Meta:
        verbose_name = "locatário"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Imovel(Arquivavel):
    locador = models.ForeignKey(Locador, on_delete=models.PROTECT, related_name="imoveis")
    endereco = models.CharField("endereço", max_length=300)

    class Meta:
        verbose_name = "imóvel"
        verbose_name_plural = "imóveis"
        ordering = ["endereco"]

    def __str__(self):
        return self.endereco


class Locacao(models.Model):
    class Status(models.TextChoices):
        ATIVA = "ativa", "Ativa"
        RESCINDIDA = "rescindida", "Rescindida"
        ENCERRADA = "encerrada", "Encerrada"

    imovel = models.ForeignKey(Imovel, on_delete=models.PROTECT, related_name="locacoes")
    locatario = models.ForeignKey(Locatario, on_delete=models.PROTECT, related_name="locacoes")
    data_entrada = models.DateField(help_text="Também é a data base do reajuste anual.")
    data_saida = models.DateField(null=True, blank=True, help_text="Fim previsto do contrato (só informativo).")
    valor_aluguel = models.PositiveIntegerField(help_text="Valor vigente, em centavos.")
    dia_vencimento = models.PositiveSmallIntegerField(help_text="Dia do mês do pagamento (1 a 31).")
    status = models.CharField(max_length=10, choices=Status, default=Status.ATIVA)
    data_encerramento = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "locação"
        verbose_name_plural = "locações"
        constraints = [
            models.UniqueConstraint(
                fields=["imovel"],
                condition=Q(status="ativa"),
                name="uma_locacao_ativa_por_imovel",
            ),
            models.CheckConstraint(
                condition=Q(dia_vencimento__gte=1, dia_vencimento__lte=31),
                name="dia_vencimento_valido",
            ),
        ]

    def __str__(self):
        return f"{self.imovel} — {self.locatario}"


class Reajuste(models.Model):
    class Status(models.TextChoices):
        CALCULADO = "calculado", "Calculado"
        APLICADO = "aplicado", "Aplicado"

    locacao = models.ForeignKey(Locacao, on_delete=models.CASCADE, related_name="reajustes")
    data_reajuste = models.DateField(help_text="Aniversário do contrato.")
    periodo_inicio = models.DateField(help_text="Primeiro mês de IGP-M usado (dia 1).")
    periodo_fim = models.DateField(help_text="Último mês de IGP-M usado (dia 1).")
    igpm_acumulado = models.DecimalField(max_digits=12, decimal_places=8, help_text="Ex.: 0.0412 = 4,12%.")
    valor_anterior = models.PositiveIntegerField(help_text="Em centavos.")
    valor_novo = models.PositiveIntegerField(help_text="Em centavos.")
    status = models.CharField(max_length=10, choices=Status, default=Status.CALCULADO)

    class Meta:
        ordering = ["-data_reajuste"]
        constraints = [
            models.UniqueConstraint(fields=["locacao", "data_reajuste"], name="um_reajuste_por_aniversario"),
        ]

    def __str__(self):
        return f"Reajuste {self.data_reajuste:%d/%m/%Y} — {self.locacao}"


class IGPM(models.Model):
    mes = models.DateField(primary_key=True, help_text="Sempre o dia 1 do mês.")
    variacao = models.DecimalField(max_digits=8, decimal_places=4, help_text="Variação do mês, em %.")
    obtido_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "IGP-M"
        verbose_name_plural = "IGP-M"
        ordering = ["-mes"]

    def __str__(self):
        return f"{self.mes:%m/%Y}: {self.variacao}%"


class Feriado(models.Model):
    """Feriados estaduais e municipais. Os nacionais vêm da biblioteca holidays."""

    data = models.DateField(primary_key=True)
    descricao = models.CharField("descrição", max_length=200)

    class Meta:
        ordering = ["data"]

    def __str__(self):
        return f"{self.data:%d/%m/%Y} — {self.descricao}"


class Aviso(models.Model):
    class Tipo(models.TextChoices):
        PAGAMENTO = "pagamento", "Pagamento"
        REAJUSTE = "reajuste", "Reajuste"

    class Destinatario(models.TextChoices):
        LOCATARIO = "locatario", "Locatário"
        LOCADOR = "locador", "Locador"

    class Status(models.TextChoices):
        ENVIADO = "enviado", "Enviado"
        FALHOU = "falhou", "Falhou"

    locacao = models.ForeignKey(Locacao, on_delete=models.CASCADE, related_name="avisos")
    tipo = models.CharField(max_length=10, choices=Tipo)
    destinatario_tipo = models.CharField(max_length=10, choices=Destinatario)
    destino = models.EmailField()
    referencia = models.CharField(
        max_length=40, help_text="Mês do vencimento (AAAA-MM) ou id do reajuste."
    )
    status = models.CharField(max_length=10, choices=Status)
    erro = models.TextField(blank=True)
    enviado_em = models.DateTimeField()

    class Meta:
        ordering = ["-enviado_em"]
        constraints = [
            # Nunca enviar o mesmo aviso em dobro (spec §3).
            models.UniqueConstraint(
                fields=["locacao", "tipo", "destinatario_tipo", "referencia"],
                name="aviso_unico",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.referencia} → {self.destino}"


class Execucao(models.Model):
    """Registra até que dia a rotina diária já foi processada (spec §5)."""

    ultimo_dia = models.DateField()
    executado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "execução"
        verbose_name_plural = "execuções"
        ordering = ["-ultimo_dia"]

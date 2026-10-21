"""Painel de administração. Por enquanto só os cadastros básicos; as ações do spec §7 vêm depois."""

from django.contrib import admin

from .models import IGPM, Aviso, Feriado, Imovel, Locacao, Locador, Locatario, Reajuste


@admin.register(Locador, Locatario)
class PessoaAdmin(admin.ModelAdmin):
    list_display = ["nome", "email", "telefone"]
    search_fields = ["nome", "email"]


@admin.register(Imovel)
class ImovelAdmin(admin.ModelAdmin):
    list_display = ["endereco", "locador"]
    search_fields = ["endereco", "locador__nome"]


class ReajusteInline(admin.TabularInline):
    model = Reajuste
    extra = 0
    can_delete = False
    readonly_fields = [f.name for f in Reajuste._meta.fields]


@admin.register(Locacao)
class LocacaoAdmin(admin.ModelAdmin):
    list_display = ["imovel", "locatario", "valor_aluguel", "dia_vencimento", "status"]
    list_filter = ["status"]
    inlines = [ReajusteInline]


@admin.register(Aviso)
class AvisoAdmin(admin.ModelAdmin):
    list_display = ["enviado_em", "tipo", "destino", "referencia", "status"]
    list_filter = ["tipo", "status", "enviado_em"]


@admin.register(IGPM)
class IGPMAdmin(admin.ModelAdmin):
    list_display = ["mes", "variacao", "obtido_em"]


admin.site.register(Feriado)

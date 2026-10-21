"""Painel de administração (spec §7)."""

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import avisos, bcb
from .mensagens import reais
from .models import IGPM, Aviso, Feriado, Imovel, Locacao, Locador, Locatario, Reajuste


class SituacaoFilter(admin.SimpleListFilter):
    """Por padrão, as listas mostram só os cadastros não arquivados."""

    title = "situação"
    parameter_name = "situacao"

    def lookups(self, request, model_admin):
        return [("arquivados", "Arquivados"), ("todos", "Todos")]

    def choices(self, changelist):
        yield {
            "selected": self.value() is None,
            "query_string": changelist.get_query_string(remove=[self.parameter_name]),
            "display": "Ativos",
        }
        for valor, texto in self.lookup_choices:
            yield {
                "selected": self.value() == valor,
                "query_string": changelist.get_query_string({self.parameter_name: valor}),
                "display": texto,
            }

    def queryset(self, request, queryset):
        if self.value() == "todos":
            return queryset
        return queryset.filter(arquivado_em__isnull=self.value() != "arquivados")


class ArquivavelAdmin(admin.ModelAdmin):
    """Remover = arquivar: o registro some das listas, mas o histórico fica guardado."""

    # Caminho até o status das locações do registro, para bloquear o arquivamento.
    status_locacoes = "locacoes__status"

    list_filter = [SituacaoFilter]
    readonly_fields = ["arquivado_em"]
    actions = ["arquivar", "desarquivar"]

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Arquivar selecionados")
    def arquivar(self, request, queryset):
        com_locacao_ativa = queryset.filter(**{self.status_locacoes: Locacao.Status.ATIVA}).distinct()
        if com_locacao_ativa:
            nomes = ", ".join(str(obj) for obj in com_locacao_ativa)
            messages.error(
                request, f"Não arquivados, pois têm locação ativa (encerre ou rescinda antes): {nomes}."
            )
        n = queryset.filter(arquivado_em__isnull=True).exclude(pk__in=com_locacao_ativa).update(
            arquivado_em=timezone.now()
        )
        if n:
            messages.success(request, f"{n} registro(s) arquivado(s).")

    @admin.action(description="Desarquivar selecionados")
    def desarquivar(self, request, queryset):
        n = queryset.filter(arquivado_em__isnull=False).update(arquivado_em=None)
        messages.success(request, f"{n} registro(s) desarquivado(s).")


def so_nao_arquivados(form, campos, obj):
    """Nos formulários, só oferece cadastros não arquivados (mais o que já está escolhido)."""
    for campo in campos:
        field = form.base_fields[campo]
        atual = getattr(obj, f"{campo}_id", None)
        field.queryset = field.queryset.filter(arquivado_em__isnull=True) | field.queryset.filter(pk=atual)


@admin.register(Locador)
class LocadorAdmin(ArquivavelAdmin):
    status_locacoes = "imoveis__locacoes__status"
    list_display = ["nome", "email", "telefone"]
    search_fields = ["nome", "email"]


@admin.register(Locatario)
class LocatarioAdmin(ArquivavelAdmin):
    list_display = ["nome", "email", "telefone"]
    search_fields = ["nome", "email"]


@admin.register(Imovel)
class ImovelAdmin(ArquivavelAdmin):
    list_display = ["endereco", "locador"]
    search_fields = ["endereco", "locador__nome"]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        so_nao_arquivados(form, ["locador"], obj)
        return form


class ReajusteInline(admin.TabularInline):
    model = Reajuste
    extra = 0
    can_delete = False
    readonly_fields = [f.name for f in Reajuste._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False


class EncerramentoForm(forms.Form):
    data = forms.DateField(label="Data", widget=forms.DateInput(attrs={"type": "date"}))


@admin.register(Locacao)
class LocacaoAdmin(admin.ModelAdmin):
    list_display = ["imovel", "locatario", "valor", "dia_vencimento", "status", "data_encerramento"]
    list_filter = ["status"]
    search_fields = ["imovel__endereco", "locatario__nome", "imovel__locador__nome"]
    # O status só muda pelas ações "rescindir" e "encerrar", que pedem a data.
    readonly_fields = ["status", "data_encerramento"]
    inlines = [ReajusteInline]
    actions = ["rescindir", "encerrar"]

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="valor do aluguel", ordering="valor_aluguel")
    def valor(self, obj):
        return reais(obj.valor_aluguel)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        so_nao_arquivados(form, ["imovel", "locatario"], obj)
        return form

    @admin.action(description="Rescindir contrato das locações selecionadas")
    def rescindir(self, request, queryset):
        return self._finalizar(request, queryset, Locacao.Status.RESCINDIDA, "rescindir")

    @admin.action(description="Encerrar (fim da locação) das locações selecionadas")
    def encerrar(self, request, queryset):
        return self._finalizar(request, queryset, Locacao.Status.ENCERRADA, "encerrar")

    def _finalizar(self, request, queryset, status, acao):
        """Pede a data numa página intermediária e marca as locações ativas com o novo status."""
        ativas = queryset.filter(status=Locacao.Status.ATIVA).select_related("imovel", "locatario")
        if not ativas:
            messages.warning(request, "Nenhuma das locações selecionadas está ativa.")
            return None

        if "confirmar" in request.POST:
            form = EncerramentoForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data["data"]
                invalidas = [loc for loc in ativas if data < loc.data_entrada]
                if invalidas:
                    nomes = ", ".join(str(loc) for loc in invalidas)
                    form.add_error("data", f"A data é anterior à entrada de: {nomes}.")
                else:
                    n = ativas.update(status=status, data_encerramento=data)
                    rotulo = Locacao.Status(status).label.lower()
                    messages.success(request, f"{n} locação(ões) marcada(s) como {rotulo} em {data:%d/%m/%Y}.")
                    return None
        else:
            form = EncerramentoForm(initial={"data": timezone.localdate()})

        contexto = {
            **self.admin_site.each_context(request),
            "title": f"{acao.capitalize()} locação",
            "opts": self.model._meta,
            "acao": acao,
            "status": Locacao.Status(status).label.lower(),
            "locacoes": ativas,
            "ignoradas": queryset.count() - len(ativas),
            "form": form,
            "action_checkbox_name": ACTION_CHECKBOX_NAME,
        }
        return TemplateResponse(request, "admin/locacao/locacao/finalizar.html", contexto)


@admin.register(Aviso)
class AvisoAdmin(admin.ModelAdmin):
    """Log de envios: somente leitura, com a ação de reenviar os que falharam."""

    list_display = ["enviado_em", "tipo", "destinatario_tipo", "destino", "locacao", "referencia", "status", "erro"]
    list_filter = ["tipo", "status", "destinatario_tipo", "enviado_em"]
    search_fields = ["destino", "locacao__imovel__endereco", "locacao__locatario__nome"]
    actions = ["reenviar"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Reenviar avisos que falharam")
    def reenviar(self, request, queryset):
        falhas = queryset.filter(status=Aviso.Status.FALHOU).select_related(
            "locacao__imovel__locador", "locacao__locatario"
        )
        if not falhas:
            messages.warning(request, "Nenhum dos avisos selecionados falhou; nada a reenviar.")
            return
        enviados, erros = 0, []
        for aviso in falhas:
            resultado = avisos.reenviar(aviso)
            if resultado and resultado.status == Aviso.Status.FALHOU:
                erros.append(f"{resultado.destino}: {resultado.erro}")
            else:
                enviados += 1
        if enviados:
            messages.success(request, f"{enviados} aviso(s) reenviado(s).")
        if erros:
            messages.error(request, "Falhou de novo: " + "; ".join(erros))


@admin.register(IGPM)
class IGPMAdmin(admin.ModelAdmin):
    list_display = ["mes", "variacao", "obtido_em"]

    def get_urls(self):
        atualizar = self.admin_site.admin_view(require_POST(self.atualizar_view))
        return [path("atualizar/", atualizar, name="locacao_igpm_atualizar"), *super().get_urls()]

    def atualizar_view(self, request):
        """Busca agora os meses novos na API do Banco Central."""
        try:
            novos = bcb.atualizar(timezone.localdate())
        except Exception as exc:
            messages.error(request, f"Não foi possível buscar o IGP-M no Banco Central: {exc}")
        else:
            if novos:
                meses = ", ".join(f"{m:%m/%Y}" for m in novos)
                messages.success(request, f"IGP-M atualizado: {meses}.")
            else:
                messages.info(request, "O IGP-M já estava atualizado; nenhum mês novo publicado.")

        destino = request.POST.get("next")
        if not url_has_allowed_host_and_scheme(destino, {request.get_host()}):
            destino = reverse("admin:locacao_igpm_changelist")
        return redirect(destino)


admin.site.register(Feriado)

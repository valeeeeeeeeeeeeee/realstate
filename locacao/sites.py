"""Site do painel: o Django Admin com a página inicial customizada (spec §7)."""

from django.contrib import admin
from django.utils import timezone

from . import painel


class PainelSite(admin.AdminSite):
    site_header = "Avisos e Reajustes de Locação"
    site_title = "Locação"
    index_title = "Painel"
    index_template = "admin/painel.html"

    def index(self, request, extra_context=None):
        hoje = timezone.localdate()
        contexto = {
            "hoje": hoje,
            "igpm_12_meses": painel.igpm_12_meses(),
            "vencimentos": painel.proximos_vencimentos(hoje),
            "dias_vencimentos": painel.DIAS_VENCIMENTOS,
            "reajustes": painel.proximos_reajustes(hoje),
            "dias_reajustes": painel.DIAS_REAJUSTES,
            "falhas": painel.falhas_de_envio(),
            "pendencias_igpm": painel.pendencias_igpm(hoje),
            **(extra_context or {}),
        }
        return super().index(request, contexto)

from django.apps import AppConfig
from django.contrib.admin import apps as admin_apps


class LocacaoConfig(AppConfig):
    name = 'locacao'


class PainelAdminConfig(admin_apps.AdminConfig):
    """Troca o admin.site padrão pelo site do painel."""

    default = False  # o app "locacao" continua usando o LocacaoConfig
    default_site = "locacao.sites.PainelSite"

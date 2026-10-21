from django.contrib import admin
from django.urls import path

# O painel é o próprio Django Admin, servido na raiz (o site é locacao.sites.PainelSite).
urlpatterns = [
    path("", admin.site.urls),
]

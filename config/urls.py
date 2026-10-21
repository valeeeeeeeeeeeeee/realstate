from django.contrib import admin
from django.urls import path

admin.site.site_header = "Avisos e Reajustes de Locação"
admin.site.site_title = "Locação"
admin.site.index_title = "Painel"

# O painel é o próprio Django Admin, servido na raiz.
urlpatterns = [
    path("", admin.site.urls),
]

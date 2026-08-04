"""Rotas da API JSON somente-leitura (montadas em /api/v1/).

Separadas de ``core.urls`` porque não compartilham nada com as views HTML:
não usam sessão, não usam ``login_required`` e não usam o hospital da sessão.
"""

from django.urls import path

from core.views.api_views import formulario, hospitais, paciente, pacientes

app_name = "api"

urlpatterns = [
    path("hospitais/", hospitais, name="hospitais"),
    path("pacientes/", pacientes, name="pacientes"),
    path("paciente/", paciente, name="paciente"),
    path("formulario/", formulario, name="formulario"),
]

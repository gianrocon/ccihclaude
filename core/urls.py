from django.urls import path

from core.views.patient_views import busca, paciente_detalhe
from core.views.import_views import importar, limpar_banco
from core.views.report_views import cobertura
from core.views.admin_views import gerenciar_usuarios, editar_usuario

urlpatterns = [
    path("", busca, name="busca"),
    path("paciente/<int:pk>/", paciente_detalhe, name="paciente_detalhe"),
    path("importar/", importar, name="importar"),
    path("limpar/", limpar_banco, name="limpar_banco"),
    path("cobertura/", cobertura, name="cobertura"),
    path("gerenciar-usuarios/", gerenciar_usuarios, name="gerenciar_usuarios"),
    path("gerenciar-usuarios/<int:pk>/editar/", editar_usuario, name="editar_usuario"),
]

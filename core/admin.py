from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Hospital, CustomUser, Importacao, Paciente, Cultura, Antibiograma, ControleAtbRaw, Internamento


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ["sigla", "nome", "ativo", "criado_em"]
    list_filter = ["ativo"]
    search_fields = ["nome", "sigla"]


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ["username", "hospital", "papel", "is_active", "is_staff"]
    list_filter = ["papel", "hospital", "is_active", "is_staff"]
    fieldsets = UserAdmin.fieldsets + (
        ("CCIH", {"fields": ("hospital", "papel")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("CCIH", {"fields": ("hospital", "papel")}),
    )


@admin.register(Importacao)
class ImportacaoAdmin(admin.ModelAdmin):
    list_display = ["hospital", "usuario", "tipo", "arquivo", "importado_em", "registros"]
    list_filter = ["hospital", "tipo"]
    readonly_fields = [f.name for f in Importacao._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ["prontuario", "nome", "hospital"]
    list_filter = ["hospital"]
    search_fields = ["prontuario", "nome"]
    readonly_fields = ["id"]


@admin.register(Cultura)
class CulturaAdmin(admin.ModelAdmin):
    list_display = ["paciente", "procedimento", "microrganismo", "dt_coleta"]
    list_filter = ["paciente__hospital"]
    search_fields = ["paciente__prontuario", "paciente__nome", "microrganismo"]
    readonly_fields = [f.name for f in Cultura._meta.fields]


@admin.register(ControleAtbRaw)
class ControleAtbRawAdmin(admin.ModelAdmin):
    list_display = ["paciente", "medicamento", "dt_inicio", "dias_em_uso"]
    list_filter = ["paciente__hospital"]
    search_fields = ["paciente__prontuario", "paciente__nome", "medicamento"]
    readonly_fields = [f.name for f in ControleAtbRaw._meta.fields]


@admin.register(Internamento)
class InternamentoAdmin(admin.ModelAdmin):
    list_display = ["paciente", "dt_entrada", "dt_alta", "dias"]
    list_filter = ["paciente__hospital"]
    search_fields = ["paciente__prontuario", "paciente__nome"]
    readonly_fields = [f.name for f in Internamento._meta.fields]

from django.db import models
from django.contrib.auth.models import AbstractUser


class Hospital(models.Model):
    nome = models.CharField(max_length=200, verbose_name="Nome")
    sigla = models.CharField(max_length=10, unique=True, verbose_name="Sigla")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Hospital"
        verbose_name_plural = "Hospitais"
        ordering = ["sigla"]

    def __str__(self):
        return f"{self.sigla} — {self.nome}"


class CustomUser(AbstractUser):
    hospitais = models.ManyToManyField(
        Hospital,
        through="Vinculo",
        related_name="usuarios",
        blank=True,
        verbose_name="Hospitais",
    )

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"

    def hospitais_disponiveis(self):
        """Hospitais ativos aos quais o usuário está vinculado."""
        return (
            Hospital.objects.filter(ativo=True, vinculos__usuario=self)
            .order_by("sigla")
            .distinct()
        )

    def papel_em(self, hospital):
        """Papel do usuário no hospital informado, ou None se não vinculado."""
        if hospital is None:
            return None
        vinculo = self.vinculos.filter(hospital=hospital).first()
        return vinculo.papel if vinculo else None

    def is_carregador_em(self, hospital):
        return self.papel_em(hospital) == Vinculo.ROLE_CARREGADOR


class Vinculo(models.Model):
    """Vínculo usuário–hospital com um papel por hospital."""

    ROLE_CONSULTOR = "consultor"
    ROLE_CARREGADOR = "carregador"
    ROLES = [
        (ROLE_CONSULTOR, "Consultor"),
        (ROLE_CARREGADOR, "Carregador"),
    ]

    usuario = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="vinculos",
        verbose_name="Usuário",
    )
    hospital = models.ForeignKey(
        Hospital,
        on_delete=models.CASCADE,
        related_name="vinculos",
        verbose_name="Hospital",
    )
    papel = models.CharField(
        max_length=20,
        choices=ROLES,
        default=ROLE_CONSULTOR,
        verbose_name="Papel",
    )

    class Meta:
        verbose_name = "Vínculo"
        verbose_name_plural = "Vínculos"
        unique_together = [("usuario", "hospital")]
        ordering = ["usuario__username", "hospital__sigla"]

    def __str__(self):
        return f"{self.usuario} @ {self.hospital.sigla} ({self.get_papel_display()})"


class Paciente(models.Model):
    hospital = models.ForeignKey(
        Hospital,
        on_delete=models.CASCADE,
        related_name="pacientes",
        verbose_name="Hospital",
    )
    prontuario = models.CharField(max_length=50, verbose_name="Prontuário")
    nome = models.TextField(blank=True, verbose_name="Nome")

    class Meta:
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"
        unique_together = [("hospital", "prontuario")]
        ordering = ["nome"]

    def __str__(self):
        return f"{self.prontuario} — {self.nome}"


class Cultura(models.Model):
    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.CASCADE,
        related_name="culturas",
        verbose_name="Paciente",
    )
    os = models.CharField(max_length=50, verbose_name="OS")
    unidade = models.CharField(max_length=100, blank=True, verbose_name="Unidade")
    dt_coleta = models.DateField(null=True, blank=True, verbose_name="Data de Coleta")
    dt_assinatura = models.DateField(null=True, blank=True, verbose_name="Data de Assinatura")
    procedimento = models.TextField(blank=True, verbose_name="Procedimento")
    microrganismo = models.TextField(blank=True, verbose_name="Microrganismo")
    obs = models.TextField(blank=True, verbose_name="Observações")
    trat_respir = models.TextField(blank=True, verbose_name="Tratamento Respiratório")

    class Meta:
        verbose_name = "Cultura"
        verbose_name_plural = "Culturas"
        unique_together = [("paciente", "os", "procedimento", "dt_assinatura")]
        ordering = ["-dt_coleta"]

    def __str__(self):
        return f"{self.procedimento} — {self.dt_coleta}"


SENSIBILIDADE_CHOICES = [
    ("S", "Sensível"),
    ("I", "Intermediário"),
    ("R", "Resistente"),
]


class Antibiograma(models.Model):
    cultura = models.ForeignKey(
        Cultura,
        on_delete=models.CASCADE,
        related_name="antibiograma",
        verbose_name="Cultura",
    )
    antibiotico = models.CharField(max_length=150, verbose_name="Antibiótico")
    sensibilidade = models.CharField(
        max_length=1,
        choices=SENSIBILIDADE_CHOICES,
        verbose_name="Sensibilidade",
    )

    class Meta:
        verbose_name = "Antibiograma"
        verbose_name_plural = "Antibiogramas"

    def __str__(self):
        return f"{self.antibiotico}: {self.sensibilidade}"


class ControleAtbRaw(models.Model):
    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.CASCADE,
        related_name="controle_atb",
        verbose_name="Paciente",
    )
    acomodacao = models.CharField(max_length=100, blank=True, verbose_name="Acomodação")
    medicamento = models.CharField(max_length=500, verbose_name="Medicamento")
    dt_inicio = models.DateField(null=True, blank=True, verbose_name="Data de Início")
    dias_solic = models.IntegerField(default=0, verbose_name="Dias Solicitados")
    dias_ccih = models.IntegerField(default=0, verbose_name="Dias CCIH")
    dias_em_uso = models.IntegerField(default=0, verbose_name="Dias em Uso")
    medico = models.CharField(max_length=150, blank=True, verbose_name="Médico")
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Controle ATB"
        verbose_name_plural = "Controles ATB"
        unique_together = [("paciente", "medicamento", "dt_inicio")]
        ordering = ["medicamento", "dt_inicio"]

    def __str__(self):
        return f"{self.medicamento} — {self.dt_inicio}"


class Internamento(models.Model):
    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.CASCADE,
        related_name="internamentos",
        verbose_name="Paciente",
    )
    dt_entrada = models.DateField(verbose_name="Data de Entrada")
    dt_alta = models.DateField(null=True, blank=True, verbose_name="Data de Alta")
    dias = models.IntegerField(default=0, verbose_name="Dias")
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Internamento"
        verbose_name_plural = "Internamentos"
        unique_together = [("paciente", "dt_entrada")]
        ordering = ["dt_entrada"]

    def __str__(self):
        return f"{self.dt_entrada} — {self.dt_alta} ({self.dias}d)"


class Importacao(models.Model):
    hospital = models.ForeignKey(
        Hospital,
        on_delete=models.CASCADE,
        related_name="importacoes",
        verbose_name="Hospital",
    )
    usuario = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Usuário",
    )
    arquivo = models.CharField(max_length=255, verbose_name="Arquivo")
    tipo = models.CharField(max_length=50, verbose_name="Tipo")
    importado_em = models.DateTimeField(auto_now_add=True, verbose_name="Importado em")
    registros = models.IntegerField(default=0, verbose_name="Registros")

    class Meta:
        verbose_name = "Importação"
        verbose_name_plural = "Importações"
        ordering = ["-importado_em"]

    def __str__(self):
        return f"{self.tipo} — {self.arquivo} ({self.importado_em:%d/%m/%Y %H:%M})"

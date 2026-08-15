# Relatório do consultor (management command via SSH) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar `manage.py relatorio_consultor --hospital=<SIGLA> [--prontuarios=<lista>]` que imprime no stdout um relatório Markdown com a cobertura de dados importados do hospital (culturas e prescrições de ATB) e, para cada prontuário informado, suas culturas/antibiograma e os intervalos de uso de antibiótico.

**Architecture:** Um único arquivo `core/management/commands/relatorio_consultor.py` (comando `BaseCommand` + funções privadas de formatação Markdown). Nenhuma lógica de negócio nova: tudo vem de `core.services.patient_service` (`get_cobertura_culturas`, `get_cobertura_atb`, `get_culturas`, `get_antibiograma`, `get_periodos_atb`), as mesmas funções já usadas pelo relatório `/cobertura/` e pela API `/api/v1/paciente/`.

**Tech Stack:** Django management command (`django.core.management.base.BaseCommand`/`CommandError`), sem dependências novas.

## Global Constraints

- Spec de referência: `docs/superpowers/specs/2026-08-15-relatorio-consultor-ssh-design.md` — qualquer dúvida de comportamento, essa é a fonte da verdade.
- Python do projeto: `.venv\Scripts\python.exe manage.py ...` (nunca `python`/`py` direto — ver `CLAUDE.md`).
- **ASCII-only nas strings literais escritas em `self.stdout.write`** (regra global do usuário: o terminal Windows usa `cp1252` e caracteres como `— – ═ → “ ”` quebram em runtime). Usar hífen `-` simples, nunca travessão `—`. Docstrings/comentários podem ter acentos normalmente.
- Reaproveitar `core/services/patient_service.py` — não duplicar cálculo de cobertura, culturas, antibiograma ou períodos de ATB.
- Seguir o padrão de lookup de prontuário com fallback de zeros à esquerda já usado em `core/views/api_views.py::paciente` (linhas 176-182), para consistência de comportamento com a API existente.
- Testes via `django.core.management.call_command` + `io.StringIO`, no padrão de `core/tests_api.py` (mesma classe de fixtures: `Hospital`, `Paciente`, `Cultura`, `Antibiograma`, `ControleAtbRaw`).

---

### Task 1: Comando base — resolução de hospital + seção de cobertura

**Files:**
- Create: `core/management/commands/relatorio_consultor.py`
- Test: `core/tests_relatorio_consultor.py`

**Interfaces:**
- Consumes: `core.services.patient_service.get_cobertura_culturas(hospital) -> list[tuple[date, date]]`, `get_cobertura_atb(hospital) -> list[tuple[date, date]]` (já existentes, ver `core/services/patient_service.py:199-218`); `core.models.Hospital` (`sigla`, `nome`, `ativo`).
- Produces: `Command` (classe do management command, nome de módulo `relatorio_consultor`) com `add_arguments` definindo `--hospital` (obrigatório) e `--prontuarios` (opcional, default `""`, string separada por vírgula) — consumido pela Task 2. Função `_fmt_data(d) -> str` e `_fmt_cobertura(intervalos) -> str` — reaproveitadas pela Task 2.

- [ ] **Step 1: Escrever os testes que falham**

```python
# core/tests_relatorio_consultor.py
"""Testes do comando relatorio_consultor.

Rodar::

    .venv\\Scripts\\python.exe manage.py test core.tests_relatorio_consultor
"""

import io

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.models import Hospital, Paciente, Cultura, Antibiograma, ControleAtbRaw
from datetime import date


class RelatorioConsultorTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hospital = Hospital.objects.create(nome="Hospital Teste", sigla="HT")

        cultura = Cultura.objects.create(
            paciente=Paciente.objects.create(
                hospital=cls.hospital, prontuario="12345", nome="PACIENTE TESTE"
            ),
            os="OS-1",
            dt_coleta=date(2026, 7, 30),
            procedimento="HEMOCULTURA",
            microrganismo="Klebsiella pneumoniae",
        )
        cls.paciente = cultura.paciente
        Antibiograma.objects.create(cultura=cultura, antibiotico="MEROPENEM", sensibilidade="R")

        ControleAtbRaw.objects.create(
            paciente=cls.paciente,
            medicamento="MEROPENEM 1g PO LIOF INJ",
            dt_inicio=date(2026, 7, 28),
            dias_em_uso=5,
        )

    def _run(self, **options):
        out = io.StringIO()
        call_command("relatorio_consultor", stdout=out, **options)
        return out.getvalue()

    def test_cobertura_sem_prontuarios(self):
        texto = self._run(hospital="HT")
        self.assertIn("# Relatorio - Hospital Teste (HT)", texto)
        self.assertIn("## Cobertura de dados importados", texto)
        self.assertIn("### Culturas (microbiologia)", texto)
        self.assertIn("2026-07-30 a 2026-07-30", texto)
        self.assertIn("### Prescricoes de antibiotico", texto)
        self.assertIn("2026-07-28 a 2026-07-28", texto)
        self.assertNotIn("## Paciente", texto)

    def test_hospital_invalido_leva_commanderror(self):
        with self.assertRaises(CommandError):
            self._run(hospital="XX")

    def test_hospital_inativo_leva_commanderror(self):
        Hospital.objects.create(nome="Inativo", sigla="IN", ativo=False)
        with self.assertRaises(CommandError):
            self._run(hospital="IN")
```

- [ ] **Step 2: Rodar os testes e confirmar que falham (comando não existe ainda)**

Run: `.venv\Scripts\python.exe manage.py test core.tests_relatorio_consultor -v 2`
Expected: `ModuleNotFoundError` ou `CommandError: Unknown command: 'relatorio_consultor'`

- [ ] **Step 3: Implementar o comando (versão base, sem seção de paciente)**

```python
# core/management/commands/relatorio_consultor.py
"""Relatorio Markdown para o consultor externo, invocado por SSH.

Ver docs/superpowers/specs/2026-08-15-relatorio-consultor-ssh-design.md.
Nenhuma logica de negocio nova: reusa core.services.patient_service, as
mesmas funcoes que ja alimentam o relatorio /cobertura/ e a API /api/v1/.
"""

from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from core.models import Hospital
from core.services import patient_service as svc


def _fmt_data(d):
    return d.strftime("%Y-%m-%d") if d else "-"


def _fmt_cobertura(intervalos):
    if not intervalos:
        return "- Nenhum dado importado.\n"
    linhas = [
        "- %s a %s" % (_fmt_data(ini), _fmt_data(fim)) for ini, fim in intervalos
    ]
    return "\n".join(linhas) + "\n"


class Command(BaseCommand):
    help = "Gera relatorio Markdown de cobertura + culturas/ATB para o consultor, via SSH."

    def add_arguments(self, parser):
        parser.add_argument("--hospital", required=True, help="Sigla do hospital")
        parser.add_argument(
            "--prontuarios",
            default="",
            help="Lista de prontuarios separados por virgula (opcional)",
        )

    def handle(self, *args, **options):
        sigla = options["hospital"].strip()
        hospital = Hospital.objects.filter(sigla__iexact=sigla, ativo=True).first()
        if hospital is None:
            raise CommandError(
                "Hospital com sigla '%s' nao encontrado ou inativo." % sigla
            )

        partes = [
            "# Relatorio - %s (%s)" % (hospital.nome, hospital.sigla),
            "Gerado em: %s\n" % datetime.now().strftime("%Y-%m-%d %H:%M"),
            "## Cobertura de dados importados",
            "### Culturas (microbiologia)",
            _fmt_cobertura(svc.get_cobertura_culturas(hospital)),
            "### Prescricoes de antibiotico",
            _fmt_cobertura(svc.get_cobertura_atb(hospital)),
        ]

        self.stdout.write("\n".join(partes))
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `.venv\Scripts\python.exe manage.py test core.tests_relatorio_consultor -v 2`
Expected: `OK` (3 testes passando)

- [ ] **Step 5: Commit**

```bash
git add core/management/commands/relatorio_consultor.py core/tests_relatorio_consultor.py
git commit -m "feat: comando relatorio_consultor (base + cobertura)"
```

---

### Task 2: Seção por paciente — culturas, antibiograma, períodos de ATB e avisos

**Files:**
- Modify: `core/management/commands/relatorio_consultor.py`
- Modify: `core/tests_relatorio_consultor.py`

**Interfaces:**
- Consumes: `_fmt_data(d)` e `Command.add_arguments` da Task 1 (não mudam de assinatura); `svc.get_culturas(paciente)`, `svc.get_antibiograma(cultura)`, `svc.get_periodos_atb(paciente)` (`core/services/patient_service.py:32-46,60-103`); `Hospital.pacientes` (related_name do FK em `Paciente.hospital`, `core/models.py:92-97`).
- Produces: comportamento final do comando — nenhuma outra task depende disso.

- [ ] **Step 1: Escrever os testes que falham (adicionar ao arquivo da Task 1)**

```python
    # adicionar dentro de RelatorioConsultorTestCase, em core/tests_relatorio_consultor.py

    def test_paciente_com_culturas_e_atb(self):
        texto = self._run(hospital="HT", prontuarios="12345")
        self.assertIn("## Paciente 12345 - PACIENTE TESTE", texto)
        self.assertIn("### Culturas", texto)
        self.assertIn("Klebsiella pneumoniae", texto)
        self.assertIn("MEROPENEM: R", texto)
        self.assertIn("### Uso de antibiotico", texto)
        self.assertIn("| MEROPENEM | 2026-07-28 |", texto)
        self.assertNotIn("## Avisos", texto)

    def test_prontuario_inexistente_vira_aviso_sem_abortar(self):
        texto = self._run(hospital="HT", prontuarios="12345,99999")
        self.assertIn("## Paciente 12345 - PACIENTE TESTE", texto)
        self.assertIn("## Avisos", texto)
        self.assertIn("Prontuario 99999 nao encontrado no hospital HT", texto)

    def test_paciente_sem_culturas_nem_atb_mostra_nenhum_registro(self):
        Paciente.objects.create(hospital=self.hospital, prontuario="55555", nome="SEM DADOS")
        texto = self._run(hospital="HT", prontuarios="55555")
        self.assertIn("## Paciente 55555 - SEM DADOS", texto)
        self.assertIn("Nenhum registro.", texto)

    def test_prontuario_com_zeros_a_esquerda(self):
        texto = self._run(hospital="HT", prontuarios="0012345")
        self.assertIn("## Paciente 12345 - PACIENTE TESTE", texto)
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `.venv\Scripts\python.exe manage.py test core.tests_relatorio_consultor -v 2`
Expected: `FAIL` — sem seção `## Paciente`, `--prontuarios` ainda não processa nada.

- [ ] **Step 3: Implementar as funções de formatação de paciente e integrar no `handle`**

```python
# adicionar em core/management/commands/relatorio_consultor.py, apos _fmt_cobertura

def _fmt_culturas(paciente):
    culturas = list(svc.get_culturas(paciente))
    if not culturas:
        return "Nenhum registro.\n"
    linhas = ["| Coleta | Sitio | Microrganismo | Antibiograma |", "|---|---|---|---|"]
    for c in culturas:
        antibiograma = ", ".join(
            "%s: %s" % (a.antibiotico, a.sensibilidade) for a in svc.get_antibiograma(c)
        ) or "-"
        linhas.append(
            "| %s | %s | %s | %s |"
            % (_fmt_data(c.dt_coleta), c.procedimento or "-", c.microrganismo or "-", antibiograma)
        )
    return "\n".join(linhas) + "\n"


def _fmt_atb_periodos(paciente):
    periodos = svc.get_periodos_atb(paciente)
    if not periodos:
        return "Nenhum registro.\n"
    linhas = ["| Medicamento | Inicio | Fim | Dias |", "|---|---|---|---|"]
    for p in periodos:
        linhas.append(
            "| %s | %s | %s | %s |"
            % (p["medicamento"], _fmt_data(p["inicio"]), _fmt_data(p["fim"]), p["total_dias"])
        )
    return "\n".join(linhas) + "\n"


def _resolver_paciente(hospital, prontuario):
    """Mesmo fallback de zeros a esquerda usado em core/views/api_views.py::paciente."""
    prontuario = prontuario.strip()
    pac = hospital.pacientes.filter(prontuario=prontuario).first()
    if pac is None:
        alternativo = prontuario.lstrip("0")
        if alternativo and alternativo != prontuario:
            pac = hospital.pacientes.filter(prontuario=alternativo).first()
    return pac
```

```python
# substituir o metodo handle() da Task 1 por esta versao em
# core/management/commands/relatorio_consultor.py

    def handle(self, *args, **options):
        sigla = options["hospital"].strip()
        hospital = Hospital.objects.filter(sigla__iexact=sigla, ativo=True).first()
        if hospital is None:
            raise CommandError(
                "Hospital com sigla '%s' nao encontrado ou inativo." % sigla
            )

        prontuarios = [p.strip() for p in options["prontuarios"].split(",") if p.strip()]

        partes = [
            "# Relatorio - %s (%s)" % (hospital.nome, hospital.sigla),
            "Gerado em: %s\n" % datetime.now().strftime("%Y-%m-%d %H:%M"),
            "## Cobertura de dados importados",
            "### Culturas (microbiologia)",
            _fmt_cobertura(svc.get_cobertura_culturas(hospital)),
            "### Prescricoes de antibiotico",
            _fmt_cobertura(svc.get_cobertura_atb(hospital)),
        ]

        avisos = []
        for prontuario in prontuarios:
            pac = _resolver_paciente(hospital, prontuario)
            if pac is None:
                avisos.append(
                    "Prontuario %s nao encontrado no hospital %s" % (prontuario, hospital.sigla)
                )
                continue
            partes.append("## Paciente %s - %s" % (pac.prontuario, pac.nome))
            partes.append("### Culturas")
            partes.append(_fmt_culturas(pac))
            partes.append("### Uso de antibiotico")
            partes.append(_fmt_atb_periodos(pac))

        if avisos:
            partes.append("## Avisos")
            partes.append("\n".join("- %s" % a for a in avisos) + "\n")

        self.stdout.write("\n".join(partes))
```

- [ ] **Step 4: Rodar todos os testes do comando e confirmar que passam**

Run: `.venv\Scripts\python.exe manage.py test core.tests_relatorio_consultor -v 2`
Expected: `OK` (7 testes passando)

- [ ] **Step 5: Rodar a suíte completa para garantir que nada quebrou**

Run: `.venv\Scripts\python.exe manage.py test`
Expected: `OK`, sem regressões em `core.tests_api` ou outros testes existentes.

- [ ] **Step 6: Commit**

```bash
git add core/management/commands/relatorio_consultor.py core/tests_relatorio_consultor.py
git commit -m "feat: secao de paciente (culturas, antibiograma, periodos de ATB) no relatorio_consultor"
```

---

## Pós-implementação (não faz parte deste plano)

- Deploy no VPS: `git pull origin master` em `~/ccih` e nada mais — é só um novo management command, sem migration.
- Uso real (documentado no spec, seção "Contrato para a skill"): `ssh gdr@161.35.125.254 "cd ~/ccih && set -a && . ./.env && set +a && ./venv/bin/python manage.py relatorio_consultor --hospital=<SIGLA> [--prontuarios=<lista>]"`.

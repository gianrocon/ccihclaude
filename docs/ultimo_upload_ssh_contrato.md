# Data de último upload (`ultimo_upload_ssh`) — contrato para quem implementa a aplicação cliente

Documento autocontido para quem for consumir esta interface. Não é preciso
ler mais nada do repositório para integrar — a seção final traz o
código-fonte do comando, para quem quiser conferir o comportamento exato
linha a linha.

## Para que serve

Uma consulta rápida e barata: "quando foi a última vez que alguém subiu
planilha de microbiologia/antimicrobiano para este hospital?" — sem
cobertura, sem dados de paciente, sem tabelas. Útil para a aplicação cliente
decidir se vale a pena reenviar uma planilha, ou para checar rapidamente se
uma importação recente (via `importar_microbiologia_ssh` /
`importar_atb_ssh`, ver `docs/importar_ssh_contrato.md`) realmente "pegou",
sem precisar rodar o relatório completo (`relatorio_consultor`, ver
`docs/relatorio_consultor_contrato.md`).

## Como chamar

```bash
ssh gdr@161.35.125.254 "cd ~/ccih && set -a && . ./.env && set +a && ./venv/bin/python manage.py ultimo_upload_ssh --hospital=<SIGLA>"
```

- `<SIGLA>` — sigla do hospital (`Hospital.sigla`, case insensitive, precisa
  estar `ativo=True`), a mesma usada no seletor de hospital da aplicação web.
  **Obrigatório**, único argumento do comando.
- `set -a && . ./.env && set +a` é obrigatório — sem carregar o `.env` de
  produção o comando roda contra o SQLite local do servidor, não o
  PostgreSQL real (mesma pegadinha de qualquer `manage.py` rodado por SSH
  neste projeto).
- Pré-requisito: a chave SSH usada precisa já ter acesso a
  `gdr@161.35.125.254` (a mesma usada para deploy). Sem token nem segredo
  adicional a gerenciar.

## O que a chamada devolve

**Só aparece no terminal (stdout) — não grava nenhum arquivo no servidor.**
Se a aplicação cliente quiser guardar como arquivo, é ela quem redireciona a
saída do próprio `ssh`:

```bash
ssh gdr@161.35.125.254 "..." > ultimo_upload.txt
```

- **stdout, sucesso**: exatamente duas linhas, texto plano (não é Markdown):

  ```
  Microbiologia: <timestamp ou ->
  Antimicrobianos: <timestamp ou ->
  ```

  - Timestamp no formato `YYYY-MM-DD HH:MM` (hora local do servidor, sem
    timezone explícito) — mesmo formato usado em "Data de upload" no
    relatório `relatorio_consultor`.
  - `-` quando o hospital nunca recebeu upload reconhecido daquele tipo.

- **stderr + exit code ≠ 0**: hospital não encontrado ou inativo
  (`CommandError`). Nenhum outro tipo de erro é possível — o comando não lê
  nenhum arquivo, só consulta o banco.

## O que "data de upload" significa aqui

Não confundir com cobertura (que é sobre o conteúdo clínico já importado).
"Data de upload" é quando a última planilha `.xlsx`/`.xls` daquele tipo foi
enviada e **reconhecida** pelo sistema — via upload web em `/importar/` ou
via `importar_microbiologia_ssh`/`importar_atb_ssh`. Atualiza mesmo que a
planilha não traga nenhum registro novo (reenvio sem novidade). Só não
atualiza quando o arquivo não é reconhecido como nenhum dos formatos
esperados. Explicação completa em `docs/relatorio_consultor_contrato.md`
(seção "Data de cobertura × Data de upload").

## Exemplo real de saída (dados fictícios)

```
$ ssh gdr@161.35.125.254 "cd ~/ccih && set -a && . ./.env && set +a && ./venv/bin/python manage.py ultimo_upload_ssh --hospital=HPEL"
Microbiologia: 2026-08-23 20:55
Antimicrobianos: 2026-08-23 20:55
```

Hospital sem nenhum upload ainda:

```
Microbiologia: -
Antimicrobianos: -
```

## Código-fonte do comando

`core/management/commands/ultimo_upload_ssh.py` — sem lógica de negócio
própria, só chama `get_ultima_importacao` (a mesma função que alimenta a
tela `/cobertura/` e o `relatorio_consultor`):

```python
"""Devolve so a data do ultimo upload de planilha (microbiologia e controle
ATB) de um hospital, via SSH - sem cobertura, sem dados de paciente.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from core.models import Hospital
from core.services import patient_service as svc


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "-"


class Command(BaseCommand):
    help = "Mostra a data do ultimo upload de microbiologia e de controle ATB para um hospital."

    def add_arguments(self, parser):
        parser.add_argument("--hospital", required=True, help="Sigla do hospital")

    def handle(self, *args, **options):
        sigla = options["hospital"].strip()
        hospital = Hospital.objects.filter(sigla__iexact=sigla, ativo=True).first()
        if hospital is None:
            raise CommandError("Hospital com sigla '%s' nao encontrado ou inativo." % sigla)

        self.stdout.write(
            "Microbiologia: %s" % _fmt(svc.get_ultima_importacao(hospital, "microbiologia"))
        )
        self.stdout.write(
            "Antimicrobianos: %s" % _fmt(svc.get_ultima_importacao(hospital, "controle_atb"))
        )
```

`get_ultima_importacao` (em `core/services/patient_service.py`) só lê
`Importacao.objects.filter(hospital=hospital, tipo=tipo).order_by
("-importado_em").first()` — nenhuma consulta pesada, nenhuma leitura de
arquivo.

## Testes de referência

`core/tests_ultimo_upload_ssh.py` cobre: hospital sem upload (`-` nas duas
linhas), hospital com upload (timestamp em cada linha), saída não contém
cobertura nem seção de paciente, hospital inválido e hospital inativo.

## Fora de escopo deste documento

- Implementação do lado cliente (script/skill que roda o SSH e, se quiser,
  salva a saída em arquivo) — cada aplicação consumidora resolve isso à sua
  maneira.
- Cobertura de dados clínicos e relatório por paciente — ver
  `docs/relatorio_consultor_contrato.md`.
- Upload de planilha via SSH — ver `docs/importar_ssh_contrato.md`.

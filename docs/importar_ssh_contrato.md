# Importação de planilhas via SSH — contrato para quem implementa a aplicação cliente

Documento autocontido para quem for implementar a aplicação/skill que sobe
planilhas Excel para o CCIH sem passar pela página web `/importar/`. Não é
preciso ler mais nada do repositório para integrar — a seção final traz o
código-fonte dos dois comandos, para quem quiser conferir o comportamento
exato linha a linha.

## O que existe

Dois management commands Django, um por tipo de planilha, invocados por SSH
no mesmo canal já usado para deploy (chave SSH de `gdr@161.35.125.254`, ver
`CLAUDE.md`). Cada um reproduz **exatamente** o que acontece quando um
usuário `carregador` sobe o arquivo pela página `/importar/`:

| Comando | Tipo de planilha | Extensão exigida |
|---|---|---|
| `importar_microbiologia_ssh` | Culturas com antibiograma | `.xlsx` |
| `importar_atb_ssh` | Prescrições de antimicrobiano | `.xls` |

Não existe um terceiro comando para "passagens/internamentos" — só
microbiologia e antimicrobianos têm interface SSH hoje.

## Como chamar

O arquivo precisa já estar em algum caminho acessível no servidor antes de
rodar o comando (a aplicação cliente é responsável por colocá-lo lá, por
exemplo via `scp`):

```bash
scp caminho/local/planilha.xlsx gdr@161.35.125.254:/tmp/micro.xlsx

ssh gdr@161.35.125.254 "cd ~/ccih && set -a && . ./.env && set +a && ./venv/bin/python manage.py importar_microbiologia_ssh --hospital=<SIGLA> --arquivo=/tmp/micro.xlsx [--usuario=<username>]"
```

```bash
scp caminho/local/controle.xls gdr@161.35.125.254:/tmp/atb.xls

ssh gdr@161.35.125.254 "cd ~/ccih && set -a && . ./.env && set +a && ./venv/bin/python manage.py importar_atb_ssh --hospital=<SIGLA> --arquivo=/tmp/atb.xls [--usuario=<username>]"
```

### Argumentos

- `--hospital` (obrigatório): sigla do hospital (`Hospital.sigla`, case
  insensitive, precisa estar `ativo=True`) — a mesma usada no seletor de
  hospital da aplicação web.
- `--arquivo` (obrigatório): caminho absoluto do arquivo **já presente no
  servidor**. O comando não faz upload/transferência — isso é
  responsabilidade de quem chama (ex.: `scp` antes do `ssh`).
- `--usuario` (opcional): `username` de um `CustomUser` existente, gravado em
  `Importacao.usuario` para auditoria (mesmo campo que a página web preenche
  com `request.user`). Se omitido, fica `None` — mesmo efeito de uma
  importação sem usuário identificado. Se o username não existir, o comando
  falha (`CommandError`) em vez de importar sem avisar.

### `set -a && . ./.env && set +a` é obrigatório

Sem carregar o `.env` de produção, o comando roda contra o SQLite local do
servidor, não o PostgreSQL real — mesma pegadinha de qualquer `manage.py`
rodado por SSH neste projeto (documentada no `CLAUDE.md`).

## Contrato de saída

- **Sucesso**: stdout com uma linha `<Tipo>: <N> registro(s) importado(s)
  para <SIGLA>.` e exit code 0. `N` pode ser `0` (planilha reenviada sem
  novidade) — isso **não é erro**.
- **Erro**: stderr + exit code ≠ 0 (`CommandError`). Tratar exit code ≠ 0
  como falha e reportar o `stderr` ao usuário, sem tentar seguir o fluxo.
  Casos de erro:
  - Hospital não encontrado ou inativo.
  - Arquivo não encontrado no caminho informado.
  - Extensão errada (`importar_microbiologia_ssh` exige `.xlsx`,
    `importar_atb_ssh` exige `.xls`) — checado **antes** de tentar abrir o
    arquivo.
  - `--usuario` informado mas o `username` não existe.
  - **Arquivo do tipo errado**: o comando detecta o conteúdo da planilha (a
    mesma heurística usada no upload web — procura a palavra
    "microbiologia" ou "antimicrobiano" nas primeiras linhas) e recusa se não
    bater com o tipo esperado pelo comando. Ex.: rodar
    `importar_microbiologia_ssh` com uma planilha de controle de ATB falha
    em vez de importar como outra coisa.
  - Arquivo do tipo certo mas malformado (ex.: cabeçalho de colunas não
    encontrado) — mesmo erro que apareceria no upload web.

## Efeito colateral esperado (igual ao upload web)

Cada importação bem-sucedida:

1. Insere/atualiza os registros clínicos (`Cultura`+`Antibiograma` para
   microbiologia; `ControleAtbRaw` para ATB) — isso é o que move a **Data de
   cobertura** exibida em `/cobertura/` e no relatório SSH
   (`relatorio_consultor`, ver `docs/relatorio_consultor_contrato.md`).
2. Grava uma linha em `Importacao` (`hospital`, `tipo`, `registros`,
   `importado_em`) **mesmo que nenhum registro novo tenha sido inserido**
   (planilha repetida) — isso é o que move a **Data de upload**. Só não
   grava quando o arquivo é recusado por tipo errado ou malformado (ver
   erros acima).

Ou seja: depois de uma chamada bem-sucedida, tanto `/cobertura/` quanto
`relatorio_consultor --hospital=<SIGLA>` já refletem o novo upload, sem
nenhum passo adicional.

## Fluxo de verificação sugerido para a aplicação cliente

Depois de importar, para confirmar que "pegou":

```bash
ssh gdr@161.35.125.254 "cd ~/ccih && set -a && . ./.env && set +a && ./venv/bin/python manage.py relatorio_consultor --hospital=<SIGLA>"
```

E conferir a linha `Data de upload:` da seção correspondente
(`### Microbiologia` ou `### Antimicrobianos`) — deve bater com o horário em
que o comando de importação rodou (ver
`docs/relatorio_consultor_contrato.md` para a anatomia completa desse
relatório).

## Código-fonte dos comandos

### `core/management/commands/importar_microbiologia_ssh.py`

```python
"""Importa planilha de microbiologia via SSH, mesmo fluxo do upload web em
/importar/ (core/views/import_views.py::importar) - inclusive atualizacao de
cobertura e da "Data de upload" (ver core/services/patient_service.py::
get_ultima_importacao), sem precisar de sessao/navegador.
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.models import CustomUser, Hospital
from core.services import importer_service


class Command(BaseCommand):
    help = "Importa planilha de microbiologia (.xlsx) via SSH, igual ao upload pela pagina /importar/."

    def add_arguments(self, parser):
        parser.add_argument("--hospital", required=True, help="Sigla do hospital")
        parser.add_argument("--arquivo", required=True, help="Caminho do .xlsx no servidor")
        parser.add_argument(
            "--usuario", default="",
            help="Username a registrar em Importacao.usuario (opcional)",
        )

    def handle(self, *args, **options):
        sigla = options["hospital"].strip()
        hospital = Hospital.objects.filter(sigla__iexact=sigla, ativo=True).first()
        if hospital is None:
            raise CommandError("Hospital com sigla '%s' nao encontrado ou inativo." % sigla)

        path = Path(options["arquivo"])
        if not path.is_file():
            raise CommandError("Arquivo nao encontrado: %s" % path)
        if path.suffix.lower() != ".xlsx":
            raise CommandError("Microbiologia exige .xlsx (recebido: %s)" % path.suffix)

        usuario = None
        username = options["usuario"].strip()
        if username:
            usuario = CustomUser.objects.filter(username=username).first()
            if usuario is None:
                raise CommandError("Usuario '%s' nao encontrado." % username)

        try:
            n = importer_service.importar_com_validacao(path, hospital, usuario, "microbiologia")
        except ValueError as exc:
            raise CommandError(str(exc))

        self.stdout.write(self.style.SUCCESS(
            "Microbiologia: %d registro(s) importado(s) para %s." % (n, hospital.sigla)
        ))
```

### `core/management/commands/importar_atb_ssh.py`

```python
"""Importa planilha de controle de antimicrobianos via SSH, mesmo fluxo do
upload web em /importar/ (core/views/import_views.py::importar) - inclusive
atualizacao de cobertura e da "Data de upload" (ver
core/services/patient_service.py::get_ultima_importacao), sem precisar de
sessao/navegador.
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.models import CustomUser, Hospital
from core.services import importer_service


class Command(BaseCommand):
    help = "Importa planilha de controle de antimicrobianos (.xls) via SSH, igual ao upload pela pagina /importar/."

    def add_arguments(self, parser):
        parser.add_argument("--hospital", required=True, help="Sigla do hospital")
        parser.add_argument("--arquivo", required=True, help="Caminho do .xls no servidor")
        parser.add_argument(
            "--usuario", default="",
            help="Username a registrar em Importacao.usuario (opcional)",
        )

    def handle(self, *args, **options):
        sigla = options["hospital"].strip()
        hospital = Hospital.objects.filter(sigla__iexact=sigla, ativo=True).first()
        if hospital is None:
            raise CommandError("Hospital com sigla '%s' nao encontrado ou inativo." % sigla)

        path = Path(options["arquivo"])
        if not path.is_file():
            raise CommandError("Arquivo nao encontrado: %s" % path)
        if path.suffix.lower() != ".xls":
            raise CommandError("Controle ATB exige .xls (recebido: %s)" % path.suffix)

        usuario = None
        username = options["usuario"].strip()
        if username:
            usuario = CustomUser.objects.filter(username=username).first()
            if usuario is None:
                raise CommandError("Usuario '%s' nao encontrado." % username)

        try:
            n = importer_service.importar_com_validacao(path, hospital, usuario, "controle_atb")
        except ValueError as exc:
            raise CommandError(str(exc))

        self.stdout.write(self.style.SUCCESS(
            "Controle ATB: %d registro(s) importado(s) para %s." % (n, hospital.sigla)
        ))
```

### `importar_com_validacao` — a checagem de tipo compartilhada pelos dois comandos

Vive em `core/services/importer_service.py`, junto das funções que já faziam
o parsing (`importar_microbiologia`, `importar_controle_atb`,
`_detect_type`):

```python
def importar_com_validacao(path, hospital, usuario, tipo_esperado: str) -> int:
    """Recusa o arquivo se o tipo detectado nao bater com tipo_esperado, em vez
    de importa-lo silenciosamente como outra coisa. Usado pelos comandos SSH
    dedicados (importar_microbiologia_ssh / importar_atb_ssh), que sao
    especificos por tipo e nao devem aceitar o arquivo errado."""
    path = Path(path)
    tipo = _detect_type(path)
    if tipo != tipo_esperado:
        raise ValueError(
            "Arquivo não reconhecido como '%s' (detectado: '%s')." % (tipo_esperado, tipo)
        )
    if tipo_esperado == "microbiologia":
        return importar_microbiologia(path, hospital, usuario)
    return importar_controle_atb(path, hospital, usuario)
```

## Testes de referência

`core/tests_importar_ssh.py` cobre este contrato: importação bem-sucedida com
registro de `Importacao.usuario`, arquivo do tipo errado recusado, extensão
errada recusada, arquivo inexistente, hospital inválido, usuário inexistente,
e upload repetido sem registro novo ainda atualizando a data de upload. O
comando de ATB não tem planilha `.xls` real gerada no teste (o projeto não
tem biblioteca de escrita de `.xls` instalada — só leitura via `xlrd`); o
caminho feliz desse comando é validado com mock de
`importar_com_validacao`, e as validações de argumento (hospital/extensão)
rodam sem mock.

## Fora de escopo deste documento

- Implementação do lado cliente (script/skill que copia o arquivo para o
  servidor e roda o SSH) — cada aplicação consumidora resolve isso à sua
  maneira.
- Importação de planilha de "passagens/internamentos" via SSH — não existe
  hoje.
- Mudanças na API HTTP `/api/v1/` (token Bearer) — canal separado, não
  documentado aqui.

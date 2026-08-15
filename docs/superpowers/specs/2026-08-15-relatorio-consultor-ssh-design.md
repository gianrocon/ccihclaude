# Relatório do consultor via SSH — design

## Contexto

Já existe uma API HTTP somente-leitura em `/api/v1/` (Bearer token), usada pelo
consultor de infectologia para consultar um paciente por vez em JSON. Este
design cobre um caso de uso diferente: alguém com acesso SSH (chave
criptografada) ao VPS de produção — como uma skill do Claude rodando no
notebook do usuário — precisa, numa única chamada, passar uma lista de
prontuários + hospital e receber:

1. A cobertura atual de dados importados no hospital, separada em
   microbiologia (culturas) e antibiótico (prescrições) — o mesmo conceito já
   calculado para a tela `/cobertura/` (períodos de datas com dados
   importados, não cruzamento clínico antibiograma × ATB em uso).
2. Para cada prontuário da lista: as culturas (com antibiograma) e a tabela de
   intervalos de uso de antibiótico.

A resposta deve ser rápida de consultar por uma skill (texto/Markdown, não
JSON).

## Decisão de transporte

**Management command Django, invocado via SSH**, em vez de estender a API
HTTP com token. A chave SSH já usada para deploy (ver `CLAUDE.md` — VPS
`gdr@161.35.125.254`) já é o limite de confiança: quem tem acesso SSH ao VPS
já pode rodar `manage.py migrate`, então rodar um comando de leitura pelo
mesmo canal não introduz superfície nova nem exige gerenciar mais um token no
notebook do usuário.

```bash
ssh gdr@161.35.125.254 "cd ~/ccih && set -a && . ./.env && set +a && ./venv/bin/python manage.py relatorio_consultor --hospital=HT --prontuarios=12345,67890" > relatorio.md
```

A integração do lado do cliente (skill do Claude que chama o SSH e salva o
arquivo local) fica fora do escopo deste design — aqui só o comando do lado
do servidor.

## Componente

Um único arquivo novo: `core/management/commands/relatorio_consultor.py`.
Comando + formatação Markdown vivem juntos (sem abstração nova de
serializer — o volume não justifica separar arquivo).

### Argumentos

- `--hospital` (obrigatório): sigla do hospital (`Hospital.sigla`, case
  insensitive, deve estar `ativo=True`).
- `--prontuarios` (opcional): lista separada por vírgula. Se omitido, o
  relatório traz só a seção de cobertura, sem seção de pacientes.

### Reaproveitamento de lógica existente

Nenhuma lógica de negócio nova. O comando só formata em Markdown o que já é
calculado por `core/services/patient_service.py`:

- `get_cobertura_culturas(hospital)` / `get_cobertura_atb(hospital)` — mesmos
  usados por `core/views/report_views.py::cobertura`.
- `get_culturas(paciente)` + `get_antibiograma(cultura)` — mesmos usados pela
  view de detalhe de paciente e pelo endpoint `/api/v1/paciente/`.
- `get_periodos_atb(paciente)` — intervalos fundidos de uso de antibiótico.

### Formato de saída (Markdown, stdout)

```markdown
# Relatório — <Hospital.nome> (<sigla>)
Gerado em: <timestamp local>

## Cobertura de dados importados
### Culturas (microbiologia)
- <intervalo 1>
- <intervalo 2>

### Prescrições de antibiótico
- <intervalo 1>

## Paciente <prontuario> — <nome>
### Culturas
| Coleta | Sítio | Microrganismo | Antibiograma |
|---|---|---|---|
| ... | ... | ... | ANTIBIOTICO: S/I/R, ... |

### Uso de antibiótico
| Medicamento | Início | Fim | Dias |
|---|---|---|---|
| ... | ... | ... | ... |

(repete a seção "Paciente" para cada prontuário encontrado, na ordem informada)

## Avisos
- Prontuário <x> não encontrado no hospital <sigla>
```

- Sem culturas/sem períodos de ATB para um paciente → a subseção aparece com
  uma linha "Nenhum registro." em vez de tabela vazia.
- Sem prontuários informados → a seção "Paciente" inteira é omitida.
- Sem avisos → a seção "Avisos" é omitida.

### Erros

- Hospital não encontrado ou inativo → `CommandError` (mensagem clara, exit
  code ≠ 0). Aborta antes de imprimir qualquer coisa.
- Prontuário individual não encontrado no hospital → **não aborta** o
  comando inteiro. Entra na seção "Avisos" ao final; os demais prontuários
  da lista continuam sendo processados normalmente.

## Testes

Novo arquivo `core/tests_relatorio_consultor.py`, usando
`django.core.management.call_command` + `io.StringIO` para capturar stdout.
Casos:

1. Hospital válido, sem `--prontuarios` → só a seção de cobertura, sem
   seção de pacientes.
2. Hospital válido, prontuário existente com culturas e período de ATB →
   tabelas preenchidas corretamente.
3. Prontuário inexistente na lista → aparece em "Avisos", resto do relatório
   segue normal.
4. Hospital inválido/inativo → `CommandError` é levantado.

## Contrato para a skill (uso pelo cliente)

Seção autocontida para quem for implementar a skill do Claude neste notebook
que consome essa interface — não depende de ler o resto do documento.

### Como chamar

```bash
ssh gdr@161.35.125.254 "cd ~/ccih && set -a && . ./.env && set +a && ./venv/bin/python manage.py relatorio_consultor --hospital=<SIGLA> [--prontuarios=<p1>,<p2>,...]" > relatorio.md
```

- `<SIGLA>`: sigla do hospital (ex.: `HT`), a mesma usada no seletor de
  hospital da aplicação web. Obrigatório.
- `--prontuarios`: opcional. Lista de números de prontuário separados por
  vírgula, sem espaços (ex.: `12345,67890`). Se omitido, o relatório traz só
  a cobertura de dados do hospital, sem seção de pacientes.
- O `set -a && . ./.env && set +a` é obrigatório — sem carregar o `.env` de
  produção o comando cai no SQLite local do servidor em vez do PostgreSQL
  real (mesma pegadinha documentada no `CLAUDE.md` do projeto para qualquer
  `manage.py` rodado por SSH).
- Pré-requisito: a chave SSH usada precisa já ter acesso a `gdr@161.35.125.254`
  (é a mesma usada para deploy). Não há token ou segredo adicional a
  gerenciar — a skill não precisa guardar nenhuma credencial própria além da
  chave SSH já configurada no notebook.

### O que a skill recebe

- **stdout**: Markdown puro (ver "Formato de saída" acima) — pode ser salvo
  direto como `.md` e lido como texto.
- **stderr + exit code ≠ 0**: erro (hospital inválido/inativo, `.env` não
  carregado, SSH falhou etc.). A skill deve tratar exit code ≠ 0 como falha
  e reportar o `stderr` ao usuário em vez de tentar interpretar o stdout.
- Prontuários individuais não encontrados **não** geram erro — aparecem na
  seção `## Avisos` do próprio Markdown. A skill deve ler essa seção para
  saber quais prontuários da lista pedida não retornaram dados.

### Notas para a skill interpretar o conteúdo

- "Cobertura" no relatório é sobre *dados importados* (períodos com culturas
  ou prescrições de ATB no sistema), não é uma afirmação clínica de que um
  antibiótico cobre um microrganismo. Não confundir os dois sentidos ao
  responder o usuário.
- A tabela de antibiograma por cultura já vem com S/I/R por antibiótico —
  qualquer inferência clínica (ex.: "esse ATB cobre esse organismo?") é
  responsabilidade da skill/do modelo, não do relatório.
- Datas no Markdown estão em formato local (`YYYY-MM-DD`), não ISO com
  timezone.

## Fora de escopo

- Skill do Claude / script cliente que chama o SSH e salva o arquivo
  localmente.
- Qualquer cruzamento clínico antibiograma × ATB em uso ("esse antibiótico
  cobre esse microrganismo?") — não existe hoje no código e não foi pedido
  aqui.
- Mudanças na API HTTP `/api/v1/` existente.

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

## Fora de escopo

- Skill do Claude / script cliente que chama o SSH e salva o arquivo
  localmente.
- Qualquer cruzamento clínico antibiograma × ATB em uso ("esse antibiótico
  cobre esse microrganismo?") — não existe hoje no código e não foi pedido
  aqui.
- Mudanças na API HTTP `/api/v1/` existente.

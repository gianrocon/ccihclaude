# Relatório do consultor (`relatorio_consultor`) — contrato para quem consome via SSH

Documento autocontido para a aplicação/skill que vai chamar este comando por
SSH e baixar o relatório. Não é preciso ler mais nada do repositório para
integrar — a seção final também traz o código Django-fonte, para quem quiser
conferir o comportamento exato linha a linha.

## Como chamar

```bash
ssh gdr@161.35.125.254 "cd ~/ccih && set -a && . ./.env && set +a && ./venv/bin/python manage.py relatorio_consultor --hospital=<SIGLA> [--prontuarios=<p1>,<p2>,...]" > relatorio.md
```

- `<SIGLA>` — sigla do hospital (ex.: `HT`), a mesma usada no seletor de
  hospital da aplicação web. **Obrigatório.**
- `--prontuarios` — opcional. Lista de números de prontuário separados por
  vírgula, sem espaços (ex.: `12345,67890`). Se omitido, o relatório traz só
  a cobertura/upload do hospital, sem seção de pacientes.
- `set -a && . ./.env && set +a` é obrigatório — sem carregar o `.env` de
  produção o comando cai no SQLite local do servidor em vez do PostgreSQL
  real.
- Pré-requisito: a chave SSH usada precisa já ter acesso a
  `gdr@161.35.125.254`. Não há token nem segredo adicional — o canal de
  confiança é o mesmo usado para deploy.

## O que a chamada devolve

- **stdout**: Markdown puro — salvar direto como `.md`.
- **stderr + exit code ≠ 0**: erro (hospital inválido/inativo, `.env` não
  carregado, falha de SSH etc.). Tratar exit code ≠ 0 como falha e reportar o
  `stderr`, sem tentar interpretar o stdout.
- Prontuário individual não encontrado **não** é erro — vira uma linha na
  seção `## Avisos` do próprio Markdown, e o comando continua processando o
  resto da lista normalmente.

## Anatomia do relatório

```markdown
# Relatorio - <Hospital.nome> (<sigla>)
Gerado em: <timestamp local, YYYY-MM-DD HH:MM>

## Cobertura de dados importados
### Microbiologia
Data de cobertura:
- <data inicial> a <data final>
- <outro intervalo, se houver gap>

Data de upload: <timestamp do ultimo .xlsx de microbiologia reconhecido>

### Antimicrobianos
Data de cobertura:
- <data inicial> a <data final>

Data de upload: <timestamp do ultimo .xls de antimicrobianos reconhecido>

## Paciente <prontuario> - <nome>
### Culturas
| Coleta | Sitio | Microrganismo | Antibiograma |
|---|---|---|---|
| <data> | <procedimento> | <microrganismo> | ANTIBIOTICO: S/I/R, ... |

### Uso de antibiotico
| Medicamento | Inicio | Fim | Dias |
|---|---|---|---|
| <medicamento> | <data> | <data> | <n> |

(repete a secao "Paciente" para cada prontuario encontrado, na ordem informada)

## Avisos
- Prontuario <x> nao encontrado no hospital <sigla>
```

Seções condicionais:

| Situação | Comportamento |
|---|---|
| Paciente sem culturas | `### Culturas` mostra `Nenhum registro.` em vez de tabela vazia |
| Paciente sem prescrições de ATB | `### Uso de antibiotico` mostra `Nenhum registro.` |
| `--prontuarios` omitido | A seção `## Paciente ...` inteira não aparece |
| Nenhum prontuário deu erro | A seção `## Avisos` não aparece |
| Hospital sem nenhum dado importado ainda | `Data de cobertura:` mostra `- Nenhum dado importado.` |
| Hospital nunca recebeu upload daquele tipo | `Data de upload: -` |

Internamentos **não** entram neste relatório — só microbiologia e
antimicrobianos importam para o consultor.

### Data de cobertura × Data de upload — não são a mesma coisa

- **Data de cobertura**: intervalo de datas *dos dados clínicos já
  importados* (menor/maior `dt_coleta` de cultura, ou `dt_inicio` de
  prescrição de ATB). Reflete o conteúdo do banco, não quando alguém mexeu
  nele.
- **Data de upload**: quando a última planilha `.xlsx`/`.xls` daquele tipo foi
  enviada e **reconhecida** pelo sistema — mesmo que ela não tenha trazido
  nenhum registro novo (planilha reenviada sem novidade ainda atualiza a data
  de upload, não a de cobertura).

Consequência prática para quem lê o relatório: `Data de upload` recente com
`Data de cobertura` "velha" é normal e não indica falha — só significa que a
última planilha enviada não trouxe dado além do que já existia. `Data de
upload` **não avança sozinha** com o tempo; se veio um arquivo inválido ou
não reconhecido como microbiologia/antimicrobiano, a data de upload
permanece a mesma de antes (o comando de importação lança um erro antes de
registrar o upload nesse caso).

### Datas e formato

- Datas de cobertura: `YYYY-MM-DD` (sem hora).
- Data/hora de upload e "Gerado em": `YYYY-MM-DD HH:MM` (hora local do
  servidor, sem timezone explícito).
- "Cobertura" aqui é sobre *dados importados* — não é uma afirmação clínica
  de que um antibiótico cobre um microrganismo. A tabela de antibiograma por
  cultura traz S/I/R por antibiótico; qualquer inferência clínica é
  responsabilidade de quem consome o relatório, não do relatório em si.

## Template HTML equivalente (`/cobertura/` na aplicação web)

O mesmo par "Data de cobertura" / "Data de upload" aparece na tela
`/cobertura/` da aplicação — os cards de Microbiologia e Antibióticos trazem
os intervalos como badges e a data de upload no rodapé do card. Internamentos
aparece só na tela web (não no relatório SSH), sem card de upload porque não
existe rastreio de upload próprio para esse tipo de dado.

```django
{% extends "base.html" %}
{% block title %}Cobertura de Dados — CCIH{% endblock %}

{% block content %}
<div class="row justify-content-center">
  <div class="col-lg-8">
    <h5 class="mb-3 text-primary fw-bold">Cobertura de Dados — {{ request.hospital_atual }}</h5>

    {% if not request.hospital_atual %}
    <div class="alert alert-warning">Seu usuário não está atribuído a nenhum hospital.</div>
    {% else %}

    <div class="row g-3">

      <div class="col-md-4">
        <div class="card shadow-sm h-100">
          <div class="card-header bg-success text-white fw-semibold">🔬 Microbiologia</div>
          <div class="card-body small">
            {% if culturas %}
              {% for inicio, fim in culturas %}
              <div class="badge bg-success-subtle text-success border border-success mb-1 w-100 text-start px-2 py-1">
                {{ inicio|date:"d/m/Y" }} → {{ fim|date:"d/m/Y" }}
              </div>
              {% endfor %}
            {% else %}
              <span class="text-muted">Sem dados.</span>
            {% endif %}
          </div>
          <div class="card-footer small text-muted">
            Último upload:
            {% if upload_micro %}{{ upload_micro|date:"d/m/Y H:i" }}{% else %}—{% endif %}
          </div>
        </div>
      </div>

      <div class="col-md-4">
        <div class="card shadow-sm h-100">
          <div class="card-header bg-primary text-white fw-semibold">💊 Antibióticos</div>
          <div class="card-body small">
            {% if atb %}
              {% for inicio, fim in atb %}
              <div class="badge bg-primary-subtle text-primary border border-primary mb-1 w-100 text-start px-2 py-1">
                {{ inicio|date:"d/m/Y" }} → {{ fim|date:"d/m/Y" }}
              </div>
              {% endfor %}
            {% else %}
              <span class="text-muted">Sem dados.</span>
            {% endif %}
          </div>
          <div class="card-footer small text-muted">
            Último upload:
            {% if upload_atb %}{{ upload_atb|date:"d/m/Y H:i" }}{% else %}—{% endif %}
          </div>
        </div>
      </div>

      <div class="col-md-4">
        <div class="card shadow-sm h-100">
          <div class="card-header bg-info text-white fw-semibold">🏥 Internamentos</div>
          <div class="card-body small">
            {% if internamentos %}
              {% for inicio, fim in internamentos %}
              <div class="badge bg-info-subtle text-info border border-info mb-1 w-100 text-start px-2 py-1">
                {{ inicio|date:"d/m/Y" }} → {{ fim|date:"d/m/Y" }}
              </div>
              {% endfor %}
            {% else %}
              <span class="text-muted">Sem dados.</span>
            {% endif %}
          </div>
        </div>
      </div>

    </div>
    {% endif %}
  </div>
</div>
{% endblock %}
```

## Exemplo real de saída (dados fictícios)

```markdown
# Relatorio - Hospital Demo (DEMO)
Gerado em: 2026-08-23 20:55

## Cobertura de dados importados
### Microbiologia
Data de cobertura:
- 2026-08-10 a 2026-08-15

Data de upload: 2026-08-23 23:55

### Antimicrobianos
Data de cobertura:
- 2026-08-10 a 2026-08-16

Data de upload: 2026-08-23 23:55

## Paciente 12345 - JOAO DA SILVA
### Culturas
| Coleta | Sitio | Microrganismo | Antibiograma |
|---|---|---|---|
| 2026-08-15 | UROCULTURA | Escherichia coli | CIPROFLOXACINO: S |
| 2026-08-10 | HEMOCULTURA | Klebsiella pneumoniae | AMICACINA: S, MEROPENEM: R |

### Uso de antibiotico
| Medicamento | Inicio | Fim | Dias |
|---|---|---|---|
| MEROPENEM | 2026-08-10 | 2026-08-16 | 6 |
```

Nota sobre a tabela "Uso de antibiotico": `get_periodos_atb` funde
prescrições do mesmo medicamento com intervalo ≤ 1 dia entre elas em um único
período — duas prescrições de MEROPENEM iniciadas em datas próximas aparecem
como uma linha só. Para a dose exata de cada prescrição individual, essa
tabela não é a fonte (é a mesma limitação já documentada no endpoint
`/api/v1/paciente/`).

## Testes de referência

`core/tests_relatorio_consultor.py` cobre este contrato: seções presentes com
e sem `--prontuarios`, hospital inválido/inativo, prontuário não encontrado
(vira aviso, não aborta), paciente sem dados, prontuário com zeros à esquerda,
e a separação `Data de cobertura` / `Data de upload` (duas ocorrências de cada
label, uma por tipo).

## Fora de escopo deste documento

- Implementação do lado cliente (script/skill que roda o SSH e salva o
  arquivo) — cada aplicação consumidora resolve isso à sua maneira.
- Qualquer cruzamento clínico antibiograma × ATB em uso.
- Mudanças na API HTTP `/api/v1/` (token Bearer) — canal separado, não
  documentado aqui.

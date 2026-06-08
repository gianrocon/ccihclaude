# CLAUDE.md — CCIH Django

## Python

```
C:\Users\gian\AppData\Local\Python\bin\python.exe
```

Nunca usar `python`, `python3` ou `py` diretamente — apontam para stubs do Microsoft Store.

## Executar o servidor

```powershell
.venv\Scripts\python.exe manage.py runserver
```

## App principal

Toda a lógica vive em `core/`. Não há outros apps Django além de `core`.

### Modelos (`core/models.py`)

- `Hospital` — entidade raiz; todos os dados pertencem a um hospital
- `CustomUser(AbstractUser)` — papéis: `consultor` (leitura) e `carregador` (importação)
- `Paciente` — único por `(hospital, prontuario)`
- `Cultura` — exame microbiológico; único por `(paciente, os, procedimento, dt_assinatura)`
- `Antibiograma` — linhas de sensibilidade (S/I/R) vinculadas a uma `Cultura`
- `ControleAtbRaw` — prescrições de antibiótico; único por `(paciente, medicamento, dt_inicio)`
- `Internamento` — períodos de internação; único por `(paciente, dt_entrada)`
- `Importacao` — log de cada carga de planilha

### Views (`core/views/`)

| Arquivo | Responsabilidade |
|---------|-----------------|
| `patient_views.py` | Busca e detalhe do paciente |
| `import_views.py` | Upload e processamento de planilhas |
| `report_views.py` | Relatório de cobertura |
| `admin_views.py` | Gerenciamento de usuários |

### Services (`core/services/`)

| Arquivo | Responsabilidade |
|---------|-----------------|
| `importer_service.py` | Parseia Excel e persiste registros |
| `patient_service.py` | Queries e lógica de paciente |
| `chart_service.py` | Geração de gráficos matplotlib |

## Banco de dados

SQLite em `db.sqlite3` (não versionar). Para ambientes de produção, trocar para PostgreSQL via `DATABASE_URL`.

## Variáveis de ambiente

Gerenciadas via `python-decouple`. Ver `.env.example`.

## Migrations

```powershell
.venv\Scripts\python.exe manage.py makemigrations
.venv\Scripts\python.exe manage.py migrate
```

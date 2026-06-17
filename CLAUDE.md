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
- `CustomUser(AbstractUser)` — vinculado a vários hospitais via `Vinculo` (M2M `hospitais`)
- `Vinculo` — vínculo usuário–hospital com um papel por hospital: `consultor` (leitura) e `carregador` (importação); único por `(usuario, hospital)`
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
| `hospital_views.py` | Troca do hospital ativo (seletor da navbar) |

#### Hospital ativo

Como um usuário pode pertencer a vários hospitais, `core/middleware.py`
(`HospitalAtualMiddleware`) resolve o hospital ativo a cada request e expõe:

- `request.hospital_atual` — `Hospital` ativo (da sessão) ou `None`
- `request.papel_atual` — papel do usuário **nesse** hospital (`consultor`/`carregador`)
- `request.hospitais_disponiveis` — hospitais ativos a que o usuário tem acesso

As views usam `request.hospital_atual` (nunca `request.user.hospital`, que não existe
mais). O decorator `carregador_required` checa `request.papel_atual`.

### Services (`core/services/`)

| Arquivo | Responsabilidade |
|---------|-----------------|
| `importer_service.py` | Parseia Excel e persiste registros |
| `patient_service.py` | Queries e lógica de paciente |
| `chart_service.py` | Geração de gráficos matplotlib |

## Banco de dados

SQLite em `db.sqlite3` (não versionar). Para ambientes de produção, trocar para PostgreSQL via `DATABASE_URL`.

## Produção (VPS gdr@161.35.125.254)

O projeto vive em `~/ccih` no servidor. O gunicorn (serviço systemd `ccih`, porta 8001)
lê o `DATABASE_URL` do `.env` via `EnvironmentFile`, mas uma sessão SSH comum **não**.

**Comandos `manage.py` no servidor DEVEM carregar o `.env` primeiro**, senão caem no
SQLite local e não tocam o PostgreSQL real:

```bash
cd ~/ccih && set -a && . ./.env && set +a && ./venv/bin/python manage.py <comando>
```

Sem isso, `migrate` aplica no SQLite e o PostgreSQL de produção fica desatualizado
(a migration consta como aplicada, mas só no banco errado).

Deploy de mudanças: commit + push para `origin/master`, depois no servidor
`git pull origin master` e rodar `migrate` com o `.env` carregado.

## Variáveis de ambiente

Gerenciadas via `python-decouple`. Ver `.env.example`.

## Migrations

```powershell
.venv\Scripts\python.exe manage.py makemigrations
.venv\Scripts\python.exe manage.py migrate
```

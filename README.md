# CCIH Django

Sistema web para a **Comissão de Controle de Infecção Hospitalar (CCIH)**, construído com Django 5.

## Funcionalidades

- Busca de pacientes por prontuário ou nome
- Histórico de culturas com antibiograma (S/I/R por antibiótico)
- Controle de antibióticos (ATB) com dias solicitados, liberados e em uso
- Registro de internamentos
- Importação de dados via planilhas Excel (culturas, ATB, internamentos)
- Relatório de cobertura por hospital
- Gerenciamento de usuários com dois papéis: **Consultor** e **Carregador**
- Suporte a múltiplos hospitais

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Framework | Django 5+ |
| Banco de dados | SQLite (dev) |
| Leitura de planilhas | openpyxl, xlrd |
| Gráficos | matplotlib |
| Arquivos estáticos | whitenoise |
| Config por ambiente | python-decouple |

## Configuração local

```bash
# 1. Clonar o repositório
git clone https://github.com/gianrocon/ccihclaude.git
cd ccihclaude

# 2. Criar e ativar ambiente virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/macOS

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env e definir SECRET_KEY

# 5. Aplicar migrações
python manage.py migrate

# 6. Criar superusuário
python manage.py createsuperuser

# 7. Executar servidor de desenvolvimento
python manage.py runserver
```

Acesse em: http://127.0.0.1:8000/

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `SECRET_KEY` | — | Chave secreta do Django (obrigatória) |
| `DEBUG` | `False` | Modo debug |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost` | Hosts permitidos (separados por vírgula) |

## Estrutura

```
ccih_django/
├── ccih_project/       # Configurações do projeto Django
├── core/               # App principal
│   ├── models.py       # Hospital, Paciente, Cultura, Antibiograma, ATB, Internamento
│   ├── services/       # Lógica de negócio (importação, gráficos, pacientes)
│   ├── views/          # Views separadas por domínio
│   └── management/     # Comandos customizados (migrate_sqlite)
├── templates/          # Templates HTML
└── requirements.txt
```

## Papéis de usuário

| Papel | Permissões |
|-------|-----------|
| `consultor` | Busca e visualização de pacientes/relatórios |
| `carregador` | Importação de planilhas e limpeza de banco |

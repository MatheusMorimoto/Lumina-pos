# Sistema Integrado de Gestão Comercial (PDV / ERP)

Backend em FastAPI organizado como monólito modular orientado a domínios. Os módulos
de vendas, crediário e estoque têm contratos, regras de negócio e persistência
separados, mas são publicados por uma única aplicação.

## Requisitos

- Python 3.11+
- Projeto Supabase ou Supabase CLI local
- PostgreSQL 15+ (fornecido pelo Supabase)

## Instalação

No diretório `meu_erp_backend`:

```bash
python -m venv .venv
```

Ative o ambiente no Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Instale as dependências e configure o ambiente:

```bash
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e informe as credenciais reais do Supabase. O
arquivo `.env` local está ignorado pelo Git.

## Banco de dados

Com a Supabase CLI configurada, aplique a migração:

```bash
supabase db reset
```

Alternativamente, execute
`supabase/migrations/20260728_initial_schema.sql` no SQL Editor do projeto.

## Execução

```bash
uvicorn app.main:app --reload
```

- API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

## Testes

```bash
pytest
```

Os testes de serviço usam repositórios falsos e não dependem de conexão com o
Supabase.

## Organização

- `app/core`: configuração, banco e segurança.
- `app/modules`: domínios independentes (`vendas`, `crediario`, `estoque`).
- `app/shared`: exceções e utilitários transversais.
- `supabase/migrations`: evolução versionada do banco.
- `tests`: testes unitários das regras de negócio.

O fluxo de dependência é `router -> service -> repository`. Regras de negócio ficam
nos serviços; detalhes do SDK do Supabase ficam isolados nos repositórios.

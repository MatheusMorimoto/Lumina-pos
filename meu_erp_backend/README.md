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

Na raiz do repositorio, o comando equivalente e:

```powershell
python app.py
```

- API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`
- Banco de dados: `http://127.0.0.1:8000/health/ready`

## Diagnostico temporario

A tela `/teste-conexao` e o endpoint `/api/health/supabase` ficam desabilitados por
padrao. Para uma validacao administrativa temporaria, configure:

```dotenv
ERP_DIAGNOSTIC_ENABLED=true
ERP_DIAGNOSTIC_USERNAME=administrador
ERP_DIAGNOSTIC_PASSWORD=<senha-forte-e-temporaria>
ERP_SUPABASE_EXPECTED_PROJECT_ID=gfqrqlvkqqnhzwbcozzp
```

O acesso usa HTTP Basic, nao inclui segredos no HTML e nao armazena a senha testada.
Depois da validacao, defina `ERP_DIAGNOSTIC_ENABLED=false` e remova as credenciais
temporarias do ambiente.

## Cadastro e senhas

`POST /api/auth/register` aceita tanto o contrato plano legado quanto o contrato
aninhado com `address`, `password_confirmation` e `legal_representative`. A senha e
enviada por HTTPS diretamente ao Supabase Auth e nunca e gravada nas tabelas
publicas. Ela nao e reversivel: no login, o Supabase compara a senha informada com
o hash seguro armazenado.

Quando a confirmacao de e-mail estiver ativa, os dados cadastrais sem a senha ficam
temporariamente nos metadados privados do proprio usuario. No primeiro login apos
a confirmacao, a funcao `complete_registration` cria o cadastro operacional em uma
transacao e remove esses metadados.

- Recuperacao: `POST /api/auth/password/recover`
- Redefinicao com sessao de recuperacao: `POST /api/auth/password/update`
- Login legado por hash local: desabilitado por padrao com
  `ERP_LEGACY_PASSWORD_LOGIN_ENABLED=false`

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

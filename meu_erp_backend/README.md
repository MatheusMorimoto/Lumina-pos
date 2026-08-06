# Lumina POS API

Backend modular em Node.js 24, TypeScript, Fastify e Supabase/PostgreSQL.

## Requisitos

- Node.js 24 LTS;
- npm;
- projeto Supabase ou Supabase CLI local;
- PostgreSQL 15+ fornecido pelo Supabase.

## Instalação

```powershell
npm ci
Copy-Item .env.example .env
npm run dev
```

A API inicia em `http://127.0.0.1:8000` por padrão.

## Comandos

```powershell
npm run dev       # desenvolvimento com watch
npm start         # produção
npm run typecheck # validação TypeScript
npm test          # testes Node
npm run check     # tipos e testes
```

## Organização

- `src/core`: configuração, Supabase e tratamento global de erros;
- `src/modules`: módulos de domínio;
- `src/shared`: funções HTTP compartilhadas;
- `tests-node`: testes unitários e de contrato;
- `supabase/migrations`: schema, funções transacionais, triggers e RLS.

O fluxo recomendado é `routes → services → repositories`. O JWT recebido na
requisição é propagado ao cliente Supabase para manter `auth.uid()` e as políticas
RLS. Operações administrativas usam uma chave separada, nunca exposta ao cliente.

## Endpoints de infraestrutura

- `GET /health`: liveness;
- `GET /health/ready`: readiness com consulta real ao Supabase;
- `GET /api/health/supabase`: diagnóstico administrativo opcional;
- `GET /teste-conexao`: tela temporária de diagnóstico.

Os módulos sob `/api` cobrem autenticação e cadastro PF/PJ, conta e fiscal,
produtos, estoque, promoções, vendas, caixa, clientes, crediário, relatórios,
entregas, conciliação e regras de adquirentes.

## Cadastro e senhas

`POST /api/auth/register` aceita os contratos plano e aninhado. A senha é enviada
diretamente ao Supabase Auth e nunca é salva em tabelas públicas, metadados,
respostas ou logs. Quando a confirmação de e-mail está ativa, somente os dados
cadastrais sem senha ficam temporariamente em `pending_registration`.

- Recuperação: `POST /api/auth/password/recover`;
- alteração com sessão: `POST /api/auth/password/update`;
- redefinição administrativa auditada: `POST /api/auth/admin/users/:userId/password`.

## Diagnóstico temporário

```dotenv
ERP_DIAGNOSTIC_ENABLED=true
ERP_DIAGNOSTIC_USERNAME=administrador
ERP_DIAGNOSTIC_PASSWORD=<senha-forte-e-temporaria>
ERP_SUPABASE_EXPECTED_PROJECT_ID=gfqrqlvkqqnhzwbcozzp
```

Desative e remova as credenciais temporárias após o uso.

## Banco e deploy

As migrations existentes foram preservadas. Para um ambiente local com Supabase:

```powershell
supabase db reset
```

O Render usa `npm ci`, `npm start` e `/health/ready`. Configure as variáveis
`ERP_SUPABASE_URL`, `ERP_SUPABASE_ANON_KEY`, `ERP_SUPABASE_SECRET_KEY` e
`ERP_CORS_ORIGINS` no painel do serviço.

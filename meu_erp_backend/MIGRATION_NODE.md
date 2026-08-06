# Backend Node.js / TypeScript

A migração do FastAPI foi concluída. A aplicação Node preserva os contratos HTTP,
regras de negócio, autenticação, cadastro PF/PJ, configurações fiscais, relatórios,
entregas, conciliação, diagnóstico e integração Supabase do projeto anterior.

## Ambiente

- Node.js 24 LTS
- npm
- Supabase/PostgreSQL existente

```powershell
npm install
Copy-Item .env.example .env
npm run dev
```

Para validar tipos e testes:

```powershell
npm run check
```

## Estrutura

- `src/core`: configuração, Supabase e erros globais;
- `src/modules`: módulos de domínio;
- `src/shared`: integração HTTP compartilhada;
- `tests-node`: testes com o test runner nativo do Node.js.

O `render.yaml` instala com `npm ci` e inicia a aplicação com `npm start`.

## Compatibilidade preservada

- Mesmas migrations Supabase e políticas RLS.
- Mesmas variáveis de ambiente com prefixo `ERP_`.
- Mesmos caminhos sob `/api`, health checks e diagnóstico protegido.
- Finalização de venda por RPC com `Idempotency-Key`.
- Cadastro transacional e senhas armazenadas somente no Supabase Auth.
- Cálculos financeiros executados com precisão decimal.

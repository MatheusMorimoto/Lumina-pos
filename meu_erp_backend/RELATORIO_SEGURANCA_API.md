# Relatorio de seguranca da API - credenciais

## Resultado

A API usa exclusivamente o Supabase Auth para cadastro, login, recuperacao e
redefinicao de senhas. Nenhuma senha ou hash permanece em tabelas publicas.
Administradores podem redefinir credenciais, mas nao consultar a senha atual.

## Fluxos publicados

| Operacao | Endpoint | Protecao |
|---|---|---|
| Cadastro | `POST /api/auth/register` | Supabase Auth e HTTPS |
| Login | `POST /api/auth/login` | Comparacao de hash pelo Supabase Auth |
| Recuperacao | `POST /api/auth/password/recover` | Resposta uniforme contra enumeracao |
| Atualizacao pelo usuario | `POST /api/auth/password/update` | Sessao de recuperacao obrigatoria |
| Redefinicao administrativa | `POST /api/auth/admin/users/{user_id}/password` | `owner/admin`, mesma loja e auditoria |

## Redefinicao administrativa

Requisicao autenticada:

```json
{
  "password": "NovaSenhaSegura123",
  "password_confirmation": "NovaSenhaSegura123"
}
```

Resposta:

```json
{"message": "Senha redefinida com sucesso."}
```

O registro de `audit_logs` contem apenas o administrador, a loja, o usuario alvo,
a acao e o horario. A senha nao e incluida no registro nem na resposta.

## Migracao do Supabase

Aplique as migracoes versionadas:

```powershell
cd meu_erp_backend
supabase link --project-ref gfqrqlvkqqnhzwbcozzp
supabase db push
```

A migracao `20260807_remove_legacy_password_hash.sql` remove definitivamente
`public.users.password_hash`. Antes da producao, confirme que existe backup do
banco e que `ERP_SUPABASE_SECRET_KEY` esta configurada somente no servidor.

## Verificacao

```powershell
cd meu_erp_backend
npm run check
```

Controles cobertos: autorizacao administrativa, isolamento por loja, ausencia da
senha na auditoria/resposta, login via Supabase e tratamento de indisponibilidade.

begin;

-- Credenciais pertencem exclusivamente ao Supabase Auth. Esta limpeza elimina
-- hashes antigos das tabelas publicas e impede qualquer retorno ao login local.
alter table if exists public.users
  drop column if exists password_hash;

comment on table public.users is
  'Perfil operacional. Senhas e hashes existem exclusivamente em auth.users.';

commit;

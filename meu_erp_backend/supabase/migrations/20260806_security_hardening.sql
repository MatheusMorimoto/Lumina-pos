begin;

-- A tabela users e um perfil operacional. Credenciais permanecem somente em
-- auth.users, e usuarios autenticados nao podem alterar loja, funcao ou status.
revoke insert, delete on table public.users from anon, authenticated;
revoke update on table public.users from anon, authenticated;
grant select on table public.users to authenticated;
grant update (name, phone) on table public.users to authenticated;

drop policy if exists users_self_or_admin_update on public.users;
create policy users_self_profile_update
  on public.users
  for update
  to authenticated
  using (id = (select auth.uid()) and active)
  with check (id = (select auth.uid()) and active and is_store_member(store_id));

-- Reinstala o cadastro sem qualquer dependencia de password_hash. Esta coluna
-- pode nao existir: a senha pertence exclusivamente ao Supabase Auth.
create or replace function public.complete_registration(payload jsonb)
returns table("user" jsonb, store jsonb)
language plpgsql security definer set search_path = public as $$
declare
  v_auth_id uuid := auth.uid(); v_store_id uuid; v_type person_type;
  v_name text; v_email text;
begin
  if v_auth_id is null then raise exception 'authentication_required'; end if;
  if exists(select 1 from users where id=v_auth_id) then raise exception 'registration_exists'; end if;
  v_type := (payload->>'person_type')::person_type;
  v_email := lower(coalesce(auth.jwt()->>'email',''));
  if v_type='company' then
    v_name := coalesce(nullif(trim(payload->>'trade_name'),''), payload->>'legal_name');
    if exists(select 1 from company_registrations where cnpj=payload->>'cnpj') then
      raise exception 'document_already_registered';
    end if;
  else
    v_name := coalesce(nullif(trim(payload->>'social_name'),''),payload->>'full_name');
    if exists(select 1 from individual_registrations where cpf=payload->>'cpf') then
      raise exception 'document_already_registered';
    end if;
  end if;
  insert into stores(name,document,person_type) values(
    v_name,case when v_type='company' then payload->>'cnpj' else payload->>'cpf' end,v_type
  ) returning id into v_store_id;
  insert into users(id,store_id,name,email,phone,role,active)
    values(v_auth_id,v_store_id,v_name,v_email,payload->>'phone','owner',true);
  if v_type='company' then
    insert into company_registrations(
      store_id,cnpj,legal_name,trade_name,state_registration,municipal_registration,
      company_size,main_cnae_code,main_cnae_description,registration_status,
      simples_option,mei_option,data_manually_corrected,legal_representative_name,
      legal_representative_cpf,observations
    ) values(
      v_store_id,payload->>'cnpj',payload->>'legal_name',payload->>'trade_name',
      payload->>'state_registration',payload->>'municipal_registration',payload->>'company_size',
      payload->>'main_cnae_code',payload->>'main_cnae_description',payload->>'registration_status',
      (payload->>'simples_option')::boolean,(payload->>'mei_option')::boolean,
      coalesce((payload->>'data_manually_corrected')::boolean,false),
      payload->>'legal_representative_name',payload->>'legal_representative_cpf',
      payload->>'observations'
    );
  else
    insert into individual_registrations(
      store_id,cpf,full_name,birth_date,identity_document,social_name,
      municipal_registration,observations
    ) values(
      v_store_id,payload->>'cpf',payload->>'full_name',
      nullif(payload->>'birth_date','')::date,payload->>'identity_document',
      payload->>'social_name',payload->>'municipal_registration',payload->>'observations'
    );
  end if;
  insert into store_addresses(
    store_id,postal_code,street,address_number,complement,neighborhood,city,state,country
  ) values(
    v_store_id,payload->>'postal_code',payload->>'street',payload->>'address_number',
    payload->>'complement',payload->>'neighborhood',payload->>'city',upper(payload->>'state'),'BR'
  );
  insert into fiscal_profiles(
    store_id,tax_regime,regime_source,data_manually_corrected,manually_reviewed
  ) values(
    v_store_id,coalesce((payload->>'tax_regime')::tax_regime,'nao_informado'),
    payload->>'regime_source',coalesce((payload->>'data_manually_corrected')::boolean,false),
    coalesce((payload->>'manually_reviewed')::boolean,false)
  );
  insert into audit_logs(store_id,user_id,action,entity_type,entity_id,data)
    values(v_store_id,v_auth_id,'registration_completed','user',v_auth_id,
      jsonb_build_object('person_type',v_type));
  return query select
    jsonb_build_object('id',v_auth_id,'email',v_email,'name',v_name,'role','owner'),
    jsonb_build_object('id',v_store_id,'name',v_name,'person_type',v_type);
end $$;

-- As funcoes SECURITY DEFINER nunca devem ser executaveis por anon/public.
revoke all on function public.complete_registration(jsonb) from public, anon;
grant execute on function public.complete_registration(jsonb) to authenticated;
revoke all on function public.review_fiscal_profile(tax_regime, text) from public, anon;
grant execute on function public.review_fiscal_profile(tax_regime, text) to authenticated;
revoke all on function public.finalize_sale(uuid, jsonb, text) from public, anon;
grant execute on function public.finalize_sale(uuid, jsonb, text) to authenticated;
revoke all on function public.pay_receivable(uuid, numeric, text, uuid, timestamptz) from public, anon;
grant execute on function public.pay_receivable(uuid, numeric, text, uuid, timestamptz) to authenticated;

commit;

begin;

-- Complementos do contrato PF/PJ. Senhas permanecem exclusivamente em auth.users.
alter table individual_registrations
  add column if not exists social_name varchar(200),
  add column if not exists municipal_registration varchar(40),
  add column if not exists observations text;

alter table company_registrations
  add column if not exists legal_representative_name varchar(200),
  add column if not exists legal_representative_cpf varchar(11),
  add column if not exists observations text;

alter table company_registrations drop constraint if exists company_legal_representative_cpf_check;
alter table company_registrations add constraint company_legal_representative_cpf_check
  check (legal_representative_cpf is null or legal_representative_cpf ~ '^[0-9]{11}$');

alter table store_addresses
  add column if not exists country char(2) not null default 'BR';

create or replace function complete_registration(payload jsonb)
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
    v_name := nullif(trim(payload->>'trade_name'),'');
    if v_name is null then v_name := payload->>'legal_name'; end if;
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
  insert into users(id,store_id,name,email,password_hash,phone,role,active)
    values(v_auth_id,v_store_id,v_name,v_email,null,payload->>'phone','owner',true);
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

revoke all on function complete_registration(jsonb) from public;
grant execute on function complete_registration(jsonb) to authenticated;

commit;

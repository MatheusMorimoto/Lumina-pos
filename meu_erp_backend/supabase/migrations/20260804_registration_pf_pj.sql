begin;

do $$ begin
  create type person_type as enum ('company', 'individual');
exception when duplicate_object then null; end $$;
do $$ begin
  create type tax_regime as enum (
    'mei', 'simples_nacional', 'lucro_presumido', 'lucro_real',
    'pessoa_fisica', 'nao_informado'
  );
exception when duplicate_object then null; end $$;

alter table stores add column if not exists person_type person_type;
alter table stores add column if not exists active boolean not null default true;
alter table users alter column password_hash drop not null;
alter table users add column if not exists phone varchar(20);
alter table users drop constraint if exists users_role_check;
alter table users add constraint users_role_check
  check (role in ('owner', 'admin', 'manager', 'operator'));

create unique index if not exists ux_users_email_lower on users(lower(email));

create table if not exists company_registrations (
  id uuid primary key default gen_random_uuid(),
  store_id uuid not null unique references stores(id) on delete cascade,
  cnpj varchar(14) not null unique check(cnpj ~ '^[0-9]{14}$'),
  legal_name varchar(200) not null,
  trade_name varchar(200), state_registration varchar(40), municipal_registration varchar(40),
  company_size varchar(80), main_cnae_code varchar(10), main_cnae_description text,
  registration_status varchar(40), simples_option boolean, mei_option boolean,
  data_manually_corrected boolean not null default false,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);

create table if not exists individual_registrations (
  id uuid primary key default gen_random_uuid(),
  store_id uuid not null unique references stores(id) on delete cascade,
  cpf varchar(11) not null unique check(cpf ~ '^[0-9]{11}$'),
  full_name varchar(200) not null, birth_date date, identity_document varchar(80),
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  check(birth_date is null or birth_date <= current_date)
);

create table if not exists store_addresses (
  id uuid primary key default gen_random_uuid(),
  store_id uuid not null references stores(id) on delete cascade,
  postal_code varchar(8) not null check(postal_code ~ '^[0-9]{8}$'),
  street varchar(200) not null, address_number varchar(30) not null,
  complement varchar(100), neighborhood varchar(100) not null,
  city varchar(100) not null, state char(2) not null check(state ~ '^[A-Z]{2}$'),
  is_primary boolean not null default true, created_at timestamptz not null default now()
);
create unique index if not exists ux_store_primary_address
  on store_addresses(store_id) where is_primary;

create table if not exists fiscal_profiles (
  id uuid primary key default gen_random_uuid(),
  store_id uuid not null unique references stores(id) on delete cascade,
  tax_regime tax_regime not null default 'nao_informado', regime_source varchar(80),
  data_manually_corrected boolean not null default false,
  manually_reviewed boolean not null default false,
  reviewed_by uuid references users(id), reviewed_at timestamptz,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);

create table if not exists product_tax_profiles (
  id uuid primary key default gen_random_uuid(),
  product_id uuid not null unique references products(id) on delete cascade,
  store_id uuid not null references stores(id) on delete cascade,
  ncm varchar(8) not null check(ncm ~ '^[0-9]{8}$'), cest varchar(7),
  merchandise_origin varchar(2) not null, cfop varchar(4) not null,
  cst_csosn varchar(4), pis_cst varchar(3), cofins_cst varchar(3),
  icms_rate numeric(7,4) not null default 0, pis_rate numeric(7,4) not null default 0,
  cofins_rate numeric(7,4) not null default 0, ipi_rate numeric(7,4) not null default 0,
  fcp_rate numeric(7,4) not null default 0, destination_state char(2),
  operation_type varchar(20) not null default 'sale', valid_from date not null default current_date,
  valid_until date, manually_reviewed boolean not null default false,
  reviewed_by uuid references users(id), reviewed_at timestamptz,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  check(valid_until is null or valid_until >= valid_from)
);

create or replace function current_store_id() returns uuid
language sql stable security definer set search_path = public as $$
  select store_id from users where id = auth.uid() and active limit 1
$$;

create or replace function is_store_member(p_store_id uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists(select 1 from users where id=auth.uid() and store_id=p_store_id and active)
$$;

create or replace function is_store_admin(p_store_id uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists(select 1 from users where id=auth.uid() and store_id=p_store_id
    and active and role in ('owner','admin'))
$$;

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
    v_name := payload->>'full_name';
    if exists(select 1 from individual_registrations where cpf=payload->>'cpf') then
      raise exception 'document_already_registered';
    end if;
  end if;
  insert into stores(name,document,person_type) values(
    v_name, case when v_type='company' then payload->>'cnpj' else payload->>'cpf' end, v_type
  ) returning id into v_store_id;
  insert into users(id,store_id,name,email,password_hash,phone,role,active)
    values(v_auth_id,v_store_id,v_name,v_email,null,payload->>'phone','owner',true);
  if v_type='company' then
    insert into company_registrations(
      store_id,cnpj,legal_name,trade_name,state_registration,municipal_registration,
      company_size,main_cnae_code,main_cnae_description,registration_status,
      simples_option,mei_option,data_manually_corrected
    ) values(
      v_store_id,payload->>'cnpj',payload->>'legal_name',payload->>'trade_name',
      payload->>'state_registration',payload->>'municipal_registration',payload->>'company_size',
      payload->>'main_cnae_code',payload->>'main_cnae_description',payload->>'registration_status',
      (payload->>'simples_option')::boolean,(payload->>'mei_option')::boolean,
      coalesce((payload->>'data_manually_corrected')::boolean,false)
    );
  else
    insert into individual_registrations(store_id,cpf,full_name,birth_date,identity_document)
      values(v_store_id,payload->>'cpf',payload->>'full_name',
        nullif(payload->>'birth_date','')::date,payload->>'identity_document');
  end if;
  insert into store_addresses(
    store_id,postal_code,street,address_number,complement,neighborhood,city,state
  ) values(
    v_store_id,payload->>'postal_code',payload->>'street',payload->>'address_number',
    payload->>'complement',payload->>'neighborhood',payload->>'city',upper(payload->>'state')
  );
  insert into fiscal_profiles(
    store_id,tax_regime,regime_source,data_manually_corrected,manually_reviewed
  ) values(
    v_store_id,coalesce((payload->>'tax_regime')::tax_regime,'nao_informado'),
    payload->>'regime_source',coalesce((payload->>'data_manually_corrected')::boolean,false),
    coalesce((payload->>'manually_reviewed')::boolean,false)
  );
  return query select
    jsonb_build_object('id',v_auth_id,'email',v_email,'name',v_name,'role','owner'),
    jsonb_build_object('id',v_store_id,'name',v_name,'person_type',v_type);
end $$;

create or replace function review_fiscal_profile(p_tax_regime tax_regime,p_regime_source text)
returns setof fiscal_profiles language plpgsql security definer set search_path=public as $$
declare v_store uuid := current_store_id(); result fiscal_profiles%rowtype;
begin
  if not is_store_admin(v_store) then raise exception 'permission_denied'; end if;
  update fiscal_profiles set tax_regime=p_tax_regime,regime_source=p_regime_source,
    manually_reviewed=true,reviewed_by=auth.uid(),reviewed_at=now(),updated_at=now()
    where store_id=v_store returning * into result;
  insert into audit_logs(store_id,user_id,action,entity_type,entity_id,data)
    values(v_store,auth.uid(),'fiscal_profile_reviewed','fiscal_profile',result.id,
      jsonb_build_object('tax_regime',p_tax_regime,'regime_source',p_regime_source));
  return next result;
end $$;

alter table stores enable row level security;
alter table users enable row level security;
alter table products enable row level security;
alter table company_registrations enable row level security;
alter table individual_registrations enable row level security;
alter table store_addresses enable row level security;
alter table fiscal_profiles enable row level security;
alter table product_tax_profiles enable row level security;
alter table cash_registers enable row level security;
alter table cash_sessions enable row level security;
alter table inventory_batches enable row level security;
alter table stock_movements enable row level security;
alter table promotions enable row level security;
alter table customers enable row level security;
alter table sales enable row level security;
alter table sale_items enable row level security;
alter table financial_institutions enable row level security;
alter table sale_payments enable row level security;
alter table receivables enable row level security;
alter table receivable_payments enable row level security;
alter table couriers enable row level security;
alter table deliveries enable row level security;
alter table delivery_status_history enable row level security;
alter table reconciliation_imports enable row level security;
alter table acquirer_transactions enable row level security;
alter table settlements enable row level security;
alter table reconciliation_matches enable row level security;
alter table reconciliation_issues enable row level security;
alter table acquirer_fee_rules enable row level security;
alter table audit_logs enable row level security;

create policy stores_member_select on stores for select using(is_store_member(id));
create policy stores_admin_update on stores for update using(is_store_admin(id)) with check(is_store_admin(id));
create policy users_same_store_select on users for select using(is_store_member(store_id));
create policy users_self_or_admin_update on users for update
  using(id=auth.uid() or is_store_admin(store_id)) with check(is_store_member(store_id));
create policy products_store_access on products for all
  using(is_store_member(store_id)) with check(is_store_member(store_id));
create policy company_registration_store_access on company_registrations for select using(is_store_member(store_id));
create policy company_registration_admin_update on company_registrations for update using(is_store_admin(store_id));
create policy individual_registration_store_access on individual_registrations for select using(is_store_member(store_id));
create policy individual_registration_admin_update on individual_registrations for update using(is_store_admin(store_id));
create policy addresses_store_select on store_addresses for select using(is_store_member(store_id));
create policy addresses_admin_write on store_addresses for all using(is_store_admin(store_id)) with check(is_store_admin(store_id));
create policy fiscal_store_select on fiscal_profiles for select using(is_store_member(store_id));
create policy product_tax_store_select on product_tax_profiles for select using(is_store_member(store_id));
create policy product_tax_admin_write on product_tax_profiles for all
  using(is_store_admin(store_id)) with check(is_store_admin(store_id));
create policy cash_registers_store_access on cash_registers for all
  using(is_store_member(store_id)) with check(is_store_member(store_id));
create policy cash_sessions_store_access on cash_sessions for all
  using(exists(select 1 from cash_registers r where r.id=cash_register_id and is_store_member(r.store_id)))
  with check(exists(select 1 from cash_registers r where r.id=cash_register_id and is_store_member(r.store_id)));
create policy batches_store_access on inventory_batches for all
  using(exists(select 1 from products p where p.id=product_id and is_store_member(p.store_id)))
  with check(exists(select 1 from products p where p.id=product_id and is_store_member(p.store_id)));
create policy movements_store_access on stock_movements for all
  using(exists(select 1 from products p where p.id=product_id and is_store_member(p.store_id)))
  with check(exists(select 1 from products p where p.id=product_id and is_store_member(p.store_id)));
create policy promotions_store_access on promotions for all
  using(exists(select 1 from products p where p.id=product_id and is_store_member(p.store_id)))
  with check(exists(select 1 from products p where p.id=product_id and is_store_member(p.store_id)));
create policy customers_store_access on customers for all
  using(is_store_member(store_id)) with check(is_store_member(store_id));
create policy sales_store_access on sales for all
  using(is_store_member(store_id)) with check(is_store_member(store_id));
create policy sale_items_store_access on sale_items for all
  using(exists(select 1 from sales s where s.id=sale_id and is_store_member(s.store_id)))
  with check(exists(select 1 from sales s where s.id=sale_id and is_store_member(s.store_id)));
create policy institutions_authenticated_read on financial_institutions for select
  using(auth.uid() is not null);
create policy sale_payments_store_access on sale_payments for all
  using(exists(select 1 from sales s where s.id=sale_id and is_store_member(s.store_id)))
  with check(exists(select 1 from sales s where s.id=sale_id and is_store_member(s.store_id)));
create policy receivables_store_access on receivables for all
  using(exists(select 1 from customers c where c.id=customer_id and is_store_member(c.store_id)))
  with check(exists(select 1 from customers c where c.id=customer_id and is_store_member(c.store_id)));
create policy receivable_payments_store_access on receivable_payments for all
  using(exists(select 1 from receivables r join customers c on c.id=r.customer_id
    where r.id=receivable_id and is_store_member(c.store_id)))
  with check(exists(select 1 from receivables r join customers c on c.id=r.customer_id
    where r.id=receivable_id and is_store_member(c.store_id)));
create policy couriers_store_access on couriers for all
  using(is_store_member(store_id)) with check(is_store_member(store_id));
create policy deliveries_store_access on deliveries for all
  using(exists(select 1 from sales s where s.id=sale_id and is_store_member(s.store_id)))
  with check(exists(select 1 from sales s where s.id=sale_id and is_store_member(s.store_id)));
create policy delivery_history_store_access on delivery_status_history for all
  using(exists(select 1 from deliveries d join sales s on s.id=d.sale_id
    where d.id=delivery_id and is_store_member(s.store_id)))
  with check(exists(select 1 from deliveries d join sales s on s.id=d.sale_id
    where d.id=delivery_id and is_store_member(s.store_id)));
create policy imports_store_access on reconciliation_imports for all
  using(is_store_member(store_id)) with check(is_store_member(store_id));
create policy transactions_store_access on acquirer_transactions for all
  using(exists(select 1 from reconciliation_imports i where i.id=import_id and is_store_member(i.store_id)))
  with check(exists(select 1 from reconciliation_imports i where i.id=import_id and is_store_member(i.store_id)));
create policy settlements_store_access on settlements for all
  using(exists(select 1 from reconciliation_imports i where i.id=import_id and is_store_member(i.store_id)))
  with check(exists(select 1 from reconciliation_imports i where i.id=import_id and is_store_member(i.store_id)));
create policy issues_store_access on reconciliation_issues for all
  using(is_store_member(store_id)) with check(is_store_member(store_id));
create policy fee_rules_store_access on acquirer_fee_rules for all
  using(is_store_member(store_id)) with check(is_store_member(store_id));
create policy audit_store_read on audit_logs for select using(is_store_admin(store_id));

-- As funções da migration anterior são SECURITY DEFINER. A validação explícita
-- abaixo impede que um usuário autenticado opere IDs pertencentes a outra loja.
create or replace function finalize_sale(p_sale_id uuid, p_payments jsonb, p_idempotency_key text)
returns setof sales language plpgsql security definer set search_path=public as $$
declare v_sale sales%rowtype; v_item record; v_paid numeric(14,2); v_batch uuid;
begin
 select * into v_sale from sales where id=p_sale_id for update;
 if not found then raise exception 'sale_not_found'; end if;
 if not is_store_member(v_sale.store_id) then raise exception 'permission_denied'; end if;
 if v_sale.status='completed' then
   if v_sale.idempotency_key=p_idempotency_key then return next v_sale; return; end if;
   raise exception 'sale_already_finalized';
 end if;
 if v_sale.status<>'open' then raise exception 'sale_not_open'; end if;
 for v_item in select * from sale_items where sale_id=p_sale_id loop
   v_batch:=null;
   if v_item.batch_id is null then
     select id into v_batch from inventory_batches where product_id=v_item.product_id
       and quantity>=v_item.quantity and (expires_at is null or expires_at>=current_date)
       order by expires_at nulls last,created_at for update skip locked limit 1;
   else
     v_batch:=v_item.batch_id;
     perform 1 from inventory_batches where id=v_batch and product_id=v_item.product_id for update;
   end if;
   if v_batch is null or (select quantity from inventory_batches where id=v_batch)<v_item.quantity
     then raise exception 'insufficient_stock'; end if;
   update inventory_batches set quantity=quantity-v_item.quantity where id=v_batch;
   update sale_items set batch_id=v_batch where id=v_item.id;
   insert into stock_movements(product_id,batch_id,type,quantity,reference_type,reference_id)
     values(v_item.product_id,v_batch,'out',v_item.quantity,'sale',p_sale_id);
 end loop;
 select coalesce(sum(total),0) into v_sale.subtotal from sale_items where sale_id=p_sale_id;
 v_sale.total:=greatest(v_sale.subtotal-v_sale.discount,0);
 select coalesce(sum((x->>'amount')::numeric),0) into v_paid from jsonb_array_elements(p_payments)x;
 if v_paid<>v_sale.total then raise exception 'payment_total_mismatch'; end if;
 insert into sale_payments(sale_id,method,amount,institution_id,installments,authorization_code,status)
 select p_sale_id,x->>'method',(x->>'amount')::numeric,nullif(x->>'institution_id','')::uuid,
   coalesce((x->>'installments')::int,1),x->>'authorization_code','approved'
   from jsonb_array_elements(p_payments)x;
 if exists(select 1 from jsonb_array_elements(p_payments)x where x->>'method'='credit_account') then
   if v_sale.customer_id is null then raise exception 'customer_required'; end if;
   insert into receivables(customer_id,sale_id,original_amount,open_amount,due_date)
   select v_sale.customer_id,p_sale_id,(x->>'amount')::numeric,(x->>'amount')::numeric,
     coalesce((x->>'due_date')::date,current_date+30)
     from jsonb_array_elements(p_payments)x where x->>'method'='credit_account';
 end if;
 update sales set subtotal=v_sale.subtotal,total=v_sale.total,status='completed',sold_at=now(),
   idempotency_key=p_idempotency_key where id=p_sale_id returning * into v_sale;
 return next v_sale;
end $$;

create or replace function pay_receivable(
  p_receivable_id uuid,p_amount numeric,p_method text,p_user_id uuid,p_paid_at timestamptz default now()
) returns setof receivables language plpgsql security definer set search_path=public as $$
declare r receivables%rowtype; v_store uuid;
begin
 select rec.* into r from receivables rec where rec.id=p_receivable_id for update;
 if not found then raise exception 'receivable_not_found'; end if;
 select c.store_id into v_store from customers c where c.id=r.customer_id;
 if not is_store_member(v_store) or p_user_id<>auth.uid() then raise exception 'permission_denied'; end if;
 if p_amount<=0 or p_amount>r.open_amount then raise exception 'invalid_payment_amount'; end if;
 insert into receivable_payments(receivable_id,amount,payment_method,paid_at,user_id)
   values(r.id,p_amount,p_method,p_paid_at,p_user_id);
 update receivables set open_amount=open_amount-p_amount,
   status=case when open_amount-p_amount=0 then 'paid' else 'open' end
   where id=r.id returning * into r;
 return next r;
end $$;

revoke all on function complete_registration(jsonb) from public;
grant execute on function complete_registration(jsonb) to authenticated;
revoke all on function review_fiscal_profile(tax_regime,text) from public;
grant execute on function review_fiscal_profile(tax_regime,text) to authenticated;
revoke all on function finalize_sale(uuid,jsonb,text) from public;
grant execute on function finalize_sale(uuid,jsonb,text) to authenticated;
revoke all on function pay_receivable(uuid,numeric,text,uuid,timestamptz) from public;
grant execute on function pay_receivable(uuid,numeric,text,uuid,timestamptz) to authenticated;

commit;

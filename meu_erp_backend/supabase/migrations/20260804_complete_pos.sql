begin;
create extension if not exists "pgcrypto";

create table if not exists stores (
 id uuid primary key default gen_random_uuid(), name varchar(200) not null,
 document varchar(20) unique, timezone varchar(60) not null default 'America/Cuiaba',
 created_at timestamptz not null default now()
);
create table if not exists users (
 id uuid primary key default gen_random_uuid(), store_id uuid not null references stores(id),
 name varchar(200) not null, email varchar(254) not null, password_hash text not null,
 role varchar(20) not null check(role in ('admin','manager','operator')), active boolean not null default true,
 created_at timestamptz not null default now(), unique(store_id,email)
);
create table if not exists cash_registers (
 id uuid primary key default gen_random_uuid(), store_id uuid not null references stores(id),
 name varchar(100) not null, active boolean not null default true, unique(store_id,name)
);
create table if not exists cash_sessions (
 id uuid primary key default gen_random_uuid(), cash_register_id uuid not null references cash_registers(id),
 user_id uuid not null references users(id), opened_at timestamptz not null default now(),
 opening_amount numeric(14,2) not null default 0 check(opening_amount>=0), closed_at timestamptz,
 declared_amount numeric(14,2), expected_amount numeric(14,2), difference numeric(14,2),
 status varchar(10) not null default 'open' check(status in ('open','closed')),
 check((status='open' and closed_at is null) or (status='closed' and closed_at is not null))
);
create unique index if not exists ux_cash_session_open on cash_sessions(cash_register_id) where status='open';
create table if not exists products (
 id uuid primary key default gen_random_uuid(), store_id uuid not null references stores(id), name varchar(200) not null,
 barcode varchar(80), sku varchar(80) not null, sale_price numeric(14,2) not null check(sale_price>=0),
 tax_amount numeric(14,2) not null default 0 check(tax_amount>=0), active boolean not null default true,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 unique(store_id,sku), unique(store_id,barcode)
);
create table if not exists inventory_batches (
 id uuid primary key default gen_random_uuid(), product_id uuid not null references products(id),
 lot_number varchar(80) not null, expires_at date, purchase_price numeric(14,2) not null default 0,
 quantity numeric(14,3) not null default 0 check(quantity>=0), created_at timestamptz not null default now(),
 unique(product_id,lot_number)
);
create table if not exists stock_movements (
 id uuid primary key default gen_random_uuid(), product_id uuid not null references products(id),
 batch_id uuid references inventory_batches(id), type varchar(20) not null check(type in ('in','out','adjustment','return')),
 quantity numeric(14,3) not null check(quantity>0), unit_cost numeric(14,2), reference_type varchar(40),
 reference_id uuid, notes text, created_at timestamptz not null default now()
);
create table if not exists promotions (
 id uuid primary key default gen_random_uuid(), product_id uuid not null references products(id),
 promotional_price numeric(14,2) not null check(promotional_price>=0), starts_at timestamptz not null,
 ends_at timestamptz not null, active boolean not null default true, check(ends_at>starts_at)
);
create table if not exists customers (
 id uuid primary key default gen_random_uuid(), store_id uuid not null references stores(id), name varchar(200) not null,
 document varchar(20), phone varchar(20), email varchar(254), credit_limit numeric(14,2) not null default 0,
 active boolean not null default true, created_at timestamptz not null default now(), unique(store_id,document)
);
create table if not exists sales (
 id uuid primary key default gen_random_uuid(), store_id uuid not null references stores(id),
 cash_session_id uuid not null references cash_sessions(id), customer_id uuid references customers(id),
 subtotal numeric(14,2) not null default 0, discount numeric(14,2) not null default 0,
 total numeric(14,2) not null default 0, status varchar(20) not null default 'open'
 check(status in ('open','completed','cancelled')), sold_at timestamptz, cancelled_at timestamptz,
 idempotency_key varchar(200), created_at timestamptz not null default now(), unique(store_id,idempotency_key)
);
create table if not exists sale_items (
 id uuid primary key default gen_random_uuid(), sale_id uuid not null references sales(id) on delete cascade,
 product_id uuid not null references products(id), batch_id uuid references inventory_batches(id),
 quantity numeric(14,3) not null check(quantity>0), unit_price numeric(14,2) not null,
 discount numeric(14,2) not null default 0, tax_amount numeric(14,2) not null default 0,
 total numeric(14,2) generated always as ((quantity*unit_price)-discount+tax_amount) stored
);
create table if not exists financial_institutions (
 id uuid primary key default gen_random_uuid(), name varchar(200) not null, type varchar(30) not null, active boolean not null default true
);
create table if not exists sale_payments (
 id uuid primary key default gen_random_uuid(), sale_id uuid not null references sales(id) on delete cascade,
 method varchar(30) not null, amount numeric(14,2) not null check(amount>0),
 institution_id uuid references financial_institutions(id), installments integer not null default 1 check(installments>0),
 authorization_code varchar(100), status varchar(20) not null default 'approved'
);
create table if not exists receivables (
 id uuid primary key default gen_random_uuid(), customer_id uuid not null references customers(id),
 sale_id uuid not null references sales(id), original_amount numeric(14,2) not null,
 open_amount numeric(14,2) not null, due_date date not null, status varchar(20) not null default 'open'
 check(status in ('open','overdue','paid','cancelled')), created_at timestamptz not null default now()
);
create table if not exists receivable_payments (
 id uuid primary key default gen_random_uuid(), receivable_id uuid not null references receivables(id),
 amount numeric(14,2) not null check(amount>0), payment_method varchar(30) not null,
 paid_at timestamptz not null default now(), user_id uuid not null references users(id)
);
create table if not exists couriers (
 id uuid primary key default gen_random_uuid(), store_id uuid not null references stores(id),
 name varchar(200) not null, phone varchar(20), active boolean not null default true
);
create table if not exists deliveries (
 id uuid primary key default gen_random_uuid(), sale_id uuid not null references sales(id),
 customer_id uuid references customers(id), courier_id uuid references couriers(id), address jsonb not null,
 status varchar(30) not null default 'pending', scheduled_at timestamptz, delivered_at timestamptz,
 created_at timestamptz not null default now()
);
create table if not exists delivery_status_history (
 id uuid primary key default gen_random_uuid(), delivery_id uuid not null references deliveries(id),
 old_status varchar(30), new_status varchar(30) not null, user_id uuid not null references users(id),
 created_at timestamptz not null default now()
);
create table if not exists reconciliation_imports (
 id uuid primary key default gen_random_uuid(), store_id uuid not null references stores(id), file_path text not null,
 format varchar(20) not null, file_hash varchar(64) not null unique, period_start date, period_end date,
 status varchar(20) not null default 'pending', file_size bigint not null, created_at timestamptz not null default now()
);
create table if not exists acquirer_transactions (
 id uuid primary key default gen_random_uuid(), import_id uuid not null references reconciliation_imports(id),
 institution_id uuid references financial_institutions(id), external_id varchar(150) not null, gross_amount numeric(14,2) not null,
 fee_amount numeric(14,2) not null default 0, net_amount numeric(14,2) not null, transaction_at timestamptz not null,
 expected_settlement_at date, unique(import_id,external_id)
);
create table if not exists settlements (
 id uuid primary key default gen_random_uuid(), import_id uuid references reconciliation_imports(id),
 institution_id uuid references financial_institutions(id), external_id varchar(150), amount numeric(14,2) not null,
 settled_at date not null
);
create table if not exists reconciliation_matches (
 id uuid primary key default gen_random_uuid(), sale_payment_id uuid references sale_payments(id),
 acquirer_transaction_id uuid references acquirer_transactions(id), settlement_id uuid references settlements(id),
 matched_at timestamptz not null default now(), confidence numeric(5,4)
);
create table if not exists reconciliation_issues (
 id uuid primary key default gen_random_uuid(), store_id uuid not null references stores(id),
 issue_type varchar(50) not null, reference_type varchar(40), reference_id uuid, expected_amount numeric(14,2),
 actual_amount numeric(14,2), status varchar(20) not null default 'open', resolution_notes text,
 created_at timestamptz not null default now(), resolved_at timestamptz
);
create table if not exists acquirer_fee_rules (
 id uuid primary key default gen_random_uuid(), store_id uuid not null references stores(id),
 institution_id uuid not null references financial_institutions(id), payment_method varchar(30) not null,
 installments_from integer not null default 1, installments_to integer not null default 1,
 fee_percent numeric(7,4) not null default 0, fixed_fee numeric(14,2) not null default 0,
 starts_at date not null, ends_at date, active boolean not null default true
);
create table if not exists audit_logs (
 id bigserial primary key, store_id uuid, user_id uuid, action varchar(50) not null,
 entity_type varchar(50) not null, entity_id uuid, data jsonb, created_at timestamptz not null default now()
);
create index if not exists ix_products_search on products(store_id,name);
create index if not exists ix_batches_expiry on inventory_batches(expires_at) where quantity>0;
create index if not exists ix_sales_filters on sales(store_id,sold_at,status);
create index if not exists ix_receivables_status on receivables(status,due_date);
create index if not exists ix_deliveries_status on deliveries(status);

create or replace function finalize_sale(p_sale_id uuid, p_payments jsonb, p_idempotency_key text)
returns setof sales language plpgsql security definer as $$
declare v_sale sales%rowtype; v_item record; v_paid numeric(14,2); v_batch uuid;
begin
 select * into v_sale from sales where id=p_sale_id for update;
 if not found then raise exception 'sale_not_found'; end if;
 if v_sale.status='completed' then
   if v_sale.idempotency_key=p_idempotency_key then return next v_sale; return; end if;
   raise exception 'sale_already_finalized';
 end if;
 if v_sale.status<>'open' then raise exception 'sale_not_open'; end if;
 for v_item in select * from sale_items where sale_id=p_sale_id loop
   if v_item.batch_id is null then
     select id into v_batch from inventory_batches where product_id=v_item.product_id and quantity>=v_item.quantity
       and (expires_at is null or expires_at>=current_date) order by expires_at nulls last,created_at for update skip locked limit 1;
   else v_batch:=v_item.batch_id; perform 1 from inventory_batches where id=v_batch for update; end if;
   if v_batch is null or (select quantity from inventory_batches where id=v_batch)<v_item.quantity then raise exception 'insufficient_stock'; end if;
   update inventory_batches set quantity=quantity-v_item.quantity where id=v_batch;
   update sale_items set batch_id=v_batch where id=v_item.id;
   insert into stock_movements(product_id,batch_id,type,quantity,reference_type,reference_id)
     values(v_item.product_id,v_batch,'out',v_item.quantity,'sale',p_sale_id);
 end loop;
 select coalesce(sum(total),0) into v_sale.subtotal from sale_items where sale_id=p_sale_id;
 v_sale.total:=greatest(v_sale.subtotal-v_sale.discount,0);
 select coalesce(sum((x->>'amount')::numeric),0) into v_paid from jsonb_array_elements(p_payments) x;
 if v_paid<>v_sale.total then raise exception 'payment_total_mismatch'; end if;
 insert into sale_payments(sale_id,method,amount,institution_id,installments,authorization_code,status)
 select p_sale_id,x->>'method',(x->>'amount')::numeric,nullif(x->>'institution_id','')::uuid,
   coalesce((x->>'installments')::int,1),x->>'authorization_code','approved' from jsonb_array_elements(p_payments)x;
 if exists(select 1 from jsonb_array_elements(p_payments)x where x->>'method'='credit_account') then
   if v_sale.customer_id is null then raise exception 'customer_required'; end if;
   insert into receivables(customer_id,sale_id,original_amount,open_amount,due_date)
   select v_sale.customer_id,p_sale_id,(x->>'amount')::numeric,(x->>'amount')::numeric,
     coalesce((x->>'due_date')::date,current_date+30) from jsonb_array_elements(p_payments)x where x->>'method'='credit_account';
 end if;
 update sales set subtotal=v_sale.subtotal,total=v_sale.total,status='completed',sold_at=now(),idempotency_key=p_idempotency_key
 where id=p_sale_id returning * into v_sale; return next v_sale;
end $$;

create or replace function pay_receivable(p_receivable_id uuid,p_amount numeric,p_method text,p_user_id uuid,p_paid_at timestamptz default now())
returns setof receivables language plpgsql security definer as $$
declare r receivables%rowtype;
begin select * into r from receivables where id=p_receivable_id for update;
 if not found then raise exception 'receivable_not_found'; end if;
 if p_amount<=0 or p_amount>r.open_amount then raise exception 'invalid_payment_amount'; end if;
 insert into receivable_payments(receivable_id,amount,payment_method,paid_at,user_id) values(r.id,p_amount,p_method,p_paid_at,p_user_id);
 update receivables set open_amount=open_amount-p_amount,status=case when open_amount-p_amount=0 then 'paid' else 'open' end
 where id=r.id returning * into r; return next r; end $$;
commit;

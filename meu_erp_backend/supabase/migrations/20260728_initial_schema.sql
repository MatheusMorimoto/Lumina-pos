begin;

create extension if not exists "pgcrypto";

create table if not exists clientes (
    id uuid primary key default gen_random_uuid(),
    nome varchar(200) not null,
    cpf_cnpj varchar(14) unique,
    telefone varchar(20),
    limite_credito numeric(14, 2) not null default 0 check (limite_credito >= 0),
    ativo boolean not null default true,
    criado_em timestamptz not null default now()
);

create table if not exists produtos (
    id uuid primary key default gen_random_uuid(),
    sku varchar(50) not null unique,
    nome varchar(200) not null,
    preco_venda numeric(14, 2) not null check (preco_venda >= 0),
    estoque_minimo numeric(14, 3) not null default 0 check (estoque_minimo >= 0),
    ativo boolean not null default true,
    criado_em timestamptz not null default now()
);

create table if not exists lotes_produto (
    id uuid primary key default gen_random_uuid(),
    produto_id uuid not null references produtos(id) on delete restrict,
    codigo_lote varchar(80) not null,
    quantidade numeric(14, 3) not null check (quantidade > 0),
    saldo numeric(14, 3) not null check (saldo >= 0),
    validade date,
    criado_em timestamptz not null default now(),
    unique (produto_id, codigo_lote)
);

create table if not exists caixas (
    id uuid primary key default gen_random_uuid(),
    operador_id uuid not null,
    saldo_inicial numeric(14, 2) not null default 0 check (saldo_inicial >= 0),
    saldo_informado numeric(14, 2),
    quebra_caixa numeric(14, 2),
    status varchar(20) not null default 'aberto'
        check (status in ('aberto', 'fechado')),
    aberto_em timestamptz not null default now(),
    fechado_em timestamptz,
    constraint fechamento_coerente check (
        (status = 'aberto' and fechado_em is null)
        or (status = 'fechado' and fechado_em is not null)
    )
);

create unique index if not exists ux_caixa_aberto_operador
    on caixas (operador_id) where status = 'aberto';

create table if not exists vendas (
    id uuid primary key default gen_random_uuid(),
    caixa_id uuid not null references caixas(id) on delete restrict,
    cliente_id uuid references clientes(id) on delete restrict,
    total numeric(14, 2) not null check (total >= 0),
    forma_pagamento varchar(30) not null check (
        forma_pagamento in (
            'dinheiro', 'pix', 'cartao_credito', 'cartao_debito', 'crediario'
        )
    ),
    status varchar(20) not null default 'concluida'
        check (status in ('concluida', 'cancelada', 'trocada')),
    criada_em timestamptz not null default now()
);

create table if not exists itens_venda (
    id uuid primary key default gen_random_uuid(),
    venda_id uuid not null references vendas(id) on delete cascade,
    produto_id uuid not null references produtos(id) on delete restrict,
    quantidade numeric(14, 3) not null check (quantidade > 0),
    preco_unitario numeric(14, 2) not null check (preco_unitario >= 0),
    desconto numeric(14, 2) not null default 0 check (desconto >= 0),
    subtotal numeric(14, 2) not null check (subtotal >= 0)
);

create table if not exists trocas (
    id uuid primary key default gen_random_uuid(),
    venda_id uuid not null references vendas(id) on delete restrict,
    item_venda_id uuid not null references itens_venda(id) on delete restrict,
    quantidade numeric(14, 3) not null check (quantidade > 0),
    motivo varchar(300) not null,
    criada_em timestamptz not null default now()
);

create table if not exists parcelas_crediario (
    id uuid primary key default gen_random_uuid(),
    cliente_id uuid not null references clientes(id) on delete restrict,
    venda_id uuid not null references vendas(id) on delete restrict,
    numero integer not null check (numero > 0),
    valor_original numeric(14, 2) not null check (valor_original > 0),
    saldo_devedor numeric(14, 2) not null check (saldo_devedor >= 0),
    vencimento date not null,
    status varchar(20) not null default 'aberta'
        check (status in ('aberta', 'parcial', 'paga', 'cancelada')),
    criada_em timestamptz not null default now(),
    unique (venda_id, numero)
);

create index if not exists ix_lotes_validade
    on lotes_produto (validade) where saldo > 0;
create index if not exists ix_vendas_caixa on vendas (caixa_id);
create index if not exists ix_parcelas_cliente_status
    on parcelas_crediario (cliente_id, status);
create index if not exists ix_parcelas_vencimento
    on parcelas_crediario (vencimento) where status in ('aberta', 'parcial');

alter table clientes enable row level security;
alter table produtos enable row level security;
alter table lotes_produto enable row level security;
alter table caixas enable row level security;
alter table vendas enable row level security;
alter table itens_venda enable row level security;
alter table trocas enable row level security;
alter table parcelas_crediario enable row level security;

commit;

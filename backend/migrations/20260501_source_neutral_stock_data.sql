create extension if not exists pgcrypto;

create table if not exists public.stocks (
  id uuid primary key default gen_random_uuid(),
  symbol text not null unique,
  exchange text not null default 'NSE',
  company_name text,
  isin text,
  series text,
  sector text,
  industry text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.stock_prices_daily (
  id uuid primary key default gen_random_uuid(),
  stock_id uuid references public.stocks(id) on delete set null,
  symbol text not null,
  date date not null,
  open numeric(18,4),
  high numeric(18,4),
  low numeric(18,4),
  close numeric(18,4),
  adj_close numeric(18,4),
  volume numeric(20,2),
  delivery_qty numeric(20,2),
  delivery_percent numeric(9,4),
  source text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (symbol, date, source)
);

create table if not exists public.financial_statements (
  id uuid primary key default gen_random_uuid(),
  stock_id uuid references public.stocks(id) on delete set null,
  symbol text not null,
  period_type text not null check (period_type in ('quarterly', 'annual')),
  period_end_date date not null,
  fiscal_year integer,
  revenue numeric(22,4),
  ebitda numeric(22,4),
  ebit numeric(22,4),
  profit_before_tax numeric(22,4),
  net_profit numeric(22,4),
  eps numeric(18,6),
  total_assets numeric(22,4),
  total_liabilities numeric(22,4),
  total_equity numeric(22,4),
  total_debt numeric(22,4),
  cash_and_equivalents numeric(22,4),
  cash_from_operations numeric(22,4),
  cash_from_investing numeric(22,4),
  cash_from_financing numeric(22,4),
  source text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (symbol, period_type, period_end_date, source)
);

create table if not exists public.ratios_snapshot (
  id uuid primary key default gen_random_uuid(),
  stock_id uuid references public.stocks(id) on delete set null,
  symbol text not null,
  snapshot_date date not null,
  market_cap numeric(22,4),
  pe numeric(18,6),
  pb numeric(18,6),
  ev_ebitda numeric(18,6),
  roe numeric(18,6),
  roce numeric(18,6),
  debt_to_equity numeric(18,6),
  dividend_yield numeric(18,6),
  sales_growth_3y numeric(18,6),
  profit_growth_3y numeric(18,6),
  eps_growth_3y numeric(18,6),
  eps_ttm numeric(18,6),
  source text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (symbol, snapshot_date, source)
);

create table if not exists public.shareholding_pattern (
  id uuid primary key default gen_random_uuid(),
  stock_id uuid references public.stocks(id) on delete set null,
  symbol text not null,
  period_end_date date not null,
  promoter_holding numeric(9,4),
  promoter_pledge numeric(9,4),
  fii_holding numeric(9,4),
  dii_holding numeric(9,4),
  public_holding numeric(9,4),
  source text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (symbol, period_end_date, source)
);

create table if not exists public.corporate_events (
  id uuid primary key default gen_random_uuid(),
  stock_id uuid references public.stocks(id) on delete set null,
  symbol text not null,
  event_date date not null,
  event_type text not null,
  title text not null,
  description text,
  source_url text,
  source text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.data_provider_runs (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  job_name text not null,
  status text not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  symbols_attempted integer not null default 0,
  symbols_succeeded integer not null default 0,
  symbols_failed integer not null default 0,
  error_summary text,
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists stocks_symbol_idx on public.stocks (symbol);
create index if not exists stock_prices_daily_symbol_date_idx on public.stock_prices_daily (symbol, date desc);
create index if not exists stock_prices_daily_source_idx on public.stock_prices_daily (source);
create index if not exists financial_statements_symbol_period_idx on public.financial_statements (symbol, period_end_date desc);
create index if not exists financial_statements_source_idx on public.financial_statements (source);
create index if not exists ratios_snapshot_symbol_date_idx on public.ratios_snapshot (symbol, snapshot_date desc);
create index if not exists ratios_snapshot_source_idx on public.ratios_snapshot (source);
create index if not exists shareholding_pattern_symbol_period_idx on public.shareholding_pattern (symbol, period_end_date desc);
create index if not exists shareholding_pattern_source_idx on public.shareholding_pattern (source);
create index if not exists corporate_events_symbol_date_idx on public.corporate_events (symbol, event_date desc);
create index if not exists corporate_events_source_idx on public.corporate_events (source);
create index if not exists data_provider_runs_provider_job_idx on public.data_provider_runs (provider, job_name, started_at desc);

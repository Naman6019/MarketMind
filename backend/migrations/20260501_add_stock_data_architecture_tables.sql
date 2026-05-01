create extension if not exists pgcrypto;

create table if not exists public.stocks (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  exchange text not null default 'NSE',
  company_name text,
  isin text,
  sector text,
  industry text,
  listing_status text,
  is_active boolean default true,
  source text not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (symbol, exchange)
);

create table if not exists public.stock_prices_daily (
  id uuid primary key default gen_random_uuid(),
  stock_id uuid references public.stocks(id) on delete cascade,
  symbol text not null,
  date date not null,
  open numeric(18,4),
  high numeric(18,4),
  low numeric(18,4),
  close numeric(18,4),
  adj_close numeric(18,4),
  volume bigint,
  value_traded numeric(24,4),
  delivery_qty bigint,
  delivery_percent numeric(8,4),
  source text not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (symbol, date, source)
);

create table if not exists public.financial_statements (
  id uuid primary key default gen_random_uuid(),
  stock_id uuid references public.stocks(id) on delete cascade,
  symbol text not null,
  period_type text not null,
  period_end_date date not null,
  fiscal_year int,
  fiscal_quarter int,
  revenue numeric(24,4),
  operating_profit numeric(24,4),
  ebitda numeric(24,4),
  ebit numeric(24,4),
  profit_before_tax numeric(24,4),
  net_profit numeric(24,4),
  eps numeric(12,4),
  total_assets numeric(24,4),
  total_liabilities numeric(24,4),
  total_equity numeric(24,4),
  total_debt numeric(24,4),
  cash_and_equivalents numeric(24,4),
  cash_from_operations numeric(24,4),
  cash_from_investing numeric(24,4),
  cash_from_financing numeric(24,4),
  source text not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (symbol, period_type, period_end_date, source)
);

create table if not exists public.ratios_snapshot (
  id uuid primary key default gen_random_uuid(),
  stock_id uuid references public.stocks(id) on delete cascade,
  symbol text not null,
  snapshot_date date not null,
  market_cap numeric(24,4),
  enterprise_value numeric(24,4),
  pe numeric(12,4),
  pb numeric(12,4),
  ps numeric(12,4),
  ev_ebitda numeric(12,4),
  roe numeric(12,4),
  roce numeric(12,4),
  roa numeric(12,4),
  debt_to_equity numeric(12,4),
  current_ratio numeric(12,4),
  interest_coverage numeric(12,4),
  dividend_yield numeric(12,4),
  sales_growth_1y numeric(12,4),
  sales_growth_3y numeric(12,4),
  profit_growth_1y numeric(12,4),
  profit_growth_3y numeric(12,4),
  eps_growth_1y numeric(12,4),
  eps_growth_3y numeric(12,4),
  source text not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (symbol, snapshot_date, source)
);

create table if not exists public.shareholding_pattern (
  id uuid primary key default gen_random_uuid(),
  stock_id uuid references public.stocks(id) on delete cascade,
  symbol text not null,
  period_end_date date not null,
  promoter_holding numeric(8,4),
  promoter_pledge numeric(8,4),
  fii_holding numeric(8,4),
  dii_holding numeric(8,4),
  public_holding numeric(8,4),
  government_holding numeric(8,4),
  source text not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (symbol, period_end_date, source)
);

create table if not exists public.corporate_events (
  id uuid primary key default gen_random_uuid(),
  stock_id uuid references public.stocks(id) on delete cascade,
  symbol text not null,
  event_date date not null,
  event_type text not null,
  title text,
  description text,
  source_url text,
  source text not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (symbol, event_date, event_type, title, source)
);

create table if not exists public.provider_runs (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  job_name text not null,
  status text not null,
  started_at timestamptz,
  finished_at timestamptz,
  symbols_attempted int default 0,
  symbols_succeeded int default 0,
  symbols_failed int default 0,
  error_summary text,
  metadata jsonb,
  created_at timestamptz default now()
);

create table if not exists public.data_quality_issues (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  table_name text,
  field_name text,
  issue_type text,
  issue_message text,
  source text,
  detected_at timestamptz default now(),
  metadata jsonb
);

create index if not exists stocks_symbol_idx on public.stocks (symbol);
create index if not exists stocks_exchange_idx on public.stocks (exchange);
create index if not exists stocks_is_active_idx on public.stocks (is_active);

create index if not exists stock_prices_daily_symbol_idx on public.stock_prices_daily (symbol);
create index if not exists stock_prices_daily_date_idx on public.stock_prices_daily (date);
create index if not exists stock_prices_daily_source_idx on public.stock_prices_daily (source);
create index if not exists stock_prices_daily_stock_id_idx on public.stock_prices_daily (stock_id);

create index if not exists financial_statements_symbol_idx on public.financial_statements (symbol);
create index if not exists financial_statements_period_type_idx on public.financial_statements (period_type);
create index if not exists financial_statements_period_end_date_idx on public.financial_statements (period_end_date);
create index if not exists financial_statements_source_idx on public.financial_statements (source);
create index if not exists financial_statements_stock_id_idx on public.financial_statements (stock_id);

create index if not exists ratios_snapshot_symbol_idx on public.ratios_snapshot (symbol);
create index if not exists ratios_snapshot_snapshot_date_idx on public.ratios_snapshot (snapshot_date);
create index if not exists ratios_snapshot_source_idx on public.ratios_snapshot (source);
create index if not exists ratios_snapshot_stock_id_idx on public.ratios_snapshot (stock_id);

create index if not exists shareholding_pattern_symbol_idx on public.shareholding_pattern (symbol);
create index if not exists shareholding_pattern_period_end_date_idx on public.shareholding_pattern (period_end_date);
create index if not exists shareholding_pattern_source_idx on public.shareholding_pattern (source);
create index if not exists shareholding_pattern_stock_id_idx on public.shareholding_pattern (stock_id);

create index if not exists corporate_events_symbol_idx on public.corporate_events (symbol);
create index if not exists corporate_events_event_date_idx on public.corporate_events (event_date);
create index if not exists corporate_events_event_type_idx on public.corporate_events (event_type);
create index if not exists corporate_events_source_idx on public.corporate_events (source);
create index if not exists corporate_events_stock_id_idx on public.corporate_events (stock_id);

create index if not exists provider_runs_provider_idx on public.provider_runs (provider);
create index if not exists provider_runs_job_name_idx on public.provider_runs (job_name);
create index if not exists provider_runs_status_idx on public.provider_runs (status);
create index if not exists provider_runs_started_at_idx on public.provider_runs (started_at);

create index if not exists data_quality_issues_symbol_idx on public.data_quality_issues (symbol);
create index if not exists data_quality_issues_source_idx on public.data_quality_issues (source);
create index if not exists data_quality_issues_detected_at_idx on public.data_quality_issues (detected_at);

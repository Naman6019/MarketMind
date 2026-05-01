-- DEPRECATED: legacy CSV import table. Production stock data now uses
-- backend/migrations/20260501_source_neutral_stock_data.sql.
create table if not exists public.stock_fundamentals (
  symbol text primary key,
  company_name text,
  industry text,
  cmp numeric,
  dividend_yield numeric,
  net_profit_qtr numeric,
  qtr_profit_var numeric,
  sales_qtr numeric,
  qtr_sales_var numeric,
  pe_ratio numeric,
  market_cap numeric,
  roce numeric,
  roe numeric,
  eps_12m numeric,
  ev_ebitda numeric,
  sales_growth_3y numeric,
  profit_growth_3y numeric,
  debt_to_equity numeric,
  promoter_holding numeric,
  fii_holding numeric,
  dii_holding numeric,
  source text default 'Screener CSV',
  source_updated_at timestamptz,
  raw_data jsonb,
  updated_at timestamptz default now()
);

create index if not exists stock_fundamentals_industry_idx
  on public.stock_fundamentals (industry);

create index if not exists stock_fundamentals_company_name_idx
  on public.stock_fundamentals (company_name);

alter table public.stock_fundamentals
  add column if not exists cmp numeric,
  add column if not exists dividend_yield numeric,
  add column if not exists net_profit_qtr numeric,
  add column if not exists qtr_profit_var numeric,
  add column if not exists sales_qtr numeric,
  add column if not exists qtr_sales_var numeric,
  add column if not exists eps_12m numeric,
  add column if not exists ev_ebitda numeric;

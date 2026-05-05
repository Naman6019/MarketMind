-- Additive schema drift fix for source-neutral stock fundamentals.
-- Safe to run multiple times in Supabase SQL Editor.

alter table if exists public.stocks
  add column if not exists listing_status text,
  add column if not exists source text;

alter table if exists public.stock_prices_daily
  add column if not exists value_traded numeric(24,4);

alter table if exists public.financial_statements
  add column if not exists fiscal_quarter integer,
  add column if not exists operating_profit numeric(24,4);

alter table if exists public.ratios_snapshot
  add column if not exists enterprise_value numeric(24,4),
  add column if not exists ps numeric(12,4),
  add column if not exists roa numeric(12,4),
  add column if not exists current_ratio numeric(12,4),
  add column if not exists interest_coverage numeric(12,4),
  add column if not exists sales_growth_1y numeric(12,4),
  add column if not exists profit_growth_1y numeric(12,4),
  add column if not exists eps_growth_1y numeric(12,4);

alter table if exists public.shareholding_pattern
  add column if not exists government_holding numeric(8,4);

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

create index if not exists data_quality_issues_symbol_idx
  on public.data_quality_issues (symbol);

create index if not exists data_quality_issues_source_idx
  on public.data_quality_issues (source);

create index if not exists data_quality_issues_detected_at_idx
  on public.data_quality_issues (detected_at);

-- Refresh Supabase/PostgREST schema cache so REST writes see the new columns.
select pg_notify('pgrst', 'reload schema');

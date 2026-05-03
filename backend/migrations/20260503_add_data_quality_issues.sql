create extension if not exists pgcrypto;

create table if not exists public.data_quality_issues (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  table_name text,
  field_name text,
  issue_type text not null,
  issue_message text not null,
  source text,
  detected_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists data_quality_issues_symbol_idx on public.data_quality_issues (symbol);
create index if not exists data_quality_issues_source_idx on public.data_quality_issues (source);
create index if not exists data_quality_issues_detected_at_idx on public.data_quality_issues (detected_at);

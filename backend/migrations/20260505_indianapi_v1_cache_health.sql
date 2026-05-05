create extension if not exists pgcrypto;

create table if not exists public.provider_endpoint_health (
  provider text not null,
  endpoint_name text not null,
  last_success_at timestamptz,
  last_failure_at timestamptz,
  last_status_code int,
  failure_count int not null default 0,
  disabled_until timestamptz,
  last_error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (provider, endpoint_name)
);

create table if not exists public.provider_response_cache (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  endpoint text not null,
  cache_key text not null,
  params_json jsonb not null default '{}'::jsonb,
  response_json jsonb not null,
  fetched_at timestamptz not null default now(),
  expires_at timestamptz,
  status text not null default 'success',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (provider, endpoint, cache_key)
);

create table if not exists public.provider_ingestion_logs (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  endpoint text not null,
  status text not null,
  status_code int,
  params_json jsonb not null default '{}'::jsonb,
  error_json jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.stock_profiles (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  endpoint text not null,
  stock_name text not null,
  response_json jsonb not null,
  fetched_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (provider, endpoint, stock_name)
);

create table if not exists public.stock_financial_stats (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  endpoint text not null,
  stock_name text not null,
  stats text not null,
  response_json jsonb not null,
  fetched_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (provider, endpoint, stock_name, stats)
);

create table if not exists public.stock_corporate_actions (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  endpoint text not null,
  stock_name text not null,
  response_json jsonb not null,
  fetched_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (provider, endpoint, stock_name)
);

create table if not exists public.stock_recent_announcements (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  endpoint text not null,
  stock_name text not null,
  response_json jsonb not null,
  fetched_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (provider, endpoint, stock_name)
);

create table if not exists public.mutual_fund_details (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  endpoint text not null,
  stock_name text not null,
  response_json jsonb not null,
  fetched_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (provider, endpoint, stock_name)
);

create index if not exists provider_endpoint_health_disabled_idx
  on public.provider_endpoint_health (provider, disabled_until);

create index if not exists provider_response_cache_expiry_idx
  on public.provider_response_cache (provider, endpoint, expires_at desc);

create index if not exists provider_ingestion_logs_provider_created_idx
  on public.provider_ingestion_logs (provider, created_at desc);

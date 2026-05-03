alter table public.stock_prices_daily
  add column if not exists value_traded numeric(24,4);

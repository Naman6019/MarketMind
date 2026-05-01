-- DEPRECATED: optional one-off bridge from the old legacy CSV table into
-- source-neutral tables. Do not use this in production jobs.

do $$
begin
  if to_regclass('public.stock_fundamentals') is not null then
    execute $migrate$
      insert into public.stocks (symbol, exchange, company_name, industry, is_active)
      select symbol, 'NSE', company_name, industry, true
      from public.stock_fundamentals
      where symbol is not null
      on conflict (symbol) do update set
        company_name = coalesce(excluded.company_name, public.stocks.company_name),
        industry = coalesce(excluded.industry, public.stocks.industry),
        updated_at = now()
    $migrate$;

    execute $migrate$
      insert into public.ratios_snapshot (
        symbol,
        snapshot_date,
        market_cap,
        pe,
        ev_ebitda,
        roe,
        roce,
        debt_to_equity,
        dividend_yield,
        sales_growth_3y,
        profit_growth_3y,
        source
      )
      select
        symbol,
        coalesce(source_updated_at::date, current_date),
        market_cap,
        pe_ratio,
        ev_ebitda,
        case when abs(roe) > 1 then roe / 100 else roe end,
        case when abs(roce) > 1 then roce / 100 else roce end,
        debt_to_equity,
        case when abs(dividend_yield) > 1 then dividend_yield / 100 else dividend_yield end,
        case when abs(sales_growth_3y) > 1 then sales_growth_3y / 100 else sales_growth_3y end,
        case when abs(profit_growth_3y) > 1 then profit_growth_3y / 100 else profit_growth_3y end,
        'legacy_csv_import'
      from public.stock_fundamentals
      where symbol is not null
      on conflict (symbol, snapshot_date, source) do update set
        market_cap = excluded.market_cap,
        pe = excluded.pe,
        ev_ebitda = excluded.ev_ebitda,
        roe = excluded.roe,
        roce = excluded.roce,
        debt_to_equity = excluded.debt_to_equity,
        dividend_yield = excluded.dividend_yield,
        sales_growth_3y = excluded.sales_growth_3y,
        profit_growth_3y = excluded.profit_growth_3y,
        updated_at = now()
    $migrate$;

    execute $migrate$
      insert into public.financial_statements (
        symbol,
        period_type,
        period_end_date,
        revenue,
        net_profit,
        eps,
        source
      )
      select
        symbol,
        'quarterly',
        coalesce(source_updated_at::date, current_date),
        sales_qtr,
        net_profit_qtr,
        eps_12m,
        'legacy_csv_import'
      from public.stock_fundamentals
      where symbol is not null
      on conflict (symbol, period_type, period_end_date, source) do update set
        revenue = excluded.revenue,
        net_profit = excluded.net_profit,
        eps = excluded.eps,
        updated_at = now()
    $migrate$;

    execute $migrate$
      insert into public.shareholding_pattern (
        symbol,
        period_end_date,
        promoter_holding,
        fii_holding,
        dii_holding,
        source
      )
      select
        symbol,
        coalesce(source_updated_at::date, current_date),
        case when abs(promoter_holding) > 1 then promoter_holding / 100 else promoter_holding end,
        case when abs(fii_holding) > 1 then fii_holding / 100 else fii_holding end,
        case when abs(dii_holding) > 1 then dii_holding / 100 else dii_holding end,
        'legacy_csv_import'
      from public.stock_fundamentals
      where symbol is not null
      on conflict (symbol, period_end_date, source) do update set
        promoter_holding = excluded.promoter_holding,
        fii_holding = excluded.fii_holding,
        dii_holding = excluded.dii_holding,
        updated_at = now()
    $migrate$;
  end if;
end $$;

-- Step 1: Database Schema for Mutual Funds

CREATE TABLE IF NOT EXISTS public.mutual_funds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_code INTEGER UNIQUE NOT NULL,
    scheme_name TEXT NOT NULL,
    isin TEXT,
    fund_house TEXT NOT NULL,
    category TEXT NOT NULL,
    sub_category TEXT NOT NULL,
    nav DECIMAL NOT NULL,
    nav_date DATE NOT NULL,
    expense_ratio DECIMAL,
    aum DECIMAL,
    exit_load TEXT,
    benchmark TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.mutual_funds ADD COLUMN IF NOT EXISTS isin TEXT;
ALTER TABLE public.mutual_funds ADD COLUMN IF NOT EXISTS expense_ratio DECIMAL;
ALTER TABLE public.mutual_funds ADD COLUMN IF NOT EXISTS aum DECIMAL;
ALTER TABLE public.mutual_funds ADD COLUMN IF NOT EXISTS exit_load TEXT;
ALTER TABLE public.mutual_funds ADD COLUMN IF NOT EXISTS benchmark TEXT;

CREATE TABLE IF NOT EXISTS public.mutual_fund_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_code INTEGER NOT NULL,
    nav DECIMAL NOT NULL,
    nav_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (scheme_code, nav_date)
);

CREATE TABLE IF NOT EXISTS public.mutual_fund_holdings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_code INTEGER NOT NULL,
    as_of_date DATE,
    security_name TEXT NOT NULL,
    isin TEXT,
    sector TEXT,
    weight_pct DECIMAL,
    source TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (scheme_code, as_of_date, security_name, isin)
);

CREATE INDEX IF NOT EXISTS idx_mutual_fund_history_scheme_date
    ON public.mutual_fund_history (scheme_code, nav_date DESC);

CREATE INDEX IF NOT EXISTS idx_mutual_fund_holdings_scheme_date
    ON public.mutual_fund_holdings (scheme_code, as_of_date DESC);

-- Note: In a real Supabase setup, you would apply this manually via the SQL Editor or migrations CLI.

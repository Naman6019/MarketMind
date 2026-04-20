-- Step 1: Database Schema for Mutual Funds

CREATE TABLE IF NOT EXISTS public.mutual_funds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_code INTEGER UNIQUE NOT NULL,
    scheme_name TEXT NOT NULL,
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

-- Note: In a real Supabase setup, you would apply this manually via the SQL Editor or migrations CLI.

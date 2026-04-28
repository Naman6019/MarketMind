import { NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';
import { calculateCAGR, calculateRiskMetrics } from '@/lib/mf/returns';

export const dynamic = 'force-dynamic';

async function fetchFromBackend(schemeCode: string) {
  const target = process.env.NODE_ENV === 'development'
    ? `http://127.0.0.1:8000/api/mf/${schemeCode}`
    : `${process.env.NEXT_PUBLIC_API_URL}/api/mf/${schemeCode}`;

  try {
    const res = await fetch(target, { cache: 'no-store' });
    if (!res.ok) return null;
    const json = await res.json();
    if (!json?.details || !Array.isArray(json?.chartData)) return null;
    return json;
  } catch {
    return null;
  }
}

export async function GET(_request: Request, context: { params: Promise<{ schemeCode: string }>}) {
  const { schemeCode } = await context.params;
  if (!/^\d+$/.test(schemeCode)) {
    return NextResponse.json({ error: 'Invalid scheme code' }, { status: 400 });
  }

  try {
    // Primary source: backend API uses the same DB path as chat resolution.
    const backendJson = await fetchFromBackend(schemeCode);
    if (backendJson) {
      return NextResponse.json(backendJson);
    }

    // Fallback: local Supabase query (for local-only runs)
    const { data: mfDetails, error } = await supabase
      .from('mutual_funds')
      .select('*')
      .eq('scheme_code', parseInt(schemeCode, 10))
      .limit(1)
      .maybeSingle();

    if (error || !mfDetails) {
      return NextResponse.json({ error: 'Mutual fund not found' }, { status: 404 });
    }

    // 1. Try to fetch history from local Supabase table
    const { data: localHistory } = await supabase
      .from('mutual_fund_history')
      .select('nav, nav_date')
      .eq('scheme_code', parseInt(schemeCode, 10))
      .order('nav_date', { ascending: false });

    let history = (localHistory || []).map(h => ({
      date: h.nav_date.split('-').reverse().join('-'), // Convert YYYY-MM-DD to DD-MM-YYYY
      nav: h.nav.toString()
    }));

    // Calculate returns
    const cagr1Y = calculateCAGR(history, 1);
    const cagr3Y = calculateCAGR(history, 3);
    const cagr5Y = calculateCAGR(history, 5);

    // Calculate risk metrics from full NAV history
    const riskMetrics = calculateRiskMetrics(history);

    // Filter last 365 days of NAV history for charting
    const recentHistory = history.slice(0, 250).reverse().map(h => ({
      date: h.date,
      value: parseFloat(h.nav)
    }));

    // --- FALLBACK FOR AUM/EXPENSE RATIO ---
    // If they are null in Supabase, we could theoretically fetch them from yfinance here.
    // But since this is a serverless function, we should keep it fast.
    // For now, we will return what we have.

    return NextResponse.json({
      details: mfDetails,
      returns: {
        '1Y': cagr1Y,
        '3Y': cagr3Y,
        '5Y': cagr5Y
      },
      riskMetrics,
      chartData: recentHistory
    });

  } catch (error) {
    return NextResponse.json({ error: (error as Error).message }, { status: 500 });
  }
}

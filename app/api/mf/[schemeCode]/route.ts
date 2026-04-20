import { NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';
import { fetchMFHistory, calculateCAGR } from '@/lib/mf/returns';

export async function GET(request: Request, context: { params: Promise<{ schemeCode: string }>}) {
  const { schemeCode } = await context.params;

  try {
    const { data: mfDetails, error } = await supabase
      .from('mutual_funds')
      .select('*')
      .eq('scheme_code', parseInt(schemeCode, 10))
      .single();

    if (error || !mfDetails) {
      return NextResponse.json({ error: 'Mutual fund not found' }, { status: 404 });
    }

    const history = await fetchMFHistory(schemeCode);
    
    // Calculate returns
    const cagr1Y = calculateCAGR(history, 1);
    const cagr3Y = calculateCAGR(history, 3);
    const cagr5Y = calculateCAGR(history, 5);

    // Filter last 365 days of NAV history for charting
    // history is descending. We grab approximately the last 250 trading days
    const recentHistory = history.slice(0, 250).reverse().map(h => ({
      date: h.date,
      value: parseFloat(h.nav)
    }));

    return NextResponse.json({
      details: mfDetails,
      returns: {
        '1Y': cagr1Y,
        '3Y': cagr3Y,
        '5Y': cagr5Y
      },
      chartData: recentHistory
    });

  } catch (error) {
    return NextResponse.json({ error: (error as Error).message }, { status: 500 });
  }
}

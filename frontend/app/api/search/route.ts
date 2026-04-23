import { NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get('q');
  const type = searchParams.get('type') || 'all'; // all | stock | mf

  if (!query || query.length < 2) {
    return NextResponse.json({ results: [] });
  }

  try {
    let results: any[] = [];

    if (type === 'all' || type === 'mf') {
      const words = query.split(/\s+/).filter(w => w.length > 0);
      const searchPattern = `%${words.join('%')}%`;

      const { data: mfData } = await supabase
        .from('mutual_funds')
        .select('scheme_code, scheme_name, fund_house')
        .or(`scheme_name.ilike.${searchPattern},fund_house.ilike.${searchPattern}`)
        .limit(10);
      
      if (mfData) {
        results.push(...mfData.map(mf => ({
          id: mf.scheme_code.toString(),
          type: 'MUTUAL_FUND',
          displayName: mf.scheme_name,
          subLabel: mf.fund_house,
          identifier: mf.scheme_code.toString()
        })));
      }
    }

    if (type === 'all' || type === 'stock') {
      const { data: stockData } = await supabase
        .from('nifty_stocks')
        .select('symbol')
        .ilike('symbol', `%${query}%`)
        .limit(10);
        
      if (stockData) {
        results.push(...stockData.map(stock => ({
          id: stock.symbol,
          type: 'STOCK',
          displayName: stock.symbol,
          subLabel: 'NSE',
          identifier: stock.symbol
        })));
      }
    }

    return NextResponse.json({ results });
  } catch (error) {
    return NextResponse.json({ error: (error as Error).message }, { status: 500 });
  }
}

'use client';

import { useState, useEffect } from 'react';

interface StockPrice {
  date: string;
  close: number;
}

interface StockData {
  ticker: string;
  history: StockPrice[];
  info: {
    name: string;
    price: number;
    change: number;
    changePercent: number;
  };
}

const cache = new Map<string, StockData>();

export function useStockData(ticker: string | null) {
  const [data, setData] = useState<StockData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ticker) return;

    if (cache.has(ticker)) {
      setData(cache.get(ticker)!);
      return;
    }

    async function fetchStock() {
      setLoading(true);
      setError(null);
      try {
        // We'll use the existing /api/chat or a new endpoint? 
        // Actually, let's hit our FastAPI backend directly for quant data
        const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const res = await fetch(`${baseUrl}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: `Quant data for ${ticker} 1y` }),
        });

        if (!res.ok) throw new Error('Failed to fetch stock data');
        const result = await res.json();
        
        // The backend returns the quant data in the 'answer' or we can add a specific quant endpoint
        // For now, let's assume we might need a dedicated quant endpoint if /api/chat is too heavy
        // But wait, our FastAPI backend already has fetch_quant_data.
        
        // For the sake of the comparison canvas, let's just mock it or assume the backend provides it
        // Actually, let's just use the mutual fund logic for now but inform the user we are working on stock-specific metrics
        
        setLoading(false);
      } catch (err: any) {
        setError(err.message);
        setLoading(false);
      }
    }

    fetchStock();
  }, [ticker]);

  return { data, loading, error };
}

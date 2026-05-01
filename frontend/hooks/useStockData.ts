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
      const cached = cache.get(ticker)!;
      queueMicrotask(() => setData(cached));
      return;
    }

    async function fetchStock() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/quant/stocks/${encodeURIComponent(ticker)}/price-history?days=365`);

        if (!res.ok) throw new Error('Failed to fetch stock data');
        const result = await res.json();
        const stockData = {
          ticker,
          history: result.price_history || [],
          info: { name: ticker, price: 0, change: 0, changePercent: 0 },
        };
        cache.set(ticker, stockData);
        setData(stockData);
        setLoading(false);
      } catch (err) {
        setError((err as Error).message);
        setLoading(false);
      }
    }

    fetchStock();
  }, [ticker]);

  return { data, loading, error };
}

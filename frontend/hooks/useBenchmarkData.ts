'use client';

import { useState, useEffect } from 'react';

export interface BenchmarkPoint {
  date: string; // DD-MM-YYYY
  close: number;
}

let cachedData: BenchmarkPoint[] | null = null;
let pendingRequest: Promise<BenchmarkPoint[]> | null = null;

export function useBenchmarkData() {
  const [data, setData] = useState<BenchmarkPoint[] | null>(cachedData);
  const [loading, setLoading] = useState<boolean>(!cachedData);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (cachedData) return;

    if (!pendingRequest) {
      pendingRequest = fetch('https://query1.finance.yahoo.com/v8/finance/chart/^NSEI?interval=1d&range=5y')
        .then(res => {
          if (!res.ok) throw new Error('Failed to fetch benchmark data');
          return res.json();
        })
        .then(json => {
          const result = json.chart.result[0];
          const timestamps = result.timestamp;
          const closes = result.indicators.quote[0].close;

          const points: BenchmarkPoint[] = [];
          for (let i = 0; i < timestamps.length; i++) {
            if (closes[i] === null || closes[i] === undefined) continue;
            
            const date = new Date(timestamps[i] * 1000);
            const day = String(date.getDate()).padStart(2, '0');
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const year = date.getFullYear();
            
            points.push({
              date: `${day}-${month}-${year}`,
              close: closes[i]
            });
          }
          cachedData = points;
          return points;
        });
    }

    pendingRequest
      .then(points => {
        setData(points);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
        pendingRequest = null; // Reset on failure
      });
  }, []);

  return { data, loading, error };
}

import { useState, useEffect } from 'react';
import { NavPoint } from '../types/funds';

let cachedBenchmarkData: NavPoint[] | null = null;
let fetchPromise: Promise<NavPoint[]> | null = null;

export function useBenchmarkData() {
  const [data, setData] = useState<NavPoint[] | null>(cachedBenchmarkData);
  const [loading, setLoading] = useState(!cachedBenchmarkData);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (cachedBenchmarkData) {
      setData(cachedBenchmarkData);
      setLoading(false);
      return;
    }

    if (!fetchPromise) {
      fetchPromise = fetch('https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1d&range=5y')
        .then(res => {
          if (!res.ok) throw new Error('Failed to fetch benchmark');
          return res.json();
        })
        .then(json => {
          const result = json.chart.result[0];
          const timestamps = result.timestamp;
          const closes = result.indicators.quote[0].close;
          
          const points: NavPoint[] = [];
          for (let i = 0; i < timestamps.length; i++) {
            if (closes[i] !== null && closes[i] !== undefined) {
              const d = new Date(timestamps[i] * 1000);
              const dateStr = `${d.getDate().toString().padStart(2, '0')}-${(d.getMonth() + 1).toString().padStart(2, '0')}-${d.getFullYear()}`;
              points.push({ date: dateStr, nav: closes[i].toString() });
            }
          }
          cachedBenchmarkData = points.reverse(); // newest-first
          return cachedBenchmarkData;
        });
    }

    fetchPromise
      .then(res => {
        setData(res);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return { data, loading, error };
}

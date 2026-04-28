import { useState, useEffect } from 'react';
import { FundDataResponse } from '../types/funds';

const globalCache = new Map<string, FundDataResponse>();
const pendingRequests = new Map<string, Promise<FundDataResponse>>();

export function useFundData(schemeCode: string | null) {
  const [data, setData] = useState<FundDataResponse | null>(schemeCode ? (globalCache.get(schemeCode) || null) : null);
  const [loading, setLoading] = useState<boolean>(schemeCode ? !globalCache.has(schemeCode) : false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!schemeCode) return;

    if (globalCache.has(schemeCode)) {
      setData(globalCache.get(schemeCode)!);
      setLoading(false);
      return;
    }

    let isMounted = true;
    setData(null);
    setLoading(true);
    setError(null);

    if (!pendingRequests.has(schemeCode)) {
      const p = fetch(`/api/mf/${schemeCode}`)
        .then(async res => {
          if (!res.ok) {
            const body = await res.text();
            try {
              const parsed = JSON.parse(body);
              const message = parsed?.detail || parsed?.error || `Failed to fetch data for ${schemeCode}`;
              throw new Error(message);
            } catch {
              throw new Error(body || `Failed to fetch data for ${schemeCode}`);
            }
          }
          return res.json();
        })
        .then((json: any) => {
          if (!json?.details || !Array.isArray(json?.chartData)) {
            throw new Error(`Failed to fetch data for ${schemeCode}`);
          }

          // Map local API response to existing FundDataResponse type
          const formatted: FundDataResponse = {
            meta: {
              fund_house: json.details.fund_house,
              scheme_type: json.details.category,
              scheme_category: json.details.sub_category,
              scheme_code: json.details.scheme_code,
              scheme_name: json.details.scheme_name
            },
            data: json.chartData.map((d: any) => ({
              date: d.date,
              nav: d.value.toString()
            })),
            status: 'ok'
          };
          globalCache.set(schemeCode, formatted);
          return formatted;
        })
        .finally(() => {
          pendingRequests.delete(schemeCode);
        });
      pendingRequests.set(schemeCode, p);
    }

    pendingRequests.get(schemeCode)!
      .then(json => {
        if (isMounted) {
          setData(json);
          setLoading(false);
        }
      })
      .catch(err => {
        if (isMounted) {
          setError(err?.message || `Failed to fetch data for ${schemeCode}`);
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [schemeCode]);

  return { 
    navData: data?.data || null, 
    meta: data?.meta || null, 
    loading, 
    error 
  };
}

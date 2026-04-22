import { useState, useEffect } from 'react';
import { FundDataResponse } from '../types/funds';

const globalCache = new Map<string, FundDataResponse>();
const pendingRequests = new Map<string, Promise<FundDataResponse>>();

export function useFundData(schemeCode: string) {
  const [data, setData] = useState<FundDataResponse | null>(globalCache.get(schemeCode) || null);
  const [loading, setLoading] = useState<boolean>(!globalCache.has(schemeCode));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!schemeCode) return;

    if (globalCache.has(schemeCode)) {
      setData(globalCache.get(schemeCode)!);
      setLoading(false);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    if (!pendingRequests.has(schemeCode)) {
      const p = fetch(`https://api.mfapi.in/mf/${schemeCode}`)
        .then(res => {
          if (!res.ok) throw new Error(`Failed to fetch data for ${schemeCode}`);
          return res.json();
        })
        .then((json: FundDataResponse) => {
          globalCache.set(schemeCode, json);
          return json;
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
          setError(err.message);
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

'use client';

import { useState } from 'react';
import { useFundData } from '../../hooks/useFundData';
import FundComparisonChart, { Period } from '../funds/FundComparisonChart';
import FundDetailsPanel from '../funds/FundDetailsPanel';

type MetricValue = string | number | null | undefined;
type ComparisonMetric = Record<string, MetricValue>;
type AuxiliaryData = {
  quant_data?: {
    comparison?: Record<string, ComparisonMetric>;
  };
};

interface Props {
  ids: string[];
  type: 'STOCK' | 'MUTUAL_FUND';
  auxiliaryData?: AuxiliaryData | null;
}

const formatValue = (value: MetricValue) => {
  if (value === null || value === undefined || value === '' || value === 'N/A') return 'N/A';
  if (typeof value === 'number') return Number.isInteger(value) ? value.toLocaleString('en-IN') : value.toLocaleString('en-IN', { maximumFractionDigits: 2 });
  return value;
};

const formatMarketCap = (value: MetricValue) => {
  if (value === null || value === undefined || value === '' || value === 'N/A') return 'N/A';
  const amount = Number(value);
  if (!Number.isFinite(amount)) return String(value);
  if (amount >= 1_00_00_00_00_000) return `₹${(amount / 1_00_00_00_00_000).toFixed(2)} lakh crore`;
  if (amount >= 1_00_00_000) return `₹${(amount / 1_00_00_000).toFixed(2)} crore`;
  return `₹${amount.toLocaleString('en-IN')}`;
};

const formatPrice = (value: MetricValue) => {
  if (value === null || value === undefined || value === '' || value === 'N/A') return 'N/A';
  const amount = Number(value);
  if (!Number.isFinite(amount)) return String(value);
  return `₹${amount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
};

const formatPercent = (value: MetricValue) => {
  if (value === null || value === undefined || value === '' || value === 'N/A') return 'N/A';
  if (typeof value === 'string' && value.endsWith('%')) return value;
  const amount = Number(value);
  if (!Number.isFinite(amount)) return String(value);
  return `${amount.toFixed(2)}%`;
};

const formatTechnicalRating = (value: MetricValue) => {
  if (value === null || value === undefined || value === '' || value === 'N/A') return 'N/A';
  const text = String(value).trim().toLowerCase();
  const ratings: Record<string, string> = {
    'strong buy': 'Strong positive technical rating',
    buy: 'Positive technical rating',
    sell: 'Negative technical rating',
    'strong sell': 'Strong negative technical rating',
  };
  return ratings[text] || String(value);
};

export default function ComparisonView({ ids, type, auxiliaryData }: Props) {
  const [period, setPeriod] = useState<Period>('1Y');

  // Heuristic: if IDs are numeric, they are mutual fund scheme codes
  const idA = ids?.[0] || null;
  const idB = ids?.[1] || null;
  const isMF = type === 'MUTUAL_FUND' || Boolean(idA && /^[0-9]+$/.test(idA));

  const fundA = useFundData(isMF ? idA : null);
  const fundB = useFundData(isMF ? idB : null);

  if (!ids || ids.length < 2) {
    return <div className="p-6 text-gray-400">Insufficient data for comparison.</div>;
  }

  if (!isMF) {
    const comparison = auxiliaryData?.quant_data?.comparison || {};
    const entities = Object.keys(comparison);
    const metrics: Array<[string, keyof ComparisonMetric, (value: MetricValue) => string]> = [
      ['Price', 'price', formatPrice],
      ['Change', 'change_pct', formatPercent],
      ['P/E Ratio', 'pe_ratio', formatValue],
      ['Market Cap', 'market_cap', formatMarketCap],
      ['Beta', 'beta', formatValue],
      ['Alpha vs Nifty', 'alpha_vs_nifty', formatPercent],
      ['RSI (14D)', 'rsi_14d', formatValue],
      ['Technical Rating', 'tv_recommendation', formatTechnicalRating],
    ];

    return (
      <div className="comparison-detail p-6 bg-[var(--panel-bg)] rounded-2xl h-full flex flex-col border border-white/10 text-white overflow-hidden shadow-2xl">
        <div className="mb-6 px-2">
          <h2 className="text-2xl font-bold text-white tracking-tight">Stock Comparison</h2>
          <p className="text-sm text-gray-400 mt-1">Structured metrics from the latest MarketMind response</p>
        </div>
        <div className="overflow-auto rounded-xl border border-white/10">
          <table className="w-full min-w-[560px] border-collapse text-sm">
            <thead className="bg-white/5 text-gray-300">
              <tr>
                <th className="px-4 py-3 text-left font-semibold">Metric</th>
                {entities.map(entity => (
                  <th key={entity} className="px-4 py-3 text-left font-semibold">{entity}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metrics.map(([label, key, formatter]) => (
                <tr key={label} className="border-t border-white/10">
                  <td className="px-4 py-3 text-gray-400">{label}</td>
                  {entities.map(entity => (
                    <td key={`${entity}-${label}`} className="px-4 py-3 text-white">
                      {formatter(comparison[entity]?.[key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  const loading = fundA.loading || fundB.loading;
  const error = fundA.error || fundB.error;
  const periods: Period[] = ['1D', '6M', '1Y', '3Y', '5Y'];

  return (
    <div className="comparison-detail p-6 bg-[var(--panel-bg)] rounded-2xl h-full flex flex-col border border-white/10 text-white overflow-hidden shadow-2xl">
      <div className="mb-8 flex justify-between items-center px-4">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Mutual Fund Comparison</h2>
          <p className="text-sm text-gray-400 mt-1">Analyzing performance and risk metrics head-to-head</p>
        </div>

        <div className="flex bg-[#1f2833] rounded-lg p-1.5 border border-white/10 shadow-inner gap-1.5">
          {periods.map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-4 py-2 text-xs font-medium rounded-md transition-all duration-200 ${period === p ? 'bg-[var(--accent-color)] text-black shadow-lg scale-105 font-bold' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="flex-1 flex flex-col items-center justify-center space-y-4">
          <div className="w-12 h-12 border-4 border-[var(--accent-color)] border-t-transparent rounded-full animate-spin"></div>
          <p className="text-[var(--accent-color)] font-medium">Fetching real-time NAV data...</p>
        </div>
      )}

      {error && (
        <div className="flex-1 flex flex-col items-center justify-center p-8 bg-red-500/10 rounded-xl border border-red-500/20 mx-4">
          <svg className="w-12 h-12 text-red-500 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <p className="text-red-400 text-center font-medium">{error}</p>
          <button 
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-colors"
          >
            Retry Connection
          </button>
        </div>
      )}
      
      {!loading && !error && fundA.meta && fundB.meta && (
        <div className="flex-1 overflow-y-auto px-4 custom-scroll space-y-10 pb-12">
          <section className="animate-in fade-in slide-in-from-bottom-4 duration-500 bg-black/10 rounded-2xl p-6 border border-white/5">
            <FundComparisonChart 
              schemeCodeA={ids[0]} 
              schemeCodeB={ids[1]} 
              nameA={fundA.meta.scheme_name} 
              nameB={fundB.meta.scheme_name} 
              period={period}
            />
          </section>

          <section className="animate-in fade-in slide-in-from-bottom-6 duration-700 delay-200">
            <div className="pt-6 border-t border-white/10">
              <FundDetailsPanel 
                schemeCodeA={ids[0]} 
                schemeCodeB={ids[1]} 
              />
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

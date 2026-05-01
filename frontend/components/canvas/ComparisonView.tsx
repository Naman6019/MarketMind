'use client';

import { useEffect, useState } from 'react';
import { useFundData } from '../../hooks/useFundData';
import FundComparisonChart, { Period } from '../funds/FundComparisonChart';
import FundDetailsPanel from '../funds/FundDetailsPanel';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

type MetricValue = string | number | null | undefined;
type FundamentalMetric = Record<string, MetricValue>;
type ComparisonMetric = Record<string, unknown>;
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
  if (value === null || value === undefined || value === '' || value === 'N/A') return 'Unavailable';
  if (typeof value === 'number') return Number.isInteger(value) ? value.toLocaleString('en-IN') : value.toLocaleString('en-IN', { maximumFractionDigits: 2 });
  return value;
};

const formatMarketCap = (value: MetricValue) => {
  if (value === null || value === undefined || value === '' || value === 'N/A') return 'Unavailable';
  const amount = Number(value);
  if (!Number.isFinite(amount)) return String(value);
  if (amount >= 1_00_00_00_00_000) return `₹${(amount / 1_00_00_00_00_000).toFixed(2)} lakh crore`;
  if (amount >= 1_00_00_000) return `₹${(amount / 1_00_00_000).toFixed(2)} crore`;
  return `₹${amount.toLocaleString('en-IN')}`;
};

const formatPrice = (value: MetricValue) => {
  if (value === null || value === undefined || value === '' || value === 'N/A') return 'Unavailable';
  const amount = Number(value);
  if (!Number.isFinite(amount)) return String(value);
  return `₹${amount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
};

const formatPercent = (value: MetricValue) => {
  if (value === null || value === undefined || value === '' || value === 'N/A') return 'Unavailable';
  if (typeof value === 'string' && value.endsWith('%')) return value;
  const amount = Number(value);
  if (!Number.isFinite(amount)) return String(value);
  return `${amount.toFixed(2)}%`;
};

const formatRatioPercent = (value: MetricValue) => {
  if (value === null || value === undefined || value === '' || value === 'N/A') return 'Unavailable';
  if (typeof value === 'string' && value.endsWith('%')) return value;
  const amount = Number(value);
  if (!Number.isFinite(amount)) return String(value);
  const percent = Math.abs(amount) <= 1 ? amount * 100 : amount;
  return `${percent.toFixed(2)}%`;
};

const formatTechnicalRating = (value: MetricValue) => {
  if (value === null || value === undefined || value === '' || value === 'N/A') return 'Unavailable';
  const text = String(value).trim().toLowerCase();
  const ratings: Record<string, string> = {
    'strong buy': 'Strong positive technical rating',
    buy: 'Positive technical rating',
    sell: 'Negative technical rating',
    'strong sell': 'Strong negative technical rating',
  };
  return ratings[text] || String(value);
};

const metricValue = (data: ComparisonMetric | undefined, key: string): MetricValue => {
  if (!data) return undefined;
  if (!key.includes('.')) return data[key] as MetricValue;
  const [parent, child] = key.split('.');
  const nested = data[parent];
  if (nested && typeof nested === 'object') return (nested as FundamentalMetric)[child];
  return undefined;
};

const metricNumber = (data: ComparisonMetric | undefined, key: string) => {
  const value = metricValue(data, key);
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
};

const chartRows = (
  comparison: Record<string, ComparisonMetric>,
  metrics: Array<[string, string]>,
) => {
  return metrics.map(([label, key]) => {
    const row: Record<string, string | number | null> = { metric: label };
    Object.entries(comparison).forEach(([entity, data]) => {
      row[entity] = metricNumber(data, key);
    });
    return row;
  });
};

const buildPriceRows = (comparison: Record<string, ComparisonMetric>) => {
  const byDate = new Map<string, Record<string, string | number | null>>();

  Object.entries(comparison).forEach(([entity, data]) => {
    const history = data.price_history;
    if (!Array.isArray(history)) return;

    history.slice(-180).forEach((point) => {
      if (!point || typeof point !== 'object') return;
      const row = point as Record<string, unknown>;
      const date = String(row.date || '');
      const close = Number(row.close);
      if (!date || !Number.isFinite(close)) return;
      const existing = byDate.get(date) || { date };
      existing[entity] = close;
      byDate.set(date, existing);
    });
  });

  return Array.from(byDate.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)));
};

export default function ComparisonView({ ids, type, auxiliaryData }: Props) {
  const [period, setPeriod] = useState<Period>('1Y');

  // Heuristic: if IDs are numeric, they are mutual fund scheme codes
  const idA = ids?.[0] || null;
  const idB = ids?.[1] || null;
  const isMF = type === 'MUTUAL_FUND' || Boolean(idA && /^[0-9]+$/.test(idA));

  const fundA = useFundData(isMF ? idA : null);
  const fundB = useFundData(isMF ? idB : null);
  const [fetchedComparison, setFetchedComparison] = useState<Record<string, ComparisonMetric>>({});
  const [stockError, setStockError] = useState<string | null>(null);

  useEffect(() => {
    const hasAuxComparison = Boolean(auxiliaryData?.quant_data?.comparison);
    if (isMF || hasAuxComparison || ids.length < 2) return;

    let cancelled = false;
    const symbols = ids.map(id => encodeURIComponent(id)).join(',');

    fetch(`/api/quant/stocks/compare?symbols=${symbols}`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to load stock comparison');
        return res.json();
      })
      .then(data => {
        if (!cancelled) setFetchedComparison(data.comparison || {});
      })
      .catch(error => {
        if (!cancelled) setStockError((error as Error).message);
      });

    return () => {
      cancelled = true;
    };
  }, [auxiliaryData, ids, isMF]);

  if (!ids || ids.length < 2) {
    return <div className="p-6 text-gray-400">Insufficient data for comparison.</div>;
  }

  if (!isMF) {
    const comparison = auxiliaryData?.quant_data?.comparison || fetchedComparison;
    const entities = Object.keys(comparison);
    const metrics: Array<[string, string, (value: MetricValue) => string]> = [
      ['Price', 'price', formatPrice],
      ['Change', 'change_pct', formatPercent],
      ['P/E Ratio', 'pe_ratio', formatValue],
      ['Market Cap', 'market_cap', formatMarketCap],
      ['Beta', 'beta', formatValue],
      ['Alpha vs Nifty', 'alpha_vs_nifty', formatPercent],
      ['RSI (14D)', 'rsi_14d', formatValue],
      ['Technical Rating', 'tv_recommendation', formatTechnicalRating],
      ['Industry', 'fundamentals.industry', formatValue],
      ['PB Ratio', 'fundamentals.pb', formatValue],
      ['EV / EBITDA', 'fundamentals.ev_ebitda', formatValue],
      ['ROE', 'fundamentals.roe', formatRatioPercent],
      ['ROCE', 'fundamentals.roce', formatRatioPercent],
      ['Debt to Equity', 'fundamentals.debt_to_equity', formatValue],
      ['Dividend Yield', 'fundamentals.dividend_yield', formatRatioPercent],
      ['EPS TTM', 'fundamentals.eps_ttm', formatPrice],
      ['Sales Growth (3Y)', 'fundamentals.sales_growth_3y', formatRatioPercent],
      ['Profit Growth (3Y)', 'fundamentals.profit_growth_3y', formatRatioPercent],
      ['EPS Growth (3Y)', 'fundamentals.eps_growth_3y', formatRatioPercent],
      ['Latest Quarterly Revenue', 'fundamentals.revenue_qtr', formatValue],
      ['Latest Quarterly Net Profit', 'fundamentals.net_profit_qtr', formatValue],
      ['Promoter Holding', 'fundamentals.promoter_holding', formatRatioPercent],
      ['FII Holding', 'fundamentals.fii_holding', formatRatioPercent],
      ['DII Holding', 'fundamentals.dii_holding', formatRatioPercent],
      ['Data Source', 'fundamentals.source', formatValue],
    ];
    const colors = ['#5eead4', '#60a5fa', '#f97316', '#a78bfa'];
    const hasFundamentals = entities.some(entity => {
      const fundamentals = comparison[entity]?.fundamentals as FundamentalMetric | undefined;
      return fundamentals && Object.values(fundamentals).some(value => value !== null && value !== undefined && value !== '');
    });
    const valuationRows = chartRows(comparison, [['PE', 'pe_ratio'], ['PB', 'fundamentals.pb'], ['EV/EBITDA', 'fundamentals.ev_ebitda'], ['Div Yield', 'fundamentals.dividend_yield']]);
    const quarterlyRows = chartRows(comparison, [['Revenue Qtr', 'fundamentals.revenue_qtr'], ['NP Qtr', 'fundamentals.net_profit_qtr']]);
    const qualityRows = chartRows(comparison, [['ROCE', 'fundamentals.roce'], ['ROE', 'fundamentals.roe']]);
    const growthRows = chartRows(comparison, [['Sales 3Y', 'fundamentals.sales_growth_3y'], ['Profit 3Y', 'fundamentals.profit_growth_3y'], ['EPS 3Y', 'fundamentals.eps_growth_3y']]);
    const holdingRows = chartRows(comparison, [['Promoter', 'fundamentals.promoter_holding'], ['FII', 'fundamentals.fii_holding'], ['DII', 'fundamentals.dii_holding']]);
    const priceRows = buildPriceRows(comparison);

    const renderBarChart = (title: string, rows: Record<string, string | number | null>[], suffix = '%') => (
      <section className="rounded-xl border border-white/10 bg-black/10 p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-200">{title}</h3>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis dataKey="metric" stroke="#9ca3af" fontSize={12} />
              <YAxis stroke="#9ca3af" fontSize={12} tickFormatter={(value) => `${value}${suffix}`} />
              <Tooltip
                cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                contentStyle={{ background: '#111827', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8, color: '#fff' }}
                formatter={(value) => {
                  const formatted = formatValue(value as MetricValue);
                  return [formatted === 'Unavailable' ? formatted : `${formatted}${suffix}`, ''];
                }}
              />
              {entities.map((entity, index) => (
                <Bar key={entity} dataKey={entity} fill={colors[index % colors.length]} radius={[4, 4, 0, 0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    );

    return (
      <div className="comparison-detail p-3 sm:p-6 bg-[var(--panel-bg)] rounded-xl sm:rounded-2xl h-full flex flex-col border border-white/10 text-white overflow-hidden shadow-2xl">
        <div className="mb-6 px-2">
          <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">Premium Stock Comparison</h2>
          <p className="text-sm text-gray-400 mt-1">
            Price, risk, and source-neutral fundamentals from MarketMind data
          </p>
        </div>
        <div className="custom-scroll flex-1 space-y-5 overflow-y-auto pr-2">
          {priceRows.length > 0 && (
            <section className="rounded-xl border border-white/10 bg-black/10 p-4">
              <h3 className="mb-3 text-sm font-semibold text-gray-200">Price History</h3>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={priceRows}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                    <XAxis dataKey="date" stroke="#9ca3af" fontSize={12} />
                    <YAxis stroke="#9ca3af" fontSize={12} />
                    <Tooltip contentStyle={{ background: '#111827', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8, color: '#fff' }} />
                    {entities.map((entity, index) => (
                      <Line key={entity} type="monotone" dataKey={entity} stroke={colors[index % colors.length]} strokeWidth={2} dot={false} connectNulls />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}
          {hasFundamentals && (
            <div className="grid gap-4 xl:grid-cols-2">
              {renderBarChart('Valuation Metrics', valuationRows, '')}
              {renderBarChart('Latest Quarterly Revenue and Profit', quarterlyRows, '')}
              {renderBarChart('Quality Metrics', qualityRows)}
              {renderBarChart('Growth Metrics', growthRows)}
              {renderBarChart('Shareholding Mix', holdingRows)}
              {renderBarChart('Debt to Equity', chartRows(comparison, [['Debt/Equity', 'fundamentals.debt_to_equity']]), '')}
            </div>
          )}
          {!hasFundamentals && (
            <div className="rounded-xl border border-amber-400/20 bg-amber-400/10 p-4 text-sm text-amber-100">
              {stockError || 'Fundamentals are unavailable because no fundamentals provider has supplied these fields yet.'}
            </div>
          )}
          <div className="overflow-auto rounded-xl border border-white/10">
            <table className="w-full min-w-[720px] border-collapse text-sm">
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
                        {formatter(metricValue(comparison[entity], key))}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  const loading = fundA.loading || fundB.loading;
  const error = fundA.error || fundB.error;
  const periods: Period[] = ['1D', '6M', '1Y', '3Y', '5Y'];

  return (
    <div className="comparison-detail p-3 sm:p-6 bg-[var(--panel-bg)] rounded-xl sm:rounded-2xl h-full flex flex-col border border-white/10 text-white overflow-hidden shadow-2xl">
      <div className="mb-5 flex flex-col gap-4 px-1 sm:mb-8 sm:flex-row sm:items-center sm:justify-between sm:px-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight sm:text-2xl">Mutual Fund Comparison</h2>
          <p className="text-sm text-gray-400 mt-1">Analyzing performance and risk metrics head-to-head</p>
        </div>

        <div className="flex max-w-full overflow-x-auto bg-[#1f2833] rounded-lg p-1.5 border border-white/10 shadow-inner gap-1.5">
          {periods.map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`shrink-0 px-3 py-2 text-xs font-medium rounded-md transition-all duration-200 sm:px-4 ${period === p ? 'bg-[var(--accent-color)] text-black shadow-lg scale-105 font-bold' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
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
        <div className="flex-1 overflow-y-auto px-1 custom-scroll space-y-6 pb-8 sm:space-y-10 sm:px-4 sm:pb-12">
          <section className="animate-in fade-in slide-in-from-bottom-4 duration-500 bg-black/10 rounded-xl p-3 border border-white/5 sm:rounded-2xl sm:p-6">
            <FundComparisonChart 
              schemeCodeA={ids[0]} 
              schemeCodeB={ids[1]} 
              nameA={fundA.meta.scheme_name} 
              nameB={fundB.meta.scheme_name} 
              period={period}
            />
          </section>

          <section className="animate-in fade-in slide-in-from-bottom-6 duration-700 delay-200">
            <div className="pt-4 border-t border-white/10 sm:pt-6">
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

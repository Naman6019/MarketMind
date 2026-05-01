'use client';

import { useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, type TooltipContentProps, type TooltipValueType } from 'recharts';
import { useFundData } from '../../hooks/useFundData';
import { filterByPeriod, normalizeTo100, downsample } from '../../lib/fundDataUtils';
import type { NavPoint } from '../../types/funds';

export type Period = '1D' | '6M' | '1Y' | '3Y' | '5Y';

interface Props {
  schemeCodeA: string;
  schemeCodeB: string;
  nameA: string;
  nameB: string;
  period: Period;
}

type ChartTooltipPayload = {
  dataKey?: string | number;
  value?: number;
  payload?: {
    actualA?: number;
    actualB?: number;
  };
};

type ChartDatum = {
  date: string;
  assetA?: number;
  assetB?: number;
  actualA?: number;
  actualB?: number;
};

export default function FundComparisonChart({ schemeCodeA, schemeCodeB, nameA, nameB, period }: Props) {
  const fundA = useFundData(schemeCodeA);
  const fundB = useFundData(schemeCodeB);

  const loading = fundA.loading || fundB.loading;
  const error = fundA.error || fundB.error;

  const chartData = useMemo(() => {
    if (!fundA.navData || !fundB.navData) return [];
    if (period === '1D') return [];

    const fA = filterByPeriod(fundA.navData, period);
    const fB = filterByPeriod(fundB.navData, period);

    const normA = normalizeTo100(fA);
    const normB = normalizeTo100(fB);

    // Merge by date
    const map = new Map<string, ChartDatum>();
    normA.forEach(d => {
      map.set(d.date, { date: d.date, assetA: d.normalized, actualA: parseFloat(d.nav) });
    });
    normB.forEach(d => {
      const existing = map.get(d.date);
      if (existing) {
        map.set(d.date, { ...existing, assetB: d.normalized, actualB: parseFloat(d.nav) });
      } else {
        map.set(d.date, { date: d.date, assetB: d.normalized, actualB: parseFloat(d.nav) });
      }
    });

    let merged = Array.from(map.values()).sort((a, b) => {
      const d1 = new Date(a.date.split('-').reverse().join('-')).getTime();
      const d2 = new Date(b.date.split('-').reverse().join('-')).getTime();
      return d1 - d2;
    });

    if (period === '3Y' || period === '5Y') {
      merged = downsample(merged, 300);
    }

    return merged;
  }, [fundA.navData, fundB.navData, period]);

  const oneDayStats = useMemo(() => {
    if (period !== '1D' || !fundA.navData || !fundB.navData) return null;
    const calc1D = (data: NavPoint[]) => {
      if (data.length < 2) return null;
      const latest = parseFloat(data[0].nav);
      const prev = parseFloat(data[1].nav);
      return ((latest / prev) - 1) * 100;
    };
    return {
      a: calc1D(fundA.navData),
      b: calc1D(fundB.navData)
    };
  }, [fundA.navData, fundB.navData, period]);

  if (loading) {
    return (
      <div className="h-[320px] w-full flex items-center justify-center bg-black/20 rounded-xl border border-white/5 animate-pulse">
        <div className="text-[var(--accent-color)] text-sm">Loading chart data...</div>
      </div>
    );
  }

  if (error) {
    return <div className="text-red-400 text-sm">Failed to load chart: {error}</div>;
  }

  const renderTooltip = ({ active, payload, label }: TooltipContentProps<TooltipValueType, string | number>) => {
    if (!active || !payload?.length) return null;

    return (
      <div className="max-w-[min(78vw,320px)] rounded-lg border border-white/10 bg-[#0b0c10]/95 p-3 text-xs shadow-xl">
        <div className="mb-2 text-gray-400">{label}</div>
        <div className="space-y-2">
          {payload.map((entry) => {
            const isFirstFund = entry.dataKey === 'assetA';
            const point = entry.payload as ChartTooltipPayload['payload'] | undefined;
            const actual = isFirstFund ? point?.actualA : point?.actualB;
            const fundName = isFirstFund ? nameA : nameB;
            const value = typeof entry.value === 'number' ? entry.value : null;
            const returnPct = value === null ? null : value - 100;

            return (
              <div key={String(entry.dataKey)} className="min-w-0">
                <div className="truncate font-medium text-white" title={fundName}>{fundName}</div>
                <div className="text-gray-400">
                  NAV: ₹{actual?.toFixed(2) ?? 'N/A'}
                  {returnPct !== null && (
                    <span className={returnPct >= 0 ? 'text-green-400' : 'text-red-400'}>
                      {' '}| {returnPct >= 0 ? '+' : ''}{returnPct.toFixed(2)}%
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="mb-4 mt-2 sm:mb-6 sm:mt-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-300 sm:text-base">Normalized Performance (Rebased to 100)</h3>
      </div>
      
      <div className="h-[260px] w-full bg-black/20 rounded-xl p-2 border border-white/5 relative sm:h-[320px] sm:p-4">
        {period === '1D' && oneDayStats ? (
          <div className="flex h-full items-center justify-center gap-12">
            <div className="text-center">
              <div className="text-sm text-gray-400 mb-2 truncate max-w-[200px]" title={nameA}>{nameA}</div>
              <div className={`text-3xl font-semibold ${oneDayStats.a! >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {oneDayStats.a! > 0 ? '+' : ''}{oneDayStats.a?.toFixed(2)}%
              </div>
              <div className="text-xs text-gray-500 mt-1">1D Change</div>
            </div>
            <div className="w-[1px] h-20 bg-white/10"></div>
            <div className="text-center">
              <div className="text-sm text-gray-400 mb-2 truncate max-w-[200px]" title={nameB}>{nameB}</div>
              <div className={`text-3xl font-semibold ${oneDayStats.b! >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {oneDayStats.b! > 0 ? '+' : ''}{oneDayStats.b?.toFixed(2)}%
              </div>
              <div className="text-xs text-gray-500 mt-1">1D Change</div>
            </div>
          </div>
        ) : chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorA" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.1}/>
                  <stop offset="95%" stopColor="#3B82F6" stopOpacity={0}/>
                </linearGradient>
                <linearGradient id="colorB" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#F97316" stopOpacity={0.1}/>
                  <stop offset="95%" stopColor="#F97316" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis 
                dataKey="date" 
                stroke="#8a9199" 
                fontSize={11} 
                tickLine={false}
                axisLine={false}
                minTickGap={30}
                tickFormatter={(val) => {
                   const d = new Date(val.split('-').reverse().join('-'));
                   return `${d.toLocaleString('default', { month: 'short' })} '${d.getFullYear().toString().substr(-2)}`;
                }} 
              />
              <YAxis 
                stroke="#8a9199" 
                fontSize={11} 
                tickLine={false}
                axisLine={false}
                domain={['auto', 'auto']} 
                tickFormatter={(val) => val.toFixed(0)}
              />
              <Tooltip content={renderTooltip} />
              <Area type="monotone" dataKey="assetA" stroke="none" fill="url(#colorA)" />
              <Area type="monotone" dataKey="assetB" stroke="none" fill="url(#colorB)" />
              <Line type="monotone" dataKey="assetA" stroke="#3B82F6" strokeWidth={2} dot={false} activeDot={{ r: 4, fill: '#3B82F6', stroke: '#fff' }} />
              <Line type="monotone" dataKey="assetB" stroke="#F97316" strokeWidth={2} dot={false} activeDot={{ r: 4, fill: '#F97316', stroke: '#fff' }} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm">No data available for this period.</div>
        )}
      </div>
    </div>
  );
}

'use client';

import { useMemo } from 'react';
import { useFundData } from '../../hooks/useFundData';
import { useBenchmarkData } from '../../hooks/useBenchmarkData';
import { 
  toReturnsArray, 
  computeCAGR, 
  computeReturns, 
  computeBeta, 
  computeAlpha, 
  computeSharpe, 
  computeStdDev 
} from '../../lib/fundMetrics';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip } from 'recharts';
import OverlapBadge from './OverlapBadge';

interface Props {
  schemeCodeA: string;
  schemeCodeB: string;
}

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'];

function MetricCard({ label, value, tooltip }: { label: string, value: string | null, tooltip: string }) {
  return (
    <div className="bg-black/20 rounded-lg p-3 border border-white/5 relative group cursor-help">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className="text-sm font-medium text-white">{value ?? 'N/A'}</div>
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-gray-900 text-xs text-gray-300 rounded shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10 pointer-events-none">
        {tooltip}
        <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900"></div>
      </div>
    </div>
  );
}

function FundColumn({ schemeCode, colorHex }: { schemeCode: string, colorHex: string }) {
  const { navData, meta } = useFundData(schemeCode);
  const benchmark = useBenchmarkData();

  const metrics = useMemo(() => {
    if (!navData) return null;
    
    const returns = computeReturns(navData);
    const cagr1Y = computeCAGR(navData, 1);
    const cagr3Y = computeCAGR(navData, 3);
    const cagr5Y = computeCAGR(navData, 5);

    const dailyReturns = toReturnsArray(navData);
    
    let beta = null;
    let alpha = null;
    
    if (benchmark.data) {
      const benchReturns = toReturnsArray(benchmark.data);
      beta = computeBeta(dailyReturns, benchReturns);
      
      const benchCAGR1Y = computeCAGR(benchmark.data, 1);
      if (cagr1Y !== null && benchCAGR1Y !== null && beta !== null) {
        alpha = computeAlpha(cagr1Y, beta, benchCAGR1Y);
      }
    }

    const sharpe = computeSharpe(dailyReturns);
    const stdDev = computeStdDev(dailyReturns);

    return {
      returns, cagr1Y, cagr3Y, cagr5Y, beta, alpha, sharpe, stdDev
    };
  }, [navData, benchmark.data]);

  if (!navData || !meta || !metrics) {
    return <div className="flex-1 p-4 text-center text-gray-500 animate-pulse">Computing metrics...</div>;
  }

  const latestNav = parseFloat(navData[0].nav).toFixed(4);
  const navDate = navData[0].date;

  const returnRow = (label: string, val: number | null, isCAGR = false) => (
    <div className="flex justify-between items-center py-2 border-b border-white/5 text-sm">
      <span className="text-gray-400">{label}</span>
      <span className={val === null ? 'text-gray-500' : val > 0 ? 'text-green-400' : 'text-red-400'}>
        {val !== null ? `${val > 0 ? '+' : ''}${val.toFixed(2)}%` : 'N/A'}
        {isCAGR && val !== null && <span className="text-[10px] text-gray-500 ml-1">CAGR</span>}
      </span>
    </div>
  );

  // Placeholder data for pie chart since mfapi doesn't provide it
  const placeholderSectors = [
    { name: 'Financials', value: 30 },
    { name: 'IT', value: 20 },
    { name: 'Consumer', value: 15 },
    { name: 'Others', value: 35 }
  ];

  return (
    <div className="flex-1 flex flex-col gap-6 p-4">
      <div className="flex flex-col gap-1">
        <h3 className="text-lg font-semibold truncate" style={{ color: colorHex }} title={meta.scheme_name}>
          {meta.scheme_name}
        </h3>
        <span className="text-xs text-gray-400 bg-white/5 self-start px-2 py-0.5 rounded">
          {meta.scheme_category}
        </span>
      </div>

      <div className="bg-black/20 rounded-xl p-4 border border-white/5">
        <h4 className="text-sm font-medium text-white mb-3">Fund Info</h4>
        <div className="grid grid-cols-2 gap-y-3 gap-x-4 text-sm">
          <div>
            <div className="text-xs text-gray-500">Fund House</div>
            <div className="text-gray-200 truncate" title={meta.fund_house}>{meta.fund_house}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Latest NAV</div>
            <div className="text-gray-200">₹{latestNav} <span className="text-[10px] text-gray-500">({navDate})</span></div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Expense Ratio</div>
            <div className="text-gray-200">N/A</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">AUM</div>
            <div className="text-gray-200">N/A</div>
          </div>
        </div>
      </div>

      <div className="bg-black/20 rounded-xl p-4 border border-white/5">
        <h4 className="text-sm font-medium text-white mb-3">Performance</h4>
        {returnRow('1 Month', metrics.returns['1M'])}
        {returnRow('3 Months', metrics.returns['3M'])}
        {returnRow('6 Months', metrics.returns['6M'])}
        {returnRow('1 Year', metrics.returns['1Y'])}
        {returnRow('3 Years', metrics.cagr3Y, true)}
        {returnRow('5 Years', metrics.cagr5Y, true)}
      </div>

      <div className="bg-black/20 rounded-xl p-4 border border-white/5">
        <h4 className="text-sm font-medium text-white mb-3">Risk Metrics</h4>
        <div className="grid grid-cols-2 gap-3">
          <MetricCard 
            label="Alpha" 
            value={metrics.alpha !== null ? metrics.alpha.toFixed(2) + '%' : null} 
            tooltip="Excess return over benchmark (Nifty 50) for the risk taken. Higher is better." 
          />
          <MetricCard 
            label="Beta" 
            value={metrics.beta !== null ? metrics.beta.toFixed(2) : null} 
            tooltip="Volatility compared to market. >1 means more volatile, <1 means less volatile." 
          />
          <MetricCard 
            label="Sharpe" 
            value={metrics.sharpe !== null ? metrics.sharpe.toFixed(2) : null} 
            tooltip="Risk-adjusted return. Higher indicates better returns per unit of risk." 
          />
          <MetricCard 
            label="Std Dev" 
            value={metrics.stdDev !== null ? metrics.stdDev.toFixed(2) + '%' : null} 
            tooltip="Annualized volatility of daily returns. Lower means less price fluctuation." 
          />
        </div>
      </div>

      <div className="bg-black/20 rounded-xl p-4 border border-white/5 flex flex-col h-[200px]">
        <h4 className="text-sm font-medium text-white mb-1">Sector Allocation</h4>
        <div className="text-xs text-gray-500 mb-2">Holdings updated monthly by AMFI</div>
        <div className="flex-1 relative w-full flex items-center">
          <ResponsiveContainer width="50%" height="100%">
            <PieChart>
              <Pie
                data={placeholderSectors}
                cx="50%"
                cy="50%"
                innerRadius={30}
                outerRadius={45}
                paddingAngle={2}
                dataKey="value"
                stroke="none"
              >
                {placeholderSectors.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <RechartsTooltip 
                contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: '6px' }}
                itemStyle={{ fontSize: '12px', color: '#fff' }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="w-[50%] flex flex-col gap-2 pl-2 overflow-y-auto">
            {placeholderSectors.map((s, i) => (
              <div key={s.name} className="flex items-center gap-2 text-xs">
                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }}></div>
                <span className="text-gray-300 truncate">{s.name}</span>
                <span className="text-gray-500 ml-auto">{s.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function FundDetailsPanel({ schemeCodeA, schemeCodeB }: Props) {
  return (
    <div className="flex flex-col relative w-full">
      <div className="flex flex-col md:flex-row relative">
        <FundColumn schemeCode={schemeCodeA} colorHex="#3B82F6" />
        <div className="hidden md:block w-[1px] bg-white/10 my-4 mx-2"></div>
        <FundColumn schemeCode={schemeCodeB} colorHex="#F97316" />
      </div>
      <div className="w-full flex justify-center mt-[-1rem] z-10">
        <OverlapBadge schemeCodeA={schemeCodeA} schemeCodeB={schemeCodeB} />
      </div>
    </div>
  );
}

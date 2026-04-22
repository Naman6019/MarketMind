'use client';

import { useMemo, useState, useEffect } from 'react';
import { useFundData } from '../../hooks/useFundData';
import { useBenchmarkData } from '../../hooks/useBenchmarkData';
import { 
  toReturnsArray, 
  computeCAGR, 
  computeReturns, 
  computeSharpe, 
  computeStdDev 
} from '../../lib/fundMetrics';
import { 
  calculateBeta, 
  calculateAlpha
} from '../../lib/quantUtils';
import { Info, TrendingUp, ShieldAlert, PieChart } from 'lucide-react';


interface Props {
  schemeCodeA: string;
  schemeCodeB: string;
}

function MetricCard({ label, value, tooltip, icon: Icon }: { label: string, value: string | null, tooltip: string, icon?: any }) {
  return (
    <div className="bg-white/5 hover:bg-white/10 transition-colors rounded-xl p-4 border border-white/10 relative group cursor-help shadow-sm">
      <div className="flex items-center gap-2 mb-2">
        {Icon && <Icon size={14} className="text-[var(--accent-color)]" />}
        <div className="text-xs font-medium text-gray-400 uppercase tracking-wider">{label}</div>
      </div>
      <div className="text-lg font-bold text-white">{value ?? '—'}</div>
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 p-2.5 bg-gray-900 text-xs leading-relaxed text-gray-300 rounded-lg shadow-2xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-20 pointer-events-none border border-white/10">
        {tooltip}
        <div className="absolute top-full left-1/2 -translate-x-1/2 border-8 border-transparent border-t-gray-900"></div>
      </div>
    </div>
  );
}

function FundColumn({ schemeCode, colorHex }: { schemeCode: string, colorHex: string }) {
  const { navData, meta } = useFundData(schemeCode);
  const benchmark = useBenchmarkData();
  const [extraMeta, setExtraMeta] = useState<any>(null);

  useEffect(() => {
    if (!schemeCode) return;
    fetch(`/api/mf/${schemeCode}`)
      .then(res => res.json())
      .then(json => {
        if (json.details) setExtraMeta(json.details);
      })
      .catch(err => console.error("Error fetching extra meta:", err));
  }, [schemeCode]);

  const metrics = useMemo(() => {
    if (!navData) return null;
    
    const returns = computeReturns(navData);
    const cagr1Y = computeCAGR(navData, 1);
    const cagr3Y = computeCAGR(navData, 3);
    const cagr5Y = computeCAGR(navData, 5);

    const dailyReturns = toReturnsArray(navData);
    
    let beta: number | null = null;
    let alpha: number | null = null;
    
    if (benchmark.data && navData.length > 30) {
      const chronologicalFund = [...navData].reverse();
      
      // Date alignment with 1-day tolerance for market holidays/reporting lags
      const benchMap = new Map<string, number>();
      benchmark.data.forEach(d => benchMap.set(d.date, d.close));

      const getBenchPrice = (dateStr: string) => {
        if (benchMap.has(dateStr)) return benchMap.get(dateStr);
        
        // Try adjacent dates (+/- 1 day)
        const [d, m, y] = dateStr.split('-').map(Number);
        const date = new Date(Date.UTC(y, m - 1, d));
        
        for (let offset = -1; offset <= 1; offset++) {
          if (offset === 0) continue;
          const adj = new Date(date);
          adj.setUTCDate(date.getUTCDate() + offset);
          const adjStr = `${String(adj.getUTCDate()).padStart(2, '0')}-${String(adj.getUTCMonth() + 1).padStart(2, '0')}-${adj.getUTCFullYear()}`;
          if (benchMap.has(adjStr)) return benchMap.get(adjStr);
        }
        return null;
      };

      const alignedFund: number[] = [];
      const alignedBench: number[] = [];
      
      for (let i = 1; i < chronologicalFund.length; i++) {
        const bCurr = getBenchPrice(chronologicalFund[i].date);
        const bPrev = getBenchPrice(chronologicalFund[i-1].date);
        
        if (typeof bCurr === 'number' && typeof bPrev === 'number') {
          const fundRet = (parseFloat(chronologicalFund[i].nav) / parseFloat(chronologicalFund[i-1].nav)) - 1;
          const benchRet = (bCurr / bPrev) - 1;
          alignedFund.push(fundRet);
          alignedBench.push(benchRet);
        }
      }

      if (alignedFund.length > 20) {
        beta = calculateBeta(alignedFund, alignedBench);
        const totalFundRet = alignedFund.reduce((acc, r) => acc * (1 + r), 1);
        const totalBenchRet = alignedBench.reduce((acc, r) => acc * (1 + r), 1);
        const years = alignedFund.length / 252;
        
        if (years > 0.1) {
          const fCAGR = Math.pow(totalFundRet, 1 / years) - 1;
          const bCAGR = Math.pow(totalBenchRet, 1 / years) - 1;
          alpha = calculateAlpha(fCAGR, bCAGR, beta) * 100;
        }
      }
    }

    const sharpe = computeSharpe(dailyReturns);
    const stdDev = computeStdDev(dailyReturns);

    return {
      returns, cagr1Y, cagr3Y, cagr5Y, beta, alpha, sharpe, stdDev
    };
  }, [navData, benchmark.data]);

  if (!navData || !meta || !metrics) {
    return <div className="flex-1 p-8 text-center text-gray-500 animate-pulse flex flex-col items-center justify-center min-h-[400px]">
      <div className="w-8 h-8 border-2 border-white/20 border-t-[var(--accent-color)] rounded-full animate-spin mb-4"></div>
      Crunching numbers...
    </div>;
  }

  const latestNav = parseFloat(navData[0].nav).toFixed(4);
  const navDate = navData[0].date;

  const returnRow = (label: string, val: number | null, isCAGR = false) => (
    <div className="flex justify-between items-center py-3 border-b border-white/5 text-sm hover:bg-white/5 px-2 rounded-lg transition-colors">
      <span className="text-gray-400">{label}</span>
      <span className={`font-medium ${val === null ? 'text-gray-500' : val > 0 ? 'text-green-400' : 'text-red-400'}`}>
        {val !== null ? `${val > 0 ? '+' : ''}${val.toFixed(2)}%` : 'N/A'}
        {isCAGR && val !== null && <span className="text-[10px] text-gray-500 ml-1.5 font-normal opacity-60">CAGR</span>}
      </span>
    </div>
  );

  return (
    <div className="flex-1 flex flex-col gap-8 p-6">
      <div className="flex flex-col gap-2">
        <h3 className="text-xl font-bold truncate group relative cursor-default leading-tight" style={{ color: colorHex }}>
          <span className="truncate block" title={meta.scheme_name}>{meta.scheme_name}</span>
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-widest text-gray-500 bg-white/5 px-2.5 py-1 rounded-full border border-white/10">
            {meta.scheme_category}
          </span>
        </div>
      </div>

      <div className="bg-black/20 rounded-2xl p-6 border border-white/5 shadow-xl">
        <div className="flex items-center gap-2 mb-4">
          <Info size={16} className="text-blue-400" />
          <h4 className="text-sm font-semibold text-white uppercase tracking-wider">Fund Overview</h4>
        </div>
        <div className="grid grid-cols-2 gap-y-5 gap-x-6 text-sm">
          <div className="flex flex-col gap-1">
            <div className="text-[11px] font-medium text-gray-500 uppercase tracking-tight">Fund House</div>
            <div className="text-gray-200 font-medium truncate" title={meta.fund_house}>{meta.fund_house}</div>
          </div>
          <div className="flex flex-col gap-1">
            <div className="text-[11px] font-medium text-gray-500 uppercase tracking-tight">Current NAV</div>
            <div className="text-gray-200 font-medium flex items-baseline gap-1.5">
              ₹{latestNav} 
              <span className="text-[10px] text-gray-500 font-normal">({navDate})</span>
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <div className="text-[11px] font-medium text-gray-500 uppercase tracking-tight flex items-center gap-1.5">
              Expense Ratio
              <Info size={10} className="text-gray-600" />
            </div>
            <div className="text-[var(--accent-color)] font-bold">{extraMeta?.expense_ratio ? `${extraMeta.expense_ratio}%` : '—'}</div>
          </div>
          <div className="flex flex-col gap-1">
            <div className="text-[11px] font-medium text-gray-500 uppercase tracking-tight flex items-center gap-1.5">
              AUM
              <Info size={10} className="text-gray-600" />
            </div>
            <div className="text-white font-bold">{extraMeta?.aum ? `₹${extraMeta.aum} Cr` : '—'}</div>
          </div>
        </div>
      </div>

      <div className="bg-black/20 rounded-2xl p-6 border border-white/5 shadow-xl">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp size={16} className="text-green-400" />
          <h4 className="text-sm font-semibold text-white uppercase tracking-wider">Returns Analysis</h4>
        </div>
        <div className="space-y-1">
          {returnRow('1 Month', metrics.returns['1M'])}
          {returnRow('6 Months', metrics.returns['6M'])}
          {returnRow('1 Year', metrics.returns['1Y'])}
          {returnRow('3 Years', metrics.cagr3Y, true)}
          {returnRow('5 Years', metrics.cagr5Y, true)}
        </div>
      </div>

      <div className="bg-black/20 rounded-2xl p-6 border border-white/5 shadow-xl">
        <div className="flex items-center gap-2 mb-5">
          <ShieldAlert size={16} className="text-red-400" />
          <h4 className="text-sm font-semibold text-white uppercase tracking-wider">Risk Profile</h4>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <MetricCard 
            label="Alpha" 
            value={metrics.alpha !== null ? (metrics.alpha > 0 ? '+' : '') + metrics.alpha.toFixed(2) + '%' : null} 
            tooltip="Excess return over benchmark (Nifty 50). Positive alpha indicates the fund beat the market after adjusting for risk." 
            icon={TrendingUp}
          />
          <MetricCard 
            label="Beta" 
            value={metrics.beta !== null ? metrics.beta.toFixed(2) : null} 
            tooltip="Sensitivity to market moves. Beta of 1.0 means it moves with the market; >1.0 is more volatile." 
            icon={TrendingUp}
          />
          <MetricCard 
            label="Sharpe" 
            value={metrics.sharpe !== null ? metrics.sharpe.toFixed(2) : null} 
            tooltip="Risk-adjusted return. Higher is better, indicating more return per unit of volatility." 
            icon={ShieldAlert}
          />
          <MetricCard 
            label="Volatility" 
            value={metrics.stdDev !== null ? metrics.stdDev.toFixed(2) + '%' : null} 
            tooltip="Annualized Standard Deviation. Measures how much the NAV fluctuates from its average." 
            icon={ShieldAlert}
          />
        </div>
      </div>

      <div className="bg-black/20 rounded-2xl p-6 border border-white/5 shadow-xl">
        <div className="flex items-center gap-2 mb-4">
          <PieChart size={16} className="text-purple-400" />
          <h4 className="text-sm font-semibold text-white uppercase tracking-wider">Portfolio Insights</h4>
        </div>
        <div className="flex flex-col items-center justify-center py-6 text-center">
          <p className="text-gray-500 text-[11px] italic leading-relaxed max-w-[240px]">
            Holdings & sector weights are refreshed monthly from AMFI disclosures.
          </p>
          <div className="mt-4 text-[10px] text-[var(--accent-color)] font-medium bg-[var(--accent-color)]/5 px-3 py-1.5 rounded-lg border border-[var(--accent-color)]/10">
            Full Portfolio Deep-Dive Coming Soon
          </div>
        </div>
      </div>
    </div>
  );
}

export default function FundDetailsPanel({ schemeCodeA, schemeCodeB }: Props) {
  return (
    <div className="flex flex-col relative w-full max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row relative">
        <FundColumn schemeCode={schemeCodeA} colorHex="#3B82F6" />
        <div className="hidden md:flex flex-col items-center justify-center px-2 py-12">
          <div className="w-[1px] h-full bg-gradient-to-b from-transparent via-white/10 to-transparent"></div>
          <div className="my-4 text-[10px] font-bold text-gray-600 bg-black p-1 rounded border border-white/5">VS</div>
          <div className="w-[1px] h-full bg-gradient-to-b from-transparent via-white/10 to-transparent"></div>
        </div>
        <FundColumn schemeCode={schemeCodeB} colorHex="#F97316" />
      </div>
    </div>
  );
}

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
import { useCanvasStore } from '@/store/useCanvasStore';
import { Info, TrendingUp, ShieldAlert, PieChart, Activity, Wallet } from 'lucide-react';


interface Props {
  schemeCodeA: string;
  schemeCodeB: string;
}

function MetricCard({ label, value, tooltip, icon: Icon, subValue }: { label: string, value: string | null, tooltip: string, icon?: any, subValue?: string }) {
  return (
    <div className="bg-white/5 hover:bg-white/10 transition-all duration-300 rounded-2xl p-5 border border-white/10 relative group cursor-help shadow-lg hover:border-[var(--accent-color)]/30">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {Icon && <Icon size={16} className="text-[var(--accent-color)]" />}
          <div className="text-xs font-bold text-gray-400 uppercase tracking-widest">{label}</div>
        </div>
      </div>
      <div className="flex flex-col gap-1">
        <div className="text-2xl font-black text-white tracking-tight">{value ?? '—'}</div>
        {subValue && <div className="text-[10px] text-gray-500 font-medium">{subValue}</div>}
      </div>
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-3 w-64 p-3 bg-[#111] text-xs leading-relaxed text-gray-300 rounded-xl shadow-2xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-30 pointer-events-none border border-white/10 backdrop-blur-md">
        {tooltip}
        <div className="absolute top-full left-1/2 -translate-x-1/2 border-8 border-transparent border-t-[#111]"></div>
      </div>
    </div>
  );
}

function FundColumn({ schemeCode, colorHex }: { schemeCode: string, colorHex: string }) {
  const { navData, meta } = useFundData(schemeCode);
  const benchmark = useBenchmarkData();
  const [extraMeta, setExtraMeta] = useState<any>(null);
  const { auxiliaryData } = useCanvasStore();

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
    let precomputedAum: string | null = null;
    let precomputedExpenseRatio: string | null = null;

    // --- USE PRE-FETCHED DATA FROM CHAT IF AVAILABLE ---
    const comparisonData = auxiliaryData?.quant_data?.comparison ?? auxiliaryData?.comparison;

    if (comparisonData) {
       // Look for this fund in comparison data
       // Names might match partially
       const fundName = meta?.scheme_name?.toLowerCase() || '';
       for (const [key, val] of Object.entries(comparisonData)) {
          const keyLower = key.toLowerCase();
          const data = val as any;
          const backendName = typeof data?.name === 'string' ? data.name.toLowerCase() : '';
          const candidates = [keyLower, backendName].filter(Boolean);

          const isMatch = candidates.some((candidate: string) => {
            const words = candidate.split(/\s+/).filter((w: string) => w.length > 2);
            const isFuzzyMatch = words.length > 0 && words.every((word: string) => fundName.includes(word));
            return isFuzzyMatch || fundName.includes(candidate) || candidate.includes(fundName);
          });

          if (isMatch) {
             if (data.beta && data.beta !== 'N/A') beta = parseFloat(data.beta);
             if (data.alpha_vs_nifty && data.alpha_vs_nifty !== 'N/A') alpha = parseFloat(data.alpha_vs_nifty);
             if (data.aum && data.aum !== 'N/A') precomputedAum = data.aum.toString();
             if (data.expense_ratio && data.expense_ratio !== 'N/A') precomputedExpenseRatio = data.expense_ratio.toString();
          }
       }
    }
    
    // --- FALLBACK TO LOCAL CALCULATION ---
    if ((beta === null || alpha === null) && benchmark.data && navData.length > 20) {
      const chronologicalFund = [...navData].reverse();
      const benchMap = new Map<string, number>();
      benchmark.data.forEach(d => benchMap.set(d.date, d.close));

      const getBenchPrice = (dateStr: string) => {
        if (benchMap.has(dateStr)) return benchMap.get(dateStr);
        const [d, m, y] = dateStr.split('-').map(Number);
        const date = new Date(Date.UTC(y, m - 1, d));
        for (let offset = -1; offset >= -3; offset--) {
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

      if (alignedFund.length > 10) {
        const calcBeta = calculateBeta(alignedFund, alignedBench);
        if (beta === null) beta = calcBeta;

        if (alpha === null) {
          const totalFundRet = alignedFund.reduce((acc, r) => acc * (1 + r), 1);
          const totalBenchRet = alignedBench.reduce((acc, r) => acc * (1 + r), 1);
          const years = alignedFund.length / 252;
          if (years > 0.05) {
            const fCAGR = Math.pow(totalFundRet, 1 / years) - 1;
            const bCAGR = Math.pow(totalBenchRet, 1 / years) - 1;
            alpha = calculateAlpha(fCAGR, bCAGR, beta) * 100;
          }
        }
      }
    }

    return {
      returns, cagr1Y, cagr3Y, cagr5Y, beta, alpha, precomputedAum, precomputedExpenseRatio,
      sharpe: computeSharpe(dailyReturns),
      stdDev: computeStdDev(dailyReturns)
    };
  }, [navData, benchmark.data, auxiliaryData, meta]);

  if (!navData || !meta || !metrics) {
    return (
      <div className="flex-1 p-12 text-center text-gray-500 flex flex-col items-center justify-center min-h-[500px]">
        <div className="relative w-16 h-16 mb-6">
            <div className="absolute inset-0 border-4 border-white/5 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-[var(--accent-color)] rounded-full animate-spin"></div>
        </div>
        <p className="text-white font-medium animate-pulse">Analyzing Risk Vectors...</p>
      </div>
    );
  }

  const latestNav = parseFloat(navData[0].nav).toFixed(2);
  const navDate = navData[0].date;

  const returnRow = (label: string, val: number | null, isCAGR = false) => (
    <div className="flex justify-between items-center py-3.5 border-b border-white/5 text-sm group/row px-3 rounded-xl transition-all hover:bg-white/5">
      <span className="text-gray-400 group-hover/row:text-white transition-colors">{label}</span>
      <span className={`font-bold flex items-center gap-1.5 ${val === null ? 'text-gray-600' : val > 0 ? 'text-green-400' : 'text-red-400'}`}>
        {val !== null ? `${val > 0 ? '+' : ''}${val.toFixed(2)}%` : 'N/A'}
        {isCAGR && val !== null && <span className="text-[9px] px-1.5 py-0.5 bg-white/5 rounded text-gray-500 uppercase tracking-tighter">CAGR</span>}
      </span>
    </div>
  );

  return (
    <div className="flex-1 flex flex-col gap-10 p-8">
      <div className="flex flex-col gap-3">
        <h3 className="text-2xl font-black truncate group relative cursor-default leading-tight tracking-tight" style={{ color: colorHex }}>
          <span className="truncate block" title={meta.scheme_name}>{meta.scheme_name}</span>
        </h3>
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-white bg-white/10 px-3 py-1 rounded-lg border border-white/10">
            {meta.scheme_category}
          </span>
          <span className="w-1.5 h-1.5 rounded-full bg-white/20"></span>
          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">{meta.fund_house}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
          <div className="bg-black/30 rounded-2xl p-5 border border-white/5 shadow-2xl flex flex-col gap-1">
              <div className="text-[10px] font-black text-gray-500 uppercase tracking-widest mb-1">Latest NAV</div>
              <div className="text-xl font-bold text-white tracking-tighter">₹{latestNav}</div>
              <div className="text-[10px] text-gray-600 font-medium">As of {navDate}</div>
          </div>
          <div className="bg-black/30 rounded-2xl p-5 border border-white/5 shadow-2xl flex flex-col gap-1">
              <div className="text-[10px] font-black text-gray-500 uppercase tracking-widest mb-1">Total AUM</div>
              <div className="text-xl font-bold text-[var(--accent-color)] tracking-tighter">
                  {metrics.precomputedAum && metrics.precomputedAum !== 'N/A' ? `₹${metrics.precomputedAum} Cr` : (extraMeta?.aum ? `₹${extraMeta.aum} Cr` : 'TBD')}
              </div>
              <div className="text-[10px] text-gray-600 font-medium leading-none">Syncing monthly...</div>
          </div>
      </div>

      <div className="grid grid-cols-1">
          <div className="bg-black/30 rounded-2xl p-5 border border-white/5 shadow-2xl flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Wallet size={16} className="text-gray-400" />
                <div className="text-[10px] font-black text-gray-500 uppercase tracking-widest">Expense Ratio</div>
              </div>
              <div className="text-lg font-bold text-white tracking-tighter">
                  {metrics.precomputedExpenseRatio && metrics.precomputedExpenseRatio !== 'N/A' ? `${metrics.precomputedExpenseRatio}%` : (extraMeta?.expense_ratio ? `${extraMeta.expense_ratio}%` : '—')}
              </div>
          </div>
      </div>

      <div className="bg-black/20 rounded-3xl p-7 border border-white/10 shadow-2xl">
        <div className="flex items-center gap-3 mb-6">
          <TrendingUp size={18} className="text-green-400" />
          <h4 className="text-xs font-black text-white uppercase tracking-[0.2em]">Absolute Performance</h4>
        </div>
        <div className="space-y-1">
          {returnRow('1 Month', metrics.returns['1M'])}
          {returnRow('6 Months', metrics.returns['6M'])}
          {returnRow('1 Year', metrics.returns['1Y'])}
          {returnRow('3 Years', metrics.cagr3Y, true)}
          {returnRow('5 Years', metrics.cagr5Y, true)}
        </div>
      </div>

      <div className="bg-black/20 rounded-3xl p-7 border border-white/10 shadow-2xl">
        <div className="flex items-center gap-3 mb-6">
          <ShieldAlert size={18} className="text-red-400" />
          <h4 className="text-xs font-black text-white uppercase tracking-[0.2em]">Risk Quant</h4>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <MetricCard 
            label="Alpha" 
            value={metrics.alpha !== null ? (metrics.alpha > 0 ? '+' : '') + metrics.alpha.toFixed(2) + '%' : null} 
            tooltip="Jensen's Alpha: Excess return over benchmark (Nifty 50) after risk adjustment. Positive means outperformance." 
            icon={TrendingUp}
            subValue="vs NIFTY 50"
          />
          <MetricCard 
            label="Beta" 
            value={metrics.beta !== null ? metrics.beta.toFixed(2) : null} 
            tooltip="Systematic Risk: Volatility relative to the market. 1.0 = tracks market, >1.0 = high sensitivity." 
            icon={Activity}
            subValue="Volatility Coeff."
          />
          <MetricCard 
            label="Sharpe" 
            value={metrics.sharpe !== null ? metrics.sharpe.toFixed(2) : null} 
            tooltip="Risk-adjusted Return: Efficiency of the fund in generating returns per unit of total risk." 
            icon={ShieldAlert}
            subValue="Efficiency"
          />
          <MetricCard 
            label="Volatility" 
            value={metrics.stdDev !== null ? metrics.stdDev.toFixed(2) + '%' : null} 
            tooltip="Standard Deviation: The degree to which the NAV fluctuates. Lower is more stable." 
            icon={Activity}
            subValue="Ann. Std Dev"
          />
        </div>
      </div>

      <div className="bg-black/40 rounded-3xl p-8 border border-white/5 border-dashed text-center">
          <PieChart size={24} className="text-gray-700 mx-auto mb-4" />
          <div className="text-[10px] font-black text-gray-500 uppercase tracking-[0.2em] mb-2">Portfolio Under Sync</div>
          <p className="text-[10px] text-gray-600 leading-relaxed max-w-[200px] mx-auto">
            Full sector allocation and stock concentration analysis is being integrated from latest AMFI fact sheets.
          </p>
      </div>
    </div>
  );
}

export default function FundDetailsPanel({ schemeCodeA, schemeCodeB }: Props) {
  return (
    <div className="flex flex-col relative w-full max-w-7xl mx-auto mb-20">
      <div className="flex flex-col md:flex-row relative items-stretch">
        <FundColumn schemeCode={schemeCodeA} colorHex="#3B82F6" />
        
        <div className="flex md:flex-col items-center justify-center p-6 relative">
          <div className="hidden md:block absolute top-0 bottom-0 left-1/2 w-[1px] bg-gradient-to-b from-transparent via-white/10 to-transparent"></div>
          <div className="relative z-10 w-12 h-12 bg-[#0a0a0a] border border-white/10 rounded-full flex items-center justify-center text-[10px] font-black text-gray-500 shadow-2xl ring-8 ring-black/50">
            VS
          </div>
          <div className="md:hidden flex-1 h-[1px] bg-gradient-to-r from-transparent via-white/10 to-transparent ml-4"></div>
        </div>

        <FundColumn schemeCode={schemeCodeB} colorHex="#F97316" />
      </div>
    </div>
  );
}

'use client';

import { useState } from 'react';
import { useFundData } from '../../hooks/useFundData';
import FundComparisonChart, { Period } from '../funds/FundComparisonChart';
import FundDetailsPanel from '../funds/FundDetailsPanel';


interface Props {
  ids: string[];
  type: 'STOCK' | 'MUTUAL_FUND';
}

export default function ComparisonView({ ids, type }: Props) {
  const [period, setPeriod] = useState<Period>('1Y');

  if (!ids || ids.length < 2) {
    return <div className="p-6 text-gray-400">Insufficient data for comparison.</div>;
  }

  // Heuristic: if IDs are numeric, they are mutual fund scheme codes
  const isMF = type === 'MUTUAL_FUND' || (ids[0] && /^[0-9]+$/.test(ids[0]));

  const fundA = useFundData(isMF ? ids[0] : null);
  const fundB = useFundData(isMF ? ids[1] : null);

  if (!isMF) {
    return (
      <div className="comparison-detail p-6 bg-[var(--panel-bg)] rounded-2xl h-full flex flex-col border border-white/10 text-white items-center justify-center text-center">
        <div className="w-16 h-16 bg-blue-500/20 rounded-full flex items-center justify-center mb-4">
          <svg className="w-8 h-8 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </div>
        <h2 className="text-xl font-semibold mb-2">Stock Comparison Coming Soon</h2>
        <p className="text-gray-400 max-w-md">
          Direct stock-to-stock comparison with synchronized charts is currently being optimized for the next release. 
          For now, please use the detailed view for individual stock analysis.
        </p>
      </div>
    );
  }

  const loading = fundA.loading || fundB.loading;
  const error = fundA.error || fundB.error;
  const periods: Period[] = ['1D', '6M', '1Y', '3Y', '5Y'];

  return (
    <div className="comparison-detail p-6 bg-[var(--panel-bg)] rounded-2xl h-full flex flex-col border border-white/10 text-white overflow-hidden">
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Mutual Fund Comparison</h2>
          <p className="text-sm text-gray-400 mt-1">Analyzing performance and risk metrics head-to-head</p>
        </div>

        <div className="flex bg-[#1f2833] rounded-lg p-1.5 border border-white/10 shadow-inner gap-1.5">
          {periods.map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-4 py-2 text-xs font-medium rounded-md transition-all duration-200 ${period === p ? 'bg-[var(--accent-color)] text-black shadow-lg scale-105' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
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
        <div className="flex-1 flex flex-col items-center justify-center p-8 bg-red-500/10 rounded-xl border border-red-500/20">
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
        <div className="flex-1 overflow-y-auto pr-2 custom-scroll space-y-12 pb-12">
          <section className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            <FundComparisonChart 
              schemeCodeA={ids[0]} 
              schemeCodeB={ids[1]} 
              nameA={fundA.meta.scheme_name} 
              nameB={fundB.meta.scheme_name} 
              period={period}
            />
          </section>

          <section className="animate-in fade-in slide-in-from-bottom-6 duration-700 delay-200">
            <div className="pt-4 border-t border-white/5">
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

'use client';

import { useFundData } from '../../hooks/useFundData';
import FundComparisonChart from '../funds/FundComparisonChart';
import FundDetailsPanel from '../funds/FundDetailsPanel';

export default function ComparisonView({ ids, type }: { ids: string[], type: 'STOCK' | 'MUTUAL_FUND' }) {
  if (!ids || ids.length < 2) return <div className="p-6">Insufficient items selected for comparison.</div>;

  if (type !== 'MUTUAL_FUND') {
    return <div className="p-6 text-red-400">Stock comparison is currently not supported natively in this view version.</div>;
  }

  const fundA = useFundData(ids[0]);
  const fundB = useFundData(ids[1]);

  const loading = fundA.loading || fundB.loading;
  const error = fundA.error || fundB.error;

  return (
    <div className="comparison-detail p-6 bg-[var(--panel-bg)] rounded-2xl h-full flex flex-col border border-white/10 text-white overflow-hidden">
      {loading && <div className="text-[var(--accent-color)] animate-pulse">Loading comparison data...</div>}
      {error && <div className="text-red-400">Error: {error}</div>}
      
      {!loading && !error && fundA.meta && fundB.meta && (
        <div className="flex-1 overflow-y-auto pr-2 custom-scroll">
          <div className="mb-4">
            <h2 className="text-2xl font-semibold text-white mb-1">Asset Comparison</h2>
          </div>

          <FundComparisonChart 
            schemeCodeA={ids[0]} 
            schemeCodeB={ids[1]} 
            nameA={fundA.meta.scheme_name} 
            nameB={fundB.meta.scheme_name} 
          />

          <FundDetailsPanel 
            schemeCodeA={ids[0]} 
            schemeCodeB={ids[1]} 
          />
        </div>
      )}
    </div>
  );
}

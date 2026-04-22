'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Info } from 'lucide-react';

interface Props {
  schemeCodeA: string;
  schemeCodeB: string;
}

export default function OverlapBadge({ schemeCodeA, schemeCodeB }: Props) {
  const [expanded, setExpanded] = useState(false);

  // Since mfapi doesn't provide actual holdings, we use a placeholder overlap
  const overlapPercentage = 35; // Mock data
  const mockOverlappingStocks = [
    { name: 'HDFC Bank Ltd.', weightA: 8.5, weightB: 9.2, overlap: 8.5 },
    { name: 'Reliance Industries Ltd.', weightA: 7.2, weightB: 6.8, overlap: 6.8 },
    { name: 'ICICI Bank Ltd.', weightA: 5.4, weightB: 6.1, overlap: 5.4 },
    { name: 'Infosys Ltd.', weightA: 4.8, weightB: 4.5, overlap: 4.5 },
    { name: 'ITC Ltd.', weightA: 3.2, weightB: 4.0, overlap: 3.2 },
  ];

  let badgeColor = 'bg-red-500/20 text-red-400 border-red-500/30';
  if (overlapPercentage < 30) badgeColor = 'bg-green-500/20 text-green-400 border-green-500/30';
  else if (overlapPercentage <= 60) badgeColor = 'bg-amber-500/20 text-amber-400 border-amber-500/30';

  return (
    <div className="flex flex-col items-center w-full max-w-md mx-auto my-4 pb-8">
      <button 
        onClick={() => setExpanded(!expanded)}
        className={`flex items-center gap-2 px-6 py-2 rounded-full border shadow-lg backdrop-blur-md transition-all hover:scale-105 ${badgeColor}`}
      >
        <span className="font-semibold">{overlapPercentage}% Portfolio Overlap</span>
        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {expanded && (
        <div className="w-full mt-4 bg-[#111827] border border-white/10 rounded-xl p-4 shadow-xl animate-in slide-in-from-top-2">
          <div className="flex items-start gap-2 mb-4 text-xs text-gray-400 bg-white/5 p-2 rounded-lg">
            <Info size={14} className="mt-0.5 flex-shrink-0 text-[var(--accent-color)]" />
            <p>Portfolio overlap shows the percentage of identical stocks held by both funds. High overlap (&gt;60%) reduces diversification benefits.</p>
          </div>
          
          <div className="text-sm">
            <div className="flex text-xs text-gray-500 uppercase tracking-wider mb-2 pb-2 border-b border-white/5">
              <div className="flex-1">Stock</div>
              <div className="w-16 text-right">Fund 1</div>
              <div className="w-16 text-right">Fund 2</div>
            </div>
            
            <div className="space-y-2">
              {mockOverlappingStocks.map((stock, i) => (
                <div key={i} className="flex items-center text-gray-300">
                  <div className="flex-1 truncate pr-2" title={stock.name}>{stock.name}</div>
                  <div className="w-16 text-right text-blue-400">{stock.weightA.toFixed(1)}%</div>
                  <div className="w-16 text-right text-orange-400">{stock.weightB.toFixed(1)}%</div>
                </div>
              ))}
            </div>
            <div className="mt-4 pt-3 border-t border-white/5 text-center text-xs text-gray-500">
              Holdings data simulated for demonstration.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

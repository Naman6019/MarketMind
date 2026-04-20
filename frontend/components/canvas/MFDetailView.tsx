'use client';

import { useEffect, useState } from 'react';
import { useCanvasStore } from '@/store/useCanvasStore';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function MFDetailView({ schemeCode }: { schemeCode?: string }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!schemeCode) return;
    const fetchMF = async () => {
      setLoading(true);
      setError('');
      try {
        const res = await fetch(`/api/mf/${schemeCode}`);
        if (!res.ok) throw new Error('Failed to load Mutual Fund details');
        const json = await res.json();
        setData(json);
      } catch (err: any) {
        setError(err.message);
      }
      setLoading(false);
    };
    fetchMF();
  }, [schemeCode]);

  if (!schemeCode) return <div className="p-6">No fund selected.</div>;

  return (
    <div className="mf-detail p-6 bg-[var(--panel-bg)] rounded-2xl h-full flex flex-col border border-white/10 text-white overflow-hidden">
      {loading && <div className="text-[var(--accent-color)] animate-pulse">Loading Mutual Fund data...</div>}
      {error && <div className="text-red-400">Error: {error}</div>}
      
      {!loading && !error && data && (
        <div className="flex-1 overflow-y-auto pr-2 custom-scroll">
          <div className="mb-6 border-b border-white/10 pb-4">
            <h2 className="text-2xl font-semibold text-white mb-2">{data.details.scheme_name}</h2>
            <div className="flex gap-2 flex-wrap text-sm">
              <span className="bg-white/10 px-2 py-1 rounded text-gray-300">{data.details.fund_house}</span>
              <span className="bg-blue-500/20 text-blue-300 px-2 py-1 rounded">{data.details.category}</span>
              <span className="bg-purple-500/20 text-purple-300 px-2 py-1 rounded">{data.details.sub_category}</span>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-black/30 p-4 rounded-xl border border-white/5">
              <div className="text-gray-400 text-sm mb-1">NAV ({new Date(data.details.nav_date).toLocaleDateString()})</div>
              <div className="text-xl font-medium text-[var(--accent-color)]">₹{data.details.nav}</div>
            </div>
            <div className="bg-black/30 p-4 rounded-xl border border-white/5">
              <div className="text-gray-400 text-sm mb-1">AUM (Cr)</div>
              <div className="text-xl font-medium">₹{data.details.aum || 'N/A'}</div>
            </div>
            <div className="bg-black/30 p-4 rounded-xl border border-white/5">
              <div className="text-gray-400 text-sm mb-1">Expense Ratio</div>
              <div className="text-xl font-medium">{data.details.expense_ratio ? `${data.details.expense_ratio}%` : 'N/A'}</div>
            </div>
            <div className="bg-black/30 p-4 rounded-xl border border-white/5">
              <div className="text-gray-400 text-sm mb-1">Exit Load</div>
              <div className="text-sm font-medium">{data.details.exit_load || 'N/A'}</div>
            </div>
          </div>

          <div className="mb-6">
            <h3 className="text-lg font-medium text-[var(--accent-color)] mb-3">Historical Returns (CAGR)</h3>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="bg-white/5 p-3 rounded-lg border border-white/10">
                <div className="text-gray-400 text-sm mb-1">1 Year</div>
                <div className={`font-semibold ${data.returns['1Y'] > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {data.returns['1Y'] !== null ? `${data.returns['1Y']}%` : 'N/A'}
                </div>
              </div>
              <div className="bg-white/5 p-3 rounded-lg border border-white/10">
                <div className="text-gray-400 text-sm mb-1">3 Years</div>
                <div className={`font-semibold ${data.returns['3Y'] > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {data.returns['3Y'] !== null ? `${data.returns['3Y']}%` : 'N/A'}
                </div>
              </div>
              <div className="bg-white/5 p-3 rounded-lg border border-white/10">
                <div className="text-gray-400 text-sm mb-1">5 Years</div>
                <div className={`font-semibold ${data.returns['5Y'] > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {data.returns['5Y'] !== null ? `${data.returns['5Y']}%` : 'N/A'}
                </div>
              </div>
            </div>
          </div>

          <div className="mb-6">
            <h3 className="text-lg font-medium text-[var(--accent-color)] mb-4">1Y NAV Trend (Rebased)</h3>
            <div className="h-64 w-full bg-black/20 rounded-xl p-2 border border-white/5">
              {data.chartData && data.chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis 
                      dataKey="date" 
                      stroke="#8a9199" 
                      fontSize={12} 
                      tickFormatter={(val) => {
                         const d = new Date(val.split('-').reverse().join('-')); // approx parsing
                         return `${d.getMonth()+1}/${d.getFullYear().toString().substr(-2)}`;
                      }} 
                    />
                    <YAxis stroke="#8a9199" fontSize={12} domain={['dataMin', 'dataMax']} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: 'rgba(11, 12, 16, 0.9)', borderColor: 'rgba(102, 252, 241, 0.2)' }} 
                      itemStyle={{ color: '#66fcf1' }}
                    />
                    <Line type="monotone" dataKey="value" stroke="#66fcf1" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-gray-500 text-sm">No recent history available for charting.</div>
              )}
            </div>
          </div>
          
          <div className="text-xs text-gray-500 border-t border-white/10 pt-4 pb-8">
            Benchmark: {data.details.benchmark || 'N/A'}<br/>
            Data synced from AMFI API. Note: Due to limitations, returns may be indicative.
          </div>
        </div>
      )}
    </div>
  );
}

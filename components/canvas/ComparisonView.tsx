'use client';

import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

export default function ComparisonView({ ids, type }: { ids: string[], type: 'STOCK' | 'MUTUAL_FUND' }) {
  const [data1, setData1] = useState<any>(null);
  const [data2, setData2] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!ids || ids.length < 2) return;
    
    // Safety check - cross type comparisons are forbidden per constraints
    const fetchComparison = async () => {
      setLoading(true);
      setError('');
      try {
        if (type === 'MUTUAL_FUND') {
          const [res1, res2] = await Promise.all([
            fetch(`/api/mf/${ids[0]}`),
            fetch(`/api/mf/${ids[1]}`)
          ]);
          
          if (!res1.ok || !res2.ok) throw new Error('Failed to load comparison data');
          
          const json1 = await res1.json();
          const json2 = await res2.json();
          
          setData1(json1);
          setData2(json2);
        } else {
          // Stock Comparison Logic Placeholder
          setError('Stock comparison is currently not supported natively in this view version.');
        }
      } catch (err: any) {
        setError(err.message);
      }
      setLoading(false);
    };
    fetchComparison();
  }, [ids, type]);

  if (!ids || ids.length < 2) return <div className="p-6">Insufficient items selected for comparison.</div>;

  // Compute merged chart data with normalization
  const mergedChartData = () => {
    if (!data1?.chartData || !data2?.chartData) return [];
    
    // We assume the timeline overlaps for the last year roughly.
    // For normalization, find start base.
    const base1 = data1.chartData[0]?.value || 1;
    const base2 = data2.chartData[0]?.value || 1;

    // Create a map by date
    const map = new Map<string, any>();
    data1.chartData.forEach((d: any) => {
      map.set(d.date, { date: d.date, asset1: (d.value / base1) * 100 });
    });
    
    data2.chartData.forEach((d: any) => {
      if (map.has(d.date)) {
        map.set(d.date, { ...map.get(d.date), asset2: (d.value / base2) * 100 });
      } else {
        map.set(d.date, { date: d.date, asset2: (d.value / base2) * 100 });
      }
    });

    // Sort map by actual date to ensure linearity
    return Array.from(map.values()).sort((a, b) => {
      const d1 = new Date(a.date.split('-').reverse().join('-')).getTime();
      const d2 = new Date(b.date.split('-').reverse().join('-')).getTime();
      return d1 - d2;
    });
  };

  const chartData = mergedChartData();

  return (
    <div className="comparison-detail p-6 bg-[var(--panel-bg)] rounded-2xl h-full flex flex-col border border-white/10 text-white overflow-hidden">
      {loading && <div className="text-[var(--accent-color)] animate-pulse">Running comparison engine...</div>}
      {error && <div className="text-red-400">Error: {error}</div>}
      
      {!loading && !error && data1 && data2 && (
        <div className="flex-1 overflow-y-auto pr-2 custom-scroll">
          <div className="mb-4">
            <h2 className="text-2xl font-semibold text-white mb-1">Asset Comparison</h2>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-6 relative">
             <div className="absolute left-1/2 top-0 bottom-0 w-[1px] bg-white/10 -translate-x-1/2"></div>
             
             {/* Asset 1 */}
             <div className="pr-4">
               <h3 className="text-lg font-medium text-[var(--accent-color)] mb-1 truncate" title={data1.details.scheme_name}>{data1.details.scheme_name}</h3>
               <div className="text-xs text-gray-400 mb-4">{data1.details.category}</div>
               
               <div className="space-y-3 text-sm">
                 <div className="flex justify-between border-b border-white/5 pb-1">
                   <span className="text-gray-400">NAV</span>
                   <span>₹{data1.details.nav}</span>
                 </div>
                 <div className="flex justify-between border-b border-white/5 pb-1">
                   <span className="text-gray-400">AUM</span>
                   <span>₹{data1.details.aum || 'N/A'} Cr</span>
                 </div>
                 <div className="flex justify-between border-b border-white/5 pb-1">
                   <span className="text-gray-400">Exp. Ratio</span>
                   <span>{data1.details.expense_ratio ? `${data1.details.expense_ratio}%` : 'N/A'}</span>
                 </div>
                 <div className="flex justify-between border-b border-white/5 pb-1 mt-4 pt-4">
                   <span className="text-[var(--accent-color)] font-medium">1Y Return</span>
                   <span className={data1.returns['1Y'] > 0 ? 'text-green-400' : 'text-red-400'}>{data1.returns['1Y']}%</span>
                 </div>
                 <div className="flex justify-between border-b border-white/5 pb-1">
                   <span className="text-[var(--accent-color)] font-medium">3Y Return</span>
                   <span className={data1.returns['3Y'] > 0 ? 'text-green-400' : 'text-red-400'}>{data1.returns['3Y']}%</span>
                 </div>
               </div>
             </div>

             {/* Asset 2 */}
             <div className="pl-4">
               <h3 className="text-lg font-medium text-[#fca311] mb-1 truncate" title={data2.details.scheme_name}>{data2.details.scheme_name}</h3>
               <div className="text-xs text-gray-400 mb-4">{data2.details.category}</div>

               <div className="space-y-3 text-sm">
                 <div className="flex justify-between border-b border-white/5 pb-1">
                   <span className="text-gray-400">NAV</span>
                   <span>₹{data2.details.nav}</span>
                 </div>
                 <div className="flex justify-between border-b border-white/5 pb-1">
                   <span className="text-gray-400">AUM</span>
                   <span>₹{data2.details.aum || 'N/A'} Cr</span>
                 </div>
                 <div className="flex justify-between border-b border-white/5 pb-1">
                   <span className="text-gray-400">Exp. Ratio</span>
                   <span>{data2.details.expense_ratio ? `${data2.details.expense_ratio}%` : 'N/A'}</span>
                 </div>
                 <div className="flex justify-between border-b border-white/5 pb-1 mt-4 pt-4">
                   <span className="text-[#fca311] font-medium">1Y Return</span>
                   <span className={data2.returns['1Y'] > 0 ? 'text-green-400' : 'text-red-400'}>{data2.returns['1Y']}%</span>
                 </div>
                 <div className="flex justify-between border-b border-white/5 pb-1">
                   <span className="text-[#fca311] font-medium">3Y Return</span>
                   <span className={data2.returns['3Y'] > 0 ? 'text-green-400' : 'text-red-400'}>{data2.returns['3Y']}%</span>
                 </div>
               </div>
             </div>
          </div>

          <div className="mb-6 mt-8">
            <h3 className="text-md font-medium text-gray-300 mb-4">Normalized 1Y Performance (Rebased to 100)</h3>
            <div className="h-64 w-full bg-black/20 rounded-xl p-2 border border-white/5">
              {chartData && chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis 
                      dataKey="date" 
                      stroke="#8a9199" 
                      fontSize={11} 
                      tickFormatter={(val) => {
                         const d = new Date(val.split('-').reverse().join('-'));
                         return `${d.getMonth()+1}/${d.getFullYear().toString().substr(-2)}`;
                      }} 
                    />
                    <YAxis stroke="#8a9199" fontSize={11} domain={['auto', 'auto']} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: 'rgba(11, 12, 16, 0.9)', borderColor: 'rgba(102, 252, 241, 0.2)' }} 
                      itemStyle={{ color: '#fff' }}
                      labelStyle={{ color: '#8a9199' }}
                    />
                    <Legend />
                    <Line name="Asset 1" type="monotone" dataKey="asset1" stroke="#66fcf1" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                    <Line name="Asset 2" type="monotone" dataKey="asset2" stroke="#fca311" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-gray-500 text-sm">No overlay data available.</div>
              )}
            </div>
          </div>
          
        </div>
      )}
    </div>
  );
}

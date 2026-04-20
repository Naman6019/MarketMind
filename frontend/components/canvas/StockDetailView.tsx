'use client';

export default function StockDetailView({ stockId }: { stockId?: string }) {
  if (!stockId) return <div className="p-4">No stock selected.</div>;
  
  return (
    <div className="stock-detail p-6 bg-[var(--panel-bg)] rounded-2xl h-full overflow-hidden border border-white/10">
      <h2 className="text-2xl font-semibold mb-4 text-white">Stock Details: {stockId}</h2>
      <p className="text-[var(--text-secondary)]">
        Detailed visualizations and charts for the stock will be displayed here. 
        (Currently simulated pending detailed integration).
      </p>
    </div>
  );
}

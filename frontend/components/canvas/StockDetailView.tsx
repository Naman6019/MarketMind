'use client';

import { useEffect, useState } from 'react';

const UNAVAILABLE = 'This data is currently unavailable from the provider.';

type JsonObject = Record<string, unknown>;

type ProviderBlock = {
  ok?: boolean;
  data?: unknown;
  fetchedAt?: string;
  stale?: boolean;
};

type StockProfileData = {
  metadata?: JsonObject;
  latest_price?: JsonObject;
  ratios?: JsonObject;
  source_summary?: JsonObject;
  indianapi?: {
    profile?: ProviderBlock;
    corporate_actions?: ProviderBlock;
    recent_announcements?: ProviderBlock;
  };
};

function isRecord(value: unknown): value is JsonObject {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}

function firstRows(data: unknown, limit = 5): JsonObject[] {
  if (Array.isArray(data)) return data.slice(0, limit);
  if (isRecord(data)) {
    for (const value of Object.values(data)) {
      const rows = firstRows(value, limit);
      if (rows.length) return rows;
    }
    return [data];
  }
  return [];
}

function pick(row: JsonObject, keys: string[]) {
  for (const key of keys) {
    if (row[key] !== undefined && row[key] !== null && row[key] !== '') return String(row[key]);
  }
  return null;
}

function ProviderSection({ title, block }: { title: string; block?: ProviderBlock }) {
  const rows = block?.ok ? firstRows(block.data) : [];

  return (
    <section className="border-t border-white/10 py-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--accent-color)]">{title}</h3>
        {block?.fetchedAt && <span className="text-xs text-gray-500">{new Date(block.fetchedAt).toLocaleString()}</span>}
      </div>
      {!rows.length ? (
        <p className="text-sm text-gray-400">{UNAVAILABLE}</p>
      ) : (
        <div className="space-y-3">
          {rows.map((row, idx) => (
            <div key={idx} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-gray-200">
              <div className="font-medium text-white">
                {pick(row, ['title', 'subject', 'companyName', 'name', 'action_type', 'type']) || 'Provider data'}
              </div>
              <div className="mt-1 text-gray-400">
                {pick(row, ['description', 'details', 'purpose', 'summary', 'industry']) || JSON.stringify(row).slice(0, 180)}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default function StockDetailView({ stockId }: { stockId?: string }) {
  const [data, setData] = useState<StockProfileData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!stockId) return;

    const fetchStock = async () => {
      setLoading(true);
      setError('');
      try {
        const res = await fetch(`/api/quant/stocks/${encodeURIComponent(stockId)}/profile`);
        if (!res.ok) throw new Error('Failed to load stock details');
        setData(await res.json());
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load stock details');
      } finally {
        setLoading(false);
      }
    };

    void fetchStock();
  }, [stockId]);

  if (!stockId) return <div className="p-4">No stock selected.</div>;

  const metadata = data?.metadata || {};
  const provider = data?.indianapi || {};

  return (
    <div className="stock-detail h-full overflow-y-auto rounded-2xl border border-white/10 bg-[var(--panel-bg)] p-6 text-white">
      <div className="mb-5">
        <h2 className="text-2xl font-semibold">{String(metadata.company_name || stockId)}</h2>
        <p className="text-sm text-[var(--text-secondary)]">{String(metadata.industry || metadata.sector || 'NSE stock research')}</p>
      </div>

      {loading && <div className="text-[var(--accent-color)]">Loading stock data...</div>}
      {error && <div className="text-red-400">{UNAVAILABLE}</div>}

      {!loading && !error && (
        <>
          <section className="grid grid-cols-2 gap-3 pb-4 md:grid-cols-4">
            <div className="rounded-lg border border-white/10 bg-black/20 p-3">
              <div className="text-xs text-gray-400">Price</div>
              <div className="text-lg font-medium">{String(data?.latest_price?.close ?? 'N/A')}</div>
            </div>
            <div className="rounded-lg border border-white/10 bg-black/20 p-3">
              <div className="text-xs text-gray-400">P/E</div>
              <div className="text-lg font-medium">{String(data?.ratios?.pe ?? 'N/A')}</div>
            </div>
            <div className="rounded-lg border border-white/10 bg-black/20 p-3">
              <div className="text-xs text-gray-400">Market Cap</div>
              <div className="text-lg font-medium">{String(data?.ratios?.market_cap ?? 'N/A')}</div>
            </div>
            <div className="rounded-lg border border-white/10 bg-black/20 p-3">
              <div className="text-xs text-gray-400">Source</div>
              <div className="text-sm font-medium">{String(data?.source_summary?.metadata || 'N/A')}</div>
            </div>
          </section>

          <ProviderSection title="Company Overview" block={provider.profile} />
          <ProviderSection title="Corporate Actions" block={provider.corporate_actions} />
          <ProviderSection title="Recent Announcements" block={provider.recent_announcements} />
        </>
      )}
    </div>
  );
}

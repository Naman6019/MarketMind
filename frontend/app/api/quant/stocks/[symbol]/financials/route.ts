import { proxyGet } from '../../../proxy';

export async function GET(request: Request, context: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await context.params;
  return proxyGet(`/api/quant/stocks/${encodeURIComponent(symbol)}/financials`, request);
}

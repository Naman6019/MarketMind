import { proxyGet } from '../../../proxy';

export async function GET(request: Request) {
  return proxyGet('/api/quant/stocks/nifty50/ticker', request);
}

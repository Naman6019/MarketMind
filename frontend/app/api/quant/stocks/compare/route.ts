import { proxyGet } from '../../proxy';

export async function GET(request: Request) {
  return proxyGet('/api/quant/stocks/compare', request);
}

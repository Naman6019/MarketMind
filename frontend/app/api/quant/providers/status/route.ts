import { proxyGet } from '../../proxy';

export async function GET(request: Request) {
  return proxyGet('/api/quant/providers/status', request);
}

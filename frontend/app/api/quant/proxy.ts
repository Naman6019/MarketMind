import { NextResponse } from 'next/server';

export function backendUrl(path: string, search = '') {
  const base = process.env.NODE_ENV === 'development'
    ? 'http://127.0.0.1:8000'
    : process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_API_URL;

  if (!base) throw new Error('Backend API URL is not configured');
  return `${base}${path}${search}`;
}

export async function proxyGet(path: string, request: Request) {
  try {
    // TODO: Add route-level rate limiting when auth/rate limits are implemented.
    const url = new URL(request.url);
    const res = await fetch(backendUrl(path, url.search), { method: 'GET' });
    const body = await res.json().catch(() => ({ error: 'Invalid backend response' }));
    return NextResponse.json(body, { status: res.status });
  } catch (error) {
    console.error('Quant proxy error:', error);
    return NextResponse.json({ error: 'Quant backend unavailable' }, { status: 502 });
  }
}

import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  try {
    const body = await req.json();

    const TARGET = process.env.NODE_ENV === 'development'
      ? 'http://127.0.0.1:8000/api/chat'
      : `${process.env.NEXT_PUBLIC_API_URL}/api/chat`;
    
    console.log(`Proxying chat request to: ${TARGET}`);

    const proxyRes = await fetch(TARGET, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!proxyRes.ok) {
        const errorText = await proxyRes.text();
        console.error(`Upstream Error (${proxyRes.status}):`, errorText);
        return NextResponse.json({ error: 'Upstream Error' }, { status: proxyRes.status });
    }
    
    const data = await proxyRes.json();
    return NextResponse.json(data);
    
  } catch (error) {
    console.error('Chat Proxy Error:', error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}

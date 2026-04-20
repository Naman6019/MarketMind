import { NextResponse } from 'next/server';
import { syncAMFIData } from '@/lib/scrapers/amfi';

export const maxDuration = 300; // 5 minutes max duration for serverless processing if Vercel Pro, otherwise 10s (why Github Actions timeout was an issue)

export async function GET(request: Request) {
  const authHeader = request.headers.get('authorization');
  const cronSecret = process.env.CRON_SECRET;
  
  if (!cronSecret || authHeader !== `Bearer ${cronSecret}`) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const result = await syncAMFIData();
    if (result.success) {
      return NextResponse.json({ success: true, message: `Synced ${result.count} schemes` });
    } else {
      return NextResponse.json({ success: false, error: result.error }, { status: 500 });
    }
  } catch (error) {
    return NextResponse.json({ success: false, error: (error as Error).message }, { status: 500 });
  }
}

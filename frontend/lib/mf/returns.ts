export type NAVData = {
  date: string; // dd-MM-yyyy format
  nav: string;
};

export async function fetchMFHistory(schemeCode: string): Promise<NAVData[]> {
  const res = await fetch(`/api/mf/${schemeCode}`);
  if (!res.ok) throw new Error('Failed to fetch MF history');
  const json = await res.json();
  // Map internal chartData back to NAVData format for utilities
  return (json.chartData || []).map((h: any) => ({
    date: h.date,
    nav: h.value.toString()
  }));
}

export function parseDate(dateStr: string): Date {
  const [d, mStr, y] = dateStr.split('-');
  const m = new Date(`${mStr} 1 2000`).getMonth();
  return new Date(Date.UTC(parseInt(y, 10), m, parseInt(d, 10)));
}

export function calculateCAGR(navHistory: NAVData[], years: 1 | 3 | 5): number | null {
  if (!navHistory || navHistory.length === 0) return null;
  
  // NAV history from mfapi.in is typically sorted newest first (descending).
  // E.g. navHistory[0] is most recent. Let's verify and just find the endpoints.
  
  const sorted = [...navHistory].sort((a, b) => parseDate(b.date).getTime() - parseDate(a.date).getTime());
  
  const currentValue = parseFloat(sorted[0].nav);
  const currentDate = parseDate(sorted[0].date);
  
  const targetDate = new Date(currentDate);
  targetDate.setFullYear(currentDate.getFullYear() - years);
  
  // Find the closest date to our target date (looking for first date <= targetDate)
  let pastValue: number | null = null;
  for (let i = 0; i < sorted.length; i++) {
    if (parseDate(sorted[i].date) <= targetDate) {
      pastValue = parseFloat(sorted[i].nav);
      break;
    }
  }
  
  if (pastValue === null || isNaN(currentValue) || isNaN(pastValue) || pastValue <= 0) {
    return null; // Not enough history
  }
  
  const cagr = (Math.pow(currentValue / pastValue, 1 / years) - 1) * 100;
  return Number(cagr.toFixed(2));
}

export function calculateRiskMetrics(navHistory: NAVData[], riskFreeRate: number = 0.06) {
  const sorted = [...navHistory].sort((a, b) => parseDate(a.date).getTime() - parseDate(b.date).getTime());
  if (sorted.length < 2) return null;

  const returns = [];
  for (let i = 1; i < sorted.length; i++) {
    const prev = parseFloat(sorted[i - 1].nav);
    const curr = parseFloat(sorted[i].nav);
    returns.push((curr - prev) / prev);
  }

  const meanReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
  const stdDev = Math.sqrt(returns.reduce((a, b) => a + Math.pow(b - meanReturn, 2), 0) / returns.length);
  
  const annualizedStdDev = stdDev * Math.sqrt(252);
  const annualizedReturn = meanReturn * 252;
  
  const sharpeRatio = (annualizedReturn - riskFreeRate) / annualizedStdDev;

  const downsideReturns = returns.filter(r => r < 0);
  const downsideStdDev = Math.sqrt(downsideReturns.reduce((a, b) => a + Math.pow(b, 2), 0) / returns.length) * Math.sqrt(252);
  const sortinoRatio = (annualizedReturn - riskFreeRate) / downsideStdDev;

  let maxDrawdown = 0;
  let peak = -Infinity;
  for (const entry of sorted) {
    const val = parseFloat(entry.nav);
    if (val > peak) peak = val;
    const dd = (peak - val) / peak;
    if (dd > maxDrawdown) maxDrawdown = dd;
  }

  return {
    stdDev: Number(annualizedStdDev.toFixed(4)),
    sharpeRatio: Number(sharpeRatio.toFixed(2)),
    sortinoRatio: Number(sortinoRatio.toFixed(2)),
    maxDrawdown: Number(maxDrawdown.toFixed(4))
  };
}

export type NAVData = {
  date: string; // dd-MM-yyyy format
  nav: string;
};

export async function fetchMFHistory(schemeCode: string): Promise<NAVData[]> {
  const res = await fetch(`https://api.mfapi.in/mf/${schemeCode}`);
  if (!res.ok) throw new Error('Failed to fetch MF history');
  const json = await res.json();
  return json.data || [];
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

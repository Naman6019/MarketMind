export function parseNavDate(dateStr: string): Date {
  const [day, month, year] = dateStr.split('-');
  return new Date(`${year}-${month}-${day}`);
}

export function filterByPeriod(data: any[], period: '1D' | '6M' | '1Y' | '3Y' | '5Y') {
  if (!data || data.length === 0) return [];
  
  const latestDate = parseNavDate(data[0].date); // data is newest-first
  const cutoffDate = new Date(latestDate);

  switch (period) {
    case '1D': cutoffDate.setDate(cutoffDate.getDate() - 2); break; // 1D needs at least 2 points
    case '6M': cutoffDate.setMonth(cutoffDate.getMonth() - 6); break;
    case '1Y': cutoffDate.setFullYear(cutoffDate.getFullYear() - 1); break;
    case '3Y': cutoffDate.setFullYear(cutoffDate.getFullYear() - 3); break;
    case '5Y': cutoffDate.setFullYear(cutoffDate.getFullYear() - 5); break;
  }

  const filtered = data.filter(d => parseNavDate(d.date) >= cutoffDate);
  // Re-reverse to chronological order for charting (oldest to newest)
  return filtered.reverse();
}

export function normalizeTo100(data: any[]) {
  if (!data || data.length === 0) return [];
  const firstNav = parseFloat(data[0].nav);
  return data.map(d => ({
    ...d,
    normalized: (parseFloat(d.nav) / firstNav) * 100
  }));
}

export function downsample(data: any[], targetPoints: number) {
  if (data.length <= targetPoints) return data;
  const result = [];
  const step = (data.length - 1) / (targetPoints - 1);
  for (let i = 0; i < targetPoints; i++) {
    const index = Math.min(Math.round(i * step), data.length - 1);
    result.push(data[index]);
  }
  return result;
}

import { NavPoint, DailyReturn } from '../types/funds';
import { parseNavDate } from './fundDataUtils';

export function toReturnsArray(navData: NavPoint[]): DailyReturn[] {
  // navData usually newest-first, but we need chronological for standard return series
  // Wait, if it's newest-first, navData[i] is newer than navData[i+1].
  // return = (new / old) - 1
  const returns: DailyReturn[] = [];
  for (let i = 0; i < navData.length - 1; i++) {
    const newer = parseFloat(navData[i].nav);
    const older = parseFloat(navData[i + 1].nav);
    if (older > 0) returns.push((newer / older) - 1);
  }
  return returns;
}

export function computeCAGR(navData: NavPoint[], years: number): number | null {
  if (navData.length < 2) return null;
  // Assuming navData is newest-first
  const latestNav = parseFloat(navData[0].nav);
  // Find the NAV 'years' ago
  const latestDate = parseNavDate(navData[0].date);
  const targetDate = new Date(latestDate);
  targetDate.setFullYear(targetDate.getFullYear() - years);

  let pastNavPoint = navData[navData.length - 1]; // fallback to oldest
  for (let i = 0; i < navData.length; i++) {
    if (parseNavDate(navData[i].date) <= targetDate) {
      pastNavPoint = navData[i];
      break;
    }
  }

  const pastNav = parseFloat(pastNavPoint.nav);
  if (pastNav <= 0) return null;
  
  // Calculate actual years elapsed between pastNavPoint and latestNav
  const elapsedMs = parseNavDate(navData[0].date).getTime() - parseNavDate(pastNavPoint.date).getTime();
  const elapsedYears = elapsedMs / (1000 * 60 * 60 * 24 * 365.25);
  
  if (elapsedYears < 0.1) return null;

  return (Math.pow(latestNav / pastNav, 1 / elapsedYears) - 1) * 100;
}

export function computeReturns(navData: NavPoint[]): Record<'1M'|'3M'|'6M'|'1Y'|'3Y'|'5Y', number | null> {
  const calcAbsReturn = (months: number): number | null => {
    if (navData.length < 2) return null;
    const latestNav = parseFloat(navData[0].nav);
    const latestDate = parseNavDate(navData[0].date);
    const targetDate = new Date(latestDate);
    targetDate.setMonth(targetDate.getMonth() - months);

    let pastNavPoint = navData[navData.length - 1];
    for (let i = 0; i < navData.length; i++) {
      if (parseNavDate(navData[i].date) <= targetDate) {
        pastNavPoint = navData[i];
        break;
      }
    }
    const pastNav = parseFloat(pastNavPoint.nav);
    if (pastNav <= 0) return null;
    return ((latestNav / pastNav) - 1) * 100;
  };

  return {
    '1M': calcAbsReturn(1),
    '3M': calcAbsReturn(3),
    '6M': calcAbsReturn(6),
    '1Y': calcAbsReturn(12),
    '3Y': calcAbsReturn(36),
    '5Y': calcAbsReturn(60),
  };
}

export function computeBeta(fundReturns: DailyReturn[], benchmarkReturns: DailyReturn[]): number | null {
  if (!fundReturns.length || !benchmarkReturns.length) return null;
  const len = Math.min(fundReturns.length, benchmarkReturns.length);
  const fr = fundReturns.slice(0, len);
  const br = benchmarkReturns.slice(0, len);

  const meanFr = fr.reduce((a, b) => a + b, 0) / len;
  const meanBr = br.reduce((a, b) => a + b, 0) / len;

  let cov = 0;
  let varBr = 0;
  for (let i = 0; i < len; i++) {
    cov += (fr[i] - meanFr) * (br[i] - meanBr);
    varBr += Math.pow(br[i] - meanBr, 2);
  }
  if (varBr === 0) return null;
  return cov / varBr;
}

export function computeAlpha(fundCAGR: number | null, beta: number | null, benchmarkCAGR: number | null, rfr = 6.5): number | null {
  if (fundCAGR === null || beta === null || benchmarkCAGR === null) return null;
  // Jensen's alpha: Alpha = Fund Return - [Risk Free Rate + Beta * (Benchmark Return - Risk Free Rate)]
  return fundCAGR - (rfr + beta * (benchmarkCAGR - rfr));
}

export function computeStdDev(fundReturns: DailyReturn[]): number | null {
  if (fundReturns.length < 2) return null;
  const mean = fundReturns.reduce((a, b) => a + b, 0) / fundReturns.length;
  const variance = fundReturns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / (fundReturns.length - 1);
  const dailyStdDev = Math.sqrt(variance);
  // Annualized
  return dailyStdDev * Math.sqrt(252) * 100;
}

export function computeSharpe(fundReturns: DailyReturn[], rfr = 0.065): number | null {
  const stdDev = computeStdDev(fundReturns); // This is in %
  if (!stdDev || stdDev === 0) return null;

  // We need annualized return for the same period.
  // Approximation using daily mean
  const mean = fundReturns.reduce((a, b) => a + b, 0) / fundReturns.length;
  const annualizedReturn = mean * 252 * 100;

  return (annualizedReturn - (rfr * 100)) / stdDev;
}

export function computeFundOverlap(holdingsA: any[], holdingsB: any[]): { percentage: number, overlapping: any[] } {
  // Holdings format assumed: { isin: string, weight: number, name: string }
  if (!holdingsA || !holdingsB) return { percentage: 0, overlapping: [] };
  
  const mapA = new Map(holdingsA.map(h => [h.isin, h]));
  let overlap = 0;
  const overlapping = [];

  for (const hB of holdingsB) {
    if (mapA.has(hB.isin)) {
      const hA = mapA.get(hB.isin);
      const minWeight = Math.min(hA.weight, hB.weight);
      overlap += minWeight;
      overlapping.push({
        isin: hB.isin,
        name: hB.name,
        weightA: hA.weight,
        weightB: hB.weight,
        overlap: minWeight
      });
    }
  }

  overlapping.sort((a, b) => b.overlap - a.overlap);
  return { percentage: overlap, overlapping };
}

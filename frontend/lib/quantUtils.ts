/**
 * Quantitative utilities for calculating risk metrics like Alpha and Beta.
 */

export interface DailyReturn {
  date: string;
  return: number;
}

/**
 * Calculates Beta for a fund relative to a benchmark.
 * beta = covariance(fundReturns, benchReturns) / variance(benchReturns)
 */
export function calculateBeta(fundReturns: number[], benchReturns: number[]): number {
  if (fundReturns.length < 2 || fundReturns.length !== benchReturns.length) return 1.0;

  const meanFund = fundReturns.reduce((a, b) => a + b, 0) / fundReturns.length;
  const meanBench = benchReturns.reduce((a, b) => a + b, 0) / benchReturns.length;

  let covariance = 0;
  let varianceBench = 0;

  for (let i = 0; i < fundReturns.length; i++) {
    const diffFund = fundReturns[i] - meanFund;
    const diffBench = benchReturns[i] - meanBench;
    covariance += diffFund * diffBench;
    varianceBench += diffBench * diffBench;
  }

  if (varianceBench === 0) return 1.0;
  return covariance / varianceBench;
}

/**
 * Calculates CAGR (Compound Annual Growth Rate)
 */
export function calculateCAGR(startValue: number, endValue: number, years: number): number {
  if (startValue <= 0 || years <= 0) return 0;
  return Math.pow(endValue / startValue, 1 / years) - 1;
}

/**
 * Calculates CAGR for benchmark data over a given number of years.
 */
export function calculateBenchCAGR(benchData: {close: number}[], years: number): number | null {
  if (!benchData || benchData.length < 2) return null;
  // benchData is oldest first
  const latest = benchData[benchData.length - 1].close;
  // Approximate years index
  const days = Math.round(years * 252);
  const startIdx = Math.max(0, benchData.length - 1 - days);
  const start = benchData[startIdx].close;
  
  if (start <= 0) return null;
  return calculateCAGR(start, latest, years);
}

/**
 * Calculates Alpha (Jensen's Alpha)
 * alpha = fundCAGR - (Rf + beta * (benchmarkCAGR - Rf))
 * Rf = Risk-free rate (default 0.065 for India)
 */
export function calculateAlpha(fundCAGR: number, benchmarkCAGR: number, beta: number, riskFreeRate: number = 0.065): number {
  return fundCAGR - (riskFreeRate + beta * (benchmarkCAGR - riskFreeRate));
}

/**
 * Aligns two sets of time series data by date.
 */
export function alignData(fundData: {date: string, nav: string}[], benchData: {date: string, close: number}[]): {fundReturns: number[], benchReturns: number[], commonDates: string[]} {
  const benchMap = new Map<string, number>();
  benchData.forEach(d => benchMap.set(d.date, d.close));

  const alignedFund: number[] = [];
  const alignedBench: number[] = [];
  const commonDates: string[] = [];

  // fundData is chronological (oldest first) from filterByPeriod
  for (let i = 1; i < fundData.length; i++) {
    const date = fundData[i].date;
    const prevDate = fundData[i-1].date;
    
    if (benchMap.has(date) && benchMap.has(prevDate)) {
      const fundRet = (parseFloat(fundData[i].nav) / parseFloat(fundData[i-1].nav)) - 1;
      const benchRet = (benchMap.get(date)! / benchMap.get(prevDate)!) - 1;
      
      alignedFund.push(fundRet);
      alignedBench.push(benchRet);
      commonDates.push(date);
    }
  }

  return { fundReturns: alignedFund, benchReturns: alignedBench, commonDates };
}

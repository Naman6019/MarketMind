export type NavPoint = { date: string; nav: string };
export type DailyReturn = number;

export interface FundMeta {
  fund_house: string;
  scheme_type: string;
  scheme_category: string;
  scheme_code: number;
  scheme_name: string;
}

export interface FundDataResponse {
  meta: FundMeta;
  data: NavPoint[];
  status: string;
  details?: any;
  returns?: Record<string, number | null>;
  riskMetrics?: any;
}

export interface FundMetrics {
  returns: Record<'1M'|'3M'|'6M'|'1Y'|'3Y'|'5Y', number | null>;
  cagr: Record<'1Y'|'3Y'|'5Y', number | null>;
  alpha: number | null;
  beta: number | null;
  sharpe: number | null;
  stdDev: number | null;
}

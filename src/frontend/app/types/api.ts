
export type Money = string;

// GET /v1/assets

export interface Asset {
  symbol: string;
  name: string;
  price: Money | null;
  price_currency: string | null;
  quoted_at: string | null;
  obtained_at: string | null;
  delayed: boolean;
}

export interface AssetsResponse {
  market_open: boolean;
  assets: Asset[];
}

// PUT /v1/me/activity/daily-totals
// Used by issue #284

export interface DailyActivityTotal {
  activity_date: string;
  activity_type: "steps";
  step_count: number;
}

export interface SyncActivityRequest {
  time_zone: string;
  totals: DailyActivityTotal[];
}

export interface SyncedActivityTotal
  extends DailyActivityTotal {
  counted: boolean;
  reward: Money;
  credited_now: Money;
}

export interface SyncActivityResponse {
  totals: SyncedActivityTotal[];
  cash_balance: Money;
  steps_per_coin: number;
}

export interface BalanceResponse {
  cash_balance: string;
}


export interface BuyTradeRequest {
  request_id: string;
  symbol: string;
  trade_type: "buy";
  quantity: number;
  expected_price: string;
}

export interface BuyTradeResponse {
  trade_id: string;
  status: string;
  unit_price: string;
  currency_amount: string;
  executed_at: string;
  cash_balance: string;
}

export interface PortfolioHolding {
  symbol: string;
  quantity: number;
  price: string | null;
  quoted_at: string | null;
  delayed: boolean;
  value: string | null;
}

export interface PortfolioResponse {
  cash_balance: string;
  holdings: PortfolioHolding[];
  holdings_value: string;
  total_value: string;
  simulated: boolean;
}

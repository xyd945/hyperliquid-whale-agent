export interface WhaleDeposit {
  wallet: string;
  amount: string;
  token: string;
  txHash: string;
  timestamp: number;
  amountUsd: number;
}

export interface HyperliquidPosition {
  coin: string;
  side: 'long' | 'short';
  notionalUsd: number;
  avgEntry: number;
  liqPx: number;
  leverage?: number;
}

export interface HyperliquidFill {
  coin: string;
  action: 'buy' | 'sell';
  notionalUsd: number;
  price: number;
  timestamp: number;
}

export interface EnrichedWallet {
  wallet: string;
  positions: HyperliquidPosition[];
  recentFills: HyperliquidFill[];
  totalNotionalUsd: number;
}

export interface WhaleDetectionParams {
  thresholdUsd: number;
  lookbackMinutes: number;
}

export interface BlockscoutTransaction {
  hash: string;
  to: string;
  from: string;
  value: string;
  timestamp: string;
  input: string;
  logs: BlockscoutLog[];
}

export interface BlockscoutLog {
  address: string;
  topics: string[];
  data: string;
  decoded?: {
    name: string;
    params: Array<{
      name: string;
      type: string;
      value: string;
    }>;
  };
}
// Hyperliquid Bridge Contract on Arbitrum
export const BRIDGE_CONTRACT_ADDRESS = '0x2Df1c51E09aECF9cacB7bc98cB1742757f163dF7';

// API Endpoints
export const BLOCKSCOUT_BASE_URL = 'https://arbitrum.blockscout.com';
export const HYPERLIQUID_INFO_ENDPOINT = 'https://api.hyperliquid.xyz/info';

// Whale Detection Thresholds
export const ALERT_THRESHOLD_USD = 10_000_000; // $10M
export const LOOKBACK_MINUTES_DEFAULT = 15;

// Bridge Contract ABI - Deposit event signature
export const DEPOSIT_EVENT_SIGNATURE = '0x5548c837ab068cf56a2c2479df0882a4922fd203edb7517321831d95078c5f62';

// Token addresses and decimals (for USD conversion)
export const TOKEN_INFO = {
  USDC: {
    address: '0xaf88d065e77c8cc2239327c5edb3a432268e5831',
    decimals: 6,
    usdRate: 1.0
  },
  USDT: {
    address: '0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9',
    decimals: 6,
    usdRate: 1.0
  },
  ETH: {
    address: '0x0000000000000000000000000000000000000000',
    decimals: 18,
    usdRate: 2500 // Approximate, should be fetched from price API in production
  }
} as const;

export type TokenSymbol = keyof typeof TOKEN_INFO;
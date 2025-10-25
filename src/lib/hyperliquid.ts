import { HYPERLIQUID_INFO_ENDPOINT } from './constants';
import { HyperliquidPosition, HyperliquidFill, EnrichedWallet } from '@/types/whale';

export class HyperliquidClient {
  private baseUrl: string;

  constructor(baseUrl: string = HYPERLIQUID_INFO_ENDPOINT) {
    this.baseUrl = baseUrl;
  }

  /**
   * Make a request to Hyperliquid info API
   */
  private async makeRequest(type: string, user?: string): Promise<any> {
    try {
      const body: any = { type };
      if (user) {
        body.user = user;
      }

      const response = await fetch(this.baseUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        throw new Error(`Hyperliquid API error: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Hyperliquid API request failed:', error);
      throw error;
    }
  }

  /**
   * Get clearinghouse state for a user (positions, margins, etc.)
   */
  async getClearinghouseState(user: string): Promise<any> {
    return this.makeRequest('clearinghouseState', user);
  }

  /**
   * Get recent fills (trades) for a user
   */
  async getUserFills(user: string): Promise<any> {
    return this.makeRequest('userFills', user);
  }

  /**
   * Get meta info (coin information, universe, etc.)
   */
  async getMeta(): Promise<any> {
    return this.makeRequest('meta');
  }

  /**
   * Parse positions from clearinghouse state
   */
  private parsePositions(clearinghouseState: any): HyperliquidPosition[] {
    const positions: HyperliquidPosition[] = [];

    try {
      if (clearinghouseState?.assetPositions) {
        for (const position of clearinghouseState.assetPositions) {
          if (position.position && parseFloat(position.position.szi) !== 0) {
            const szi = parseFloat(position.position.szi);
            const entryPx = parseFloat(position.position.entryPx || '0');
            const unrealizedPnl = parseFloat(position.position.unrealizedPnl || '0');
            
            positions.push({
              coin: position.position.coin,
              side: szi > 0 ? 'long' : 'short',
              notionalUsd: Math.abs(szi * entryPx),
              avgEntry: entryPx,
              liqPx: parseFloat(position.position.liquidationPx || '0'),
              leverage: position.position.leverage ? parseFloat(position.position.leverage) : undefined
            });
          }
        }
      }
    } catch (error) {
      console.error('Error parsing positions:', error);
    }

    return positions;
  }

  /**
   * Parse recent fills from user fills data
   */
  private parseFills(userFills: any): HyperliquidFill[] {
    const fills: HyperliquidFill[] = [];

    try {
      if (Array.isArray(userFills)) {
        for (const fill of userFills.slice(0, 10)) { // Get last 10 fills
          if (fill.coin && fill.px && fill.sz) {
            const size = parseFloat(fill.sz);
            const price = parseFloat(fill.px);
            
            fills.push({
              coin: fill.coin,
              action: size > 0 ? 'buy' : 'sell',
              notionalUsd: Math.abs(size * price),
              price: price,
              timestamp: fill.time || Date.now()
            });
          }
        }
      }
    } catch (error) {
      console.error('Error parsing fills:', error);
    }

    return fills;
  }

  /**
   * Enrich wallet data with positions and recent trades
   */
  async enrichWallet(walletAddress: string): Promise<EnrichedWallet> {
    try {
      // Fetch both clearinghouse state and user fills in parallel
      const [clearinghouseState, userFills] = await Promise.all([
        this.getClearinghouseState(walletAddress),
        this.getUserFills(walletAddress)
      ]);

      const positions = this.parsePositions(clearinghouseState);
      const recentFills = this.parseFills(userFills);

      // Calculate total notional USD across all positions
      const totalNotionalUsd = positions.reduce((sum, pos) => sum + pos.notionalUsd, 0);

      return {
        wallet: walletAddress,
        positions,
        recentFills,
        totalNotionalUsd
      };
    } catch (error) {
      console.error(`Error enriching wallet ${walletAddress}:`, error);
      
      // Return empty data on error
      return {
        wallet: walletAddress,
        positions: [],
        recentFills: [],
        totalNotionalUsd: 0
      };
    }
  }

  /**
   * Get market data for price information
   */
  async getAllMids(): Promise<any> {
    return this.makeRequest('allMids');
  }

  /**
   * Format wallet summary for display
   */
  formatWalletSummary(enrichedWallet: EnrichedWallet): string {
    const { wallet, positions, recentFills, totalNotionalUsd } = enrichedWallet;
    
    if (positions.length === 0) {
      return `Whale ${wallet.slice(0, 6)}...${wallet.slice(-4)} has no open positions.`;
    }

    const topPosition = positions[0]; // Largest position
    const recentActivity = recentFills.length > 0 
      ? `, recent ${recentFills[0].action} of ${recentFills[0].coin} at $${recentFills[0].price.toFixed(2)}`
      : '';

    return `Whale ${wallet.slice(0, 6)}...${wallet.slice(-4)} has $${totalNotionalUsd.toLocaleString()} in positions. ` +
           `Top position: ${topPosition.side} ${topPosition.coin} worth $${topPosition.notionalUsd.toLocaleString()} ` +
           `(entry: $${topPosition.avgEntry.toFixed(2)}, liq: $${topPosition.liqPx.toFixed(2)})${recentActivity}.`;
  }
}

// Export singleton instance
export const hyperliquidClient = new HyperliquidClient();
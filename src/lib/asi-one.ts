/**
 * ASI:ONE API Integration
 * Connects frontend to Agentverse agents through ASI:ONE protocol
 */

export interface ASIOneConfig {
  apiKey?: string;
  baseUrl: string;
  agentAddress?: string;
  localMailboxUrl?: string;
}

export interface ASIOneMessage {
  content: string;
  sender: 'user' | 'agent';
  timestamp: number;
}

export interface ASIOneResponse {
  success: boolean;
  message?: string;
  data?: any;
  error?: string;
  source?: 'asi-one' | 'local-mailbox';
}

export interface AgentDiscoveryResult {
  address: string;
  name: string;
  description: string;
  capabilities: string[];
  isOnline: boolean;
  source: 'asi-one' | 'local';
}

export class ASIOneClient {
  private config: ASIOneConfig;

  constructor(config: ASIOneConfig) {
    this.config = config;
  }

  /**
   * Send message to agent via ASI:ONE or local mailbox
   */
  async sendMessage(message: string, agentAddress?: string, preferLocal = false): Promise<ASIOneResponse> {
    try {
      const targetAgent = agentAddress || this.config.agentAddress;
      
      if (!targetAgent) {
        throw new Error('Agent address is required');
      }

      // Try local mailbox first if preferred or if it's configured
      if (preferLocal && this.config.localMailboxUrl) {
        try {
          const localResponse = await this.sendToLocalMailbox(message, targetAgent);
          if (localResponse.success) {
            return { ...localResponse, source: 'local-mailbox' };
          }
        } catch (error) {
          console.warn('Local mailbox failed, falling back to ASI:ONE:', error);
        }
      }

      // Use the correct ASI:ONE chat completions endpoint
      const response = await fetch(`${this.config.baseUrl}/v1/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          ...(this.config.apiKey && { 'Authorization': `Bearer ${this.config.apiKey}` })
        },
        body: JSON.stringify({
          model: "asi1-mini",
          messages: [
            {
              role: "system",
              content: `You are a whale tracking agent with address ${targetAgent}. Analyze Hyperliquid trading data and provide insights about large trades and whale activity.`
            },
            {
              role: "user",
              content: message
            }
          ],
          temperature: 0.7,
          stream: false,
          max_tokens: 1024
        })
      });

      if (!response.ok) {
        throw new Error(`ASI:ONE API error: ${response.status}`);
      }

      const data = await response.json();
      
      // Extract the assistant's response from the chat completion format
      const assistantMessage = data.choices?.[0]?.message?.content || data.message || 'No response received';
      
      return {
        success: true,
        message: assistantMessage,
        data,
        source: 'asi-one'
      };
    } catch (error) {
      console.error('ASI:ONE API error:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  /**
   * Send message to local mailbox agent
   */
  private async sendToLocalMailbox(message: string, agentAddress: string): Promise<ASIOneResponse> {
    if (!this.config.localMailboxUrl) {
      throw new Error('Local mailbox URL not configured');
    }

    const response = await fetch(`${this.config.localMailboxUrl}/send`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        to: agentAddress,
        message: message,
        type: 'query'
      })
    });

    if (!response.ok) {
      throw new Error(`Local mailbox error: ${response.status}`);
    }

    const data = await response.json();
    
    return {
      success: true,
      message: data.response || data.message || 'Response received',
      data
    };
  }

  /**
   * Discover available whale agents
   */
  async discoverAgents(): Promise<AgentDiscoveryResult[]> {
    const agents: AgentDiscoveryResult[] = [];

    // Check local mailbox agent
    if (this.config.localMailboxUrl && this.config.agentAddress) {
      try {
        const localAgent = await this.checkLocalAgent();
        if (localAgent) {
          agents.push(localAgent);
        }
      } catch (error) {
        console.warn('Failed to check local agent:', error);
      }
    }

    // Discover agents via ASI:ONE
    try {
      const asiAgents = await this.discoverASIOneAgents();
      agents.push(...asiAgents);
    } catch (error) {
      console.warn('Failed to discover ASI:ONE agents:', error);
    }

    return agents;
  }

  /**
   * Check if local whale agent is available
   */
  private async checkLocalAgent(): Promise<AgentDiscoveryResult | null> {
    if (!this.config.localMailboxUrl || !this.config.agentAddress) {
      return null;
    }

    try {
      const response = await fetch(`${this.config.localMailboxUrl}/status`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        }
      });

      if (response.ok) {
        const data = await response.json();
        return {
          address: this.config.agentAddress,
          name: 'Local Whale Agent',
          description: 'Local Hyperliquid whale tracking agent with real-time monitoring',
          capabilities: ['whale-tracking', 'deposit-monitoring', 'trading-analysis', 'real-time-alerts'],
          isOnline: data.status === 'online' || data.running === true,
          source: 'local'
        };
      }
    } catch (error) {
      console.warn('Local agent check failed:', error);
    }

    return null;
  }

  /**
   * Discover whale agents via ASI:ONE
   */
  private async discoverASIOneAgents(): Promise<AgentDiscoveryResult[]> {
    try {
      // For now, return a default agent since we know ASI:One is configured
      // In the future, this could search for actual agents via ASI:One API
      if (this.config.agentAddress) {
        return [{
          address: this.config.agentAddress,
          name: 'Whale Agent (ASI:One)',
          description: 'Hyperliquid whale tracking agent via ASI:One',
          capabilities: ['whale-tracking', 'market-analysis', 'trading-insights'],
          isOnline: true,
          source: 'asi-one' as const
        }];
      }
      
      return [];
    } catch (error) {
      console.error('ASI:ONE agent discovery failed:', error);
      return [];
    }
  }

  /**
   * Get agent status and capabilities
   */
  async getAgentInfo(agentAddress?: string): Promise<ASIOneResponse> {
    try {
      const targetAgent = agentAddress || this.config.agentAddress;
      
      if (!targetAgent) {
        throw new Error('Agent address is required');
      }

      const response = await fetch(`${this.config.baseUrl}/api/v1/agents/${targetAgent}`, {
        method: 'GET',
        headers: {
          ...(this.config.apiKey && { 'Authorization': `Bearer ${this.config.apiKey}` })
        }
      });

      if (!response.ok) {
        throw new Error(`ASI:ONE API error: ${response.status}`);
      }

      const data = await response.json();
      
      return {
        success: true,
        data
      };
    } catch (error) {
      console.error('ASI:ONE API error:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  /**
   * Register agent with ASI:ONE (for agent developers)
   */
  async registerAgent(agentMetadata: any): Promise<ASIOneResponse> {
    try {
      const response = await fetch(`${this.config.baseUrl}/api/v1/agents/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(this.config.apiKey && { 'Authorization': `Bearer ${this.config.apiKey}` })
        },
        body: JSON.stringify(agentMetadata)
      });

      if (!response.ok) {
        throw new Error(`ASI:ONE API error: ${response.status}`);
      }

      const data = await response.json();
      
      return {
        success: true,
        data
      };
    } catch (error) {
      console.error('ASI:ONE registration error:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }
}

// Default configuration for development
const defaultConfig: ASIOneConfig = {
  baseUrl: process.env.NEXT_PUBLIC_ASI_ONE_URL || 'https://api.asi1.ai',
  apiKey: process.env.NEXT_PUBLIC_ASI_ONE_API_KEY,
  agentAddress: process.env.NEXT_PUBLIC_WHALE_AGENT_ADDRESS || 'agent1qfe8jqus8ka24sneygllla33uv5qxcc63rq6pxqmpmhk3mcga72mungnmne',
  localMailboxUrl: process.env.NEXT_PUBLIC_LOCAL_MAILBOX_URL || 'http://localhost:8000'
};

// Export singleton instance
export const asiOneClient = new ASIOneClient(defaultConfig);

// Utility function to check if ASI:ONE is configured
export function isASIOneConfigured(): boolean {
  return !!(defaultConfig.baseUrl && defaultConfig.apiKey && defaultConfig.agentAddress);
}

// Utility function to check if local mailbox is available
export function isLocalMailboxConfigured(): boolean {
  return !!(defaultConfig.localMailboxUrl && defaultConfig.agentAddress);
}
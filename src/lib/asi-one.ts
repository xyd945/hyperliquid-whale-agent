/**
 * ASI:ONE API Integration
 * Connects frontend to Agentverse agents through ASI:ONE protocol
 */

export interface ASIOneConfig {
  apiKey?: string;
  baseUrl: string;
  agentAddress?: string;
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
}

export class ASIOneClient {
  private config: ASIOneConfig;

  constructor(config: ASIOneConfig) {
    this.config = config;
  }

  /**
   * Send message to Agentverse agent via ASI:ONE
   */
  async sendMessage(message: string, agentAddress?: string): Promise<ASIOneResponse> {
    try {
      const targetAgent = agentAddress || this.config.agentAddress;
      
      if (!targetAgent) {
        throw new Error('Agent address is required');
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
  baseUrl: process.env.NEXT_PUBLIC_ASI_ONE_URL || 'https://api.asi.one',
  apiKey: process.env.ASI_ONE_API_KEY,
  agentAddress: process.env.NEXT_PUBLIC_WHALE_AGENT_ADDRESS
};

// Export singleton instance
export const asiOneClient = new ASIOneClient(defaultConfig);

// Utility function to check if ASI:ONE is configured
export function isASIOneConfigured(): boolean {
  return !!(defaultConfig.baseUrl && defaultConfig.agentAddress);
}
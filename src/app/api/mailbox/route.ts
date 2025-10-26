import { NextRequest, NextResponse } from 'next/server';

// Simple in-memory message queue for local agent communication
interface Message {
  id: string;
  to: string;
  from: string;
  content: string;
  timestamp: number;
  type: 'query' | 'response';
}

class LocalMailbox {
  private messages: Message[] = [];
  private responses: Map<string, string> = new Map();

  addMessage(message: Omit<Message, 'id' | 'timestamp'>): string {
    const id = Date.now().toString() + Math.random().toString(36).substr(2, 9);
    const fullMessage: Message = {
      ...message,
      id,
      timestamp: Date.now()
    };
    
    this.messages.push(fullMessage);
    
    // Clean up old messages (keep last 100)
    if (this.messages.length > 100) {
      this.messages = this.messages.slice(-100);
    }
    
    return id;
  }

  getMessages(agentAddress?: string): Message[] {
    if (agentAddress) {
      return this.messages.filter(m => m.to === agentAddress || m.from === agentAddress);
    }
    return this.messages;
  }

  setResponse(messageId: string, response: string): void {
    this.responses.set(messageId, response);
  }

  getResponse(messageId: string): string | undefined {
    return this.responses.get(messageId);
  }
}

const mailbox = new LocalMailbox();

export async function POST(request: NextRequest) {
  try {
    const { to, message, type = 'query' } = await request.json();

    if (!to || !message) {
      return NextResponse.json(
        { error: 'Missing required fields: to, message' },
        { status: 400 }
      );
    }

    // Add message to mailbox
    const messageId = mailbox.addMessage({
      to,
      from: 'frontend',
      content: message,
      type
    });

    // For demo purposes, simulate whale agent responses
    let response = '';
    const lowerMessage = message.toLowerCase();
    
    if (lowerMessage.includes('status')) {
      response = `🐋 **Whale Agent Status Report**

**System Status:** ✅ Online and monitoring
**Connected to:** Hyperliquid Mainnet
**Last Update:** ${new Date().toLocaleString()}

**Current Monitoring:**
• Large deposits (>$100K)
• Whale trading patterns
• Market impact analysis
• Real-time alerts

**Recent Activity:**
• 3 large deposits detected in last hour
• 2 whale trades with >$1M volume
• Market volatility: Moderate

Type "alerts" for recent whale alerts or "help" for available commands.`;
    } else if (lowerMessage.includes('alerts')) {
      response = `🚨 **Recent Whale Alerts**

**Last 24 Hours:**
1. **Large Deposit** - $2.3M USDC
   • Address: 0x742d...8f3a
   • Time: 2 hours ago
   • Impact: Moderate buying pressure

2. **Whale Trade** - $1.8M ETH/USDC
   • Size: 450 ETH
   • Direction: Sell
   • Time: 4 hours ago
   • Price Impact: -0.3%

3. **Position Build** - $5.2M Multi-asset
   • Assets: ETH, BTC, SOL
   • Strategy: Accumulation
   • Time: 6 hours ago

**Market Sentiment:** Cautiously bullish
**Whale Activity Level:** High`;
    } else if (lowerMessage.includes('help')) {
      response = `🐋 **Whale Agent Commands**

**Available Commands:**
• \`status\` - Get current system status
• \`alerts\` - View recent whale alerts
• \`whale [address]\` - Analyze specific wallet
• \`deposits\` - Show recent large deposits
• \`trades\` - View significant trades
• \`market\` - Current market analysis

**Features:**
✅ Real-time whale monitoring
✅ Large deposit tracking
✅ Trading pattern analysis
✅ Market impact assessment
✅ Custom alerts

**Data Sources:**
• Hyperliquid API
• On-chain transaction data
• Trading volume analysis

Need help with a specific command? Just ask!`;
    } else if (lowerMessage.includes('whale') && lowerMessage.length > 10) {
      response = `🔍 **Whale Analysis**

Analyzing wallet activity...

**Wallet Overview:**
• Total Portfolio: $12.4M
• Active Since: 2023-08
• Trade Count: 1,247
• Win Rate: 68%

**Recent Activity:**
• Last Trade: 3 hours ago
• Volume (24h): $890K
• P&L (7d): +$234K (+2.1%)

**Trading Patterns:**
• Preferred Assets: ETH, BTC, SOL
• Avg Position Size: $150K
• Hold Time: 2.3 days
• Risk Level: Moderate

**Market Impact:**
• Price Impact: Low-Medium
• Following: 23 copy traders
• Influence Score: 7.2/10`;
    } else {
      response = `🐋 **Whale Agent Response**

I received your message: "${message}"

I'm currently monitoring Hyperliquid for whale activity. Here's what I can help you with:

• **Real-time whale tracking** - Monitor large trades and deposits
• **Market analysis** - Understand whale impact on prices  
• **Alert system** - Get notified of significant whale movements
• **Portfolio analysis** - Deep dive into whale wallets

Try asking:
• "status" - Current system status
• "alerts" - Recent whale activity
• "help" - Full command list

What would you like to know about whale activity?`;
    }

    // Store the response
    mailbox.setResponse(messageId, response);

    return NextResponse.json({
      success: true,
      messageId,
      response,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('Mailbox API Error:', error);
    
    return NextResponse.json(
      { 
        error: 'Internal server error',
        message: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const agentAddress = searchParams.get('agent');
    const action = searchParams.get('action');

    if (action === 'status') {
      return NextResponse.json({
        status: 'online',
        running: true,
        agent: 'Hyperliquid Whale Watcher',
        address: 'agent1qfe8jqus8ka24sneygllla33uv5qxcc63rq6pxqmpmhk3mcga72mungnmne',
        timestamp: new Date().toISOString(),
        messageCount: mailbox.getMessages().length
      });
    }

    // Return messages for the agent
    const messages = mailbox.getMessages(agentAddress || undefined);
    
    return NextResponse.json({
      success: true,
      messages,
      count: messages.length,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('Mailbox GET Error:', error);
    
    return NextResponse.json(
      { 
        error: 'Internal server error',
        message: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}
# 🐋 Hyperliquid Whale Watcher

A real-time whale detection and trading intelligence system for Hyperliquid bridge deposits. Built for the hackathon with a focus on stateless architecture and real-time processing.

## 🎯 Features

- **Real-time Whale Detection**: Monitor large deposits (>$100k) to Hyperliquid bridge using Blockscout MCP
- **Trading Intelligence**: Analyze whale positions and recent trading activity on Hyperliquid
- **Interactive Chat Interface**: Modern chat UI for querying whale activity
- **ASI:ONE Integration**: Connect to Agentverse agents via ASI:ONE protocol
- **Responsive Design**: Beautiful UI with Tailwind CSS and dark mode support

## 🏗️ Architecture

### Core Components

1. **Blockscout Integration** (`src/lib/blockscout.ts`)
   - Monitors Ethereum mainnet for bridge deposits
   - Filters transactions above threshold
   - Decodes deposit events

2. **Hyperliquid API Client** (`src/lib/hyperliquid.ts`)
   - Fetches wallet positions and trading data
   - Calculates total exposure and recent activity
   - Formats whale summaries

3. **Agentverse Agent** (`src/lib/agentverse.ts`)
   - Provides `getRecentWhales` and `enrichWallet` tools
   - Handles natural language queries
   - Formats responses for chat interface

4. **ASI:ONE Integration** (`src/lib/asi-one.ts`)
   - Connects frontend to Agentverse agents
   - Fallback to local processing
   - Agent registration capabilities

5. **Next.js Frontend** (`src/components/chat-interface.tsx`)
   - Real-time chat interface
   - Message history and formatting
   - Quick action buttons

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ 
- npm or yarn
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd hyperliquid-whale-agent
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env.local
   ```
   
   Edit `.env.local` with your configuration:
   ```env
   # ASI:ONE Configuration (optional)
   NEXT_PUBLIC_ASI_ONE_URL=https://api.asi.one
   ASI_ONE_API_KEY=your_api_key
   NEXT_PUBLIC_WHALE_AGENT_ADDRESS=your_agent_address
   
   # Whale Detection Settings
   ALERT_THRESHOLD_USD=100000
   LOOKBACK_MINUTES_DEFAULT=60
   ```

4. **Start the development server**
   ```bash
   npm run dev
   ```

5. **Open your browser**
   Navigate to `http://localhost:3000`

## 💬 Usage

### Chat Commands

- **"Show recent whales"** - Display recent large deposits
- **"Whale activity today"** - Get today's whale movements  
- **Provide wallet address** - Analyze specific wallet (e.g., `0x123...abc`)

### Example Queries

```
User: Show recent whales
Bot: 🐋 3 Whale Deposits Detected:
     • $250,000 USDC deposit
       Wallet: 0x1234...5678
       TX: 0xabcd...

User: 0x1234567890123456789012345678901234567890
Bot: Whale 0x1234...7890 has $1.2M in positions. 
     Top position: long ETH worth $800K (entry: $2,450, liq: $2,100)
```

## 🔧 Configuration

### Whale Detection Parameters

- **ALERT_THRESHOLD_USD**: Minimum deposit amount to trigger whale alert (default: $100,000)
- **LOOKBACK_MINUTES_DEFAULT**: How far back to scan for deposits (default: 60 minutes)

### Supported Tokens

- **USDC**: 0xA0b86a33E6441c8C06DD2c2b4c1c0e0e8F8b8c8d
- **USDT**: 0xdAC17F958D2ee523a2206206994597C13D831ec7  
- **ETH**: Native ETH deposits

### API Endpoints

- **POST /api/whale** - Send chat message
- **GET /api/whale** - Health check and status

## 🧪 Testing

### Manual Testing

1. **Test whale detection**:
   ```bash
   curl -X POST http://localhost:3000/api/whale \
     -H "Content-Type: application/json" \
     -d '{"message": "show recent whales"}'
   ```

2. **Test wallet analysis**:
   ```bash
   curl -X POST http://localhost:3000/api/whale \
     -H "Content-Type: application/json" \
     -d '{"message": "0x1234567890123456789012345678901234567890"}'
   ```

3. **Health check**:
   ```bash
   curl http://localhost:3000/api/whale
   ```

## 🚢 Deployment

### Vercel Deployment

1. **Connect to Vercel**
   ```bash
   npm install -g vercel
   vercel login
   vercel
   ```

2. **Set environment variables** in Vercel dashboard

3. **Deploy**
   ```bash
   vercel --prod
   ```

### Environment Variables for Production

```env
NEXT_PUBLIC_ASI_ONE_URL=https://api.asi.one
ASI_ONE_API_KEY=prod_api_key
NEXT_PUBLIC_WHALE_AGENT_ADDRESS=agent_address
ALERT_THRESHOLD_USD=100000
LOOKBACK_MINUTES_DEFAULT=60
```

## 📊 Data Flow

```
Ethereum Mainnet → Blockscout API → Whale Detection → Hyperliquid API → Agent Processing → Chat Interface
                                                                      ↓
                                                              ASI:ONE (optional)
                                                                      ↓
                                                              Agentverse Agent
```

## 🔒 Security Considerations

- No private keys stored
- Read-only API access
- Rate limiting on external APIs
- Input validation and sanitization
- CORS protection

## 🛠️ Development

### Project Structure

```
src/
├── app/                 # Next.js app router
│   ├── api/whale/      # API endpoints
│   ├── globals.css     # Global styles
│   ├── layout.tsx      # Root layout
│   └── page.tsx        # Home page
├── components/         # React components
│   └── chat-interface.tsx
├── lib/               # Core logic
│   ├── agentverse.ts  # Agent implementation
│   ├── asi-one.ts     # ASI:ONE integration
│   ├── blockscout.ts  # Blockchain monitoring
│   ├── constants.ts   # Configuration
│   └── hyperliquid.ts # Trading data
└── types/             # TypeScript definitions
    └── whale.ts
```

### Adding New Features

1. **New whale detection sources**: Extend `blockscout.ts`
2. **Additional trading data**: Enhance `hyperliquid.ts`  
3. **Chat commands**: Update `agentverse.ts`
4. **UI components**: Add to `components/`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- **Blockscout** for blockchain data access
- **Hyperliquid** for trading API
- **Agentverse** for agent infrastructure  
- **ASI:ONE** for agent connectivity
- **Next.js** and **Tailwind CSS** for the frontend

## 📞 Support

For questions or issues:
1. Check the [Issues](../../issues) page
2. Review the documentation
3. Contact the development team

---

**⚠️ Disclaimer**: This tool is for research and educational purposes only. Not financial advice. Always do your own research before making trading decisions.
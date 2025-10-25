# Hyperliquid Whale Watcher - Agentverse Deployment Guide

## Overview
This guide explains how to deploy the Hyperliquid Whale Watcher agent to Agentverse and configure the frontend to communicate with it.

## Files for Deployment

### 1. Agent Code
- **File**: `whale_agent_agentverse.py`
- **Description**: Clean version of the whale agent ready for Agentverse deployment
- **Features**:
  - Blockscout MCP integration for blockchain data
  - Hyperliquid API integration for trading data
  - Whale deposit detection with configurable thresholds
  - Wallet enrichment with position and trading history

### 2. Dependencies
- **File**: `requirements.txt`
- **Contents**:
  ```
  aiohttp==3.9.1
  uagents==0.12.0
  requests==2.31.0
  pydantic==2.5.0
  ```

## Deployment Steps

### Step 1: Deploy to Agentverse
1. Go to [Agentverse](https://agentverse.ai)
2. Create a new agent project
3. Copy the contents of `whale_agent_agentverse.py` into the agent code editor
4. Install the dependencies from `requirements.txt`
5. Deploy the agent and note the agent address

### Step 2: Update Frontend Configuration
1. Update your `.env` file with the new agent address:
   ```
   NEXT_PUBLIC_WHALE_AGENT_ADDRESS=<your_deployed_agent_address>
   ```

2. Ensure ASI:ONE configuration is correct:
   ```
   NEXT_PUBLIC_ASI_ONE_URL=https://api.asi.one
   ASI_ONE_API_KEY=<your_asi_one_api_key>
   ```

### Step 3: Test the Integration
1. Start your frontend: `npm run dev`
2. Navigate to `http://localhost:3001`
3. Test whale detection queries:
   - "Show recent whales"
   - "Any whale activity?"
   - Provide a wallet address for analysis

## Agent Capabilities

### 1. Whale Detection
- Monitors Hyperliquid bridge contract for large deposits
- Configurable threshold (default: $10M)
- Uses Blockscout MCP for blockchain data access

### 2. Wallet Analysis
- Fetches Hyperliquid trading positions
- Shows recent trading activity
- Calculates total position value

### 3. Message Types Supported
- **WhaleQueryRequest**: General queries about whale activity
- **WhaleDetectionRequest**: Specific whale detection with custom parameters
- **WalletEnrichmentRequest**: Detailed wallet analysis

## Configuration Constants

The agent uses these default configurations:
- **Bridge Contract**: `0x2Df1c51E09aECF9cacB7bc98cB1742757f163dF7`
- **Alert Threshold**: $10,000,000 USD
- **Lookback Period**: 15 minutes
- **Supported Tokens**: USDC, USDT, ETH

## Troubleshooting

### Common Issues
1. **MCP Connection Errors**: Ensure Blockscout MCP is accessible
2. **Hyperliquid API Errors**: Check API endpoint availability
3. **Agent Communication**: Verify ASI:ONE configuration and agent address

### Logs
The agent logs important events:
- Startup confirmation
- Query processing
- Error handling
- Whale detection results

## Security Notes
- No private keys or sensitive data in the agent code
- All API calls use public endpoints
- Agent address is public and safe to share

## Next Steps
After successful deployment:
1. Monitor agent logs for proper operation
2. Test various query types
3. Adjust thresholds as needed
4. Consider adding more token support or features
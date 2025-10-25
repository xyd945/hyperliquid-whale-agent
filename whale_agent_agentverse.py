"""
Hyperliquid Whale Watcher Agent - Agentverse Deployment Version
A Fetch.ai uAgent for detecting whale deposits and analyzing Hyperliquid trading data
Uses external Blockscout MCP server for blockchain data access

This version uses proper MCP integration with external MCP server connection.
"""

import json
import time
import asyncio
import aiohttp
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import uuid4
from openai import OpenAI
from uagents import Agent, Context, Model, Protocol
from pydantic import BaseModel

# Import chat protocol for ASI:One compatibility
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    EndSessionContent,
    chat_protocol_spec
)

# Import MCP components for external server connection
try:
    from uagents.mcp import MCPClient, MCPServerAdapter
    MCP_AVAILABLE = True
except ImportError:
    print("MCP components not available - falling back to direct API calls")
    MCP_AVAILABLE = False

# Configuration Constants
BRIDGE_CONTRACT_ADDRESS = "0x2Df1c51E09aECF9cacB7bc98cB1742757f163dF7"
BLOCKSCOUT_MCP_URL = "https://mcp.blockscout.com/mcp"
HYPERLIQUID_INFO_ENDPOINT = "https://api.hyperliquid.xyz/info"
ALERT_THRESHOLD_USD = 10_000_000  # $10M
LOOKBACK_MINUTES_DEFAULT = 15
DEPOSIT_EVENT_SIGNATURE = "0x5548c837ab068cf56a2c2479df0882a4922fd203edb7517321831d95078c5f62"
ARBITRUM_CHAIN_ID = 42161

# Token Information
TOKEN_INFO = {
    "USDC": {
        "address": "0xaf88d065e77c8cc2239327c5edb3a432268e5831",
        "decimals": 6,
        "usd_rate": 1.0
    },
    "USDT": {
        "address": "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9",
        "decimals": 6,
        "usd_rate": 1.0
    },
    "ETH": {
        "address": "0x0000000000000000000000000000000000000000",
        "decimals": 18,
        "usd_rate": 2500  # Approximate - should fetch from price API
    }
}

# Pydantic Models for Message Handling
class WhaleQueryRequest(Model):
    query: str

class WhaleQueryResponse(Model):
    response: str

class TextMessage(Model):
    content: str

class WhaleDetectionRequest(Model):
    threshold_usd: Optional[float] = ALERT_THRESHOLD_USD
    lookback_minutes: Optional[int] = LOOKBACK_MINUTES_DEFAULT

class WalletEnrichmentRequest(Model):
    wallet_address: str

# Data Classes
class WhaleDeposit:
    def __init__(self, wallet: str, amount: str, token: str, tx_hash: str, timestamp: int, amount_usd: float):
        self.wallet = wallet
        self.amount = amount
        self.token = token
        self.tx_hash = tx_hash
        self.timestamp = timestamp
        self.amount_usd = amount_usd

class HyperliquidPosition:
    def __init__(self, coin: str, side: str, notional_usd: float, avg_entry: float, liq_px: float, leverage: Optional[float] = None):
        self.coin = coin
        self.side = side
        self.notional_usd = notional_usd
        self.avg_entry = avg_entry
        self.liq_px = liq_px
        self.leverage = leverage

class HyperliquidFill:
    def __init__(self, coin: str, action: str, notional_usd: float, price: float, timestamp: int):
        self.coin = coin
        self.action = action
        self.notional_usd = notional_usd
        self.price = price
        self.timestamp = timestamp

class EnrichedWallet:
    def __init__(self, wallet: str, positions: List[HyperliquidPosition], recent_fills: List[HyperliquidFill], total_notional_usd: float):
        self.wallet = wallet
        self.positions = positions
        self.recent_fills = recent_fills
        self.total_notional_usd = total_notional_usd

# Blockscout MCP Client - Updated for External MCP Server Connection
class BlockscoutMCPClient:
    def __init__(self, mcp_url: str = BLOCKSCOUT_MCP_URL):
        self.mcp_url = mcp_url
        self.mcp_client = None
        self.session = None

    async def _initialize_mcp_client(self):
        """Initialize MCP client connection to external Blockscout MCP server"""
        if MCP_AVAILABLE and self.mcp_client is None:
            try:
                # Connect to external Blockscout MCP server
                self.mcp_client = MCPClient(server_url=self.mcp_url)
                await self.mcp_client.connect()
                print(f"Connected to Blockscout MCP server at {self.mcp_url}")
                return True
            except Exception as e:
                print(f"Failed to connect to MCP server: {e}")
                self.mcp_client = None
                return False
        return self.mcp_client is not None

    async def _get_session(self):
        """Get or create aiohttp session for fallback HTTP requests"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the external Blockscout MCP server"""
        try:
            if await self._initialize_mcp_client():
                # Use MCP client to call tool
                result = await self.mcp_client.call_tool(tool_name, arguments)
                print(f"MCP tool {tool_name} called successfully")
                return result
            else:
                raise Exception("MCP client not available")
        except Exception as e:
            print(f"MCP tool call failed for {tool_name}: {e}")
            # Fallback to direct HTTP if MCP fails
            return await self._fallback_http_request(tool_name, arguments)

    async def _fallback_http_request(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback to direct HTTP requests if MCP is not available"""
        try:
            print(f"Using HTTP fallback for {tool_name}")
            session = await self._get_session()
            
            # Map MCP tool calls to HTTP endpoints
            if tool_name == "get_transactions_by_address":
                # Use Blockscout API directly
                chain_id = arguments.get("chain_id", ARBITRUM_CHAIN_ID)
                address = arguments.get("address")
                
                url = f"https://arbitrum.blockscout.com/api/v2/addresses/{address}/transactions"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data
            
            elif tool_name == "get_address_info":
                # Get address information
                chain_id = arguments.get("chain_id", ARBITRUM_CHAIN_ID)
                address = arguments.get("address")
                
                url = f"https://arbitrum.blockscout.com/api/v2/addresses/{address}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data
            
            else:
                raise Exception(f"Unknown tool: {tool_name}")
                
        except Exception as e:
            print(f"HTTP fallback failed for {tool_name}: {e}")
            return {}

    async def get_recent_bridge_transactions(self, lookback_minutes: int = LOOKBACK_MINUTES_DEFAULT) -> List[Dict]:
        """Fetch recent transactions to the Hyperliquid bridge contract using MCP tools"""
        try:
            # Use Blockscout MCP tool to get transactions by address
            result = await self._call_mcp_tool(
                "get_transactions_by_address",
                {
                    "chain_id": ARBITRUM_CHAIN_ID,
                    "address": BRIDGE_CONTRACT_ADDRESS
                }
            )
            
            # Filter transactions by time (client-side filtering)
            current_time = int(time.time())
            cutoff_time = current_time - (lookback_minutes * 60)
            
            transactions = result.get("items", [])
            if isinstance(transactions, list):
                filtered_transactions = []
                for tx in transactions:
                    tx_timestamp = tx.get("timestamp")
                    if tx_timestamp:
                        # Convert timestamp to unix timestamp if needed
                        if isinstance(tx_timestamp, str):
                            try:
                                from datetime import datetime
                                dt = datetime.fromisoformat(tx_timestamp.replace('Z', '+00:00'))
                                tx_timestamp = int(dt.timestamp())
                            except:
                                continue
                        
                        if tx_timestamp >= cutoff_time:
                            filtered_transactions.append(tx)
                    else:
                        # If no timestamp, include it (better to have false positives)
                        filtered_transactions.append(tx)
                
                return filtered_transactions[:50]  # Limit to 50 most recent
            
            return transactions if isinstance(transactions, list) else []
        except Exception as e:
            print(f"Error fetching bridge transactions: {e}")
            return []

    def decode_deposit_event(self, transaction: Dict) -> Optional[Dict[str, str]]:
        """Decode deposit event from transaction data"""
        try:
            # Check if transaction is to the bridge contract
            if transaction.get("to", {}).get("hash", "").lower() != BRIDGE_CONTRACT_ADDRESS.lower():
                return None
            
            # Check transaction value and input data
            value = transaction.get("value", "0")
            if value and value != "0":
                # This is likely a deposit transaction
                from_address = transaction.get("from", {}).get("hash", "")
                
                # For simplicity, we'll treat ETH deposits based on value
                # In a full implementation, we'd decode the input data
                return {
                    "user": from_address,
                    "amount": value,
                    "token": "0x0000000000000000000000000000000000000000"  # ETH
                }
            
            return None
        except Exception as e:
            print(f"Error decoding deposit event: {e}")
            return None

    def convert_to_usd(self, amount: str, token_address: str) -> float:
        """Convert token amount to USD"""
        try:
            # Find token info by address
            token_info = None
            for symbol, info in TOKEN_INFO.items():
                if info["address"].lower() == token_address.lower():
                    token_info = info
                    break
            
            if not token_info:
                return 0.0
            
            # Convert hex amount to decimal
            amount_int = int(amount, 16) if amount.startswith("0x") else int(amount)
            amount_decimal = amount_int / (10 ** token_info["decimals"])
            
            return amount_decimal * token_info["usd_rate"]
        except Exception as e:
            print(f"Error converting to USD: {e}")
            return 0.0

    async def get_recent_whales(self, threshold_usd: float = ALERT_THRESHOLD_USD, lookback_minutes: int = LOOKBACK_MINUTES_DEFAULT) -> List[WhaleDeposit]:
        """Get recent whale deposits above threshold using MCP tools"""
        whales = []
        
        try:
            transactions = await self.get_recent_bridge_transactions(lookback_minutes)
            
            for tx in transactions:
                deposit_data = self.decode_deposit_event(tx)
                if deposit_data:
                    amount_usd = self.convert_to_usd(deposit_data["amount"], deposit_data["token"])
                    
                    if amount_usd >= threshold_usd:
                        # Find token symbol
                        token_symbol = "UNKNOWN"
                        for symbol, info in TOKEN_INFO.items():
                            if info["address"].lower() == deposit_data["token"].lower():
                                token_symbol = symbol
                                break
                        
                        whale = WhaleDeposit(
                            wallet=deposit_data["user"],
                            amount=deposit_data["amount"],
                            token=token_symbol,
                            tx_hash=tx.get("hash", ""),
                            timestamp=int(tx.get("timestamp", time.time())),
                            amount_usd=amount_usd
                        )
                        whales.append(whale)
            
            # Sort by amount USD descending
            whales.sort(key=lambda x: x.amount_usd, reverse=True)
            return whales
            
        except Exception as e:
            print(f"Error getting recent whales: {e}")
            return []

    async def get_address_info(self, address: str) -> Dict[str, Any]:
        """Get detailed address information using MCP tools"""
        try:
            result = await self._call_mcp_tool(
                "get_address_info",
                {
                    "chain_id": ARBITRUM_CHAIN_ID,
                    "address": address
                }
            )
            return result
        except Exception as e:
            print(f"Error getting address info for {address}: {e}")
            return {}

    async def close(self):
        """Close connections"""
        if self.mcp_client:
            try:
                await self.mcp_client.disconnect()
            except:
                pass
        if self.session:
            await self.session.close()

# Hyperliquid Client
class HyperliquidClient:
    def __init__(self, base_url: str = HYPERLIQUID_INFO_ENDPOINT):
        self.base_url = base_url

    async def make_request(self, request_type: str, user: Optional[str] = None) -> Dict:
        """Make a request to Hyperliquid info API"""
        try:
            body = {"type": request_type}
            if user:
                body["user"] = user
            
            print(f"Making Hyperliquid API request: {request_type} for user: {user}")
            
            # Use aiohttp for async requests instead of requests
            session = await self._get_session()
            async with session.post(
                self.base_url,
                headers={"Content-Type": "application/json"},
                json=body,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                data = await response.json()
                print(f"Hyperliquid API response received for {request_type}")
                return data
                
        except Exception as e:
            print(f"Hyperliquid API request failed for {request_type}: {e}")
            raise e

    async def _get_session(self):
        """Get or create aiohttp session"""
        if not hasattr(self, 'session') or self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def get_clearinghouse_state(self, user: str) -> Dict:
        """Get clearinghouse state for a user"""
        return await self.make_request("clearinghouseState", user)

    async def get_user_fills(self, user: str) -> Dict:
        """Get recent fills for a user"""
        return await self.make_request("userFills", user)

    def parse_positions(self, clearinghouse_state: Dict) -> List[HyperliquidPosition]:
        """Parse positions from clearinghouse state"""
        positions = []
        
        try:
            asset_positions = clearinghouse_state.get("assetPositions", [])
            for position_data in asset_positions:
                position = position_data.get("position", {})
                szi = float(position.get("szi", 0))
                
                if szi != 0:
                    entry_px = float(position.get("entryPx", 0))
                    
                    pos = HyperliquidPosition(
                        coin=position.get("coin", ""),
                        side="long" if szi > 0 else "short",
                        notional_usd=abs(szi * entry_px),
                        avg_entry=entry_px,
                        liq_px=float(position.get("liquidationPx", 0))
                    )
                    positions.append(pos)
        except Exception as e:
            print(f"Error parsing positions: {e}")
        
        return positions

    def parse_fills(self, user_fills: Dict) -> List[HyperliquidFill]:
        """Parse fills from user fills data"""
        fills = []
        
        try:
            fills_data = user_fills if isinstance(user_fills, list) else []
            for fill_data in fills_data[:10]:  # Last 10 fills
                fill = HyperliquidFill(
                    coin=fill_data.get("coin", ""),
                    action="buy" if float(fill_data.get("sz", 0)) > 0 else "sell",
                    notional_usd=abs(float(fill_data.get("sz", 0)) * float(fill_data.get("px", 0))),
                    price=float(fill_data.get("px", 0)),
                    timestamp=int(fill_data.get("time", time.time() * 1000))
                )
                fills.append(fill)
        except Exception as e:
            print(f"Error parsing fills: {e}")
        
        return fills

    async def enrich_wallet(self, wallet_address: str) -> EnrichedWallet:
        """Enrich wallet with Hyperliquid trading data"""
        try:
            # Get clearinghouse state and fills
            clearinghouse_state = await self.get_clearinghouse_state(wallet_address)
            user_fills = await self.get_user_fills(wallet_address)
            
            # Parse data
            positions = self.parse_positions(clearinghouse_state)
            recent_fills = self.parse_fills(user_fills)
            
            # Calculate total notional
            total_notional_usd = sum(pos.notional_usd for pos in positions)
            
            return EnrichedWallet(
                wallet=wallet_address,
                positions=positions,
                recent_fills=recent_fills,
                total_notional_usd=total_notional_usd
            )
        except Exception as e:
            print(f"Error enriching wallet: {e}")
            return EnrichedWallet(wallet_address, [], [], 0.0)

    def format_wallet_summary(self, enriched_wallet: EnrichedWallet) -> str:
        """Format wallet summary for display"""
        summary = f"📊 **Wallet Analysis: {enriched_wallet.wallet[:6]}...{enriched_wallet.wallet[-4:]}**\n\n"
        
        if enriched_wallet.positions:
            summary += f"💰 **Total Position Value:** ${enriched_wallet.total_notional_usd:,.2f}\n\n"
            summary += "**Active Positions:**\n"
            for pos in enriched_wallet.positions[:5]:
                summary += f"• {pos.coin}: {pos.side.upper()} ${pos.notional_usd:,.2f} @ ${pos.avg_entry:.2f}\n"
        else:
            summary += "No active positions found.\n"
        
        if enriched_wallet.recent_fills:
            summary += f"\n**Recent Trades ({len(enriched_wallet.recent_fills)}):**\n"
            for fill in enriched_wallet.recent_fills[:3]:
                summary += f"• {fill.action.upper()} {fill.coin} ${fill.notional_usd:,.2f} @ ${fill.price:.2f}\n"
        
        return summary

# ASI:One API key configuration - hardcoded as per documentation
ASI_ONE_API_KEY = "sk_fb3d2f75d420447aa0b66a187cc8edf78ede76314e3949e5860037bab3dca0d1"  # Replace with your actual ASI:One API key

# Initialize OpenAI client for ASI:One integration - following official example
openai_client = OpenAI(
    # By default, we are using the ASI-1 LLM endpoint and model
    base_url='https://api.asi1.ai/v1',
    
    # You can get an ASI-1 api key by creating an account at https://asi1.ai/dashboard/api-keys
    api_key=ASI_ONE_API_KEY,
)

# Create the uAgent for Agentverse deployment with MCP integration
agent = Agent(
    name="hyperliquid_whale_watcher",
    seed="hyperliquid_whale_detection_seed_phrase_2024"
)

# Create chat protocol for ASI:One compatibility - following official documentation
# IMPORTANT: This must be created BEFORE any message handlers that use it
protocol = Protocol(spec=chat_protocol_spec)

# Initialize MCP-enabled clients
blockscout_client = BlockscoutMCPClient()
hyperliquid_client = HyperliquidClient()

@agent.on_event("startup")
async def startup_handler(ctx: Context):
    ctx.logger.info(f"🐋 Hyperliquid Whale Watcher Agent started!")
    ctx.logger.info(f"Agent address: {agent.address}")
    ctx.logger.info(f"Monitoring deposits above ${ALERT_THRESHOLD_USD:,}")
    
    # Test MCP connection
    if MCP_AVAILABLE:
        try:
            await blockscout_client._initialize_mcp_client()
            ctx.logger.info("✅ MCP connection to Blockscout server established")
        except Exception as e:
            ctx.logger.warning(f"⚠️ MCP connection failed, using HTTP fallback: {e}")
    else:
        ctx.logger.info("📡 Using HTTP fallback for blockchain data access")

@agent.on_event("shutdown")
async def shutdown_handler(ctx: Context):
    ctx.logger.info("🛑 Shutting down Whale Watcher Agent")
    await blockscout_client.close()
    if hasattr(hyperliquid_client, 'session') and hyperliquid_client.session:
        await hyperliquid_client.session.close()

# Chat message handler for ASI:One compatibility
@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages from ASI:One - following exact documentation pattern"""
    # Send the acknowledgement for receiving the message
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )

    # Collect up all the text chunks
    text = ''
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text

    # Query the model based on the user question
    response = 'I am afraid something went wrong and I am unable to answer your question at the moment'
    try:
        if text:
            ctx.logger.info(f"Processing whale query: {text}")
            
            # Process whale-related queries
            if any(keyword in text.lower() for keyword in ["whale", "deposit", "recent", "activity"]):
                # Get recent whale activity
                whales = await blockscout_client.get_recent_whales()
                if whales:
                    response = f"🐋 **Recent Whale Activity** (Last {LOOKBACK_MINUTES_DEFAULT} minutes):\n\n"
                    for i, whale in enumerate(whales[:5], 1):
                        response += f"{i}. **${whale.amount_usd:,.0f}** {whale.token} deposit\n"
                        response += f"   Wallet: `{whale.wallet[:6]}...{whale.wallet[-4:]}`\n"
                        response += f"   TX: `{whale.tx_hash[:10]}...`\n\n"
                else:
                    response = f"No whale deposits above ${ALERT_THRESHOLD_USD:,} found in the last {LOOKBACK_MINUTES_DEFAULT} minutes."
            
            elif "wallet" in text.lower() or "address" in text.lower():
                # Extract potential wallet address from text
                import re
                wallet_pattern = r'0x[a-fA-F0-9]{40}'
                matches = re.findall(wallet_pattern, text)
                if matches:
                    wallet_address = matches[0]
                    enriched = await hyperliquid_client.enrich_wallet(wallet_address)
                    response = hyperliquid_client.format_wallet_summary(enriched)
                else:
                    response = "Please provide a valid wallet address (0x...) to analyze."
            
            else:
                response = f"""🐋 **Hyperliquid Whale Watcher**

I monitor large deposits to Hyperliquid and analyze trading activity. Here's what I can help with:

• **Recent whale activity**: Ask about "recent whales" or "whale deposits"
• **Wallet analysis**: Provide a wallet address to see Hyperliquid positions and trades
• **Deposit monitoring**: I track deposits above ${ALERT_THRESHOLD_USD:,}

What would you like to know?"""

    except Exception as e:
        ctx.logger.error(f"Error processing message: {e}")
        response = 'I am afraid something went wrong and I am unable to answer your question at the moment'

    # Send response back as ChatMessage
    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.utcnow(),
            msg_id=uuid4(),
            content=[
                # we send the contents back in the chat message
                TextContent(type="text", text=response),
                # we also signal that the session is over, this also informs the user that we are not recording any of the
                # previous history of messages.
                EndSessionContent(type="end-session"),
            ]
        )
    )


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    # we are not interested in the acknowledgements for this example, but they can be useful to
    # implement read receipts, for example.
    pass

async def handle_whale_query_internal(ctx: Context, sender: str, msg: WhaleQueryRequest):
    """Internal handler for whale queries"""
    query_lower = msg.query.lower()
    
    try:
        # Check if asking for recent whales
        if any(keyword in query_lower for keyword in ["whale", "deposit", "recent", "activity"]):
            ctx.logger.info("Processing recent whale activity request")
            
            whales = await blockscout_client.get_recent_whales()
            
            if whales:
                response = f"🐋 **Recent Whale Activity** (${ALERT_THRESHOLD_USD:,}+ deposits)\n\n"
                for i, whale in enumerate(whales[:5], 1):
                    response += f"{i}. **${whale.amount_usd:,.0f}** {whale.token}\n"
                    response += f"   Wallet: `{whale.wallet[:6]}...{whale.wallet[-4:]}`\n"
                    response += f"   Time: {datetime.fromtimestamp(whale.timestamp).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                
                if len(whales) > 5:
                    response += f"... and {len(whales) - 5} more whale deposits\n"
            else:
                response = f"No whale deposits above ${ALERT_THRESHOLD_USD:,} found in the last {LOOKBACK_MINUTES_DEFAULT} minutes."
        
        # Check if it's a wallet address (starts with 0x and is 42 characters)
        elif msg.query.startswith("0x") and len(msg.query) == 42:
            ctx.logger.info(f"Processing wallet analysis request for {msg.query}")
            wallet_address = msg.query
            
            # Validate wallet address format
            if all(c in "0123456789abcdefABCDEF" for c in wallet_address[2:]):
                try:
                    # Get blockchain info from Blockscout MCP
                    address_info = await blockscout_client.get_address_info(wallet_address)
                    
                    # Get Hyperliquid trading data
                    enriched_wallet = await hyperliquid_client.enrich_wallet(wallet_address)
                    
                    response = f"📊 **Comprehensive Wallet Analysis: {wallet_address[:6]}...{wallet_address[-4:]}**\n\n"
                    
                    # Add blockchain information
                    if address_info:
                        balance = address_info.get("coin_balance", "0")
                        if balance and balance != "0":
                            eth_balance = float(balance) / 1e18
                            response += f"💰 **On-chain Balance:** {eth_balance:.4f} ETH\n"
                        
                        tx_count = address_info.get("transactions_count", 0)
                        if tx_count:
                            response += f"📈 **Transaction Count:** {tx_count:,}\n"
                    
                    response += "\n"
                    response += hyperliquid_client.format_wallet_summary(enriched_wallet)
                    
                except Exception as e:
                    ctx.logger.error(f"Error analyzing wallet {wallet_address}: {e}")
                    response = f"Error analyzing wallet {wallet_address}: {str(e)}"
            else:
                response = "Invalid wallet address format."
        
        else:
            # Default help response
            response = f"""I'm the Hyperliquid Whale Watcher! I can help you:

🐋 **Track whale deposits** - Ask "show recent whales" or "any whale activity?"
📊 **Analyze wallets** - Provide a wallet address like 0x123... to see their Hyperliquid positions
💰 **Monitor large moves** - I detect deposits above ${ALERT_THRESHOLD_USD:,} to the Hyperliquid bridge

What would you like to know about whale activity?"""
        
        # Send response as ChatMessage with TextContent for ASI:One compatibility
        chat_response = ChatMessage(
            content=TextContent(text=response),
            id=f"response_{int(time.time())}"
        )
        await ctx.send(sender, chat_response)
        
    except Exception as e:
        ctx.logger.error(f"Error handling query: {e}")
        error_response = ChatMessage(
            content=TextContent(text=f"Sorry, I encountered an error processing your request: {str(e)}. Please try again."),
            id=f"error_{int(time.time())}"
        )
        await ctx.send(sender, error_response)

@agent.on_message(model=WhaleDetectionRequest)
async def handle_whale_detection(ctx: Context, sender: str, msg: WhaleDetectionRequest):
    """Handle specific whale detection requests"""
    ctx.logger.info(f"Whale detection request from {sender}: threshold=${msg.threshold_usd}, lookback={msg.lookback_minutes}min")
    
    try:
        whales = await blockscout_client.get_recent_whales(msg.threshold_usd, msg.lookback_minutes)
        
        response_data = {
            "success": True,
            "whale_count": len(whales),
            "whales": [
                {
                    "wallet": whale.wallet,
                    "amount_usd": whale.amount_usd,
                    "token": whale.token,
                    "tx_hash": whale.tx_hash,
                    "timestamp": whale.timestamp
                }
                for whale in whales
            ],
            "message": f"Found {len(whales)} whale deposits above ${msg.threshold_usd:,} in the last {msg.lookback_minutes} minutes"
        }
        
        await ctx.send(sender, WhaleQueryResponse(response=json.dumps(response_data, indent=2)))
        
    except Exception as e:
        ctx.logger.error(f"Error in whale detection: {e}")
        error_response = {
            "success": False,
            "whale_count": 0,
            "whales": [],
            "message": f"Error detecting whales: {str(e)}"
        }
        await ctx.send(sender, WhaleQueryResponse(response=json.dumps(error_response, indent=2)))

@agent.on_message(model=WalletEnrichmentRequest)
async def handle_wallet_enrichment(ctx: Context, sender: str, msg: WalletEnrichmentRequest):
    """Handle wallet enrichment requests"""
    ctx.logger.info(f"Wallet enrichment request from {sender}: {msg.wallet_address}")
    
    try:
        enriched_wallet = await hyperliquid_client.enrich_wallet(msg.wallet_address)
        summary = hyperliquid_client.format_wallet_summary(enriched_wallet)
        
        await ctx.send(sender, WhaleQueryResponse(response=summary))
        
    except Exception as e:
        ctx.logger.error(f"Error enriching wallet: {e}")
        await ctx.send(sender, WhaleQueryResponse(response=f"Error enriching wallet {msg.wallet_address}: {str(e)}"))

# Include the chat protocol in the agent with manifest publishing for ASI:One compatibility
# This must be done AFTER all message handlers are defined
agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    print("🐋 Starting Hyperliquid Whale Watcher Agent...")
    print(f"Agent address: {agent.address}")
    print(f"Monitoring threshold: ${ALERT_THRESHOLD_USD:,}")
    agent.run()
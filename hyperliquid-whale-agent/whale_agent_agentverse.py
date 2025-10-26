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
import asyncio
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

# FastMCP uAgent integration - no direct MCP imports needed
# We'll communicate with the FastMCP uAgent via uAgent protocol

# Configuration Constants
BRIDGE_CONTRACT_ADDRESS = "0x2Df1c51E09aECF9cacB7bc98cB1742757f163dF7"
BLOCKSCOUT_MCP_URL = "https://mcp.blockscout.com/mcp"
HYPERLIQUID_INFO_ENDPOINT = "https://api.hyperliquid.xyz/info"
ALERT_THRESHOLD_USD = 100_000  # $100K (reduced from $10M for better detection)
LOOKBACK_MINUTES_DEFAULT = 60  # 1 hour (increased from 15 minutes)
DEPOSIT_EVENT_SIGNATURE = "0x5548c837ab068cf56a2c2479df0882a4922fd203edb7517321831d95078c5f62"
ARBITRUM_CHAIN_ID = 42161

# FastMCP uAgent Configuration
FASTMCP_AGENT_ADDRESS = "agent1q2mx6n23zjppzzpcf06gh9u8k2gu6fd4jnzytnvkvwf6zrh0frvnz274uyp"  # Your FastMCP agent address

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

# FastMCP uAgent Communication Models
class MCPToolRequest(Model):
    tool_name: str
    arguments: Dict[str, Any]
    correlation_id: str  # Add correlation ID for matching requests/responses

class MCPToolResponse(Model):
    success: bool
    result: Dict[str, Any]
    error: Optional[str] = None
    correlation_id: str  # Add correlation ID for matching requests/responses

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

# Blockscout MCP Client - Updated for FastMCP uAgent Communication
class BlockscoutMCPClient:
    def __init__(self, fastmcp_agent_address: str = FASTMCP_AGENT_ADDRESS):
        self.fastmcp_agent_address = fastmcp_agent_address
        self.context = None
        self._session = None
        # Store pending requests for async communication
        self.pending_requests: Dict[str, asyncio.Future] = {}  # Will be set by the agent

    def set_context(self, context: Context):
        """Set the uAgent context for sending messages"""
        self.context = context

    async def _get_session(self):
        """Get or create aiohttp session for fallback HTTP requests"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool via the FastMCP uAgent using proper async message passing"""
        print(f"🔧 FastMCP Tool Call: {tool_name} with args: {arguments}")
        
        try:
            if self.context:
                # Generate correlation ID for this request
                correlation_id = str(uuid4())
                print(f"📡 Sending async request to FastMCP uAgent: {self.fastmcp_agent_address}")
                print(f"🔍 DEBUG: Correlation ID: {correlation_id}")
                
                # Create future to wait for response
                response_future = asyncio.Future()
                self.pending_requests[correlation_id] = response_future
                
                request = MCPToolRequest(
                    tool_name=tool_name,
                    arguments=arguments,
                    correlation_id=correlation_id
                )
                
                print(f"🔍 DEBUG: Sending MCPToolRequest: {request}")
                
                # Send message asynchronously (no timeout, no waiting for return)
                await self.context.send(self.fastmcp_agent_address, request)
                print(f"📤 Sent async request, waiting for response...")
                
                # Wait for response with timeout
                try:
                    response = await asyncio.wait_for(response_future, timeout=30.0)
                    
                    if response.success:
                        print(f"✅ FastMCP result for {tool_name}: {type(response.result)} - {len(str(response.result))} chars")
                        if isinstance(response.result, dict) and "items" in response.result:
                            print(f"📊 Found {len(response.result.get('items', []))} items in FastMCP response")
                        return response.result
                    else:
                        print(f"❌ FastMCP tool call failed for {tool_name}: {response.error}")
                        raise Exception(f"FastMCP error: {response.error}")
                        
                except asyncio.TimeoutError:
                    print(f"⏰ FastMCP request timeout for {tool_name}")
                    # Clean up pending request
                    self.pending_requests.pop(correlation_id, None)
                    raise Exception(f"FastMCP timeout for {tool_name}")
                finally:
                    # Clean up pending request if still exists
                    self.pending_requests.pop(correlation_id, None)
            else:
                print(f"❌ No context available for FastMCP communication")
                raise Exception("No context available for FastMCP communication")
                
        except Exception as e:
            print(f"❌ FastMCP tool call failed for {tool_name}: {e}")
            # Fallback to direct HTTP if FastMCP fails
            print(f"🔄 Falling back to HTTP for {tool_name}")
            try:
                result = await self._fallback_http_request(tool_name, arguments)
                print(f"✅ HTTP fallback successful for {tool_name}")
                return result
            except Exception as fallback_error:
                print(f"❌ HTTP fallback also failed for {tool_name}: {fallback_error}")
                return {}

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
        print(f"🔍 Fetching bridge transactions for {BRIDGE_CONTRACT_ADDRESS} (last {lookback_minutes} minutes)")
        
        try:
            # Use Blockscout MCP tool to get transactions by address
            result = await self._call_mcp_tool(
                "get_transactions_by_address",
                {
                    "chain_id": ARBITRUM_CHAIN_ID,
                    "address": BRIDGE_CONTRACT_ADDRESS
                }
            )
            
            print(f"📥 Raw result type: {type(result)}, keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
            
            # Filter transactions by time (client-side filtering)
            current_time = int(time.time())
            cutoff_time = current_time - (lookback_minutes * 60)
            print(f"⏰ Time filter: current={current_time}, cutoff={cutoff_time}")
            
            transactions = result.get("items", [])
            print(f"📋 Found {len(transactions)} total transactions")
            
            if isinstance(transactions, list):
                filtered_transactions = []
                for i, tx in enumerate(transactions):
                    tx_timestamp = tx.get("timestamp")
                    print(f"🔍 TX {i}: hash={tx.get('hash', 'N/A')[:10]}..., timestamp={tx_timestamp}")
                    
                    if tx_timestamp:
                        # Convert timestamp to unix timestamp if needed
                        if isinstance(tx_timestamp, str):
                            try:
                                from datetime import datetime
                                dt = datetime.fromisoformat(tx_timestamp.replace('Z', '+00:00'))
                                tx_timestamp = int(dt.timestamp())
                                print(f"  ⏰ Converted timestamp: {tx_timestamp}")
                            except Exception as ts_error:
                                print(f"  ❌ Timestamp conversion failed: {ts_error}")
                                continue
                        
                        if tx_timestamp >= cutoff_time:
                            filtered_transactions.append(tx)
                            print(f"  ✅ TX included (within time range)")
                        else:
                            print(f"  ⏭️ TX skipped (too old: {current_time - tx_timestamp}s ago)")
                    else:
                        # If no timestamp, include it (better to have false positives)
                        filtered_transactions.append(tx)
                        print(f"  ⚠️ TX included (no timestamp)")
                
                print(f"📊 Filtered to {len(filtered_transactions)} recent transactions")
                return filtered_transactions[:50]  # Limit to 50 most recent
            
            print(f"⚠️ Transactions not in expected format: {type(transactions)}")
            return transactions if isinstance(transactions, list) else []
        except Exception as e:
            print(f"❌ Error fetching bridge transactions: {e}")
            import traceback
            print(f"🔍 Full traceback: {traceback.format_exc()}")
            return []

    def decode_deposit_event(self, transaction: Dict) -> Optional[Dict[str, str]]:
        """Decode deposit event from transaction data"""
        try:
            print(f"  🔍 Decoding TX: to={transaction.get('to', {}).get('hash', 'N/A')[:10]}..., value={transaction.get('value', '0')}")
            
            # Check if transaction is to the bridge contract
            to_address = transaction.get("to", {}).get("hash", "")
            if to_address.lower() != BRIDGE_CONTRACT_ADDRESS.lower():
                print(f"    ⏭️ Not to bridge contract: {to_address[:10]}... != {BRIDGE_CONTRACT_ADDRESS[:10]}...")
                return None
            
            print(f"    ✅ Transaction is to bridge contract")
            
            # Check transaction value and input data
            value = transaction.get("value", "0")
            print(f"    💰 Transaction value: {value}")
            
            if value and value != "0":
                # This is likely a deposit transaction
                from_address = transaction.get("from", {}).get("hash", "")
                print(f"    👤 From address: {from_address[:10]}...{from_address[-4:] if len(from_address) > 10 else ''}")
                
                # For simplicity, we'll treat ETH deposits based on value
                # In a full implementation, we'd decode the input data
                deposit_data = {
                    "user": from_address,
                    "amount": value,
                    "token": "0x0000000000000000000000000000000000000000"  # ETH
                }
                print(f"    ✅ Deposit decoded: {deposit_data}")
                return deposit_data
            
            print(f"    ⏭️ No value in transaction")
            return None
        except Exception as e:
            print(f"    ❌ Error decoding deposit event: {e}")
            return None

    def convert_to_usd(self, amount: str, token_address: str) -> float:
        """Convert token amount to USD"""
        try:
            print(f"    💱 Converting to USD: amount={amount}, token={token_address[:10]}...")
            
            # Find token info by address
            token_info = None
            for symbol, info in TOKEN_INFO.items():
                if info["address"].lower() == token_address.lower():
                    token_info = info
                    print(f"      ✅ Found token: {symbol}")
                    break
            
            if not token_info:
                print(f"      ❌ Token not found in TOKEN_INFO")
                return 0.0
            
            # Convert hex amount to decimal
            amount_int = int(amount, 16) if amount.startswith("0x") else int(amount)
            amount_decimal = amount_int / (10 ** token_info["decimals"])
            usd_value = amount_decimal * token_info["usd_rate"]
            
            print(f"      💰 Conversion: {amount_int} wei -> {amount_decimal:.6f} {token_info.get('symbol', 'tokens')} -> ${usd_value:,.2f}")
            
            return usd_value
        except Exception as e:
            print(f"      ❌ Error converting to USD: {e}")
            return 0.0

    async def get_recent_whales(self, threshold_usd: float = ALERT_THRESHOLD_USD, lookback_minutes: int = LOOKBACK_MINUTES_DEFAULT) -> List[WhaleDeposit]:
        """Get recent whale deposits above threshold using MCP tools"""
        print(f"🐋 Starting whale detection: threshold=${threshold_usd:,}, lookback={lookback_minutes}min")
        whales = []
        
        try:
            transactions = await self.get_recent_bridge_transactions(lookback_minutes)
            print(f"📋 Processing {len(transactions)} transactions for whale detection")
            
            for i, tx in enumerate(transactions):
                print(f"🔍 Processing TX {i+1}/{len(transactions)}: {tx.get('hash', 'N/A')[:10]}...")
                
                deposit_data = self.decode_deposit_event(tx)
                if deposit_data:
                    print(f"  💰 Deposit detected: {deposit_data['amount']} of token {deposit_data['token'][:10]}...")
                    amount_usd = self.convert_to_usd(deposit_data["amount"], deposit_data["token"])
                    print(f"  💵 USD value: ${amount_usd:,.2f}")
                    
                    if amount_usd >= threshold_usd:
                        print(f"  🐋 WHALE DETECTED! ${amount_usd:,.2f} >= ${threshold_usd:,.2f}")
                        
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
                        print(f"  ✅ Whale added to list (total: {len(whales)})")
                    else:
                        print(f"  ⏭️ Below threshold: ${amount_usd:,.2f} < ${threshold_usd:,.2f}")
                else:
                    print(f"  ⏭️ No deposit data found in transaction")
            
            # Sort by amount USD descending
            whales.sort(key=lambda x: x.amount_usd, reverse=True)
            print(f"🎯 Final result: {len(whales)} whales detected")
            
            for i, whale in enumerate(whales):
                print(f"  🐋 #{i+1}: ${whale.amount_usd:,.2f} {whale.token} from {whale.wallet[:6]}...{whale.wallet[-4:]}")
            
            return whales
            
        except Exception as e:
            print(f"❌ Error getting recent whales: {e}")
            import traceback
            print(f"🔍 Full traceback: {traceback.format_exc()}")
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
    ctx.logger.info(f"FastMCP Agent: {FASTMCP_AGENT_ADDRESS}")
    ctx.logger.info(f"🔍 DEBUG: FASTMCP_AGENT_ADDRESS type: {type(FASTMCP_AGENT_ADDRESS)}")
    ctx.logger.info(f"🔍 DEBUG: FASTMCP_AGENT_ADDRESS value: '{FASTMCP_AGENT_ADDRESS}'")
    ctx.logger.info(f"🔍 DEBUG: FASTMCP_AGENT_ADDRESS length: {len(FASTMCP_AGENT_ADDRESS)}")
    
    # Set the context for the blockscout client to enable FastMCP communication
    blockscout_client.set_context(ctx)
    ctx.logger.info(f"🔍 DEBUG: blockscout_client.fastmcp_agent_address: '{blockscout_client.fastmcp_agent_address}'")
    
    # Test FastMCP connection using a valid tool
    try:
        ctx.logger.info("Testing FastMCP connection...")
        test_result = await blockscout_client._call_mcp_tool("get_chains_list", {})
        ctx.logger.info(f"FastMCP connection test result: {len(str(test_result))} chars received")
    except Exception as e:
        ctx.logger.warning(f"FastMCP connection test failed (will use HTTP fallback): {e}")
    
    ctx.logger.info("✅ Agent startup complete")

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
            print(f"🔍 User query: '{msg.query}' - Processing whale activity request")
            
            whales = await blockscout_client.get_recent_whales()
            print(f"📊 Query result: Found {len(whales)} whales")
            
            if whales:
                response = f"🐋 **Recent Whale Activity** (${ALERT_THRESHOLD_USD:,}+ deposits)\n\n"
                for i, whale in enumerate(whales[:5], 1):
                    response += f"{i}. **${whale.amount_usd:,.0f}** {whale.token}\n"
                    response += f"   Wallet: `{whale.wallet[:6]}...{whale.wallet[-4:]}`\n"
                    response += f"   Time: {datetime.fromtimestamp(whale.timestamp).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                
                if len(whales) > 5:
                    response += f"... and {len(whales) - 5} more whale deposits\n"
                    
                # Add debug info to response
                response += f"\n🔍 **Debug Info:**\n"
                response += f"- Searched last {LOOKBACK_MINUTES_DEFAULT} minutes\n"
                response += f"- Bridge contract: `{BRIDGE_CONTRACT_ADDRESS[:10]}...`\n"
                response += f"- Total whales found: {len(whales)}\n"
                response += f"- FastMCP Agent: {FASTMCP_AGENT_ADDRESS[:20]}...\n"
            else:
                response = f"No whale deposits above ${ALERT_THRESHOLD_USD:,} found in the last {LOOKBACK_MINUTES_DEFAULT} minutes.\n\n"
                response += f"🔍 **Debug Info:**\n"
                response += f"- Searched bridge contract: `{BRIDGE_CONTRACT_ADDRESS[:10]}...`\n"
                response += f"- Time window: {LOOKBACK_MINUTES_DEFAULT} minutes\n"
                response += f"- Threshold: ${ALERT_THRESHOLD_USD:,}\n"
                response += f"- FastMCP Agent: {FASTMCP_AGENT_ADDRESS[:20]}...\n"
        
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
# Add FastMCP message handlers
@agent.on_message(model=MCPToolResponse)
async def handle_fastmcp_response(ctx: Context, sender: str, msg: MCPToolResponse):
    """Handle responses from FastMCP uAgent"""
    ctx.logger.info(f"📨 Received FastMCP response from {sender}: success={msg.success}, correlation_id={msg.correlation_id}")
    
    # Find the pending request by correlation ID
    if msg.correlation_id in blockscout_client.pending_requests:
        future = blockscout_client.pending_requests[msg.correlation_id]
        if not future.done():
            # Complete the future with the response
            future.set_result(msg)
            ctx.logger.info(f"✅ Completed pending request {msg.correlation_id}")
        else:
            ctx.logger.warning(f"⚠️ Future for {msg.correlation_id} was already completed")
    else:
        ctx.logger.warning(f"⚠️ No pending request found for correlation_id: {msg.correlation_id}")

agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    print("🐋 Starting Hyperliquid Whale Watcher Agent...")
    print(f"Agent address: {agent.address}")
    print(f"Monitoring threshold: ${ALERT_THRESHOLD_USD:,}")
    agent.run()
#!/usr/bin/env python3
"""
Hyperliquid Whale Detection Agent - Local Mailbox Version
This agent directly integrates with Blockscout MCP server to detect large transactions
and whale activities across multiple blockchains.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import requests
from uuid import uuid4
from uagents import Agent, Context, Model, Protocol
from uagents.setup import fund_agent_if_low
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import chat protocol for ASI:One compatibility
try:
    from uagents_core.contrib.protocols.chat import (
        ChatMessage,
        ChatAcknowledgement,
        TextContent,
        EndSessionContent,
        chat_protocol_spec
    )
    CHAT_PROTOCOL_AVAILABLE = True
except ImportError:
    # Fallback if chat protocol is not available
    CHAT_PROTOCOL_AVAILABLE = False
    print("⚠️  Chat protocol not available - ASI:One compatibility limited")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Agent configuration
AGENT_MAILBOX_KEY = "hyperliquid_whale_detection_mailbox_key_2024"
AGENT_SEED = "hyperliquid_whale_detection_seed_phrase_2024"

# Blockscout MCP server configuration
BLOCKSCOUT_MCP_URL = "https://mcp.blockscout.com"
BLOCKSCOUT_MCP_ENDPOINT = f"{BLOCKSCOUT_MCP_URL}/mcp"

# ASI:One configuration from environment
ASI_ONE_BASE_URL = os.getenv("NEXT_PUBLIC_ASI_ONE_URL", "https://api.asi.one")
ASI_ONE_API_KEY = os.getenv("ASI_ONE_API_KEY")
WHALE_AGENT_ADDRESS = os.getenv("NEXT_PUBLIC_WHALE_AGENT_ADDRESS")

# Whale detection thresholds
WHALE_THRESHOLD_USD = 100000  # $100k+ transactions
LARGE_TRANSFER_THRESHOLD = 50000  # $50k+ transfers

class WhaleAlert(Model):
    """Model for whale alert notifications"""
    chain_id: int
    transaction_hash: str
    from_address: str
    to_address: str
    value_usd: float
    token_symbol: str
    block_number: int
    timestamp: str
    alert_type: str  # "large_transfer", "whale_deposit", "whale_withdrawal"

class ChainMonitorStatus(Model):
    """Model for chain monitoring status"""
    chain_id: int
    chain_name: str
    last_block_checked: int
    active: bool
    last_update: str

class QueryMessage(Model):
    """Model for query messages"""
    message: str

# Create the mailbox agent
agent = Agent(
    name="hyperliquid_whale_watcher_mailbox",
    seed=AGENT_SEED,
    mailbox=True,
    endpoint=["https://agentverse.ai/v1/submit"],
)

# Create chat protocol for ASI:One compatibility (but don't include it yet)
if CHAT_PROTOCOL_AVAILABLE:
    chat_protocol = Protocol(spec=chat_protocol_spec)
    print("✅ Chat protocol created for ASI:One compatibility")
else:
    chat_protocol = None
    print("⚠️  Chat protocol not available - agent will work but ASI:One @ mentions may not work")

# Global state
monitored_chains: Dict[int, ChainMonitorStatus] = {}
recent_alerts: List[WhaleAlert] = []

class BlockscoutMCPClient:
    """Client for interacting with Blockscout MCP server using JSON-RPC 2.0"""
    
    def __init__(self, mcp_endpoint: str):
        self.mcp_endpoint = mcp_endpoint
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
            'Origin': 'http://localhost:8000',
            'User-Agent': 'HyperliquidWhaleAgent/1.0'
        })
        self.request_id = 0
        self.initialized = False
        self.capabilities = {}
    
    def _parse_sse_response(self, response_text: str) -> dict:
        """Parse Server-Sent Events response format"""
        try:
            lines = response_text.strip().split('\n')
            events = []
            current_event = {}
            
            for line in lines:
                if line.startswith('event:'):
                    if current_event:
                        events.append(current_event)
                    current_event = {'event': line[6:].strip()}
                elif line.startswith('data:'):
                    data_str = line[5:].strip()
                    if data_str:
                        try:
                            current_event['data'] = json.loads(data_str)
                        except json.JSONDecodeError:
                            current_event['data'] = data_str
                elif line == '':
                    if current_event:
                        events.append(current_event)
                        current_event = {}
            
            # Add the last event if it exists
            if current_event:
                events.append(current_event)
            
            # Look for the event with the actual result (not notifications)
            for event in events:
                if 'data' in event and isinstance(event['data'], dict):
                    data = event['data']
                    if 'result' in data and 'id' in data:
                        return data
                    elif 'error' in data and 'id' in data:
                        return data
            
            # If no result found, return the first event's data
            if events and 'data' in events[0]:
                return events[0]['data'] if isinstance(events[0]['data'], dict) else {}
            
            return {}
        except Exception as e:
            logger.error(f"Failed to parse SSE response: {e}")
            return {}

    def _make_rpc_request(self, method: str, params: dict = None) -> dict:
        """Make a JSON-RPC request to the MCP server"""
        # Initialize the MCP connection if not already done
        if not self.initialized:
            self._initialize_mcp()
        
        # Now make the actual request
        self.request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self.request_id
        }
        
        # Only include params if they are provided and not empty
        if params:
            payload["params"] = params
        
        try:
            logger.info(f"Sending MCP request: {method} to {self.mcp_endpoint}")
            response = self.session.post(self.mcp_endpoint, json=payload)
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Raw response text: {response.text[:500]}...")  # Log first 500 chars
            
            response.raise_for_status()
            if response.text.strip():
                # Parse SSE response
                result = self._parse_sse_response(response.text)
                logger.info(f"Parsed result: {result}")
                
                if result and "error" in result:
                    logger.error(f"MCP RPC error for {method}: {result['error']}")
                    return None
                elif result:
                    return result.get("result")
                else:
                    logger.warning(f"Could not parse response for method {method}")
                    return None
            else:
                logger.warning(f"Empty response for method {method}")
                return None
        except Exception as e:
            logger.error(f"MCP request failed for {method}: {e}")
            return None
    
    def _initialize_mcp(self):
        """Initialize the MCP connection"""
        if self.initialized:
            return
            
        try:
            # Send initialize request
            self.request_id += 1
            init_payload = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": self.request_id,
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {
                            "listChanged": True
                        }
                    },
                    "clientInfo": {
                        "name": "hyperliquid-whale-watcher",
                        "version": "1.0.0"
                    }
                }
            }
            
            logger.info("Initializing MCP connection...")
            response = self.session.post(self.mcp_endpoint, json=init_payload)
            response.raise_for_status()
            
            if response.text.strip():
                result = self._parse_sse_response(response.text)
                if result and "error" not in result:
                    self.capabilities = result.get("result", {}).get("capabilities", {})
                    self.initialized = True
                    logger.info("Successfully initialized MCP connection")
                    
                    # Send initialized notification
                    self._send_initialized_notification()
                else:
                    logger.error(f"Failed to initialize MCP: {result.get('error') if result else 'No response'}")
            else:
                logger.warning("Empty response during MCP initialization")
        except Exception as e:
            logger.error(f"MCP initialization failed: {e}")
    
    def _send_initialized_notification(self):
        """Send the initialized notification to complete the handshake"""
        try:
            notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            
            response = self.session.post(self.mcp_endpoint, json=notification)
            logger.info("Sent initialized notification")
        except Exception as e:
            logger.warning(f"Failed to send initialized notification: {e}")
    
    async def get_tools_list(self) -> List[Dict[str, Any]]:
        """Get list of available tools from the MCP server"""
        try:
            result = self._make_rpc_request("tools/list")
            if result and "tools" in result:
                return result["tools"]
            return []
        except Exception as e:
            logger.error(f"Failed to get tools list: {e}")
            return []
    
    async def get_chains_list(self) -> List[Dict[str, Any]]:
        """Get list of supported blockchain networks using tools/call"""
        try:
            # First get the list of available tools
            tools = await self.get_tools_list()
            logger.info(f"Available tools: {[tool.get('name') for tool in tools]}")
            
            # Check if we need to unlock blockchain analysis first
            unlock_tool = None
            chain_tool = None
            for tool in tools:
                tool_name = tool.get('name', '')
                if tool_name == '__unlock_blockchain_analysis__':
                    unlock_tool = tool_name
                elif tool_name == 'get_chains_list':
                    chain_tool = tool_name
            
            # If unlock tool exists, call it first
            if unlock_tool:
                logger.info(f"Unlocking blockchain analysis with: {unlock_tool}")
                unlock_result = self._make_rpc_request("tools/call", {
                    "name": unlock_tool,
                    "arguments": {}
                })
                logger.info(f"Unlock result: {unlock_result}")
                
                # After unlocking, get tools list again to see newly available tools
                tools = await self.get_tools_list()
                logger.info(f"Available tools after unlock: {[tool.get('name') for tool in tools]}")
                
                # Find the chains list tool again
                for tool in tools:
                    tool_name = tool.get('name', '')
                    if tool_name == 'get_chains_list':
                        chain_tool = tool_name
                        break
            
            if chain_tool:
                # Call the chain tool
                logger.info(f"Calling chain tool: {chain_tool}")
                result = self._make_rpc_request("tools/call", {
                    "name": chain_tool,
                    "arguments": {}
                })
                logger.info(f"Chain tool response: {result}")
                
                # Parse the response - it's wrapped in content array with text
                if result and 'content' in result:
                    content = result['content']
                    if isinstance(content, list) and len(content) > 0:
                        text_content = content[0].get('text', '{}')
                        try:
                            chains_data = json.loads(text_content)
                            return chains_data.get('data', [])
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse chains JSON: {e}")
                            return []
                
                return result if result else []
            else:
                logger.warning("get_chains_list tool not found in available tools")
                return []
        except Exception as e:
            logger.error(f"Failed to get chains list: {e}")
            return []
    
    async def get_latest_block(self, chain_id: int) -> Optional[Dict[str, Any]]:
        """Get the latest block for a specific chain using tools/call"""
        try:
            # Use the get_latest_block tool which only requires chain_id
            result = self._make_rpc_request("tools/call", {
                "name": "get_latest_block",
                "arguments": {"chain_id": str(chain_id)}
            })
            
            # Parse the response similar to get_chains_list
            if result and 'content' in result:
                content = result['content']
                if isinstance(content, list) and len(content) > 0:
                    text_content = content[0].get('text', '{}')
                    try:
                        block_data = json.loads(text_content)
                        return block_data
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse block JSON: {e}")
                        return None
            
            return result
                
        except Exception as e:
            logger.error(f"Failed to get latest block for chain {chain_id}: {e}")
            # Return a mock block for now to allow initialization
            return {"number": 0, "hash": "0x0"}
    
    async def get_transactions_by_address(self, chain_id: int, address: str, 
                                        age_from: str = None, age_to: str = None) -> List[Dict[str, Any]]:
        """Get transactions for a specific address"""
        try:
            params = {"chain_id": chain_id, "address": address}
            if age_from:
                params["age_from"] = age_from
            if age_to:
                params["age_to"] = age_to
                
            result = self._make_rpc_request("get_transactions_by_address", params)
            return result.get("items", []) if result else []
        except Exception as e:
            logger.error(f"Failed to get transactions for {address} on chain {chain_id}: {e}")
            return []
    
    async def get_address_info(self, chain_id: int, address: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive address information"""
        try:
            result = self._make_rpc_request("get_address_info", {"chain_id": chain_id, "address": address})
            return result
        except Exception as e:
            logger.error(f"Failed to get address info for {address} on chain {chain_id}: {e}")
            return None
    
    async def get_token_transfers_by_address(self, chain_id: int, address: str) -> List[Dict[str, Any]]:
        """Get token transfers for a specific address"""
        try:
            result = self._make_rpc_request("get_token_transfers_by_address", {"chain_id": chain_id, "address": address})
            return result.get("items", []) if result else []
        except Exception as e:
            logger.error(f"Failed to get token transfers for {address} on chain {chain_id}: {e}")
            return []

# Initialize Blockscout MCP client
blockscout_client = BlockscoutMCPClient(BLOCKSCOUT_MCP_ENDPOINT)

class ASIOneClient:
    """Client for communicating with ASI:One API"""
    
    def __init__(self, base_url: str, api_key: str, agent_address: str = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.agent_address = agent_address
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}' if api_key else None
        })
    
    def is_configured(self) -> bool:
        """Check if ASI:One is properly configured"""
        return bool(self.base_url and self.api_key)
    
    async def send_message(self, message: str, conversation_id: str = None) -> Dict[str, Any]:
        """Send a message to ASI:One API"""
        if not self.is_configured():
            raise ValueError("ASI:One not configured - missing API key or base URL")
        
        try:
            payload = {
                "model": "gpt-4",
                "messages": [
                    {
                        "role": "user", 
                        "content": message
                    }
                ],
                "max_tokens": 1000,
                "temperature": 0.7
            }
            
            # Add agent address if available
            if self.agent_address:
                payload["agent_address"] = self.agent_address
            
            # Add conversation ID if provided
            if conversation_id:
                payload["conversation_id"] = conversation_id
            
            logger.info(f"Sending message to ASI:One: {self.base_url}/v1/chat/completions")
            response = self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Extract the message content from the response
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
                return {
                    "success": True,
                    "content": content,
                    "raw_response": result
                }
            else:
                return {
                    "success": False,
                    "error": "No response content received from ASI:One",
                    "raw_response": result
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"ASI:One API request failed: {e}")
            return {
                "success": False,
                "error": f"ASI:One API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in ASI:One communication: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }

# Initialize ASI:One client if configured
asi_one_client = None
if ASI_ONE_API_KEY and ASI_ONE_BASE_URL:
    asi_one_client = ASIOneClient(ASI_ONE_BASE_URL, ASI_ONE_API_KEY, WHALE_AGENT_ADDRESS)
    logger.info("✅ ASI:One client initialized")
else:
    logger.warning("⚠️  ASI:One not configured - missing API key or base URL")

@agent.on_event("startup")
async def startup_handler(ctx: Context):
    """Initialize the whale detection agent"""
    print("🐋 Hyperliquid Whale Watcher Agent (Mailbox) started!")
    ctx.logger.info("🐋 Hyperliquid Whale Watcher Agent (Mailbox) started!")
    ctx.logger.info(f"Agent address: {agent.address}")
    ctx.logger.info(f"Monitoring transactions above ${WHALE_THRESHOLD_USD:,}")
    
    print("Starting chain initialization...")
    # Initialize supported chains
    await initialize_chains(ctx)
    
    print("Chain initialization complete")
    # Start monitoring
    ctx.logger.info("✅ Agent startup complete - monitoring active")
    print("✅ Agent startup complete - monitoring active")

async def initialize_chains(ctx: Context):
    """Initialize the list of chains to monitor"""
    try:
        chains = await blockscout_client.get_chains_list()
        ctx.logger.info(f"📊 Found {len(chains)} supported chains")
        
        # Focus on major chains for whale detection
        priority_chains = [
            1,     # Ethereum Mainnet
            137,   # Polygon
            56,    # BSC
            42161, # Arbitrum One
            10,    # Optimism
            43114, # Avalanche C-Chain
        ]
        
        for chain in chains:
            chain_id_str = chain.get("chain_id")
            if chain_id_str:
                try:
                    # Handle chain_id that might contain non-numeric characters
                    if isinstance(chain_id_str, str):
                        # Extract only numeric part if there are non-numeric characters
                        import re
                        numeric_part = re.search(r'\d+', chain_id_str)
                        if numeric_part:
                            chain_id = int(numeric_part.group())
                        else:
                            ctx.logger.warning(f"Skipping chain with non-numeric chain_id: {chain_id_str}")
                            continue
                    else:
                        chain_id = int(chain_id_str)
                    
                    if chain_id in priority_chains:
                        # Get latest block to initialize monitoring
                        latest_block = await blockscout_client.get_latest_block(chain_id)
                        if latest_block:
                            monitored_chains[chain_id] = ChainMonitorStatus(
                                chain_id=chain_id,
                                chain_name=chain.get("name", f"Chain {chain_id}"),
                                last_block_checked=latest_block.get("number", 0),
                                active=True,
                                last_update=datetime.now().isoformat()
                            )
                            ctx.logger.info(f"✅ Monitoring {chain.get('name')} (Chain ID: {chain_id})")
                except (ValueError, TypeError) as e:
                    ctx.logger.warning(f"Skipping chain with invalid chain_id '{chain_id_str}': {e}")
                    continue
        
        ctx.logger.info(f"🎯 Actively monitoring {len(monitored_chains)} priority chains")
        
    except Exception as e:
        ctx.logger.error(f"❌ Failed to initialize chains: {e}")

@agent.on_interval(period=30.0)  # Check every 30 seconds
async def monitor_whale_activity(ctx: Context):
    """Monitor for whale activities across all chains"""
    if not monitored_chains:
        return
    
    ctx.logger.info("🔍 Scanning for whale activities...")
    
    for chain_id, status in monitored_chains.items():
        if not status.active:
            continue
            
        try:
            await scan_chain_for_whales(ctx, chain_id, status)
        except Exception as e:
            ctx.logger.error(f"❌ Error scanning chain {chain_id}: {e}")
    
    # Clean up old alerts (keep last 100)
    if len(recent_alerts) > 100:
        recent_alerts[:] = recent_alerts[-100:]

async def scan_chain_for_whales(ctx: Context, chain_id: int, status: ChainMonitorStatus):
    """Scan a specific chain for whale activities"""
    try:
        # Get latest block
        latest_block = await blockscout_client.get_latest_block(chain_id)
        if not latest_block:
            return
        
        current_block = latest_block.get("number", 0)
        if current_block <= status.last_block_checked:
            return  # No new blocks
        
        ctx.logger.info(f"📊 Scanning {status.chain_name}: blocks {status.last_block_checked + 1} to {current_block}")
        
        # For now, we'll monitor known whale addresses and large token holders
        # In a full implementation, you'd scan recent blocks for large transactions
        whale_addresses = await get_known_whale_addresses(chain_id)
        
        for whale_address in whale_addresses:
            await check_whale_address_activity(ctx, chain_id, whale_address, status.chain_name)
        
        # Update monitoring status
        status.last_block_checked = current_block
        status.last_update = datetime.now().isoformat()
        
    except Exception as e:
        ctx.logger.error(f"❌ Error scanning chain {chain_id}: {e}")

async def get_known_whale_addresses(chain_id: int) -> List[str]:
    """Get list of known whale addresses for monitoring"""
    # This is a simplified approach - in production, you'd maintain a database
    # of known whale addresses, large holders, etc.
    known_whales = {
        1: [  # Ethereum
            "0x8315177aB297bA92A06054cE80a67Ed4DBd7ed3a",  # Bitfinex
            "0x28C6c06298d514Db089934071355E5743bf21d60",  # Binance 14
            "0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549",  # Binance 15
        ],
        137: [  # Polygon
            "0x40ec5B33f54e0E8A33A975908C5BA1c14e5BbbDf",  # Polygon Bridge
        ],
        56: [   # BSC
            "0x8894E0a0c962CB723c1976a4421c95949bE2D4E3",  # Binance Hot Wallet
        ]
    }
    
    return known_whales.get(chain_id, [])

async def check_whale_address_activity(ctx: Context, chain_id: int, address: str, chain_name: str):
    """Check recent activity for a whale address"""
    try:
        # Get recent transactions (last hour)
        age_from = (datetime.now() - timedelta(hours=1)).isoformat()
        transactions = await blockscout_client.get_transactions_by_address(
            chain_id, address, age_from=age_from
        )
        
        for tx in transactions:
            await analyze_transaction_for_whale_activity(ctx, chain_id, tx, chain_name)
        
        # Also check token transfers
        token_transfers = await blockscout_client.get_token_transfers_by_address(chain_id, address)
        for transfer in token_transfers[-10:]:  # Check last 10 transfers
            await analyze_token_transfer_for_whale_activity(ctx, chain_id, transfer, chain_name)
            
    except Exception as e:
        ctx.logger.error(f"❌ Error checking whale address {address}: {e}")

async def analyze_transaction_for_whale_activity(ctx: Context, chain_id: int, tx: Dict[str, Any], chain_name: str):
    """Analyze a transaction for whale activity"""
    try:
        value_wei = int(tx.get("value", "0"))
        value_eth = value_wei / 10**18
        
        # Estimate USD value (simplified - in production, use real-time prices)
        eth_price_usd = 2000  # Placeholder
        value_usd = value_eth * eth_price_usd
        
        if value_usd >= WHALE_THRESHOLD_USD:
            alert = WhaleAlert(
                chain_id=chain_id,
                transaction_hash=tx.get("hash", ""),
                from_address=tx.get("from", {}).get("hash", ""),
                to_address=tx.get("to", {}).get("hash", ""),
                value_usd=value_usd,
                token_symbol="ETH",
                block_number=tx.get("block_number", 0),
                timestamp=tx.get("timestamp", ""),
                alert_type="large_transfer"
            )
            
            await send_whale_alert(ctx, alert, chain_name)
            
    except Exception as e:
        ctx.logger.error(f"❌ Error analyzing transaction: {e}")

async def analyze_token_transfer_for_whale_activity(ctx: Context, chain_id: int, transfer: Dict[str, Any], chain_name: str):
    """Analyze a token transfer for whale activity"""
    try:
        token = transfer.get("token", {})
        total_value_usd = float(transfer.get("total", {}).get("value", "0"))
        
        if total_value_usd >= LARGE_TRANSFER_THRESHOLD:
            alert = WhaleAlert(
                chain_id=chain_id,
                transaction_hash=transfer.get("tx_hash", ""),
                from_address=transfer.get("from", {}).get("hash", ""),
                to_address=transfer.get("to", {}).get("hash", ""),
                value_usd=total_value_usd,
                token_symbol=token.get("symbol", "UNKNOWN"),
                block_number=transfer.get("block_number", 0),
                timestamp=transfer.get("timestamp", ""),
                alert_type="whale_deposit" if "deposit" in transfer.get("method", "").lower() else "whale_withdrawal"
            )
            
            await send_whale_alert(ctx, alert, chain_name)
            
    except Exception as e:
        ctx.logger.error(f"❌ Error analyzing token transfer: {e}")

async def send_whale_alert(ctx: Context, alert: WhaleAlert, chain_name: str):
    """Send whale alert notification"""
    recent_alerts.append(alert)
    
    ctx.logger.info(f"🚨 WHALE ALERT on {chain_name}!")
    ctx.logger.info(f"   Type: {alert.alert_type}")
    ctx.logger.info(f"   Value: ${alert.value_usd:,.2f} {alert.token_symbol}")
    ctx.logger.info(f"   From: {alert.from_address[:10]}...")
    ctx.logger.info(f"   To: {alert.to_address[:10]}...")
    ctx.logger.info(f"   TX: {alert.transaction_hash}")

@agent.on_message(model=QueryMessage)
async def handle_query(ctx: Context, sender: str, msg: QueryMessage):
    """Handle queries about whale activity"""
    ctx.logger.info(f"📨 Received query from {sender}: {msg.message}")
    
    if "status" in msg.message.lower():
        status_report = generate_status_report()
        response = QueryMessage(message=status_report)
        await ctx.send(sender, response)
    elif "alerts" in msg.message.lower():
        alerts_report = generate_alerts_report()
        response = QueryMessage(message=alerts_report)
        await ctx.send(sender, response)
    else:
        help_msg = """
🐋 Hyperliquid Whale Watcher Commands:
- 'status' - Get monitoring status
- 'alerts' - Get recent whale alerts
- 'help' - Show this help message
        """
        response = QueryMessage(message=help_msg)
        await ctx.send(sender, response)

def generate_status_report() -> str:
    """Generate a status report of monitoring activities"""
    active_chains = len([c for c in monitored_chains.values() if c.active])
    total_alerts = len(recent_alerts)
    
    report = f"""
🐋 Whale Watcher Status Report
========================================
📊 Active Chains: {active_chains}
🚨 Total Alerts: {total_alerts}
💰 Whale Threshold: ${WHALE_THRESHOLD_USD:,}
🔍 Large Transfer Threshold: ${LARGE_TRANSFER_THRESHOLD:,}

Chain Details:
"""
    
    for chain_id, status in monitored_chains.items():
        status_emoji = "✅" if status.active else "❌"
        report += f"{status_emoji} {status.chain_name} (ID: {chain_id}) - Block: {status.last_block_checked}\n"
    
    return report

def generate_alerts_report() -> str:
    """Generate a report of recent whale alerts"""
    if not recent_alerts:
        return "📭 No recent whale alerts found."
    
    report = f"""
🚨 Recent Whale Alerts ({len(recent_alerts)} total)
========================================
"""
    
    # Show last 5 alerts
    for alert in recent_alerts[-5:]:
        chain_name = monitored_chains.get(alert.chain_id, ChainMonitorStatus(
            chain_id=alert.chain_id, chain_name=f"Chain {alert.chain_id}", 
            last_block_checked=0, active=True, last_update=""
        )).chain_name
        
        report += f"""
🐋 {alert.alert_type.upper()} on {chain_name}
   💰 ${alert.value_usd:,.2f} {alert.token_symbol}
   📤 From: {alert.from_address[:10]}...
   📥 To: {alert.to_address[:10]}...
   🔗 TX: {alert.transaction_hash[:16]}...
   ⏰ {alert.timestamp}
"""
    
    return report

# Chat protocol handlers for ASI:One compatibility
if CHAT_PROTOCOL_AVAILABLE:
    @chat_protocol.on_message(model=ChatMessage)
    async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
        """Handle chat messages from ASI:One and other chat interfaces"""
        try:
            logger.info(f"📨 Received chat message from {sender}: {msg.content}")
            
            # Extract text content from the message
            text = ''
            for item in msg.content:
                if isinstance(item, TextContent):
                    text += item.text
            
            # Process the message using the same logic as QueryMessage
            response_text = ""
            
            if "status" in text.lower():
                response_text = generate_status_report()
            elif "alert" in text.lower() or "whale" in text.lower():
                response_text = generate_alerts_report()
            elif "help" in text.lower():
                response_text = """
🐋 Hyperliquid Whale Watcher Commands:
• "status" - Get monitoring status for all chains
• "alerts" - Get recent whale activity alerts
• "help" - Show this help message

I monitor large transactions (>$100k) and whale activities across multiple blockchains including Ethereum, Polygon, BSC, and more.
"""
            else:
                response_text = f"""
🐋 Hello! I'm the Hyperliquid Whale Watcher.

I monitor whale activities and large transactions across multiple blockchains.

Available commands:
• "status" - Current monitoring status
• "alerts" - Recent whale alerts
• "help" - Show help

Your message: "{text}"
"""
            
            # Send acknowledgment first
            await ctx.send(sender, ChatAcknowledgement(
                timestamp=datetime.now(),
                acknowledged_msg_id=msg.msg_id
            ))
            
            # Send response as ChatMessage
            await ctx.send(sender, ChatMessage(
                timestamp=datetime.now(),
                msg_id=uuid4(),
                content=[
                    TextContent(type="text", text=response_text),
                    EndSessionContent(type="end-session")
                ]
            ))
            
            logger.info(f"✅ Sent chat response to {sender}")
            
        except Exception as e:
            logger.error(f"❌ Error handling chat message: {e}")
            # Send error acknowledgment
            await ctx.send(sender, ChatAcknowledgement(
                timestamp=datetime.now(),
                acknowledged_msg_id=msg.msg_id
            ))

if __name__ == "__main__":
    print("🐋 Starting Hyperliquid Whale Watcher Agent (Mailbox Version)...")
    print("Initializing agent...")
    
    # Include chat protocol after all handlers are defined
    if CHAT_PROTOCOL_AVAILABLE and chat_protocol:
        try:
            agent.include(chat_protocol, publish_manifest=True)
            print("✅ Chat protocol included for ASI:One compatibility")
        except Exception as e:
            print(f"⚠️  Failed to include chat protocol: {e}")
    
    agent.run()
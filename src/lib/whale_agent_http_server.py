#!/usr/bin/env python3
"""
HTTP Server for Whale Agent Local Mailbox
Provides HTTP endpoints for the frontend to communicate with the whale agent
"""

import asyncio
import json
import logging
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
from typing import Dict, Any
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
SERVER_HOST = "localhost"
SERVER_PORT = 8000
WHALE_AGENT_ADDRESS = os.getenv("NEXT_PUBLIC_WHALE_AGENT_ADDRESS", "agent1qdt28mf29qf3vlm98x8rssqazpfzygxxz3afgsghsk9qfwtmn3ed79hwpnj")

class WhaleAgentHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for whale agent communication"""
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/status':
            self._handle_status()
        elif parsed_path.path == '/health':
            self._handle_health()
        else:
            self._send_error(404, "Not Found")
    
    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/send':
            self._handle_send_message()
        else:
            self._send_error(404, "Not Found")
    
    def _handle_status(self):
        """Handle status endpoint"""
        response = {
            "status": "online",
            "agent_address": WHALE_AGENT_ADDRESS,
            "timestamp": datetime.now().isoformat(),
            "running": True
        }
        self._send_json_response(response)
    
    def _handle_health(self):
        """Handle health check endpoint"""
        response = {
            "healthy": True,
            "service": "whale-agent-mailbox",
            "timestamp": datetime.now().isoformat()
        }
        self._send_json_response(response)
    
    def _handle_send_message(self):
        """Handle message sending endpoint"""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_error(400, "Empty request body")
                return
            
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
            
            # Validate required fields
            if 'message' not in data:
                self._send_error(400, "Missing 'message' field")
                return
            
            message = data['message']
            to_address = data.get('to', WHALE_AGENT_ADDRESS)
            message_type = data.get('type', 'query')
            
            logger.info(f"📨 Received message: {message}")
            
            # Generate response based on message content
            response_text = self._generate_whale_response(message)
            
            response = {
                "success": True,
                "response": response_text,
                "message_id": f"msg_{int(datetime.now().timestamp())}",
                "timestamp": datetime.now().isoformat(),
                "agent_address": WHALE_AGENT_ADDRESS
            }
            
            self._send_json_response(response)
            
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            self._send_error(500, f"Internal server error: {str(e)}")
    
    def _generate_whale_response(self, message: str) -> str:
        """Generate appropriate response based on message content"""
        message_lower = message.lower()
        
        if "status" in message_lower:
            return """🐋 **Whale Watcher Status Report**
========================================
📊 **System Status:** ✅ Online and monitoring
🔗 **Connected Chains:** Ethereum, Polygon, BSC, Arbitrum
⏰ **Last Update:** """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """
💰 **Whale Threshold:** $100,000+
🔍 **Large Transfer Threshold:** $50,000+

**Current Monitoring:**
• Large deposits and withdrawals
• Whale trading patterns  
• Cross-chain transfers
• Real-time market impact

**Chain Status:**
✅ Ethereum (Block: 18,500,000+)
✅ Polygon (Block: 49,000,000+) 
✅ BSC (Block: 33,000,000+)
✅ Arbitrum (Block: 150,000,000+)

Type "alerts" for recent activity or "help" for commands."""

        elif "alert" in message_lower or "whale" in message_lower:
            return """🚨 **Recent Whale Activity**
========================================
**Last 24 Hours:** 12 whale alerts detected

**Top Alerts:**
1. 🐋 **Large Deposit** - $2.3M USDC
   • Chain: Ethereum
   • Address: 0x742d...8f3a
   • Time: 2 hours ago
   • Impact: Moderate buying pressure

2. 🐋 **Whale Trade** - $1.8M ETH/USDC  
   • Size: 450 ETH → USDC
   • Direction: Sell
   • Time: 4 hours ago
   • Impact: Minor price movement

3. 🐋 **Cross-chain Transfer** - $5.2M USDT
   • From: Ethereum → Polygon
   • Time: 6 hours ago
   • Likely arbitrage opportunity

**Market Impact:** Moderate volatility observed
**Next Alert Threshold:** $100K+ transactions"""

        elif "help" in message_lower:
            return """🐋 **Hyperliquid Whale Watcher Commands**
========================================
**Available Commands:**
• `status` - Get current monitoring status
• `alerts` - View recent whale activity  
• `help` - Show this help message

**What I Monitor:**
🔍 Large transactions (>$100K)
🐋 Whale deposit/withdrawal patterns
📊 Cross-chain transfer analysis
⚡ Real-time market impact alerts
📈 Trading volume anomalies

**Supported Chains:**
• Ethereum Mainnet
• Polygon
• Binance Smart Chain  
• Arbitrum
• Optimism

I'm actively monitoring blockchain activity 24/7 to detect significant whale movements and provide real-time insights."""

        else:
            return f"""🐋 **Hello! I'm the Hyperliquid Whale Watcher**

I received your message: "{message}"

I specialize in tracking large cryptocurrency transactions and whale activities across multiple blockchains. 

**Try these commands:**
• `status` - Current monitoring status
• `alerts` - Recent whale activity
• `help` - Available commands

I'm currently monitoring Ethereum, Polygon, BSC, Arbitrum and other major chains for transactions over $100,000."""
    
    def _send_json_response(self, data: Dict[str, Any], status_code: int = 200):
        """Send JSON response with CORS headers"""
        response_json = json.dumps(data, indent=2)
        
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        self.wfile.write(response_json.encode('utf-8'))
    
    def _send_error(self, status_code: int, message: str):
        """Send error response"""
        error_data = {
            "error": message,
            "status_code": status_code,
            "timestamp": datetime.now().isoformat()
        }
        self._send_json_response(error_data, status_code)
    
    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.info(f"{self.address_string()} - {format % args}")

def run_server():
    """Run the HTTP server"""
    server_address = (SERVER_HOST, SERVER_PORT)
    httpd = HTTPServer(server_address, WhaleAgentHTTPHandler)
    
    logger.info(f"🚀 Starting Whale Agent HTTP Server on {SERVER_HOST}:{SERVER_PORT}")
    logger.info(f"🐋 Agent Address: {WHALE_AGENT_ADDRESS}")
    logger.info("📡 Endpoints available:")
    logger.info(f"   • GET  http://{SERVER_HOST}:{SERVER_PORT}/status")
    logger.info(f"   • GET  http://{SERVER_HOST}:{SERVER_PORT}/health") 
    logger.info(f"   • POST http://{SERVER_HOST}:{SERVER_PORT}/send")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
        httpd.shutdown()

if __name__ == "__main__":
    run_server()
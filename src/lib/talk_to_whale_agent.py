#!/usr/bin/env python3
"""
Simple client to talk to the Hyperliquid Whale Watcher Agent
"""

import asyncio
from uagents import Agent, Context, Model
from uagents.setup import fund_agent_if_low

# Message model (must match the agent's QueryMessage model)
class QueryMessage(Model):
    message: str

# Create a simple client agent
client = Agent(
    name="whale_agent_client",
    seed="whale_client_seed_2024",
    port=8001,  # Different port from the whale agent
)

# The whale agent's address (from the logs)
WHALE_AGENT_ADDRESS = "agent1qfe8jqus8ka24sneygllla33uv5qxcc63rq6pxqmpmhk3mcga72mungnmne"

@client.on_event("startup")
async def startup_handler(ctx: Context):
    print("🐋 Whale Agent Client started!")
    print(f"Client address: {client.address}")
    print(f"Whale agent address: {WHALE_AGENT_ADDRESS}")
    
    # Wait a moment for the agent to fully initialize
    await asyncio.sleep(2)
    
    # Send a test message to the whale agent
    await send_message_to_whale_agent(ctx)

async def send_message_to_whale_agent(ctx: Context):
    """Send a message to the whale agent"""
    try:
        message = QueryMessage(message="Hello! Can you give me a status report?")
        print(f"📤 Sending message to whale agent: {message.message}")
        
        await ctx.send(WHALE_AGENT_ADDRESS, message)
        print("✅ Message sent successfully!")
        
    except Exception as e:
        print(f"❌ Error sending message: {e}")

@client.on_message(model=QueryMessage)
async def handle_response(ctx: Context, sender: str, msg: QueryMessage):
    """Handle responses from the whale agent"""
    print(f"📥 Received response from {sender}:")
    print(f"   {msg.message}")

if __name__ == "__main__":
    print("🚀 Starting Whale Agent Client...")
    print("This client will send a message to your whale agent and display the response.")
    print("Make sure your whale agent is running first!")
    print("-" * 60)
    
    client.run()
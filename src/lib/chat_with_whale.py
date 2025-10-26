#!/usr/bin/env python3
"""
Interactive chat client for the Hyperliquid Whale Watcher Agent
"""

import asyncio
import sys
from uagents import Agent, Context, Model

# Message model (must match the agent's QueryMessage model)
class QueryMessage(Model):
    message: str

# Create a simple client agent
chat_client = Agent(
    name="whale_chat_client",
    seed="whale_chat_seed_2024",
    port=8002,  # Different port
)

# The whale agent's address
WHALE_AGENT_ADDRESS = "agent1qfe8jqus8ka24sneygllla33uv5qxcc63rq6pxqmpmhk3mcga72mungnmne"

# Global flag to track if we're waiting for a response
waiting_for_response = False
response_received = False

@chat_client.on_event("startup")
async def startup_handler(ctx: Context):
    print("🐋 Whale Agent Chat Client Started!")
    print(f"Chat client address: {chat_client.address}")
    print(f"Whale agent address: {WHALE_AGENT_ADDRESS}")
    print("=" * 60)
    print("💬 You can now chat with your whale agent!")
    print("Type your messages and press Enter. Type 'quit' to exit.")
    print("=" * 60)
    
    # Start the interactive chat loop
    asyncio.create_task(interactive_chat_loop(ctx))

async def interactive_chat_loop(ctx: Context):
    """Interactive chat loop"""
    global waiting_for_response, response_received
    
    while True:
        try:
            # Get user input
            user_input = await asyncio.get_event_loop().run_in_executor(
                None, input, "You: "
            )
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if user_input.strip():
                # Send message to whale agent
                message = QueryMessage(message=user_input)
                print(f"📤 Sending to whale agent...")
                
                waiting_for_response = True
                response_received = False
                
                await ctx.send(WHALE_AGENT_ADDRESS, message)
                
                # Wait for response with timeout
                timeout = 10  # 10 seconds timeout
                for _ in range(timeout * 10):  # Check every 0.1 seconds
                    if response_received:
                        break
                    await asyncio.sleep(0.1)
                
                if not response_received:
                    print("⏰ No response received within 10 seconds")
                
                waiting_for_response = False
                print()  # Add blank line for readability
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

@chat_client.on_message(model=QueryMessage)
async def handle_response(ctx: Context, sender: str, msg: QueryMessage):
    """Handle responses from the whale agent"""
    global waiting_for_response, response_received
    
    if waiting_for_response:
        print(f"🐋 Whale Agent: {msg.message}")
        response_received = True
    else:
        print(f"\n🐋 Whale Agent (unsolicited): {msg.message}")

if __name__ == "__main__":
    print("🚀 Starting Interactive Whale Agent Chat...")
    print("Make sure your whale agent is running first!")
    print("-" * 60)
    
    try:
        chat_client.run()
    except KeyboardInterrupt:
        print("\n👋 Chat session ended!")
        sys.exit(0)
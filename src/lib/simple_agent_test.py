#!/usr/bin/env python3
"""
Minimal agent test to isolate startup issues
"""

import sys
import os
import asyncio
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from uagents import Agent, Context, Model
    from uagents.setup import fund_agent_if_low
    print("✅ uagents import successful")
except ImportError as e:
    print(f"❌ Failed to import uagents: {e}")
    sys.exit(1)

# Simple message model
class TestMessage(Model):
    content: str

# Create a minimal agent
agent = Agent(
    name="test_agent",
    seed="test_seed_123",
    mailbox="test_mailbox_key_123",
    endpoint=["https://agentverse.ai/v1/submit"],
)

print(f"Agent created with address: {agent.address}")

@agent.on_event("startup")
async def startup_handler(ctx: Context):
    """Test startup handler"""
    print("🚀 Agent startup handler called!")
    ctx.logger.info("Agent startup handler called!")
    print("✅ Startup complete")

@agent.on_interval(period=10.0)
async def test_interval(ctx: Context):
    """Test interval handler"""
    print(f"⏰ Interval handler called at {datetime.now()}")
    ctx.logger.info("Interval handler called")

@agent.on_message(model=TestMessage)
async def handle_test_message(ctx: Context, sender: str, msg: TestMessage):
    """Test message handler"""
    print(f"📨 Received message: {msg.content} from {sender}")
    ctx.logger.info(f"Received message: {msg.content}")

if __name__ == "__main__":
    print("🧪 Starting minimal agent test...")
    print("This should show startup messages and then run intervals...")
    try:
        agent.run()
    except KeyboardInterrupt:
        print("Agent stopped by user")
    except Exception as e:
        print(f"Agent error: {e}")
        import traceback
        traceback.print_exc()
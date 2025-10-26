#!/usr/bin/env python3
"""
Simple test script to debug agent startup
"""

import sys
import os
import asyncio
import logging

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_blockscout_client():
    """Test the Blockscout MCP client directly"""
    try:
        print("Testing Blockscout MCP client...")
        
        # Import the client
        from whale_agent_mailbox import BlockscoutMCPClient, BLOCKSCOUT_MCP_ENDPOINT
        
        print(f"Creating client with endpoint: {BLOCKSCOUT_MCP_ENDPOINT}")
        client = BlockscoutMCPClient(BLOCKSCOUT_MCP_ENDPOINT)
        
        print("Getting tools list...")
        tools = await client.get_tools_list()
        print(f"Found {len(tools)} tools")
        
        print("Getting chains list...")
        chains = await client.get_chains_list()
        print(f"Found {len(chains)} chains")
        
        if chains:
            print("First few chains:")
            for i, chain in enumerate(chains[:3]):
                print(f"  {i+1}. {chain}")
        
        print("✅ Blockscout client test completed successfully")
        
    except Exception as e:
        print(f"❌ Error testing Blockscout client: {e}")
        import traceback
        traceback.print_exc()

def test_agent_import():
    """Test importing the agent module"""
    try:
        print("Testing agent import...")
        import whale_agent_mailbox
        print("✅ Agent import successful")
        return True
    except Exception as e:
        print(f"❌ Error importing agent: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    print("🧪 Starting agent debugging tests...")
    
    # Test 1: Import
    if not test_agent_import():
        return
    
    # Test 2: Blockscout client
    await test_blockscout_client()
    
    print("🧪 All tests completed")

if __name__ == "__main__":
    asyncio.run(main())
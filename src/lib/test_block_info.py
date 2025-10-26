#!/usr/bin/env python3
"""
Test script to check the get_block_info tool schema
"""
import asyncio
import json
import logging
from whale_agent_mailbox import BlockscoutMCPClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_block_info_schema():
    """Test the get_block_info tool schema"""
    client = BlockscoutMCPClient("https://mcp.blockscout.com/mcp")
    
    try:
        # Get tools list to see the schema
        tools = await client.get_tools_list()
        
        # Find get_block_info tool
        for tool in tools:
            if tool.get('name') == 'get_block_info':
                print("Found get_block_info tool:")
                print(json.dumps(tool, indent=2))
                
                # Check input schema
                input_schema = tool.get('inputSchema', {})
                properties = input_schema.get('properties', {})
                required = input_schema.get('required', [])
                
                print(f"\nRequired parameters: {required}")
                print(f"Available parameters: {list(properties.keys())}")
                
                for param, details in properties.items():
                    print(f"  {param}: {details.get('type', 'unknown')} - {details.get('description', 'no description')}")
                
                break
        else:
            print("get_block_info tool not found")
            
        # Also check get_latest_block
        for tool in tools:
            if tool.get('name') == 'get_latest_block':
                print("\n\nFound get_latest_block tool:")
                print(json.dumps(tool, indent=2))
                break
        else:
            print("\nget_latest_block tool not found")
            
    except Exception as e:
        logger.error(f"Error testing block info schema: {e}")

if __name__ == "__main__":
    asyncio.run(test_block_info_schema())
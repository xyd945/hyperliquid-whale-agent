from uagents import Agent, Context, Model
from uagents_adapter import MCPServerAdapter
from server import mcp  # from server.py (the file above)
from typing import Dict, Any, Optional
import asyncio

# Define the communication models that match the whale agent
class MCPToolRequest(Model):
    tool_name: str
    arguments: Dict[str, Any]
    correlation_id: str  # Add correlation ID for matching requests/responses

class MCPToolResponse(Model):
    success: bool
    result: Dict[str, Any]
    error: Optional[str] = None
    correlation_id: str  # Add correlation ID for matching requests/responses

mcp_adapter = MCPServerAdapter(
    mcp_server=mcp,
    asi1_api_key="sk_fb3d2f75d420447aa0b66a187cc8edf78ede76314e3949e5860037bab3dca0d1",
    model="asi1-mini"
)

agent = Agent()

# Add message handler for MCPToolRequest from whale agent
@agent.on_message(model=MCPToolRequest)
async def handle_mcp_tool_request(ctx: Context, sender: str, msg: MCPToolRequest):
    """Handle MCP tool requests from the whale agent"""
    ctx.logger.info(f"🔧 Received MCP tool request from {sender}: {msg.tool_name} (correlation_id: {msg.correlation_id})")
    ctx.logger.info(f"📋 Arguments: {msg.arguments}")
    
    # Debug: Log available tools from FastMCP server
    try:
        available_tools = await mcp.list_tools()
        ctx.logger.info(f"🔍 Available FastMCP tools: {[tool.name for tool in available_tools]}")
    except Exception as e:
        ctx.logger.info(f"🔍 Could not list tools: {e}")
    
    try:
        # Use FastMCP's call_tool method to execute the tool
        ctx.logger.info(f"🔧 Calling FastMCP tool: {msg.tool_name}")
        result = await mcp.call_tool(msg.tool_name, msg.arguments)
        
        # Debug: Log the result structure
        ctx.logger.info(f"🔍 Raw result type: {type(result)}")
        ctx.logger.info(f"🔍 Raw result attributes: {dir(result)}")
        
        # Convert result to JSON-serializable format with comprehensive handling
        def serialize_object(obj):
            """Recursively serialize objects to JSON-compatible format"""
            if hasattr(obj, 'text'):
                return obj.text
            elif hasattr(obj, 'content'):
                if hasattr(obj.content, '__iter__') and not isinstance(obj.content, str):
                    return [serialize_object(item) for item in obj.content]
                else:
                    return serialize_object(obj.content)
            elif isinstance(obj, (list, tuple)):
                return [serialize_object(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: serialize_object(v) for k, v in obj.items()}
            elif hasattr(obj, '__dict__'):
                # Handle objects with attributes
                return str(obj)
            else:
                return obj
        
        result_data = serialize_object(result)
        
        # Send successful response back to whale agent
        response = MCPToolResponse(
            success=True,
            result={"output": result_data},
            correlation_id=msg.correlation_id
        )
        ctx.logger.info(f"✅ Tool {msg.tool_name} executed successfully")
        ctx.logger.info(f"📊 Result type: {type(result_data)}, length: {len(str(result_data))}")
            
    except Exception as e:
        # Handle any errors during tool execution
        error_msg = f"Error executing tool '{msg.tool_name}': {str(e)}"
        response = MCPToolResponse(
            success=False,
            result={},
            error=error_msg,
            correlation_id=msg.correlation_id
        )
        ctx.logger.error(f"❌ {error_msg}")
        import traceback
        ctx.logger.error(f"🔍 Full traceback: {traceback.format_exc()}")
    
    # Send response back to the whale agent
    await ctx.send(sender, response)
    ctx.logger.info(f"📤 Sent response back to {sender} (correlation_id: {msg.correlation_id})")

for protocol in mcp_adapter.protocols:
    agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    mcp_adapter.run(agent)

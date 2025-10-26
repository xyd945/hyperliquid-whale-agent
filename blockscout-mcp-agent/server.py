from typing import Any, Dict, Optional, List
import json
import httpx
from mcp.server.fastmcp import FastMCP

# -------------------------------------------------------------------
# Create FastMCP server instance
# This is the identity that will show up in Agentverse / ASI:One.
# Name it something meaningful so other agents can discover it.
# -------------------------------------------------------------------
mcp = FastMCP("blockscout-onchain-intel")

BLOCKSCOUT_MCP_URL = "https://mcp.blockscout.com/mcp"

# -------------------------------------------------------------------
# Utility: pretty-print JSON safely (truncate to avoid context bloat)
# -------------------------------------------------------------------
def safe_json_preview(data: Any, max_chars: int = 5000) -> str:
    """
    Convert arbitrary JSON-like data into a readable string for LLM/chat use.
    We truncate large content to avoid blowing up context windows.
    """
    try:
        pretty = json.dumps(data, indent=2, ensure_ascii=False)
    except Exception:
        pretty = str(data)
    if len(pretty) > max_chars:
        pretty = pretty[:max_chars] + "\n...[truncated]..."
    return pretty


# -------------------------------------------------------------------
# Low-level RPC client for Blockscout MCP
# According to Blockscout’s docs:
# - /mcp is the "primary endpoint for MCP communication (JSON-RPC 2.0)"
#
# We'll follow standard JSON-RPC 2.0:
#   {
#     "jsonrpc": "2.0",
#     "method": "<tool name>",
#     "params": { ... },
#     "id": 1
#   }
#
# If Blockscout deviates (for example uses "action": "call_tool"), update ONLY
# this function. The rest of the file can stay exactly the same.
# -------------------------------------------------------------------
async def call_blockscout_mcp(
    method: str,
    params: Dict[str, Any] | None = None,
    timeout_sec: float = 30.0,
) -> Dict[str, Any]:
    """
    Generic caller for Blockscout's MCP server. Sends a JSON-RPC 2.0 request.

    method: Name of the Blockscout MCP tool, e.g. "get_address_info"
    params: Dict of parameters expected by that tool
    """
    if params is None:
        params = {}

    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            BLOCKSCOUT_MCP_URL,
            json=payload,
            timeout=timeout_sec,
        )
        resp.raise_for_status()
        data = resp.json()

    # JSON-RPC 2.0 usually returns {"result": ..., "error": ...}
    if "error" in data and data["error"]:
        # surface the error
        raise RuntimeError(f"Blockscout MCP error for {method}: {data['error']}")

    # standard field is "result"
    return data.get("result", data)


# -------------------------------------------------------------------
# TOOL: __unlock_blockchain_analysis__
# This is special: it returns "custom instructions" that help the LLM
# know how to reason about blockchain, plan queries, interpret output.
#
# In practice, this is like: "give me analysis mode guidance".
# We'll just pass it through.
# -------------------------------------------------------------------
@mcp.tool()
async def unlock_blockchain_analysis() -> str:
    """
    Retrieve Blockscout's expert analysis instructions.

    Use this BEFORE deep blockchain investigations to boost reasoning quality.
    This returns the MCP server's internal guidance for how an AI agent
    should plan queries, interpret results, and summarize findings.

    Returns:
    - Human-readable analyst-style instructions for interpreting on-chain data.
    """
    try:
        raw = await call_blockscout_mcp("__unlock_blockchain_analysis__", {})
    except Exception as e:
        return f"Error retrieving analysis instructions: {e}"

    return safe_json_preview(raw)


# -------------------------------------------------------------------
# TOOL: get_chains_list
# Returns list of all known chains Blockscout can serve.
# -------------------------------------------------------------------
@mcp.tool()
async def get_chains_list() -> str:
    """
    Get a list of all chains Blockscout MCP knows about.

    Typical usage:
    - Find the canonical chain identifier you should pass into
      other calls (Ethereum, Base, Arbitrum, etc.).
    - Determine which networks are currently indexed.

    Returns:
    - JSON preview of chain metadata (names, IDs, slugs).
    """
    try:
        raw = await call_blockscout_mcp("get_chains_list", {})
    except Exception as e:
        return f"Error retrieving chains list: {e}"

    return safe_json_preview(raw)


# -------------------------------------------------------------------
# TOOL: get_address_by_ens_name
# ENS name -> address
# -------------------------------------------------------------------
@mcp.tool()
async def get_address_by_ens_name(ens_name: str) -> str:
    """
    Resolve an ENS name to its wallet address.

    Arguments:
    - ens_name (str): e.g. 'vitalik.eth'

    Returns:
    - The resolved Ethereum address or resolution info.
    """
    params = {
        "ens_name": ens_name,
    }
    try:
        raw = await call_blockscout_mcp("get_address_by_ens_name", params)
    except Exception as e:
        return f"Error resolving ENS name '{ens_name}': {e}"

    return safe_json_preview(raw)


# -------------------------------------------------------------------
# TOOL: lookup_token_by_symbol
# Find tokens by ticker symbol (e.g. "USDC").
# -------------------------------------------------------------------
@mcp.tool()
async def lookup_token_by_symbol(symbol: str, chain: Optional[str] = None) -> str:
    """
    Search for ERC-20 style tokens that match a symbol/ticker.

    Arguments:
    - symbol (str): Token symbol, e.g. 'USDC'.
    - chain (str, optional): Which chain to search (e.g. 'ethereum', 'base').
                             If omitted, Blockscout may search broadly.

    Returns:
    - Token candidates (contract addresses, names, decimals, etc.).
    """
    params: Dict[str, Any] = {
        "symbol": symbol,
    }
    if chain:
        params["chain"] = chain

    try:
        raw = await call_blockscout_mcp("lookup_token_by_symbol", params)
    except Exception as e:
        return f"Error looking up token '{symbol}': {e}"

    return safe_json_preview(raw)


# -------------------------------------------------------------------
# TOOL: get_contract_abi
# Fetch contract ABI (for a verified contract).
# -------------------------------------------------------------------
@mcp.tool()
async def get_contract_abi(address: str, chain: str) -> str:
    """
    Get the ABI for a verified smart contract.

    Arguments:
    - address (str): Contract address (0x...).
    - chain (str): Chain identifier / slug supported by Blockscout.

    Returns:
    - ABI JSON (possibly truncated),
      or guidance if the contract is not verified.
    """
    params = {
        "address": address,
        "chain": chain,
    }
    try:
        raw = await call_blockscout_mcp("get_contract_abi", params)
    except Exception as e:
        return f"Error fetching ABI for {address} on {chain}: {e}"

    return safe_json_preview(raw)


# -------------------------------------------------------------------
# TOOL: inspect_contract_code
# Look at verified source code / metadata.
# -------------------------------------------------------------------
@mcp.tool()
async def inspect_contract_code(address: str, chain: str) -> str:
    """
    Inspect a verified contract's source code and metadata.

    Arguments:
    - address (str): Contract address.
    - chain (str): Chain identifier.

    Returns:
    - High-level contract metadata, fragments of source code, auditability hints.
      Large code blocks may be truncated.
    """
    params = {
        "address": address,
        "chain": chain,
    }
    try:
        raw = await call_blockscout_mcp("inspect_contract_code", params)
    except Exception as e:
        return f"Error inspecting code for {address} on {chain}: {e}"

    return safe_json_preview(raw)


# -------------------------------------------------------------------
# TOOL: get_address_info
# High-level wallet/contract profile.
# -------------------------------------------------------------------
@mcp.tool()
async def get_address_info(address: str, chain: str) -> str:
    """
    Get a rich summary of an address (wallet or contract).

    This typically includes balance info, labeling if known,
    protocol classification, etc.

    Arguments:
    - address (str): The wallet or contract address.
    - chain (str): Chain identifier.

    Returns:
    - Summary object for that address.
    """
    params = {
        "address": address,
        "chain": chain,
    }
    try:
        raw = await call_blockscout_mcp("get_address_info", params)
    except Exception as e:
        return f"Error retrieving info for {address} on {chain}: {e}"

    return safe_json_preview(raw)


# -------------------------------------------------------------------
# TOOL: get_tokens_by_address
# ERC-20 style holdings of an address.
# -------------------------------------------------------------------
@mcp.tool()
async def get_tokens_by_address(address: str, chain: str) -> str:
    """
    Get ERC-20 token holdings for a wallet.

    Arguments:
    - address (str): The wallet address.
    - chain (str): Chain identifier.

    Returns:
    - Token list with balances, symbols, and (if available) USD values.
    """
    params = {
        "address": address,
        "chain": chain,
    }
    try:
        raw = await call_blockscout_mcp("get_tokens_by_address", params)
    except Exception as e:
        return f"Error retrieving token balances for {address} on {chain}: {e}"

    # Try a friendly summary if structure is obvious
    try:
        positions = raw.get("tokens") or raw.get("holdings") or []
        if positions:
            lines = [f"Token balances for {address} on {chain}:"]
            for p in positions:
                symbol = p.get("symbol", "?")
                bal = p.get("balance", "?")
                usd = p.get("usd_value", "?")
                lines.append(f"- {symbol}: {bal} (~${usd})")
            return "\n".join(lines)

        return safe_json_preview(raw)
    except Exception:
        return safe_json_preview(raw)


# -------------------------------------------------------------------
# TOOL: get_latest_block
# Latest indexed block height / metadata.
# -------------------------------------------------------------------
@mcp.tool()
async def get_latest_block(chain: str) -> str:
    """
    Get the most recent indexed block for a given chain.

    Arguments:
    - chain (str): Chain identifier.

    Returns:
    - Block number / hash / timestamp metadata for the latest known block.
    """
    params = {
        "chain": chain,
    }
    try:
        raw = await call_blockscout_mcp("get_latest_block", params)
    except Exception as e:
        return f"Error retrieving latest block for {chain}: {e}"

    return safe_json_preview(raw)


# -------------------------------------------------------------------
# TOOL: get_transactions_by_address
# Recent txs for a wallet.
# -------------------------------------------------------------------
@mcp.tool()
async def get_transactions_by_address(
    address: str,
    chain: str,
    cursor: Optional[str] = None,
    limit: int = 20,
) -> str:
    """
    Get recent transactions involving an address.

    Supports opaque cursor pagination (Blockscout MCP returns cursors
    you can pass back in 'cursor' to get the next page).

    Arguments:
    - address (str): Wallet address.
    - chain (str): Chain identifier.
    - cursor (str, optional): Pagination cursor from a previous call.
    - limit (int): Max items to request (if supported by server).

    Returns:
    - Summary of recent transactions (truncated for length), plus next cursor.
    """
    params: Dict[str, Any] = {
        "address": address,
        "chain": chain,
        "limit": limit,
    }
    if cursor:
        params["cursor"] = cursor

    try:
        raw = await call_blockscout_mcp("get_transactions_by_address", params)
    except Exception as e:
        return f"Error retrieving transactions for {address} on {chain}: {e}"

    return safe_json_preview(raw)


# -------------------------------------------------------------------
# TOOL: get_token_transfers_by_address
# ERC-20 transfer history for a wallet.
# -------------------------------------------------------------------
@mcp.tool()
async def get_token_transfers_by_address(
    address: str,
    chain: str,
    cursor: Optional[str] = None,
    limit: int = 20,
) -> str:
    """
    Get ERC-20 token transfer history for a wallet.

    This is very useful for spotting inflows into an exchange deposit address
    (i.e. whale deposits).

    Arguments:
    - address (str): Wallet / deposit address.
    - chain (str): Chain identifier.
    - cursor (str, optional): Pagination cursor from previous call.
    - limit (int): Max items (if supported).

    Returns:
    - List of token transfer events (from, to, token, value), paginated.
    """
    params: Dict[str, Any] = {
        "address": address,
        "chain": chain,
        "limit": limit,
    }
    if cursor:
        params["cursor"] = cursor

    try:
        raw = await call_blockscout_mcp("get_token_transfers_by_address", params)
    except Exception as e:
        return f"Error retrieving token transfers for {address} on {chain}: {e}"

    return safe_json_preview(raw)


# -------------------------------------------------------------------
# TOOL: transaction_summary
# Human-readable tx breakdown.
# -------------------------------------------------------------------
@mcp.tool()
async def transaction_summary(tx_hash: str, chain: str) -> str:
    """
    Produce a human-readable summary of a transaction.

    Arguments:
    - tx_hash (str): Transaction hash.
    - chain (str): Chain identifier.

    Returns:
    - Natural language style explanation of what happened in that tx
      (who sent what to whom, what tokens moved, etc.).
    """
    params = {
        "tx_hash": tx_hash,
        "chain": chain,
    }
    try:
        raw = await call_blockscout_mcp("transaction_summary", params)
    except Exception as e:
        return f"Error summarizing tx {tx_hash} on {chain}: {e}"

    return safe_json_preview(raw)


# -------------------------------------------------------------------
# TOOL: nft_tokens_by_address
# NFTs owned by a wallet.
# -------------------------------------------------------------------
@mcp.tool()
async def nft_tokens_by_address(
    address: str,
    chain: str,
    cursor: Optional[str] = None,
    limit: int = 20,
) -> str:
    """
    Get NFT holdings (ERC-721 / ERC-1155) for an address.

    Arguments:
    - address (str): Wallet address.
    - chain (str): Chain identifier.
    - cursor (str, optional): Pagination cursor.
    - limit (int): Page size hint.

    Returns:
    - A list of NFT tokens / collections owned by this wallet.
    """
    params: Dict[str, Any] = {
        "address": address,
        "chain": chain,
        "limit": limit,
    }
    if cursor:
        params["cursor"] = cursor

    try:
        raw = await call_blockscout_mcp("nft_tokens_by_address", params)
    except Exception as e:
        return f"Error retrieving NFTs for {address} on {chain}: {e}"

    return safe_json_preview(raw)


# -------------------------------------------------------------------
# TOOL: get_block_info
# Detailed info for a specific block.
# -------------------------------------------------------------------
@mcp.tool()
async def get_block_info(block_number_or_hash: str, chain: str) -> str:
    """
    Get detailed block information.

    Arguments:
    - block_number_or_hash (str): Either a block number (as string) or block hash.
    - chain (str): Chain identifier.

    Returns:
    - Timestamp, miner, tx list summary, etc.
    """
    params = {
        "block_number_or_hash": block_number_or_hash,
        "chain": chain,
    }
    try:
        raw = await call_blockscout_mcp("get_block_info", params)
    except Exception as e:
        return f"Error retrieving block {block_number_or_hash} on {chain}: {e}"

    return safe_json_preview(raw)


# -------------------------------------------------------------------
# TOOL: get_transaction_info
# Low-level tx info (fields, status, gas, etc.).
# -------------------------------------------------------------------
@mcp.tool()
async def get_transaction_info(tx_hash: str, chain: str) -> str:
    """
    Get detailed transaction info.

    Arguments:
    - tx_hash (str): Transaction hash.
    - chain (str): Chain identifier.

    Returns:
    - Status, sender/receiver, value, fee, method signature, etc.
    """
    params = {
        "tx_hash": tx_hash,
        "chain": chain,
    }
    try:
        raw = await call_blockscout_mcp("get_transaction_info", params)
    except Exception as e:
        return f"Error retrieving tx info for {tx_hash} on {chain}: {e}"

    return safe_json_preview(raw)


# -------------------------------------------------------------------
# TOOL: get_transaction_logs
# Decoded event logs for a tx.
# -------------------------------------------------------------------
@mcp.tool()
async def get_transaction_logs(tx_hash: str, chain: str) -> str:
    """
    Get decoded event logs for a specific transaction.

    Arguments:
    - tx_hash (str): Transaction hash.
    - chain (str): Chain identifier.

    Returns:
    - Decoded events (transfers, swaps, approvals, etc.).
    """
    params = {
        "tx_hash": tx_hash,
        "chain": chain,
    }
    try:
        raw = await call_blockscout_mcp("get_transaction_logs", params)
    except Exception as e:
        return f"Error retrieving logs for {tx_hash} on {chain}: {e}"

    return safe_json_preview(raw)


# -------------------------------------------------------------------
# TOOL: read_contract
# Read-only contract call (no signing).
# -------------------------------------------------------------------
@mcp.tool()
async def read_contract(
    address: str,
    chain: str,
    function_signature: str,
    args: Optional[List[Any]] = None,
) -> str:
    """
    Execute a read-only call on a smart contract.

    This is useful for:
    - Fetching pool reserves,
    - Checking allowance,
    - Reading config/state vars.

    Arguments:
    - address (str): Contract address.
    - chain (str): Chain identifier.
    - function_signature (str): e.g. "balanceOf(address)(uint256)"
      or "getReserves()(uint112,uint112,uint32)"
    - args (list[Any], optional): Arguments to the function in order.

    Returns:
    - Decoded return values (or raw hex if decoding failed).
    """
    params: Dict[str, Any] = {
        "address": address,
        "chain": chain,
        "function_signature": function_signature,
        "args": args or [],
    }
    try:
        raw = await call_blockscout_mcp("read_contract", params)
    except Exception as e:
        return f"Error reading contract {address} on {chain}: {e}"

    return safe_json_preview(raw)


# -------------------------------------------------------------------
# TOOL: direct_api_call
# Escape hatch for advanced / raw access to curated Blockscout REST paths.
# You can use this when you know exactly which REST endpoint you want.
# -------------------------------------------------------------------
@mcp.tool()
async def direct_api_call(
    path: str,
    query: Optional[Dict[str, Any]] = None,
    chain: Optional[str] = None,
) -> str:
    """
    Low-level escape hatch: call a curated raw Blockscout API path directly.

    ONLY use this if higher-level tools are not sufficient.

    Arguments:
    - path (str): Curated REST path or identifier known by the Blockscout MCP.
    - query (dict, optional): Extra query params.
    - chain (str, optional): Chain identifier, if required by that path.

    Returns:
    - Raw API response (truncated for safety).
    """
    params: Dict[str, Any] = {
        "path": path,
    }
    if query:
        params["query"] = query
    if chain:
        params["chain"] = chain

    try:
        raw = await call_blockscout_mcp("direct_api_call", params)
    except Exception as e:
        return f"Error calling direct_api_call on {path}: {e}"

    return safe_json_preview(raw)


# -------------------------------------------------------------------
# LOCAL DEBUG ENTRYPOINT
# When you run `python server.py` locally (not in Agentverse),
# this lets FastMCP serve over stdio so you can poke it with an MCP host.
# In Agentverse, you'll wrap this mcp with MCPServerAdapter in a separate
# file (agent entrypoint) exactly like in the Fetch.ai docs.
# -------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run(transport="stdio")

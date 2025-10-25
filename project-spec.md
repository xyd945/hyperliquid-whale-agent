# Hyperliquid Whale Agent – Simplified MVP Project Spec

## 0. Goal / One-liner
Build a real-time **Hyperliquid Whale Watcher Agent** that:
1. Detects large bridge deposits (“whale deposits”) into Hyperliquid using Blockscout MCP.
2. Immediately queries Hyperliquid APIs to fetch that wallet’s trading exposure, leverage, and liquidation info.
3. Exposes this intelligence through:
   - An **Agentverse agent** that users can query.
   - A **Vercel web UI** connected through the **ASI:ONE API**, allowing users to ask “Which whales just made big moves?”

No database, no persistence — everything happens live and statelessly.

---

## 1. High-level Architecture

```text
[User]
   │ natural language question
   ▼
[Vercel Frontend]
   │ calls ASI:ONE API
   ▼
[ASI:ONE LLM]
   │ tool-calls our Agentverse Agent
   ▼
[Agentverse Agent]
   │ uses two live services:
   │   1) Blockscout MCP (detect whales)
   │   2) Hyperliquid API (enrich whales)
   ▼
[LLM summarizes → sends back to user]
```

### Key Components
1. **Whale Detector (stateless)**
   - Uses Blockscout MCP to scan the Hyperliquid bridge contract for recent large deposits.https://mcp.blockscout.com/
   - Decodes per-user deposits using verified ABI:  
     https://arbitrum.blockscout.com/address/0x2Df1c51E09aECF9cacB7bc98cB1742757f163dF7?tab=contract_abi
   - Returns list of whales: `{wallet, amount, token, txHash, timestamp}`.

2. **Hyperliquid Insights (stateless)**
   - For each wallet, call Hyperliquid `info` API:
     - `clearinghouseState` → current positions and leverage.
     - `userFills` → recent trade actions.
   - Combine into quick summary: top coin, side, notional, liqPx.

3. **Agentverse Agent**
   - Tools:
     - `getRecentWhales(thresholdUsd, lookbackMinutes)` → queries Blockscout MCP directly.
     - `enrichWallet(address)` → calls Hyperliquid `info` API.
   - Logic:
     - Parse user intent → detect whales → enrich with positions → summarize results.

4. **Frontend (Vercel)**
   - Minimal chat-style UI built with Next.js.
   - Calls ASI:ONE API with user prompt.
   - Displays streamed model responses.

---

## 2. Data Flow (MVP)

### Step 1. Whale Detection
1. Query Blockscout MCP for transactions sent to Hyperliquid bridge contract (`0x2Df1c51E09aECF9cacB7bc98cB1742757f163dF7`).
2. Decode deposit events to extract `{user, amount, token}` using the contract ABI.
3. Convert to USD equivalent (assuming USDC = 1:1).
4. Filter: `amountUsd >= ALERT_THRESHOLD` (e.g. 9,999,999 USD).
5. Return top whale list to the agent.

### Step 2. Whale Enrichment
For each whale wallet:
1. Query Hyperliquid API → `clearinghouseState` and `userFills`.
2. Return structured JSON with wallet’s exposure and recent trades.

Example response:
```json
{
  "wallet": "0x1234...abcd",
  "positions": [
    {
      "coin": "SOL",
      "side": "long",
      "notionalUsd": 3200000,
      "avgEntry": 145.2,
      "liqPx": 131.4
    }
  ],
  "recentFills": [
    {"coin": "SOL", "action": "buy", "notionalUsd": 1200000, "price": 145.7}
  ]
}
```

### Step 3. Agent Output
Agent composes human-readable answer, e.g.:
> “A whale 0x1234...abcd deposited $500k and opened a 3.2M SOL long at $145.2, liq at $131.4.”

---

## 3. Components & Responsibilities

### 3.1 Agentverse Agent
- Name: `hyperliquid-whale-watcher`
- Tools:
  - `getRecentWhales(thresholdUsd:number, lookbackMinutes:number)` — uses Blockscout MCP to query deposit logs.
  - `enrichWallet(address:string)` — fetches wallet exposure using Hyperliquid `info` API.
- Reasoning:
  - Parse intent (“Any new whales long SOL today?”).
  - Call both tools and filter for relevant positions.
  - Summarize into concise message.

### 3.2 Frontend (Vercel)
- Simple chat UI with:
  - Input → calls `/api/chat`.
  - Backend function → calls ASI:ONE API.
  - Streamed LLM output display.
- Styling: Tailwind + shadcn/ui.
- Disclaimer footer: “Research use only, not financial advice.”

---

## 4. Config / Env

- `BRIDGE_CONTRACT_ADDRESS` = `0x2Df1c51E09aECF9cacB7bc98cB1742757f163dF7`
- `BLOCKSCOUT_BASE_URL` = e.g. `https://arbitrum.blockscout.com`
- `ALERT_THRESHOLD_USD` = 9,999,999
- `LOOKBACK_MINUTES_DEFAULT` = 15
- `HL_INFO_ENDPOINT` = `https://api.hyperliquid.xyz/info`
- `ASI_ONE_API_KEY` = ASI:ONE API key for the Vercel edge function

No database or persistence layer required.

---

## 5. Developer Checklist (Hackathon Scope)

### Core Logic
- [ ] Implement Blockscout MCP call to scan bridge txs (last N minutes).
- [ ] Decode logs with bridge ABI → extract wallet + amount.
- [ ] Filter by threshold.
- [ ] For each whale, call Hyperliquid API for `clearinghouseState` and `userFills`.
- [ ] Merge and format for agent output.

### Agentverse
- [ ] Register `hyperliquid-whale-watcher`.
- [ ] Add tool schemas for `getRecentWhales` + `enrichWallet`.
- [ ] Validate live API calls work from agent runtime.

### Frontend
- [ ] Simple Next.js + Tailwind chat UI.
- [ ] Connect to ASI:ONE endpoint.
- [ ] Deploy to Vercel.

---

## 6. TL;DR
For the hackathon:
- **No DB**, **no cron jobs** — everything stateless.
- One request = one live scan of bridge + Hyperliquid APIs.
- Focus on end-to-end demo:
  - User asks → agent finds whales → shows positions.

This makes setup extremely fast and demo-ready within one day.

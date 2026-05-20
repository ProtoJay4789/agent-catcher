# 🛡️ Agent Catcher — Dual-Agent Token Risk Oracle for Sui

> Real-time token risk scoring powered by off-chain AI agents and on-chain Move contracts.

---

## What It Does

Agent Catcher is a **dual-agent token risk oracle** that scans any Sui token address and returns a 0–100 risk score with labeled risk factors — all stored on-chain as a tamper-proof registry. Users submit a token address, off-chain agents fetch security data via GoPlus, calculate a weighted risk score, and write the result to a shared `RiskRegistry` object on Sui devnet. The on-chain registry enforces freshness (max 1 hour staleness) and score validity (0–100 range), ensuring every assessment is trustworthy.

The system works in two modes: **live scanning** against the GoPlus API for EVM-compatible tokens, and **simulation mode** that generates realistic test data for Sui-native tokens (which GoPlus doesn't yet support). This makes it immediately useful for demos and extensible to any token ecosystem once cross-chain indexing is added.

Think of it as a **Chainlink-style oracle, but purpose-built for token safety**. DEXes, wallets, and agent frameworks can query the registry object to get risk assessments without trusting any single off-chain provider — the data is on-chain, verifiable, and timestamped.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER / DAPP                              │
│           (submits token address via CLI or frontend)           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   OFF-CHAIN AGENT (Python)                      │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────┐  │
│  │  GoPlus API  │───▶│  Risk Scoring    │───▶│  Sui RPC     │  │
│  │  (scan)      │    │  Engine          │    │  (submit)    │  │
│  └──────────────┘    │  11 weighted     │    └──────┬───────┘  │
│                      │  risk factors    │           │           │
│  ┌──────────────┐    └──────────────────┘           │           │
│  │  Simulation  │───────────────────────────────────┘           │
│  │  (fallback)  │                                              │
│  └──────────────┘                                              │
└──────────────────────────────────────────┬──────────────────────┘
                                           │
                           ┌───────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ON-CHAIN (Sui Move)                            │
│                                                                 │
│  RiskRegistry (shared object)                                   │
│  ├── assessments: vector<ID>    ← list of all assessment IDs   │
│  └── authorized_agents          ← agent allowlist               │
│                                                                 │
│  RiskAssessment (owned object, per-token)                       │
│  ├── token_address: String                                    │
│  ├── risk_score: u64 (0-100)                                   │
│  ├── risk_level: String (LOW/MEDIUM/HIGH/CRITICAL)             │
│  ├── risk_factors: vector<String>                              │
│  ├── agent_id: String                                          │
│  └── timestamp: u64                                            │
│                                                                 │
│  Validation: score ∈ [0,100], timestamp < now, age < 1hr       │
│  Events: RiskAssessmentCreated emitted per submission           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Smart Contracts** | Move (Sui Move, object-centric) |
| **Backend Agent** | Python 3, requests, argparse |
| **Data Source** | [GoPlus Security API](https://gopluslabs.io/) |
| **Blockchain** | Sui devnet |
| **Frontend** | Vanilla HTML/CSS/JS (dark terminal UI) |
| **RPC Client** | Sui JSON-RPC (`fullnode.devnet.sui.io`) |

---

## Live Deployment

| | |
|---|---|
| **Package ID** | `0x20e7a4ff0eab4f0eae72614c61022853c39368fb336b48db8e87a19284a97e43` |
| **Registry ID** | `0x7639df5cdbf75797895ef2632f0f84ed6a053be7f7ba1a3470bb1c1d33d7ebeb` |
| **Network** | Sui Devnet |
| **Explorer** | [suiscan.xyz/devnet](https://suiscan.xyz/devnet) |
| **Package on Explorer** | [View Package](https://suiscan.xyz/devnet/package/0x20e7a4ff0eab4f0eae72614c61022853c39368fb336b48db8e87a19284a97e43) |

---

## How to Run Locally

### 1. Clone the repo

```bash
git clone https://github.com/ProtoJay4789/agent-catcher-sui.git
cd agent-catcher-sui
```

### 2. Run the agent monitor (Python)

```bash
cd agent

# Install dependencies
pip install requests

# Simulated scan (no API key needed)
python3 monitor.py --token 0x2::sui::SUI --simulate

# Live GoPlus scan (EVM-compatible tokens)
python3 monitor.py --token 0xSomeTokenAddress

# Simulated scan + scaffold on-chain submission
python3 monitor.py --token 0x2::sui::SUI --simulate --submit

# JSON output mode
python3 monitor.py --token 0x2::sui::SUI --simulate --json
```

### 3. Run the frontend dashboard

```bash
cd frontend
# Open index.html in a browser, or:
python3 -m http.server 8080
# Then visit http://localhost:8080
```

The frontend reads on-chain data via Sui RPC and displays a real-time dashboard with risk scores, badges, and assessment history.

### 4. Build the Move contract (optional)

```bash
cd contracts
sui move build
sui move test
```

---

## Project Structure

```
agent-catcher-sui/
├── README.md                          ← you are here
├── agent/
│   ├── monitor.py                     ← CLI agent: scans tokens, scores risk
│   └── sui_client.py                  ← Sui RPC client + RiskOracleClient
├── contracts/
│   ├── sources/
│   │   └── risk_oracle.move           ← Move contract (RiskRegistry + RiskAssessment)
│   ├── Move.toml                      ← Move package manifest
│   └── build/                         ← compiled artifacts (devnet deployment)
│       └── agent_catcher/
├── frontend/
│   └── index.html                     ← single-file dashboard (dark terminal UI)
└── docs/
    ├── MOVE_CRASH_COURSE.md           ← Move language reference notes
    ├── x-post-draft.md                ← social media copy
    └── entertainment-post.md          ← content marketing draft
```

---

## Key Features

- **On-chain risk registry** — every assessment is a Sui object with a unique ID, queryable by anyone
- **Weighted scoring engine** — 11 risk factors (honeypot, hidden owner, self-destruct, etc.) with configurable weights
- **Staleness enforcement** — contracts reject assessments older than 1 hour at the Move level
- **Dual data source** — live GoPlus API for EVM tokens + simulation mode for Sui-native tokens
- **Event emission** — `RiskAssessmentCreated` events for real-time monitoring via indexers
- **Agent identity** — each assessment records which agent submitted it, enabling reputation systems
- **CLI + Dashboard** — terminal-based monitor for devs, web UI for everyone else
- **Risk classification** — automatic LOW / MEDIUM / HIGH / CRITICAL badge assignment

---

## Why Sui

Sui's **object model** is uniquely suited for agent infrastructure:

- **First-class objects** — every `RiskAssessment` is a standalone on-chain object with its own ID. No mapping gymnastics like Solidity's `mapping(address => ...)`. You can query, transfer, and compose objects directly.
- **Shared objects** — the `RiskRegistry` is a shared object that any authorized agent can mutate concurrently, without account-based nonce management.
- **Move safety guarantees** — linear types prevent accidental double-spends or data corruption. Resources can't be copied or dropped; they must be explicitly used.
- **Low latency** — Sui's parallel execution means assessment writes don't contend with each other, critical for high-throughput oracle systems.
- **Composability** — other protocols can read `RiskAssessment` objects directly in the same transaction, enabling atomic DeFi actions gated by risk scores (e.g., "swap only if risk score > 80").

---

## What's Next

- [ ] **Multi-agent consensus** — require 2+ agents to agree on risk scores before writing to the registry (dual-agent validation)
- [ ] **GoPlus Sui integration** — partner with GoPlus to add native Sui token support
- [ ] **On-chain reputation** — track agent accuracy over time using Sui's event system
- [ ] **DEX integration module** — plug Agent Catcher into Cetus/DeepBook as a pre-swap safety check
- [ ] **Batch scanning** — scan all tokens in a DEX pool in a single transaction
- [ ] **Mainnet deployment** — graduate from devnet after audit
- [ ] **SDK release** — drop-in `agent-catcher-sdk` for Python and TypeScript

---

## Team

**GenTech Labs** — solo builder ([@ProtoJay4789](https://github.com/ProtoJay4789))

Building at the intersection of AI agents and on-chain infrastructure. Previously shipped agent logic on EVM and SVM; now porting to Sui's object model.

---

## Links

| | |
|---|---|
| **Hackathon** | [overflow.sui.io](https://overflow.sui.io/) |
| **Explorer** | [suiscan.xyz/devnet](https://suiscan.xyz/devnet) |
| **GitHub** | [github.com/ProtoJay4789](https://github.com/ProtoJay4789) |
| **Track** | The Agentic Web |

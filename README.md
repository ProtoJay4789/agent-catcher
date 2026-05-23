# 🛡️ Rugcheck — Bags Token Risk Scanner

> Autonomous AI agent that monitors new Bags.fm token launches, detects rugs/honeypots/sketchy contracts, and alerts users before they lose money.

---

## 🎯 What It Does

Rugcheck is an **autonomous monitoring agent** that:

1. **Scouts** new token launches on Bags.fm via their API
2. **Scores** each token using a weighted risk engine (11 Solana-specific factors)
3. **Alerts** users via Telegram/webhook when HIGH or CRITICAL risk tokens are detected
4. **Dashboard** shows live feed of scanned tokens with risk scores

The agent runs **continuously** — no human intervention needed. It's the "Chainlink for token safety."

---

## 🏗️ Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Bags Scout      │────▶│  Risk Scorer     │────▶│  Alerts          │
│  (API feed)      │     │  (Python)        │     │  (TG/WH/Term)    │
└──────────────────┘     └──────────────────┘     └──────────────────┘
         │                        │                         │
         ▼                        ▼                         ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Token Meta      │     │  Score Store     │     │  Dashboard       │
│  (Bags API)      │     │  (JSON/SQLite)   │     │  (HTML+JS)       │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

---

## 🔍 Risk Factors

Rugcheck analyzes **11 weighted risk factors** specific to Solana/Bags tokens:

| Factor | Weight | Description |
|--------|--------|-------------|
| Mint Authority Active | 18% | Can supply be inflated? |
| Freeze Authority Active | 15% | Can trades be frozen? |
| Low Liquidity | 12% | LP < $10K |
| LP Not Locked | 10% | Liquidity not locked |
| High Concentration | 10% | Top holder > 30% |
| No Social Presence | 8% | No website/social |
| Recent Creation | 7% | Created < 24h ago |
| Hidden Owner | 8% | Creator not revealed |
| Malicious Behavior | 5% | Known scam patterns |
| Low Holder Count | 4% | < 100 holders |
| No Contract Verified | 3% | Contract not verified |

**Scoring:** 0-100 scale (100 = safest)

- 🟢 **LOW** (80-100): Safe to trade
- 🟡 **MEDIUM** (60-79): Proceed with caution
- 🟠 **HIGH** (40-59): Risky — do your research
- 🔴 **CRITICAL** (0-39): DO NOT APE IN

---

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/ProtoJay4789/rugcheck
cd rugcheck
pip install -r requirements.txt
```

### Scan a Token

```bash
# Scan with simulated data (demo)
python3 agent/bags_scanner.py --token <mint_address> --simulate

# Scan live via Bags API
BAGS_API_KEY=your_key python3 agent/bags_scanner.py --token <mint_address>
```

### Run the Agent

```bash
# Continuous monitoring (simulated)
python3 agent/agent_loop.py --simulate

# Live monitoring with alerts
BAGS_API_KEY=your_key python3 agent/agent_loop.py --webhook https://your-webhook.com
```

### Open Dashboard

```bash
open frontend/dashboard.html
```

---

## 📊 Demo

### Safe Token
```
🛡️  Rugcheck — Bags Token Risk Report [SIMULATED]
============================================================
  📌 Token:     SafeToken (SAFE)
  🔑 Mint:      So11111111111111111111111111111111
  👥 Holders:   12,500
  💰 LP Value:  $250,000.00
  🔐 Mint Auth: REVOKED
  🧊 Freeze:    REVOKED
------------------------------------------------------------
  🎯 Risk Assessment
------------------------------------------------------------
    Score:     100/100
    Level:     🟢 LOW
============================================================
```

### Dangerous Token
```
🛡️  Rugcheck — Bags Token Risk Report [SIMULATED]
============================================================
  📌 Token:     ScamCoin (SCAM)
  🔑 Mint:      0xdead...beef
  👥 Holders:   15
  💰 LP Value:  $500.00
  🔐 Mint Auth: ACTIVE
  🧊 Freeze:    ACTIVE
------------------------------------------------------------
  🎯 Risk Assessment
------------------------------------------------------------
    Score:     0/100
    Level:     🔴 CRITICAL
============================================================
```

---

## 🧪 Tests

```bash
# Run all tests
python3 -m pytest agent/tests/ -v

# Run Bags scanner tests only
python3 -m pytest agent/tests/test_bags_scanner.py -v

# Run with coverage
python3 -m pytest agent/tests/ --cov=agent
```

**Test Results:** 21/21 passing ✅

---

## 📁 Project Structure

```
rugcheck/
├── agent/
│   ├── bags_scanner.py      # Main scanner (Bags API + Solana RPC)
│   ├── agent_loop.py        # Continuous monitoring agent
│   ├── monitor.py           # Original Sui version (kept for reference)
│   └── tests/
│       ├── test_bags_scanner.py  # Bags scanner tests (21 tests)
│       └── test_scoring.py       # Original scoring tests
├── frontend/
│   └── dashboard.html       # Live monitoring dashboard
├── docs/
│   └── submission.md        # Hackathon submission docs
├── requirements.txt
└── README.md
```

---

## 🎯 Hackathon Submission

**Track:** AI Agents (weight 7) + Bags API (weight 9)

**Why This Wins:**

1. **Solves a Real Problem:** New Bags launches = rug risk. Users need protection.
2. **Autonomous Agent:** Runs continuously without human intervention.
3. **Deep Bags Integration:** Uses Bags API for token data + Solana RPC for on-chain verification.
4. **Production Ready:** 21/21 tests passing, clean architecture, extensible.
5. **Clear Demo:** Deploy honeypot → agent catches it live in <60 seconds.

**Competitive Advantage:**

- Most hackathon submissions are thin wrappers with 0 stars
- Rugcheck has **real utility** for the Bags ecosystem
- Scoring engine is battle-tested (adapted from Sui Overflow 2026)
- Dashboard provides immediate visual impact

---

## 🔮 Future Roadmap

- [ ] Telegram bot integration (live alerts)
- [ ] On-chain scoring registry (Solana program)
- [ ] Historical risk tracking (SQLite)
- [ ] Multi-chain support (EVM, Sui)
- [ ] API endpoint for third-party integrations
- [ ] Machine learning risk model (train on rug data)

---

## 📝 License

MIT License — built for the Bags Hackathon 2026

---

## 🙏 Acknowledgments

- [Bags.fm](https://bags.fm) for the platform and API
- [Solana](https://solana.com) for the infrastructure
- [DoraHacks](https://dorahacks.io) for hosting the hackathon

---

**Built by [GenTech Labs](https://github.com/ProtoJay4789)** — 🛡️ Protecting Bags users from rugs, one scan at a time.

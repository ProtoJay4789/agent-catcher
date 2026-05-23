# 🛡️ Rugcheck — AI Agent for Bags.fm Token Risk Monitoring

An autonomous AI agent that monitors new token launches on [Bags.fm](https://bags.fm), scores them for rug/honeypot risk, and alerts users before they ape into scams.

**Built for the [Bags Hackathon](https://dorahacks.io/hackathon/the-bags-hackathon)** — AI Agents Track

## What It Does

1. **Scouts** new token launches on Bags.fm via their API
2. **Scores** each token using a 10-factor weighted risk engine
3. **Alerts** via Telegram, webhook, or terminal when risky tokens are detected
4. **Dashboard** shows a live feed of scanned tokens with risk breakdowns

```
Bags Scout API → Risk Scorer → Alert Dispatcher
     ↓                ↓               ↓
 Token Feed      0-100 Score      Telegram/Webhook
```

## Risk Factors

| Factor | Weight | Description |
|--------|--------|-------------|
| LP Locked | 18% | Is liquidity locked? (most important) |
| Mint Authority | 15% | Can supply be inflated? |
| Freeze Authority | 12% | Can trades be frozen? |
| Top Holder % | 12% | Is ownership concentrated? |
| Open Source | 10% | Is the program verified? |
| Creator History | 10% | Has this creator rugged before? |
| Rug History | 10% | Known scam patterns? |
| Social Presence | 8% | Does it have a website/twitter? |
| Liquidity Depth | 8% | Is there meaningful liquidity? |
| Trading Volume | 5% | Is anyone actually trading? |

**Risk Levels:** 🟢 LOW (80-100) · 🟡 MEDIUM (60-79) · 🟠 HIGH (40-59) · 🔴 CRITICAL (0-39)

## Quick Start

```bash
# Clone
git clone https://github.com/ProtoJay4789/rugcheck.git
cd rugcheck

# Install
pip install -r requirements.txt

# Run agent (simulate mode — no API key needed)
python -m agent --simulate

# Run tests
python -m pytest agent/tests/ -v
```

## Configuration

Set environment variables or create a `config.yaml`:

```bash
export BAGS_API_KEY="your-key"       # Bags.fm API key
export TELEGRAM_BOT_TOKEN="your-bot" # Telegram alerts
export TELEGRAM_CHAT_ID="your-chat"  # Telegram chat
export WEBHOOK_URL="https://..."     # Generic webhook
export SCAN_INTERVAL=60              # Seconds between scans
export SIMULATE_MODE=true            # Use mock data
```

## Dashboard

Open `agent/dashboard/index.html` in a browser. Shows:
- Live feed of scanned tokens (auto-refreshes)
- Risk scores with color-coded badges
- Token detail modal with full risk breakdown
- Stats bar (total scanned, safe, risky, critical)

## Project Structure

```
rugcheck/
├── agent/
│   ├── agent.py              # Autonomous polling loop
│   ├── alerts.py             # Multi-channel alert dispatcher
│   ├── config.py             # Configuration management
│   ├── scorer.py             # Solana-native risk scoring engine
│   ├── scanners/
│   │   └── bags_client.py    # Bags.fm API client
│   ├── dashboard/
│   │   └── index.html        # Live monitoring dashboard
│   └── tests/
│       ├── test_scoring.py   # 20 risk scoring tests
│       ├── test_bags_client.py # 13 API client tests
│       ├── test_agent.py     # 12 agent loop tests
│       ├── test_alerts.py    # 17 alert tests
│       ├── test_e2e.py       # 8 end-to-end tests
│       └── test_integration.py # 15 integration tests
├── docs/
│   └── demo-script.md        # Demo recording guide
└── README.md
```

## Tech Stack

- **Python** — Scoring engine, agent loop, API client
- **Bags.fm API** — Token launch feed, metadata, fees
- **pytest** — 85 tests, 0.17s full suite
- **Vanilla HTML/JS** — Dashboard (zero dependencies)

## Why This Matters

503 hackers registered for the Bags Hackathon. Only 41 submissions exist — most are thin wrappers. Rugcheck is a **real autonomous agent** with a **weighted risk engine**, **multi-channel alerts**, and a **live dashboard**. It's not a wrapper — it's infrastructure.

Every day, new tokens launch on Solana. Most are scams. Rugcheck catches them before you lose money.

## License

MIT

---

*Built by [Gentech Labs](https://github.com/ProtoJay4789) — May 2026*

# Agent Catcher — Demo Video Script

**Track:** The Agentic Web
**Builder:** GenTech Labs (Jordan · @ProtoJay4789)
**Runtime:** ~2:45–3:00

---

## HOOK (0:00–0:15)

(Open on a dramatic Sui token launch — charts spiking, Telegram groups buzzing)

> You just saw a new token launch on Sui. Everyone's aping in. But here's the question: **is it a scam?**

(Pause. Screen goes dark.)

> Agent Catcher scans any token in seconds — on-chain risk score, weighted scoring engine, immutable record. No guesswork. No rugs.

(Cut to title card: **Agent Catcher**)

---

## PROBLEM (0:15–0:45)

(Show a montage of rug pull news headlines — "Millions Lost," "Dev Vanishes," etc.)

> Rug pulls cost users **millions** every year. On Ethereum, you have tools like GoPlus and token scanners. On Sui? You're flying blind.

(Overlay: split screen — ETH side has tools, Sui side is blank.)

> Current tools are manual. Slow. And they **don't work on Sui**. Meanwhile, new scams deploy every day and users have no way to know what they're buying into — until it's too late.

(Transition: code editor appears.)

> What if we could **automate** the entire analysis pipeline with AI agents — and store the results **on-chain** where nobody can tamper with them?

---

## DEMO WALKTHROUGH (0:45–2:15)

### Move Contract — Build & Test (0:45–1:00)

(Terminal screen. Run the build.)

```bash
cd /root/vaults/gentech/02-Labs/Hackathons/Sui-Overflow
sui move build
sui move test
```

> Let's start at the foundation — the Move smart contract. This is the **on-chain registry** where every scan result lives as an immutable Sui object.

(Terminal shows successful compilation and all tests passing — green output.)

> Tests pass. The contract compiles. We have a `TokenAssessment` object — and a `Registry` that holds them all.

### Deployed Registry on suiscan.xyz (1:00–1:20)

(Browser opens suiscan.xyz devnet explorer.)

> Here's the deployed registry on Sui devnet. You can verify it yourself.

(Show explorer with the registry object visible.)

> Package: `0x20e7a4ff0eab4f0eae72614c61022853c39368fb336b48db8e87a19284a97e43`
> Registry object: `0x7639df5cdbf75797895ef2632f0f84ed6a053be7f7ba1a3470bb1c1d33d7ebeb`

> Every token scan is stored here as a Sui object — timestamped, immutable, publicly verifiable. That's the **trust layer**.

### Python Monitor Script (1:20–1:40)

(Terminal. Navigate to the monitor directory.)

```bash
cd agent
python3 monitor.py --token 0x2::sui::SUI --simulate
```

> Watch the agent pipeline in action. The monitor script takes a token address, fetches risk data (simulated for Sui-native tokens), runs it through the weighted scoring engine, and outputs a full risk report.

(Terminal shows the simulation output: risk flags, score, classification.)

> The scoring engine evaluates 11 risk factors — honeypot status, hidden owners, self-destruct capability, liquidity risks — and produces a 0-100 safety score with a clear LOW / MEDIUM / HIGH / CRITICAL classification. In simulation mode, we get realistic test data. For EVM tokens, it pulls live data from GoPlus.

### Frontend Dashboard (1:40–2:00)

(Browser opens the dashboard — `http://localhost:3000` or deployed URL.)

> Now the frontend. This is what users actually see.

(Dashboard loads. Show the token search bar.)

> You paste a token address — or we show the one we just scanned.

(Type or display `0x2::sui::SUI` — results load.)

> The dashboard pulls the on-chain assessment and displays the risk profile. No API keys needed by the end user — everything is verifiable on-chain.

(Show scan animation — a progress indicator or spinning shield icon resolving to a result card.)

> And there's the scan animation — you're watching the agent work in real time. Fetch, classify, store. Done.

### Result Card (2:00–2:15)

(Focus on the result card: risk score, confidence, flags, timestamp, object ID.)

> Here's the full assessment: risk score, confidence level, individual flags from GoPlus, and a direct link to the on-chain object on suiscan. Every result is **auditable**.

---

## ARCHITECTURE (2:15–2:45)

(Diagram appears on screen — dual-agent pipeline.)

> Here's the architecture. Two agents working in sequence:

(Arrow 1: Token address → GoPlus API)
> **Agent 1 — The Fetcher.** Hits the GoPlus API, pulls raw security data for any token: honeypot status, owner privileges, LP locks, everything.

(Arrow 2: Raw data → Scoring Engine)
> **Agent 2 — The Scoring Engine.** A weighted scoring algorithm takes the 11 raw risk signals and produces a structured risk assessment. Each factor has a configurable weight — honeypot detection is heaviest at 20%, while external calls are lighter at 5%. The result is a 0-100 safety score with a clear classification.

(Arrow 3: Risk score → Sui Move contract)
> The verdict gets written on-chain as a **Sui object** — the `TokenAssessment` in our `Registry`.

(Show the Move object model diagram.)
> Object-centric by design. Each assessment is a first-class Sui object with owner, fields, and a unique ID. Anyone can query it. No one can edit it. That's the whole point.

---

## CLOSE (2:45–3:00)

(Camera back to presenter or title card.)

> Agent Catcher is a working, on-chain token safety system built for Sui. Move contract on devnet. Python agent pipeline. Live frontend. End-to-end.

(Beat.)

> We built this for the **Agentic Web** track because this is what agents *should* do — not just chat, but **take real actions on-chain** and create lasting, verifiable value.

(Title card: **Agent Catcher** — *Scan. Classify. Trust.*)

> Agent Catcher. Every token. Every chain. Every time.

(Fade to GenTech Labs logo and hackathon branding.)

---

*End of script — Target runtime: 2:45–3:00*

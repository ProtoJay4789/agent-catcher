# X Post — Draft for @ProtoJay4789

## Option A: Thread (Recommended)

**Post 1 (Main):**
🔵 Porting our hackathon agents to @SuiNetwork for Overflow 2026

$500K+ in prizes. Tracks: Agentic Web + DeFi & Payments.

We ported Agent Catcher from Solidity to Move in one afternoon. Here's what we noticed 🧵

**Post 2:**
1/ Objects > Accounts

Everything in Move is an object with a unique ID. No more mapping(address => uint256).

Your token, your contract state, your user profiles — all objects. Composability is built-in.

**Post 3:**
2/ Linear Types = Security by Default

Move's ability system (key, store, copy, drop) enforces ownership at the type level.

You literally CAN'T copy a token or drop an asset without explicit permission. Reentrancy? Impossible.

**Post 4:**
3/ Testing Is Built-In

#[test] attribute + test_scenario module = tests in the same file as your contract.

No separate test framework. We wrote 7 tests in 20 minutes. Solidity test suites take hours.

**Post 5:**
4/ Shared Objects Replace Proxy Patterns

In Solidity, multi-user state needs a proxy contract.

In Move: transfer::share_object() makes any object accessible by anyone. Our RiskRegistry is shared — agents submit, users query, no proxies.

**Post 6:**
5/ Why Hack on Sui?

• Object model fits agent infrastructure perfectly
• Move learnable in 2-3 days for Solidity/Rust devs
• Ecosystem growing but under-saturated = first-mover advantage
• $500K+ across Agentic Web + DeFi tracks

**Post 7 (CTA):**
Sui Overflow 2026 runs May → August. Registration open now.

If you're building AI agents or DeFi, this is the hackathon.

🔗 overflow.sui.io

#SuiOverflow #MoveLang #Web3 #DeFi #AIAgents

---

## Option B: Single Post (Shorter)

🔵 Just ported our agent contracts to @SuiNetwork for Overflow 2026

What I noticed:
→ Objects > Accounts (composability built-in)
→ Linear types prevent double-spend by default
→ Tests in the same file as contracts
→ Shared objects replace proxy patterns
→ Move is learnable in 2-3 days

$500K+ prizes. May → August. Registration open.

overflow.sui.io

#SuiOverflow #MoveLang #AIAgents

# 🔵 Sui Overflow 2026 — Why We're Porting

**Posted to:** Entertainment
**Context:** Hackathon brainstorm, porting existing agent contracts to Sui Move

---

## What I Noticed Porting to Sui Move

We just scaffolded our first Sui Overflow 2026 project — porting Agent Catcher from Solidity/EVM to Move. Here's what jumped out:

**1. Objects > Accounts**
Everything in Move is an object with a unique ID. No more `mapping(address => uint256)`. Your token, your contract state, even your user profiles — all objects. This means composability is built-in. Objects can own other objects, pass through functions, and transfer between owners natively.

**2. Linear Types Prevent Double-Spend by Default**
Move's ability system (`key`, `store`, `copy`, `drop`) enforces ownership rules at the type level. You literally can't copy a token or drop an asset without explicit permission. Solidity devs spend months fighting reentrancy — Move makes it impossible.

**3. Strings Are Just Bytes**
No more `abi.encodePacked(keccak256(...))`. Strings in Move are `vector<u8>` with a UTF-8 wrapper. It's simpler but requires explicit conversion at entry points. Trade-off: less gas-efficient for on-chain string ops, but way clearer for security audits.

**4. Events Are First-Class**
Every contract emission is a typed struct with `has copy, drop`. No more event signature hashes or log parsing. Sui Explorer shows them natively. Our risk oracle assessments will be queryable on-chain from day one.

**5. Testing Is Built-In**
The `#[test]` attribute + `test_scenario` module means you write tests in the same file as your contract. No separate test framework, no fork testing needed for unit tests. We wrote 7 tests in 20 minutes.

**6. Shared Objects = Shared State Without Proxies**
In Solidity, you need a proxy pattern or shared contract for multi-user state. In Move, `transfer::share_object()` makes any object accessible by anyone. Our RiskRegistry is a shared object — agents submit assessments, users query them, all without proxy contracts.

## Why Sui for Hackathons?

- **$500K+ prize pool** (May → August 2026)
- **Tracks match our stack:** Agentic Web (AI agents) + DeFi & Payments
- **Object model is perfect for agent infrastructure** — agents as objects, assessments as objects, portfolios as objects
- **Move is learnable in 2-3 days** for Solidity/Rust devs
- **Growing ecosystem** but under-saturated compared to Ethereum/Solana — first-mover advantage

## What We're Building

Agent Catcher — a dual-agent token risk oracle. Two off-chain agents fetch token data (GoPlus API + LLM classification), post risk scores on-chain. Users query any token's risk level before aping in.

Ported from Solidity in one afternoon. Move contracts are cleaner, shorter, and more secure by default.

**Sui Overflow 2026** | $500K+ | May → August | overflow.sui.io

---

*GenTech Labs — building across chains.*

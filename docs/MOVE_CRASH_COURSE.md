# Sui Move Crash Course — 2-Hour Guide for Solidity/Rust Devs

> Goal: Learn enough Move to port Agent Catcher from Solidity to Sui.

## Key Differences: Solidity → Sui Move

### 1. **Objects, Not Accounts**
```solidity
// Solidity: contract state lives in storage slots
mapping(address => uint256) balances;
```

```move
// Sui Move: everything is an object with a unique ID
struct Token has key, store {
    id: UID,
    balance: u64,
    owner: address,
}
```

### 2. **Abilities (Type System)**
Move uses "abilities" to control object behavior:
- `key` — can be stored on-chain as an object
- `store` — can be stored inside other objects
- `copy` — can be cloned (usually NOT for assets)
- `drop` — can be deleted

```move
// Fungible token (like ERC-20)
struct Coin has key, store {
    id: UID,
    value: u64,
}

// NFT (unique, non-copyable)
struct NFT has key, drop {
    id: UID,
    name: vector<u8>,
}
```

### 3. **No `selfdestruct`**
Objects live forever unless explicitly deleted with `transfer::delete`. This is by design — Sui is append-only.

### 4. **Entry Functions**
Explicit public entry points for transactions:

```move
module my_module::vault {
    public entry fun deposit(
        vault: &mut Vault,
        coin: Coin,
        ctx: &mut TxContext
    ) {
        transfer::public_transfer(coin, tx_context::sender(ctx));
        // ... business logic
    }
}
```

### 5. **Transfer Functions**
- `transfer::transfer(obj, recipient)` — private transfer
- `transfer::public_transfer(obj, recipient)` — public transfer (if obj has `store`)
- `transfer::share_object(obj)` — make shared (accessible by anyone)
- `transfer::freeze_object(obj)` — make immutable

## Solidity → Move Cheat Sheet

| Solidity | Sui Move |
|----------|----------|
| `mapping(address => uint256)` | `Table<address, u64>` or object fields |
| `uint256` | `u64` (or `u128` for big numbers) |
| `address` | `address` (same) |
| `require(condition, "msg")` | `assert!(condition, ERROR_CODE)` |
| `msg.sender` | `tx_context::sender(ctx)` |
| `block.timestamp` | `tx_context::epoch_timestamp_ms(ctx)` |
| `emit(Event)` | `event::emit(event)` |
| `contract` | `module` |
| `function` | `public fun` |
| `modifier` | Inline logic (no modifiers in Move) |

## Agent Catcher Porting Guide

### Original Solidity (Simplistic)
```solidity
contract RiskOracle {
    struct Assessment {
        string tokenAddress;
        uint256 riskScore;
        string riskLevel;
        uint256 timestamp;
    }
    
    mapping(bytes32 => Assessment) public assessments;
    
    function submitAssessment(
        string memory tokenAddress,
        uint256 riskScore,
        string memory riskLevel
    ) external onlyAgent {
        bytes32 id = keccak256(abi.encodePacked(tokenAddress, block.timestamp));
        assessments[id] = Assessment(tokenAddress, riskScore, riskLevel, block.timestamp);
    }
}
```

### Sui Move Version
```move
module agent_catcher::risk_oracle {
    use sui::object::{Self, UID};
    use sui::tx_context::{Self, TxContext};
    use sui::transfer;
    use std::string::{Self, String};
    
    struct RiskAssessment has key, store {
        id: UID,
        token_address: String,
        risk_score: u64,
        risk_level: String,
        timestamp: u64,
    }
    
    public entry fun submit_assessment(
        token_address: vector<u8>,
        risk_score: u64,
        risk_level: vector<u8>,
        ctx: &mut TxContext
    ) {
        let assessment = RiskAssessment {
            id: object::new(ctx),
            token_address: string::utf8(token_address),
            risk_score,
            risk_level: string::utf8(risk_level),
            timestamp: tx_context::epoch_timestamp_ms(ctx) / 1000,
        };
        
        transfer::public_transfer(assessment, tx_context::sender(ctx));
    }
}
```

**Key changes:**
- Strings are `vector<u8>` in entry functions, converted with `string::utf8()`
- Object ID auto-generated with `object::new(ctx)`
- Transfer to sender instead of storing in mapping
- `entry` keyword for public functions

## Testing in Move

```move
#[test]
fun test_submit_assessment() {
    let mut scenario = test_scenario::begin(@0xA);
    
    test_scenario::next_tx(&mut scenario, @0xA);
    {
        risk_oracle::submit_assessment(
            b"0x2::sui::SUI",  // token_address
            85,                // risk_score
            b"LOW",            // risk_level
            test_scenario::ctx(&mut scenario),
        );
    };
    
    // Verify result
    test_scenario::next_tx(&mut scenario, @0xA);
    {
        let assessment = test_scenario::take_from_sender<RiskAssessment>(&scenario);
        let (score, level, _) = risk_oracle::get_assessment(&assessment);
        assert!(score == 85, 0);
        assert!(level == string::utf8(b"LOW"), 1);
        test_scenario::return_to_sender(&scenario, assessment);
    };
    
    test_scenario::end(scenario);
}
```

## Quick Reference

### String Handling
```move
use std::string::{Self, String};

// vector<u8> → String
let s = string::utf8(b"hello");

// String → vector<u8>
let bytes = *string::bytes(&s);
```

### Object Creation
```move
use sui::object::{Self, UID};

let id = object::new(ctx);  // Creates new unique ID
let obj = MyObject { id, field: value };
```

### Error Handling
```move
const EUnauthorized: u64 = 0;
const EInvalidScore: u64 = 1;

assert!(condition, EUnauthorized);  // Aborts with error code if false
```

### Events
```move
use sui::event;

struct AssessmentCreated has copy, drop {
    id: ID,
    score: u64,
}

event::emit(AssessmentCreated { id: object::id(&obj), score: 85 });
```

## Resources

1. **Sui Move Intro Course:** https://github.com/sui-foundation/sui-move-intro-course
2. **The Move Book:** https://move-book.com/
3. **Sui Docs:** https://docs.sui.io/
4. **Move Playground:** https://play.sui.io/

## Next Steps

1. ✅ Read this guide (30 min)
2. 🔧 Install Sui CLI: `cargo install --locked sui`
3. 🎮 Try Move Playground: https://play.sui.io/
4. 📖 Complete Sui Move Intro Course (1-2 hours)
5. 🚀 Port Agent Catcher contract

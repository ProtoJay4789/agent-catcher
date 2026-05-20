/// Agent Catcher — Sui Overflow 2026
/// Dual-agent token risk oracle for Sui tokens
/// 
/// Agents fetch token data off-chain and store risk scores on-chain.
/// Users can query risk assessments for any Sui token.

module agent_catcher::risk_oracle {
    use sui::object::{Self, ID, UID};
    use sui::tx_context::{Self, TxContext};
    use sui::transfer;
    use sui::event;
    use std::string::{Self, String};

    // ====== Error Codes ======
    #[allow(unused_const)]
    const EUnauthorized: u64 = 0;
    const EStaleData: u64 = 1;
    const EInvalidScore: u64 = 2;

    // ====== Constants ======
    const MAX_STALENESS_SECS: u64 = 3600; // 1 hour
    const MIN_SCORE: u64 = 0;
    const MAX_SCORE: u64 = 100;

    // ====== Structs ======

    /// Risk assessment for a token
    public struct RiskAssessment has key, store {
        id: UID,
        token_address: String,       // Sui token type (e.g., "0x2::sui::SUI")
        risk_score: u64,             // 0-100 (0=risky, 100=safe)
        risk_level: String,          // "LOW", "MEDIUM", "HIGH", "CRITICAL"
        risk_factors: vector<String>, // List of detected risks
        agent_id: String,            // Which agent submitted this
        timestamp: u64,              // Epoch timestamp
    }

    /// Registry of all risk assessments
    public struct RiskRegistry has key, store {
        id: UID,
        assessments: vector<ID>,
        authorized_agents: vector<String>,
    }

    // ====== Events ======
    
    public struct RiskAssessmentCreated has copy, drop {
        assessment_id: ID,
        token_address: String,
        risk_score: u64,
        risk_level: String,
    }

    // ====== Public Functions ======

    /// Initialize the registry (call once)
    public fun init_registry(ctx: &mut TxContext) {
        let registry = RiskRegistry {
            id: object::new(ctx),
            assessments: vector[],
            authorized_agents: vector[],
        };
        transfer::share_object(registry);
    }

    /// Submit a risk assessment (agent only)
    #[allow(lint(self_transfer))]
    public fun submit_assessment(
        registry: &mut RiskRegistry,
        token_address: vector<u8>,
        risk_score: u64,
        risk_level: vector<u8>,
        risk_factors: vector<vector<u8>>,
        agent_id: vector<u8>,
        timestamp: u64,
        ctx: &mut TxContext
    ) {
        // Validate score range
        assert!(risk_score >= MIN_SCORE && risk_score <= MAX_SCORE, EInvalidScore);
        
        // Validate timestamp freshness
        let current_time = tx_context::epoch_timestamp_ms(ctx) / 1000;
        assert!(timestamp <= current_time, EStaleData);
        assert!(current_time - timestamp <= MAX_STALENESS_SECS, EStaleData);

        // Create risk_factors vector
        let mut factors: vector<String> = vector[];
        let mut i = 0;
        while (i < vector::length(&risk_factors)) {
            let factor_bytes = *vector::borrow(&risk_factors, i);
            vector::push_back(&mut factors, string::utf8(factor_bytes));
            i = i + 1;
        };

        // Create assessment object
        let assessment = RiskAssessment {
            id: object::new(ctx),
            token_address: string::utf8(token_address),
            risk_score,
            risk_level: string::utf8(risk_level),
            risk_factors: factors,
            agent_id: string::utf8(agent_id),
            timestamp,
        };

        let assessment_id = object::id(&assessment);
        
        // Add to registry
        vector::push_back(&mut registry.assessments, assessment_id);
        
        // Emit event
        event::emit(RiskAssessmentCreated {
            assessment_id,
            token_address: assessment.token_address,
            risk_score,
            risk_level: assessment.risk_level,
        });

        // Transfer assessment to sender
        transfer::public_transfer(assessment, tx_context::sender(ctx));
    }

    /// Query risk assessment by ID
    public fun get_assessment(assessment: &RiskAssessment): (u64, String, vector<String>) {
        (assessment.risk_score, assessment.risk_level, assessment.risk_factors)
    }

    /// Check if data is stale
    public fun is_stale(assessment: &RiskAssessment, current_time: u64): bool {
        current_time - assessment.timestamp > MAX_STALENESS_SECS
    }

    /// Get registry size
    public fun registry_size(registry: &RiskRegistry): u64 {
        vector::length(&registry.assessments)
    }

    // ====== Test Functions ======

    #[test_only]
    public fun init_for_testing(ctx: &mut TxContext) {
        init_registry(ctx);
    }

    #[test_only]
    public fun create_test_assessment(
        token_address: vector<u8>,
        risk_score: u64,
        risk_level: vector<u8>,
        ctx: &mut TxContext
    ): RiskAssessment {
        RiskAssessment {
            id: object::new(ctx),
            token_address: string::utf8(token_address),
            risk_score,
            risk_level: string::utf8(risk_level),
            risk_factors: vector[],
            agent_id: string::utf8(b"test"),
            timestamp: tx_context::epoch_timestamp_ms(ctx) / 1000,
        }
    }
}

#[test_only]
module agent_catcher::risk_oracle_tests {
    use agent_catcher::risk_oracle::{Self, RiskRegistry, RiskAssessment};
    use std::string;

    // ====== Tests ======

    #[test]
    fun test_registry_init() {
        let mut scenario = sui::test_scenario::begin(@0xA);
        {
            risk_oracle::init_for_testing(sui::test_scenario::ctx(&mut scenario));
        };
        sui::test_scenario::next_tx(&mut scenario, @0xA);
        {
            let registry = sui::test_scenario::take_shared<RiskRegistry>(&scenario);
            assert!(risk_oracle::registry_size(&registry) == 0, 0);
            sui::test_scenario::return_shared(registry);
        };
        sui::test_scenario::end(scenario);
    }

    #[test]
    fun test_submit_assessment() {
        let mut scenario = sui::test_scenario::begin(@0xA);
        {
            risk_oracle::init_for_testing(sui::test_scenario::ctx(&mut scenario));
        };
        sui::test_scenario::next_tx(&mut scenario, @0xA);
        {
            let mut registry = sui::test_scenario::take_shared<RiskRegistry>(&scenario);
            let ts = sui::tx_context::epoch_timestamp_ms(sui::test_scenario::ctx(&mut scenario)) / 1000;
            
            risk_oracle::submit_assessment(
                &mut registry,
                b"0x2::sui::SUI",
                85,
                b"LOW",
                vector[],
                b"agent_v1",
                ts,
                sui::test_scenario::ctx(&mut scenario),
            );
            
            assert!(risk_oracle::registry_size(&registry) == 1, 1);
            sui::test_scenario::return_shared(registry);
        };
        sui::test_scenario::end(scenario);
    }

    #[test]
    #[expected_failure(abort_code = risk_oracle::EInvalidScore)]
    fun test_invalid_score_too_high() {
        let mut scenario = sui::test_scenario::begin(@0xA);
        {
            risk_oracle::init_for_testing(sui::test_scenario::ctx(&mut scenario));
        };
        sui::test_scenario::next_tx(&mut scenario, @0xA);
        {
            let mut registry = sui::test_scenario::take_shared<RiskRegistry>(&scenario);
            let ts = sui::tx_context::epoch_timestamp_ms(sui::test_scenario::ctx(&mut scenario)) / 1000;
            
            risk_oracle::submit_assessment(
                &mut registry,
                b"0x2::sui::SUI",
                150,  // Invalid: > 100
                b"HIGH",
                vector[],
                b"agent_v1",
                ts,
                sui::test_scenario::ctx(&mut scenario),
            );
            
            sui::test_scenario::return_shared(registry);
        };
        sui::test_scenario::end(scenario);
    }

    #[test]
    fun test_get_assessment() {
        let mut scenario = sui::test_scenario::begin(@0xA);
        {
            risk_oracle::init_for_testing(sui::test_scenario::ctx(&mut scenario));
        };
        sui::test_scenario::next_tx(&mut scenario, @0xA);
        {
            let mut registry = sui::test_scenario::take_shared<RiskRegistry>(&scenario);
            let ts = sui::tx_context::epoch_timestamp_ms(sui::test_scenario::ctx(&mut scenario)) / 1000;
            
            risk_oracle::submit_assessment(
                &mut registry,
                b"0x2::sui::SUI",
                92,
                b"LOW",
                vector[],
                b"agent_v1",
                ts,
                sui::test_scenario::ctx(&mut scenario),
            );
            
            sui::test_scenario::return_shared(registry);
        };
        
        // Assessment was transferred to @0xA (the sender)
        sui::test_scenario::next_tx(&mut scenario, @0xA);
        {
            let assessment = sui::test_scenario::take_from_address<RiskAssessment>(&scenario, @0xA);
            let (score, level, _factors) = risk_oracle::get_assessment(&assessment);
            assert!(score == 92, 2);
            assert!(level == string::utf8(b"LOW"), 3);
            sui::test_scenario::return_to_address(@0xA, assessment);
        };
        sui::test_scenario::end(scenario);
    }

    #[test]
    fun test_staleness_check() {
        let mut scenario = sui::test_scenario::begin(@0xA);
        {
            risk_oracle::init_for_testing(sui::test_scenario::ctx(&mut scenario));
        };
        sui::test_scenario::next_tx(&mut scenario, @0xA);
        {
            let mut registry = sui::test_scenario::take_shared<RiskRegistry>(&scenario);
            let ts = sui::tx_context::epoch_timestamp_ms(sui::test_scenario::ctx(&mut scenario)) / 1000;
            
            risk_oracle::submit_assessment(
                &mut registry,
                b"0x2::sui::SUI",
                85,
                b"LOW",
                vector[],
                b"agent_v1",
                ts,
                sui::test_scenario::ctx(&mut scenario),
            );
            
            sui::test_scenario::return_shared(registry);
        };
        
        // Assessment was transferred to @0xA (the sender)
        sui::test_scenario::next_tx(&mut scenario, @0xA);
        {
            let assessment = sui::test_scenario::take_from_address<RiskAssessment>(&scenario, @0xA);
            let ts = sui::tx_context::epoch_timestamp_ms(sui::test_scenario::ctx(&mut scenario)) / 1000;
            
            // Current time should be close to submission time
            assert!(!risk_oracle::is_stale(&assessment, ts + 300), 4); // 5 min later
            
            // Much later = stale
            assert!(risk_oracle::is_stale(&assessment, ts + 3601), 5); // 1hr + 1s
            
            sui::test_scenario::return_to_address(@0xA, assessment);
        };
        sui::test_scenario::end(scenario);
    }
}

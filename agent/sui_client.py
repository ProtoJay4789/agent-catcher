"""
Sui RPC Client for Agent Catcher
Connects Python agent logic to on-chain risk oracle

Usage:
    client = SuiClient("testnet")
    client.submit_risk_assessment(
        token_address="0x2::sui::SUI",
        risk_score=85,
        risk_level="LOW",
        risk_factors=["high_liquidity", "verified_contract"],
        agent_id="agent_v1"
    )
"""

import json
import requests
import time
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class SuiConfig:
    """Sui network configuration"""
    name: str
    rpc_url: str
    explorer_url: str
    faucet_url: Optional[str]


NETWORKS = {
    "mainnet": SuiConfig(
        name="mainnet",
        rpc_url="https://fullnode.mainnet.sui.io:443",
        explorer_url="https://suiscan.xyz/mainnet",
        faucet_url=None,
    ),
    "testnet": SuiConfig(
        name="testnet",
        rpc_url="https://fullnode.testnet.sui.io:443",
        explorer_url="https://suiscan.xyz/testnet",
        faucet_url="https://faucet.testnet.sui.io",
    ),
    "devnet": SuiConfig(
        name="devnet",
        rpc_url="https://fullnode.devnet.sui.io:443",
        explorer_url="https://suiscan.xyz/devnet",
        faucet_url="https://faucet.devnet.sui.io",
    ),
}


class SuiClient:
    """Sui RPC client for interacting with on-chain contracts"""
    
    def __init__(self, network: str = "testnet"):
        self.config = NETWORKS[network]
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "AgentCatcher/1.0"
        })
    
    def _rpc_call(self, method: str, params: dict = None) -> dict:
        """Execute Sui RPC call"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }
        
        response = self.session.post(self.config.rpc_url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        if "error" in result:
            raise Exception(f"RPC Error: {result['error']}")
        
        return result.get("result", {})
    
    def get_sui_balance(self, address: str) -> float:
        """Get SUI balance for an address"""
        result = self._rpc_call("sui_getBalance", [address, "0x2::sui::SUI"])
        return int(result.get("totalBalance", 0)) / 1e9  # Convert from MIST
    
    def get_gas_price(self) -> int:
        """Get current gas price"""
        result = self._rpc_call("sui_getReferenceGasPrice")
        return result
    
    def get_objects(self, address: str) -> List[dict]:
        """Get all objects owned by an address"""
        result = self._rpc_call("sui_getOwnedObjects", {
            "owner": address,
            "limit": 50,
            "options": {"showType": True, "showContent": True}
        })
        return result.get("data", [])
    
    def execute_move_call(
        self,
        sender: str,
        package_id: str,
        module: str,
        function: str,
        arguments: List[list],
        type_arguments: List[str] = None,
        gas_budget: int = 50_000_000
    ) -> dict:
        """Execute a Move call (requires signing)"""
        tx_bytes = self._create_move_call_tx(
            sender, package_id, module, function, 
            arguments, type_arguments, gas_budget
        )
        # Note: Actual execution requires keypair signing
        # This creates the transaction bytes for offline signing
        return {
            "tx_bytes": tx_bytes,
            "gas_budget": gas_budget,
            "note": "Sign with sui keypair before broadcasting"
        }
    
    def _create_move_call_tx(
        self,
        sender: str,
        package_id: str,
        module: str,
        function: str,
        arguments: List[list],
        type_arguments: List[str] = None,
        gas_budget: int = 50_000_000
    ) -> str:
        """Create unsigned Move call transaction"""
        # Build transaction programmable
        tx_kind = {
            "TransactionKind": {
                "ProgrammableTransaction": {
                    "inputs": [],
                    "commands": [{
                        "MoveCall": {
                            "package": package_id,
                            "module": module,
                            "function": function,
                            "type_arguments": type_arguments or [],
                            "arguments": arguments
                        }
                    }]
                }
            }
        }
        
        # Encode to base64 (simplified - real impl needs proper serialization)
        import base64
        return base64.b64encode(json.dumps(tx_kind).encode()).decode()
    
    def dry_run_move_call(
        self,
        sender: str,
        package_id: str,
        module: str,
        function: str,
        arguments: List[list],
        type_arguments: List[str] = None
    ) -> dict:
        """Dry-run a Move call to check for errors"""
        tx_kind = {
            "TransactionKind": {
                "ProgrammableTransaction": {
                    "inputs": [],
                    "commands": [{
                        "MoveCall": {
                            "package": package_id,
                            "module": module,
                            "function": function,
                            "type_arguments": type_arguments or [],
                            "arguments": arguments
                        }
                    }]
                }
            }
        }
        
        result = self._rpc_call("sui_devInspectTransactionBlock", {
            "sender": sender,
            "transactionKind": tx_kind,
            "gasPrice": self.get_gas_price(),
        })
        
        return result


class RiskOracleClient:
    """High-level client for Agent Catcher risk oracle"""
    
    # Deployed on Sui Devnet
    PACKAGE_ID = "0x20e7a4ff0eab4f0eae72614c61022853c39368fb336b48db8e87a19284a97e43"
    MODULE = "risk_oracle"
    REGISTRY_ID = "0x7639df5cdbf75797895ef2632f0f84ed6a053be7f7ba1a3470bb1c1d33d7ebeb"
    
    def __init__(self, network: str = "devnet", private_key: str = None):
        self.client = SuiClient(network)
        self.private_key = private_key  # Store for signing
        print(f"🔍 RiskOracleClient initialized for {network}")
        print(f"   Explorer: {self.client.config.explorer_url}")
    
    def submit_risk_assessment(
        self,
        token_address: str,
        risk_score: int,
        risk_level: str,
        risk_factors: List[str],
        agent_id: str = "python_agent_v1"
    ) -> dict:
        """Submit risk assessment to on-chain oracle"""
        timestamp = int(time.time())
        
        # Build arguments for submit_assessment
        arguments = [
            {"Object": {"objectId": self.REGISTRY_ID, "mutable": True}},
            {"Pure": list(token_address.encode())},
            {"Pure": [risk_score]},
            {"Pure": list(risk_level.encode())},
            {"Pure": [list(f.encode()) for f in risk_factors]},
            {"Pure": list(agent_id.encode())},
            {"Pure": [timestamp]},
        ]
        
        print(f"📤 Submitting risk assessment...")
        print(f"   Token: {token_address}")
        print(f"   Score: {risk_score}/100")
        print(f"   Level: {risk_level}")
        print(f"   Factors: {risk_factors}")
        
        # Execute on-chain
        # Note: In production, sign with private_key before broadcasting
        result = self.client.execute_move_call(
            sender="0x0000000000000000000000000000000000000000000000000000000000000000",  # Replace with sender
            package_id=self.PACKAGE_ID,
            module=self.MODULE,
            function="submit_assessment",
            arguments=arguments
        )
        
        print(f"✅ Transaction created: {result['tx_bytes'][:50]}...")
        return result
    
    def get_risk_assessment(self, assessment_id: str) -> dict:
        """Fetch risk assessment from chain"""
        # Query object by ID
        result = self.client._rpc_call("sui_getObject", [
            assessment_id,
            {"showContent": True, "showType": True}
        ])
        
        if result.get("status") == "Exists":
            content = result["data"]["content"]
            fields = content.get("fields", {})
            
            return {
                "token_address": fields.get("token_address", ""),
                "risk_score": fields.get("risk_score", 0),
                "risk_level": fields.get("risk_level", ""),
                "risk_factors": fields.get("risk_factors", []),
                "agent_id": fields.get("agent_id", ""),
                "timestamp": fields.get("timestamp", 0),
            }
        
        return None
    
    def check_staleness(self, assessment_id: str) -> bool:
        """Check if assessment is stale (>1 hour old)"""
        assessment = self.get_risk_assessment(assessment_id)
        if not assessment:
            return True
        
        current_time = int(time.time())
        age_secs = current_time - assessment["timestamp"]
        return age_secs > 3600  # 1 hour
    
    def print_registry_stats(self):
        """Print statistics about registry"""
        print(f"\n📊 Registry Stats:")
        print(f"   Package: {self.PACKAGE_ID[:20]}...")
        print(f"   Registry: {self.REGISTRY_ID[:20]}...")
        # TODO: Query on-chain for actual assessment count


# ====== Example Usage ======

if __name__ == "__main__":
    # Initialize client
    oracle = RiskOracleClient(network="testnet")
    
    # Example: Submit risk assessment
    print("\n🧪 Example: Submitting risk assessment for SUI token")
    result = oracle.submit_risk_assessment(
        token_address="0x2::sui::SUI",
        risk_score=87,
        risk_level="LOW",
        risk_factors=["high_liquidity", "verified_contract", "active_development"],
        agent_id="gentech_agent_v1"
    )
    
    # Print stats
    oracle.print_registry_stats()
    
    print("\n💡 Next steps:")
    print("   1. Install Sui CLI: https://docs.sui.io/references/cli")
    print("   2. Deploy contract: sui client publish --gas-budget 100000000")
    print("   3. Update PACKAGE_ID and REGISTRY_ID in this file")
    print("   4. Sign transactions with your private key")

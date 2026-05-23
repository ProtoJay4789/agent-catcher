#!/usr/bin/env python3
"""
Rugcheck v2 — Configuration
============================
Centralized configuration loaded from environment variables or config.yaml.

Environment variables:
    BAGS_API_KEY          — Bags.fm API key
    TELEGRAM_BOT_TOKEN    — Telegram bot token for alerts
    TELEGRAM_CHAT_ID      — Telegram chat ID for alerts
    WEBHOOK_URL           — Generic webhook URL (Discord, Slack, etc.)
    SCAN_INTERVAL         — Seconds between scan cycles (default: 60)
    SIMULATE_MODE         — Use simulated data instead of live API (default: true)
    LOG_FILE              — Optional JSON log file path
"""

import os
import sys
from typing import Optional


# ─── Defaults ────────────────────────────────────────────────────────────────

DEFAULTS = {
    "BAGS_API_KEY": "",
    "TELEGRAM_BOT_TOKEN": "",
    "TELEGRAM_CHAT_ID": "",
    "WEBHOOK_URL": "",
    "SCAN_INTERVAL": "60",
    "SIMULATE_MODE": "true",
    "LOG_FILE": "",
}


# ─── Config class ────────────────────────────────────────────────────────────

class Config:
    """
    Rugcheck configuration container.

    Values are loaded from environment variables with sensible defaults.
    Optionally loads from a config.yaml file if present.
    """

    def __init__(self):
        self.bags_api_key: str = os.getenv("BAGS_API_KEY", DEFAULTS["BAGS_API_KEY"])
        self.telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", DEFAULTS["TELEGRAM_BOT_TOKEN"])
        self.telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", DEFAULTS["TELEGRAM_CHAT_ID"])
        self.webhook_url: str = os.getenv("WEBHOOK_URL", DEFAULTS["WEBHOOK_URL"])
        self.scan_interval: int = int(os.getenv("SCAN_INTERVAL", DEFAULTS["SCAN_INTERVAL"]))
        self.simulate_mode: bool = os.getenv("SIMULATE_MODE", DEFAULTS["SIMULATE_MODE"]).lower() in ("true", "1", "yes")
        self.log_file: str = os.getenv("LOG_FILE", DEFAULTS["LOG_FILE"])

        # Try loading from config.yaml if it exists
        self._load_yaml_if_available()

    def _load_yaml_if_available(self):
        """Attempt to load config.yaml from the project root."""
        try:
            import yaml
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    data = yaml.safe_load(f) or {}
                # Env vars take precedence over yaml
                for key, val in data.items():
                    attr = key.lower()
                    if hasattr(self, attr) and not os.getenv(key):
                        setattr(self, attr, val)
        except ImportError:
            pass  # yaml not installed — that's fine, env vars are enough
        except Exception as e:
            print(f"⚠️  Warning: Could not load config.yaml: {e}", file=sys.stderr)

    @property
    def simulate(self) -> bool:
        """Alias for simulate_mode."""
        return self.simulate_mode

    def __repr__(self) -> str:
        return (
            f"Config(bags_api_key={'***' if self.bags_api_key else '(none)'}, "
            f"scan_interval={self.scan_interval}, simulate_mode={self.simulate_mode})"
        )

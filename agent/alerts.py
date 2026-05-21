#!/usr/bin/env python3
"""
Agent Catcher — Alert System
============================
Dispatches risk alerts via multiple channels:
  - Terminal (stdout, always enabled)
  - Webhook (generic HTTP POST — Discord, Slack, custom)
  - Telegram (via Bot API)

Usage:
    from alerts import AlertDispatcher
    dispatcher = AlertDispatcher(webhook_url="https://...", telegram_bot_token="...", telegram_chat_id="...")
    dispatcher.send(token_address, score, level, factors)
"""

import json
import time
import urllib.request
import urllib.error
from typing import Dict, List, Optional


# ─── Alert Levels ──────────────────────────────────────────────────────────────

# Which levels actually trigger alerts (LOW and MEDIUM are informational only)
ALERT_LEVELS = {"HIGH", "CRITICAL"}


# ─── Alert Formatter ───────────────────────────────────────────────────────────

def format_alert_text(token_address: str, score: int, level: str,
                       factors: Dict[str, bool], agent_id: str = "gentech_agent_v1") -> str:
    """Format a human-readable alert message."""
    risk_flags = [k for k, v in factors.items() if v and k != "is_open_source"]
    if not factors.get("is_open_source", False):
        risk_flags.append("closed_source")

    emoji = "🔴" if level == "CRITICAL" else "🟠"
    flag_str = ", ".join(risk_flags) if risk_flags else "none"

    return (
        f"{emoji} AGENT CATCHER ALERT — {level}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Token:  {token_address}\n"
        f"Score:  {score}/100\n"
        f"Level:  {level}\n"
        f"Flags:  {flag_str}\n"
        f"Agent:  {agent_id}\n"
        f"Time:   {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}"
    )


def format_alert_json(token_address: str, score: int, level: str,
                       factors: Dict[str, bool], agent_id: str = "gentech_agent_v1") -> Dict:
    """Format alert as structured JSON payload."""
    risk_flags = [k for k, v in factors.items() if v and k != "is_open_source"]
    if not factors.get("is_open_source", False):
        risk_flags.append("closed_source")

    return {
        "alert": True,
        "token_address": token_address,
        "score": score,
        "level": level,
        "risk_flags": risk_flags,
        "agent_id": agent_id,
        "timestamp": int(time.time()),
        "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ─── Dispatchers ───────────────────────────────────────────────────────────────

class TerminalAlert:
    """Always prints to stdout. No config needed."""

    name = "terminal"

    def send(self, text: str, payload: Dict) -> bool:
        print()
        print(text)
        print()
        return True


class WebhookAlert:
    """POST JSON to a generic webhook (Discord, Slack, custom)."""

    name = "webhook"

    def __init__(self, url: str, timeout: int = 10):
        self.url = url
        self.timeout = timeout

    def send(self, text: str, payload: Dict) -> bool:
        """Send alert via HTTP POST. Returns True on success."""
        # Wrap in Discord-compatible format if it looks like a Discord webhook
        if "discord.com" in self.url:
            body = {"content": text}
        else:
            body = {"text": text, "payload": payload}

        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status in (200, 204)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            print(f"⚠️  Webhook alert failed: {e}")
            return False


class TelegramAlert:
    """Send alert via Telegram Bot API."""

    name = "telegram"

    def __init__(self, bot_token: str, chat_id: str, timeout: int = 10):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    def send(self, text: str, payload: Dict) -> bool:
        """Send alert via Telegram. Returns True on success."""
        body = json.dumps({
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
        }).encode("utf-8")

        req = urllib.request.Request(
            self.api_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read())
                return result.get("ok", False)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            print(f"⚠️  Telegram alert failed: {e}")
            return False


# ─── Dispatcher ────────────────────────────────────────────────────────────────

class AlertDispatcher:
    """
    Central dispatcher that sends alerts through all configured channels.

    Only fires for HIGH and CRITICAL risk levels.
    """

    def __init__(self, webhook_url: Optional[str] = None,
                 telegram_bot_token: Optional[str] = None,
                 telegram_chat_id: Optional[str] = None,
                 alert_levels: Optional[set] = None):
        self.channels: List = [TerminalAlert()]
        self.alert_levels = alert_levels or ALERT_LEVELS
        self._last_alerts: List[Dict] = []

        if webhook_url:
            self.channels.append(WebhookAlert(webhook_url))

        if telegram_bot_token and telegram_chat_id:
            self.channels.append(TelegramAlert(telegram_bot_token, telegram_chat_id))

    def should_alert(self, level: str) -> bool:
        """Check if this risk level should trigger an alert."""
        return level in self.alert_levels

    def send(self, token_address: str, score: int, level: str,
             factors: Dict[str, bool], agent_id: str = "gentech_agent_v1",
             force: bool = False) -> List[Dict]:
        """
        Dispatch alert through all channels.

        Returns list of {channel, success} results.
        Only sends if level is in alert_levels (or force=True).
        """
        if not self.should_alert(level) and not force:
            return []

        text = format_alert_text(token_address, score, level, factors, agent_id)
        payload = format_alert_json(token_address, score, level, factors, agent_id)

        results = []
        for channel in self.channels:
            try:
                success = channel.send(text, payload)
                results.append({"channel": channel.name, "success": success})
            except Exception as e:
                results.append({"channel": channel.name, "success": False, "error": str(e)})

        self._last_alerts.append({
            "token": token_address,
            "score": score,
            "level": level,
            "results": results,
            "timestamp": int(time.time()),
        })

        return results

    @property
    def last_alerts(self) -> List[Dict]:
        return list(self._last_alerts)

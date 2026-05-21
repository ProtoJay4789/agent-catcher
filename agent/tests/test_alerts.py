#!/usr/bin/env python3
"""
Unit tests for Agent Catcher alert system.

Tests cover:
  - Alert formatting (text + JSON)
  - Alert level filtering (HIGH/CRITICAL only)
  - Terminal dispatcher
  - Webhook dispatcher (mocked)
  - Telegram dispatcher (mocked)
  - AlertDispatcher orchestration

Run: python3 -m pytest agent/tests/test_alerts.py -v
"""

import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alerts import (
    AlertDispatcher,
    TerminalAlert,
    WebhookAlert,
    TelegramAlert,
    format_alert_text,
    format_alert_json,
    ALERT_LEVELS,
)


# ─── Formatting Tests ─────────────────────────────────────────────────────────

class TestFormatAlertText:
    def test_critical_alert_format(self):
        factors = {"is_honeypot": True, "is_open_source": False, "hidden_owner": True}
        text = format_alert_text("0xdead", 15, "CRITICAL", factors)
        assert "🔴" in text
        assert "CRITICAL" in text
        assert "0xdead" in text
        assert "15/100" in text
        assert "is_honeypot" in text

    def test_high_alert_format(self):
        factors = {"is_honeypot": False, "is_open_source": False, "selfdestruct": True}
        text = format_alert_text("0xabc", 45, "HIGH", factors)
        assert "🟠" in text
        assert "HIGH" in text

    def test_closed_source_flagged(self):
        factors = {"is_open_source": False, "is_honeypot": False}
        text = format_alert_text("0xtoken", 60, "HIGH", factors)
        assert "closed_source" in text

    def test_no_risk_flags(self):
        factors = {"is_open_source": True, "is_honeypot": False}
        text = format_alert_text("0xsafe", 95, "LOW", factors)
        assert "none" in text.lower()


class TestFormatAlertJson:
    def test_json_structure(self):
        factors = {"is_honeypot": True, "is_open_source": False}
        payload = format_alert_json("0xdead", 20, "CRITICAL", factors)
        assert payload["alert"] is True
        assert payload["token_address"] == "0xdead"
        assert payload["score"] == 20
        assert payload["level"] == "CRITICAL"
        assert "timestamp" in payload
        assert "timestamp_iso" in payload

    def test_risk_flags_extraction(self):
        factors = {"is_honeypot": True, "is_open_source": True, "selfdestruct": True}
        payload = format_alert_json("0xtoken", 50, "HIGH", factors)
        assert "is_honeypot" in payload["risk_flags"]
        assert "selfdestruct" in payload["risk_flags"]
        assert "is_open_source" not in payload["risk_flags"]  # True = safe


# ─── Alert Level Filtering ────────────────────────────────────────────────────

class TestAlertLevelFiltering:
    def test_should_alert_critical(self):
        d = AlertDispatcher()
        assert d.should_alert("CRITICAL") is True

    def test_should_alert_high(self):
        d = AlertDispatcher()
        assert d.should_alert("HIGH") is True

    def test_should_not_alert_medium(self):
        d = AlertDispatcher()
        assert d.should_alert("MEDIUM") is False

    def test_should_not_alert_low(self):
        d = AlertDispatcher()
        assert d.should_alert("LOW") is False

    def test_custom_alert_levels(self):
        d = AlertDispatcher(alert_levels={"CRITICAL"})
        assert d.should_alert("CRITICAL") is True
        assert d.should_alert("HIGH") is False


# ─── Terminal Dispatcher ──────────────────────────────────────────────────────

class TestTerminalAlert:
    def test_send_returns_true(self, capsys):
        alert = TerminalAlert()
        result = alert.send("Test alert message", {"test": True})
        assert result is True

    def test_send_prints_output(self, capsys):
        alert = TerminalAlert()
        alert.send("VISIBLE ALERT", {})
        captured = capsys.readouterr()
        assert "VISIBLE ALERT" in captured.out


# ─── Webhook Dispatcher (Mocked) ─────────────────────────────────────────────

class TestWebhookAlert:
    def test_send_success(self):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("alerts.urllib.request.urlopen", return_value=mock_response):
            webhook = WebhookAlert("https://example.com/hook")
            result = webhook.send("test alert", {"test": True})
            assert result is True

    def test_send_failure_returns_false(self):
        import urllib.error
        with patch("alerts.urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
            webhook = WebhookAlert("https://example.com/hook")
            result = webhook.send("test alert", {"test": True})
            assert result is False

    def test_discord_webhook_format(self):
        """Discord webhooks use {content: text} format."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("alerts.urllib.request.urlopen", return_value=mock_response) as mock_open:
            webhook = WebhookAlert("https://discord.com/api/webhooks/123/abc")
            webhook.send("discord alert", {"test": True})

            # Verify the request body was Discord-formatted
            call_args = mock_open.call_args
            req = call_args[0][0]
            body = json.loads(req.data.decode())
            assert "content" in body


# ─── Telegram Dispatcher (Mocked) ────────────────────────────────────────────

class TestTelegramAlert:
    def test_send_success(self):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"ok": True}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("alerts.urllib.request.urlopen", return_value=mock_response):
            tg = TelegramAlert("token123", "chat456")
            result = tg.send("telegram alert", {"test": True})
            assert result is True

    def test_send_failure_returns_false(self):
        import urllib.error
        with patch("alerts.urllib.request.urlopen", side_effect=urllib.error.URLError("network error")):
            tg = TelegramAlert("token123", "chat456")
            result = tg.send("telegram alert", {"test": True})
            assert result is False


# ─── AlertDispatcher Integration ──────────────────────────────────────────────

class TestAlertDispatcher:
    def test_sends_terminal_only(self, capsys):
        d = AlertDispatcher()
        results = d.send("0xdead", 10, "CRITICAL", {"is_honeypot": True})
        assert len(results) == 1
        assert results[0]["channel"] == "terminal"
        assert results[0]["success"] is True

    def test_no_send_for_low(self):
        d = AlertDispatcher()
        results = d.send("0xsafe", 90, "LOW", {})
        assert len(results) == 0

    def test_force_send(self):
        d = AlertDispatcher()
        results = d.send("0xsafe", 90, "LOW", {}, force=True)
        assert len(results) == 1  # forced through

    def test_alerts_logged(self):
        d = AlertDispatcher()
        d.send("0xdead", 10, "CRITICAL", {"is_honeypot": True})
        assert len(d.last_alerts) == 1
        assert d.last_alerts[0]["token"] == "0xdead"

    def test_multiple_dispatches(self):
        d = AlertDispatcher()
        d.send("0xtoken1", 10, "CRITICAL", {})
        d.send("0xtoken2", 45, "HIGH", {})
        d.send("0xtoken3", 80, "LOW", {})  # should NOT dispatch
        assert len(d.last_alerts) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

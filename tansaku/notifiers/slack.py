"""Slack Block Kit notifier with interactive buttons for assignment decisions."""

from __future__ import annotations

import time
import requests

from .base import Notifier, DecisionResult

SLACK_API = "https://slack.com/api"


class SlackNotifier(Notifier):
    def __init__(self, bot_token: str, channel: str):
        self.token = bot_token
        self.channel = channel

    def _call(self, method: str, payload: dict) -> dict:
        r = requests.post(
            f"{SLACK_API}/{method}",
            json=payload,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data.get('error')}")
        return data

    def _ping(self) -> None:
        self._call("auth.test", {})

    # ── Public interface ──────────────────────────────────────────────────────

    def send_intake_summary(
        self,
        ticket_key: str,
        summary: str,
        assignee_options: list[dict],
    ) -> str:
        """Send message with Block Kit buttons. Returns thread_ts as message_id."""
        buttons = [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": opt["label"]},
                "value": f"assign:{ticket_key}:{opt['value']}",
                "action_id": f"assign_{i}",
            }
            for i, opt in enumerate(assignee_options)
        ]
        buttons.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "⏭ Skip"},
            "value": f"assign:{ticket_key}:skip",
            "action_id": "assign_skip",
            "style": "danger",
        })

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": f"🔵 {ticket_key}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": summary[:700]}},
            {"type": "actions", "elements": buttons},
        ]

        result = self._call("chat.postMessage", {
            "channel": self.channel,
            "blocks": blocks,
            "text": f"Intake: {ticket_key}",
        })
        return result["ts"]

    def wait_for_decision(self, message_id: str, timeout: int = 300) -> DecisionResult:
        """Poll conversations.replies until a response from a non-bot appears.

        Note: for full interactive button support, configure Slack Interactivity
        webhook. This polling fallback works for plain text replies (reply 'assign XXXX → name').
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = self._call("conversations.replies", {
                "channel": self.channel,
                "ts": message_id,
                "limit": 10,
            })
            messages = result.get("messages", [])
            for msg in messages[1:]:  # skip the original message
                if not msg.get("bot_id"):
                    text = msg.get("text", "").strip()
                    # Accept "→ alice@co.com" or "alice@co.com" or "skip"
                    value = text.lstrip("→ ").strip()
                    return DecisionResult(chosen=value, raw_text=text)
            time.sleep(5)
        return DecisionResult(chosen="skip", raw_text="", timed_out=True)

    def send_confirmation(self, ticket_key: str, assignee_label: str, status: str) -> None:
        self._call("chat.postMessage", {
            "channel": self.channel,
            "text": f"✅ *{ticket_key}* → {assignee_label} ({status})",
        })

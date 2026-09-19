"""Telegram Bot API notifier with InlineKeyboard for assignment decisions."""

from __future__ import annotations

import time
import requests

from .base import Notifier, DecisionResult

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramNotifier(Notifier):
    def __init__(self, bot_token: str, chat_id: str):
        self.token = bot_token
        self.chat_id = chat_id
        self._last_update_id = 0

    def _call(self, method: str, payload: dict) -> dict:
        url = TELEGRAM_API.format(token=self.token, method=method)
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data}")
        return data["result"]

    def _ping(self) -> None:
        self._call("getMe", {})

    # ── Public interface ──────────────────────────────────────────────────────

    def send_intake_summary(
        self,
        ticket_key: str,
        summary: str,
        assignee_options: list[dict],
    ) -> str:
        """Send message with InlineKeyboard rows (2 buttons per row)."""
        text = f"🔵 *{ticket_key}*\n\n{summary[:800]}\n\n_Assign to:_"

        # Build inline keyboard — 2 buttons per row
        rows = []
        pair = []
        for opt in assignee_options:
            pair.append({
                "text": opt["label"],
                "callback_data": f"assign:{ticket_key}:{opt['value']}",
            })
            if len(pair) == 2:
                rows.append(pair)
                pair = []
        if pair:
            rows.append(pair)
        rows.append([{"text": "⏭ Skip", "callback_data": f"assign:{ticket_key}:skip"}])

        result = self._call("sendMessage", {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": rows},
        })
        return str(result["message_id"])

    def wait_for_decision(self, message_id: str, timeout: int = 300) -> DecisionResult:
        """Poll getUpdates every 5s until a callback_query matching our message arrives."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            updates = self._call("getUpdates", {
                "offset": self._last_update_id + 1,
                "timeout": 5,
                "allowed_updates": ["callback_query"],
            })
            for upd in updates:
                self._last_update_id = upd["update_id"]
                cq = upd.get("callback_query")
                if not cq:
                    continue
                data = cq.get("data", "")
                # Acknowledge the button press
                self._call("answerCallbackQuery", {"callback_query_id": cq["id"]})
                if data.startswith("assign:"):
                    parts = data.split(":", 2)
                    value = parts[2] if len(parts) == 3 else "skip"
                    return DecisionResult(chosen=value, raw_text=data)
        return DecisionResult(chosen="skip", raw_text="", timed_out=True)

    def send_confirmation(self, ticket_key: str, assignee_label: str, status: str) -> None:
        self._call("sendMessage", {
            "chat_id": self.chat_id,
            "text": f"✅ *{ticket_key}* → {assignee_label} ({status})",
            "parse_mode": "Markdown",
        })

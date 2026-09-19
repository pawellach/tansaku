"""Notification channel implementations."""

from .base import Notifier, DecisionResult
from .telegram import TelegramNotifier
from .slack import SlackNotifier

__all__ = ["Notifier", "DecisionResult", "TelegramNotifier", "SlackNotifier"]


def get_notifier(cfg: dict) -> "Notifier | None":
    """Factory: return the configured notifier, or None if channel='none'."""
    channel = (cfg.get("notification") or {}).get("channel", "none")
    notif_cfg = cfg.get("notification") or {}

    if channel == "telegram":
        t = notif_cfg.get("telegram") or {}
        return TelegramNotifier(
            bot_token=t.get("bot_token", ""),
            chat_id=str(t.get("chat_id", "")),
        )
    if channel == "slack":
        s = notif_cfg.get("slack") or {}
        return SlackNotifier(
            bot_token=s.get("bot_token", ""),
            channel=s.get("channel", "#intake"),
        )
    return None

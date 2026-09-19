"""Abstract base class for notification channels."""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DecisionResult:
    """Result of waiting for a human decision."""
    chosen: str       # e.g. "alice@company.com" or "skip"
    raw_text: str     # original message/callback text
    timed_out: bool = False


class Notifier(ABC):
    @abstractmethod
    def send_intake_summary(
        self,
        ticket_key: str,
        summary: str,
        assignee_options: list[dict],  # [{"label": "Alice", "value": "alice@co.com"}, ...]
    ) -> str:
        """Send intake summary with assignment buttons. Returns message_id."""

    @abstractmethod
    def wait_for_decision(self, message_id: str, timeout: int = 300) -> DecisionResult:
        """Poll until the user selects an option or timeout expires."""

    @abstractmethod
    def send_confirmation(self, ticket_key: str, assignee_label: str, status: str) -> None:
        """Send a final confirmation message."""

    def test_connection(self) -> bool:
        """Return True if the channel is reachable."""
        try:
            self._ping()
            return True
        except Exception:
            return False

    def _ping(self) -> None:
        raise NotImplementedError

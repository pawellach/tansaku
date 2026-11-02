import unittest
from unittest.mock import patch

from tansaku.cli import _maybe_notify
from tansaku.notifiers.base import DecisionResult


class FakeJira:
    def __init__(self):
        self.assigned = []
        self.transitions = []

    def lookup_account_id(self, identifier):
        return "account-123" if identifier == "developer.a@example.com" else None

    def assign(self, key, account_id):
        self.assigned.append((key, account_id))

    def transition(self, key, transition_id):
        self.transitions.append((key, transition_id))


class FakeAgent:
    def __init__(self):
        self.jira = FakeJira()


class FakeNotifier:
    def __init__(self):
        self.sent = []
        self.confirmations = []

    def send_intake_summary(self, ticket_key, summary, options):
        self.sent.append((ticket_key, options))
        return "message-1"

    def wait_for_decision(self, message_id, timeout=120):
        return DecisionResult(chosen="developer.a@example.com", raw_text="assign:PROJ-1:developer.a@example.com")

    def send_confirmation(self, ticket_key, assignee_label, status):
        self.confirmations.append((ticket_key, assignee_label, status))


class AssignmentFlowTests(unittest.TestCase):
    def test_telegram_decision_assigns_and_transitions_issue(self):
        agent = FakeAgent()
        notifier = FakeNotifier()
        cfg = {
            "_team": {
                "sprint_capacity": {
                    "members": [{
                        "name": "Developer A",
                        "email": "developer.a@example.com",
                    }]
                }
            },
            "intake": {"transitions": {"in_progress": "21"}},
        }

        with patch("tansaku.cli.get_notifier", return_value=notifier):
            _maybe_notify(agent, cfg, {"summary": "analysis", "actions": []}, "PROJ-1")

        self.assertEqual(agent.jira.assigned, [("PROJ-1", "account-123")])
        self.assertEqual(agent.jira.transitions, [("PROJ-1", "21")])
        self.assertEqual(notifier.confirmations, [("PROJ-1", "Developer A", "In Progress")])


if __name__ == "__main__":
    unittest.main()

"""Tansaku CLI entry point."""

from __future__ import annotations

import sys
import json

import click

from .config import load_config, validate_config
from .agent import IntakeAgent
from .notifiers import get_notifier


@click.group()
def cli():
    """Tansaku — AI intake agent for Jira."""


@cli.command()
@click.option("--config", "config_path", default="config.yaml", show_default=True,
              help="Path to config.yaml")
@click.option("--dry-run", is_flag=True, help="Preview only — no writes to Jira")
@click.option("--ticket", default=None, help="Process a single ticket (e.g. PROJ-123)")
@click.option("--notify/--no-notify", default=True,
              help="Send notification via configured channel")
def run(config_path: str, dry_run: bool, ticket: str | None, notify: bool):
    """Run intake analysis (batch or single ticket)."""
    cfg = _load_or_exit(config_path)
    mode = "[DRY-RUN]" if dry_run else "[LIVE]"
    click.echo(f"\nTansaku {mode} — {'ticket ' + ticket if ticket else 'daily batch'}\n")

    agent = IntakeAgent(cfg, dry_run=dry_run)
    result = agent.run(ticket_key=ticket)

    click.echo("\n" + "─" * 60)
    click.echo(result.get("summary", "(no summary)"))
    click.echo(f"\n{len(result.get('actions', []))} tool calls executed.")

    if notify and not dry_run and result.get("status") == "ok":
        _maybe_notify(cfg, result, ticket)

    if result.get("status") != "ok":
        sys.exit(1)


@cli.command()
@click.argument("ticket_key")
@click.option("--config", "config_path", default="config.yaml", show_default=True)
def test(ticket_key: str, config_path: str):
    """Test analysis for a single ticket without writing to Jira."""
    cfg = _load_or_exit(config_path)
    click.echo(f"\nTest run for {ticket_key} (dry-run, no Jira writes)\n")
    agent = IntakeAgent(cfg, dry_run=True)
    result = agent.run(ticket_key=ticket_key)
    click.echo("\n" + result.get("summary", "(no summary)"))


@cli.command()
@click.option("--config", "config_path", default="config.yaml", show_default=True)
def setup(config_path: str):
    """Verify all connections (Jira, Anthropic, notification channel)."""
    cfg = _load_or_exit(config_path)

    click.echo("\nTansaku setup check\n" + "─" * 40)

    # Jira
    from .jira_client import JiraClient
    jira_cfg = cfg["jira"]
    try:
        jira = JiraClient(jira_cfg["base_url"], jira_cfg["email"], jira_cfg["api_token"])
        issues = jira.search(f"project = {jira_cfg['project']} ORDER BY created DESC", ["summary"], max_results=1)
        click.echo(f"✓ Jira  — project {jira_cfg['project']}, latest: {issues[0]['key'] if issues else 'n/a'}")
    except Exception as e:
        click.echo(f"✗ Jira  — {e}", err=True)

    # Anthropic
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=cfg["anthropic"]["api_key"])
        client.models.list()
        click.echo(f"✓ Anthropic — model {cfg['anthropic'].get('model', '?')}")
    except Exception as e:
        click.echo(f"✗ Anthropic — {e}", err=True)

    # Notification channel
    notifier = get_notifier(cfg)
    if notifier is None:
        click.echo("  Notifications — disabled (channel: none)")
    elif notifier.test_connection():
        channel = cfg.get("notification", {}).get("channel", "?")
        click.echo(f"✓ Notifications — {channel}")
    else:
        channel = cfg.get("notification", {}).get("channel", "?")
        click.echo(f"✗ Notifications — {channel} connection failed", err=True)

    click.echo("\nDone. Run 'tansaku run --dry-run' to preview intake.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_or_exit(config_path: str) -> dict:
    try:
        cfg = load_config(config_path)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    errors = validate_config(cfg)
    if errors:
        click.echo("Configuration errors:", err=True)
        for e in errors:
            click.echo(f"  • {e}", err=True)
        sys.exit(1)
    return cfg


def _maybe_notify(cfg: dict, result: dict, ticket_key: str | None) -> None:
    notifier = get_notifier(cfg)
    if notifier is None:
        return

    team_cfg = cfg.get("_team", {})
    members = team_cfg.get("members", []) if team_cfg else []
    assignee_options = [{"label": m.get("name", m.get("email", "")), "value": m.get("email", "")}
                        for m in members]
    if not assignee_options:
        assignee_options = [{"label": "Skip", "value": "skip"}]

    summary = result.get("summary", "")[:600]
    key = ticket_key or "batch"
    try:
        msg_id = notifier.send_intake_summary(key, summary, assignee_options)
        decision = notifier.wait_for_decision(msg_id, timeout=120)
        if not decision.timed_out and decision.chosen != "skip":
            click.echo(f"  Decision received: {decision.chosen}")
            notifier.send_confirmation(key, decision.chosen, "In Progress")
        else:
            click.echo("  No decision received (timeout or skip).")
    except Exception as e:
        click.echo(f"  Notification error: {e}", err=True)

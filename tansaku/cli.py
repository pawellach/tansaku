"""Tansaku CLI entry point."""

from __future__ import annotations

import sys
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

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
        _maybe_notify(agent, cfg, result, ticket)

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


def _maybe_notify(agent: IntakeAgent, cfg: dict, result: dict, ticket_key: str | None) -> None:
    notifier = get_notifier(cfg)
    if notifier is None:
        return

    team_cfg = cfg.get("_team", {})
    members = team_cfg.get("members", []) if team_cfg else []
    if not members:
        members = (team_cfg.get("sprint_capacity", {}) or {}).get("members", [])

    # The callback carries a stable operator-supplied identifier. Prefer an
    # explicit account ID, then email, then display name for small teams.
    assignee_options = []
    assignees_by_value = {}
    account_ids_by_value = {}
    for member in members:
        identifier = (member.get("jira_account_id") or member.get("account_id")
                      or member.get("email") or member.get("name", "")).strip()
        if not identifier:
            continue
        label = member.get("name") or member.get("email") or identifier
        assignee_options.append({"label": label, "value": identifier})
        assignees_by_value[identifier] = label
        account_ids_by_value[identifier] = member.get("jira_account_id") or member.get("account_id")
    if not assignee_options:
        click.echo("  Notification skipped: team.json has no Jira assignee identifiers.", err=True)
        return

    summary = result.get("summary", "")[:600]
    keys = _notification_ticket_keys(result, ticket_key)
    if not keys:
        click.echo("  Notification skipped: no processed ticket key was found.", err=True)
        return

    transition_id = str((cfg.get("intake", {}) or {}).get("transitions", {}).get("in_progress", "21"))
    for key in keys:
        decision = None
        try:
            with _ticket_lock(cfg, key):
                current = agent.jira.get_issue(key)
                if current.get("assignee"):
                    _audit(cfg, key, "skipped", reason="already_assigned")
                    click.echo(f"  {key}: skipped; Jira already has an assignee.")
                    continue
                if current.get("status", "").lower() in {"done", "closed", "resolved", "cancelled"}:
                    _audit(cfg, key, "skipped", reason=f"status={current.get('status')}")
                    click.echo(f"  {key}: skipped; Jira status is {current.get('status')}.")
                    continue

                msg_id = notifier.send_intake_summary(key, summary, assignee_options)
                decision = notifier.wait_for_decision(msg_id, timeout=120)
                if decision.timed_out or decision.chosen == "skip":
                    _audit(cfg, key, "skipped", decision=decision.chosen, reason="timeout_or_skip")
                    click.echo(f"  {key}: no assignment received (timeout or skip).")
                    continue

                label = assignees_by_value.get(decision.chosen, decision.chosen)
                account_id = account_ids_by_value.get(decision.chosen) or agent.jira.lookup_account_id(decision.chosen)
                if not account_id:
                    raise RuntimeError(f"Could not resolve Jira account for '{decision.chosen}'")

                agent.jira.assign(key, account_id)
                agent.jira.transition(key, transition_id)
                _audit(cfg, key, "completed", decision=decision.chosen, account_id=account_id,
                       transition_id=transition_id)
                click.echo(f"  {key}: assigned to {label}; transitioned to In Progress.")
                notifier.send_confirmation(key, label, "In Progress")
        except Exception as e:
            _audit(cfg, key, "failed", decision=decision.chosen if decision else None, reason=str(e))
            click.echo(f"  {key}: notification/assignment error: {e}", err=True)


@contextmanager
def _ticket_lock(cfg: dict, ticket_key: str):
    """Acquire a process-safe per-ticket lock without adding a dependency."""
    lock_dir = Path((cfg.get("intake", {}) or {}).get("lock_dir", ".tansaku-locks"))
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{ticket_key}.lock"
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"pid={os.getpid()}\n")
        yield
    except FileExistsError:
        raise RuntimeError(f"ticket lock already held: {ticket_key}")
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _audit(cfg: dict, ticket_key: str, outcome: str, **details) -> None:
    """Append a redacted assignment decision to a local JSONL audit log."""
    path = Path((cfg.get("intake", {}) or {}).get("assignment_audit_log", "tansaku-assignment-audit.jsonl"))
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticket": ticket_key,
        "outcome": outcome,
        **{k: v for k, v in details.items() if v is not None},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _notification_ticket_keys(result: dict, ticket_key: str | None) -> list[str]:
    """Return unique issue keys touched by the agent, preserving action order."""
    if ticket_key:
        return [ticket_key]

    keys = []
    for action in result.get("actions", []):
        key = (action.get("input") or {}).get("issue_key")
        if key and key not in keys:
            keys.append(key)
    return keys

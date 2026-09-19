"""Configuration loader with environment variable substitution."""

import os
import re
from pathlib import Path
from typing import Any

import yaml


_ENV_RE = re.compile(r"\$\{([^}]+)\}")


def _substitute_env(value: Any) -> Any:
    """Recursively substitute ${VAR} patterns with environment variable values."""
    if isinstance(value, str):
        def replace(m: re.Match) -> str:
            var = m.group(1)
            v = os.environ.get(var, "")
            if not v:
                # Don't raise — allow partial config; validate later
                pass
            return v
        return _ENV_RE.sub(replace, value)
    if isinstance(value, dict):
        return {k: _substitute_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_env(i) for i in value]
    return value


def load_config(path: str = "config.yaml") -> dict:
    """Load and validate config.yaml, substituting ${ENV_VAR} references."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            "Run: cp config.example.yaml config.yaml  and edit it."
        )
    with p.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    cfg = _substitute_env(raw)

    # Load optional knowledge base
    kb_path = cfg.get("knowledge_base", "")
    if kb_path and Path(kb_path).exists():
        import json
        with open(kb_path, encoding="utf-8") as f:
            cfg["_knowledge_base"] = json.load(f)
    else:
        cfg["_knowledge_base"] = {}

    # Load optional team map
    team_path = cfg.get("team", "")
    if team_path and Path(team_path).exists():
        import json
        with open(team_path, encoding="utf-8") as f:
            cfg["_team"] = json.load(f)
    else:
        cfg["_team"] = {}

    return cfg


def validate_config(cfg: dict) -> list[str]:
    """Return list of validation errors (empty = OK)."""
    errors = []
    jira = cfg.get("jira", {})
    if not jira.get("base_url"):
        errors.append("jira.base_url is required")
    if not jira.get("email"):
        errors.append("jira.email is required")
    if not jira.get("api_token"):
        errors.append("jira.api_token missing — set JIRA_API_TOKEN env var")
    if not jira.get("project"):
        errors.append("jira.project is required")

    ai = cfg.get("ai", cfg.get("anthropic", {}))  # support legacy "anthropic:" key
    provider = ai.get("provider", "anthropic")
    if provider == "anthropic":
        if not ai.get("api_key"):
            errors.append("ai.api_key missing — set ANTHROPIC_API_KEY env var")
    elif provider == "bedrock":
        # Credentials may also come from IAM role / env — only warn if explicit keys are half-set
        has_key = bool(ai.get("aws_access_key"))
        has_secret = bool(ai.get("aws_secret_key"))
        if has_key != has_secret:
            errors.append("ai.aws_access_key and ai.aws_secret_key must both be set (or both omitted for IAM role)")
    elif provider == "openai":
        if not ai.get("api_key"):
            errors.append("ai.api_key missing — set OPENAI_API_KEY env var")
    else:
        errors.append(f"ai.provider '{provider}' unknown — choose: anthropic | bedrock | openai")

    return errors

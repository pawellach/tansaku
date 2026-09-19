# Tansaku — Architecture

## Overview

Tansaku is a self-hostable AI intake agent for Jira. It runs on a schedule (via GitHub Actions or any cron), analyses newly created issues using Claude, writes analytical comments for developers, and requests assignment decisions through Telegram or Slack.

## Components

```
tansaku/
├── cli.py           Entry point (click). Commands: run, test, setup
├── config.py        YAML loader with ${ENV_VAR} substitution + validation
├── agent.py         Anthropic Messages API agentic loop with tool_use
├── jira_client.py   Jira REST client (POST /search/jql, comments, transitions)
├── confluence_client.py  Optional documentation lookup
├── prompts.py       Language-aware system prompts (en / pl)
└── notifiers/
    ├── base.py      Abstract Notifier interface
    ├── telegram.py  Telegram Bot API + InlineKeyboard polling
    └── slack.py     Slack Block Kit + conversations.replies polling
```

## Data Flow

```
[Cron / manual trigger]
        │
        ▼
   tansaku run
        │
        ├─► Jira: search new issues (POST /search/jql)
        │
        ├─► For each issue:
        │       ├─► Jira: GET issue details + comments
        │       ├─► Confluence: search relevant docs (optional)
        │       └─► Anthropic: analyse via tool_use loop
        │               └─► tools: search_jira, get_issue, search_confluence,
        │                          add_comment, transition, add_label
        │
        └─► Notifier: send summary + InlineKeyboard
                └─► Poll for human decision (5s intervals, 5min timeout)
                        └─► Jira: assign + transition to In Progress
```

## Idempotency

Processed issues receive an `ai-intake` label (configurable). The agent skips any issue that already has this label, preventing duplicate analysis.

## Adding a New Notifier

1. Create `tansaku/notifiers/myservice.py`
2. Subclass `Notifier` (base.py) and implement `send_intake_summary`, `wait_for_decision`, `send_confirmation`
3. Register in `notifiers/__init__.py` `get_notifier()` factory
4. Add config keys under `notification.myservice.*`

## Running on a VPS / Shared Hosting

```bash
# Install
git clone https://github.com/pawellach/tansaku && cd tansaku
pip install -r requirements.txt && pip install -e .

# Configure
cp config.example.yaml config.yaml  # edit with your values
export JIRA_API_TOKEN=...
export ANTHROPIC_API_KEY=...
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...

# Cron (every 2h, Mon-Fri)
0 7,9,11,13,15 * * 1-5 cd /path/to/tansaku && tansaku run >> tansaku.log 2>&1
```

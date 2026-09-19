"""Core agentic loop: Anthropic Messages API + Jira tool_use."""

from __future__ import annotations

import json
from typing import Any

import anthropic

from .jira_client import JiraClient
from .confluence_client import ConfluenceClient
from .prompts import get_system_prompt


TOOLS = [
    {
        "name": "search_jira_issues",
        "description": "Search Jira issues using JQL. Returns a list of issues.",
        "input_schema": {
            "type": "object",
            "properties": {
                "jql": {"type": "string"},
                "fields": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["jql"],
        },
    },
    {
        "name": "get_jira_issue",
        "description": "Get full details of a single Jira issue.",
        "input_schema": {
            "type": "object",
            "properties": {"issue_key": {"type": "string"}},
            "required": ["issue_key"],
        },
    },
    {
        "name": "add_jira_comment",
        "description": "Add a comment to a Jira issue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_key": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["issue_key", "body"],
        },
    },
    {
        "name": "transition_jira_issue",
        "description": "Change the status of a Jira issue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_key": {"type": "string"},
                "transition_id": {"type": "string", "description": "Transition ID from config."},
            },
            "required": ["issue_key", "transition_id"],
        },
    },
    {
        "name": "add_jira_label",
        "description": "Add a label to a Jira issue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_key": {"type": "string"},
                "label": {"type": "string"},
            },
            "required": ["issue_key", "label"],
        },
    },
    {
        "name": "search_confluence",
        "description": "Search Confluence for relevant documentation.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
]


class IntakeAgent:
    def __init__(self, cfg: dict, dry_run: bool = False, verbose: bool = True):
        self.cfg = cfg
        self.dry_run = dry_run
        self.verbose = verbose

        jira_cfg = cfg.get("jira", {})
        self.jira = JiraClient(
            base_url=jira_cfg["base_url"],
            email=jira_cfg["email"],
            api_token=jira_cfg["api_token"],
        )

        conf_cfg = cfg.get("confluence", {})
        self.confluence = ConfluenceClient(
            base_url=jira_cfg["base_url"],
            email=jira_cfg["email"],
            api_token=jira_cfg["api_token"],
            spaces=conf_cfg.get("spaces", []),
        ) if conf_cfg.get("enabled", True) else None

        ant_cfg = cfg.get("anthropic", {})
        self.anthropic = anthropic.Anthropic(api_key=ant_cfg["api_key"])
        self.model = ant_cfg.get("model", "claude-opus-4-5-20251101")
        self.max_tokens = ant_cfg.get("max_tokens", 8096)

        intake_cfg = cfg.get("intake", {})
        self.label = intake_cfg.get("label", "ai-intake")
        self.transitions = intake_cfg.get("transitions", {})
        self.language = intake_cfg.get("language", "en")
        self.knowledge_base = cfg.get("_knowledge_base", {})

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)

    def _build_user_message(self, ticket_key: str | None, project: str, intake_cfg: dict) -> str:
        if ticket_key:
            return (
                f"Perform intake for ticket {ticket_key}. "
                "Steps: get ticket details, search Confluence for relevant docs, "
                "write analytical comment, transition to Waiting, add intake label."
            )
        window = intake_cfg.get("time_window_hours", 2)
        skip = intake_cfg.get("statuses_to_skip", ["Waiting", "In test", "In Progress"])
        skip_str = ",".join(f"'{s}'" for s in skip)
        return (
            f"Perform daily intake for project {project}:\n"
            f"1. Search: project = {project} AND created >= '-{window}h' "
            f"AND statusCategory NOT IN ('Done') AND status NOT IN ({skip_str}) "
            f"ORDER BY created DESC (max {intake_cfg.get('max_batch', 5)})\n"
            "2. For each ticket: get details, search Confluence, write analytical comment\n"
            f"3. Transition each to Waiting (transition_id={self.transitions.get('waiting','41')})\n"
            f"4. Add label '{self.label}'\n"
            "5. Return a summary table of what was done."
        )

    def _execute_tool(self, name: str, inputs: dict) -> Any:
        """Execute a tool call. Write ops are skipped in dry_run mode."""
        if name == "search_jira_issues":
            fields = inputs.get("fields", ["summary", "description", "status", "reporter", "labels", "comment"])
            return self.jira.search(inputs["jql"], fields)

        if name == "get_jira_issue":
            issues = self.jira.search(
                f"issue = {inputs['issue_key']}",
                ["summary", "description", "comment", "reporter", "assignee",
                 "status", "labels", "issuetype", "priority"],
                max_results=1,
            )
            return issues[0] if issues else {"error": "Not found"}

        if name == "add_jira_comment":
            if self.dry_run:
                return {"dry_run": True, "preview": inputs["body"][:200]}
            return self.jira.add_comment(inputs["issue_key"], inputs["body"])

        if name == "transition_jira_issue":
            if self.dry_run:
                names = {"41": "Waiting", "21": "In Progress", "61": "Rejected"}
                return {"dry_run": True, "would_transition_to": names.get(inputs["transition_id"], inputs["transition_id"])}
            self.jira.transition(inputs["issue_key"], inputs["transition_id"])
            return {"ok": True}

        if name == "add_jira_label":
            if self.dry_run:
                return {"dry_run": True, "would_add_label": inputs["label"]}
            self.jira.add_label(inputs["issue_key"], inputs["label"])
            return {"ok": True}

        if name == "search_confluence":
            if not self.confluence:
                return {"pages": []}
            return {"pages": self.confluence.search(inputs["query"])}

        return {"error": f"Unknown tool: {name}"}

    def run(self, ticket_key: str | None = None) -> dict:
        """Run the intake agent. Returns summary dict."""
        intake_cfg = self.cfg.get("intake", {})
        project = self.cfg.get("jira", {}).get("project", "PROJ")

        system = get_system_prompt(self.language)
        # Inject knowledge base facts if available
        facts = self.knowledge_base.get("facts", [])
        if facts:
            system += "\n\nProject-specific rules:\n" + "\n".join(f"- {f}" for f in facts)

        messages = [{"role": "user", "content": self._build_user_message(ticket_key, project, intake_cfg)}]
        actions: list[dict] = []

        for _ in range(25):
            response = self.anthropic.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                tools=TOOLS,
                messages=messages,
            )

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    self._log(f"  → {block.name}({json.dumps(block.input)[:80]})")
                    result = self._execute_tool(block.name, block.input)
                    actions.append({"tool": block.name, "input": block.input, "result": result})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                final_text = next((b.text for b in response.content if b.type == "text"), "")
                return {"status": "ok", "summary": final_text, "actions": actions}

            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        return {"status": "max_iterations", "actions": actions}

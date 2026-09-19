"""Jira REST API client. Uses POST /rest/api/3/search/jql (GET /search deprecated 2024)."""

from __future__ import annotations

import json
from typing import Any

import requests


class JiraClient:
    def __init__(self, base_url: str, email: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.auth = (email, api_token)
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}

    def _get(self, path: str, params: dict | None = None) -> dict:
        r = requests.get(
            f"{self.base_url}{path}", params=params,
            auth=self.auth, headers=self.headers, timeout=30
        )
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict) -> dict:
        r = requests.post(
            f"{self.base_url}{path}", json=body,
            auth=self.auth, headers=self.headers, timeout=30
        )
        r.raise_for_status()
        return r.json() if r.content else {}

    def _put(self, path: str, body: dict) -> None:
        r = requests.put(
            f"{self.base_url}{path}", json=body,
            auth=self.auth, headers=self.headers, timeout=30
        )
        r.raise_for_status()

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, jql: str, fields: list[str], max_results: int = 10) -> list[dict]:
        """Search issues via POST /rest/api/3/search/jql."""
        result = self._post("/rest/api/3/search/jql", {
            "jql": jql,
            "maxResults": max_results,
            "fields": fields,
        })
        issues = []
        for issue in result.get("issues", []):
            f = issue.get("fields", {})
            comments = []
            for c in (f.get("comment") or {}).get("comments", [])[-5:]:
                comments.append({
                    "author": (c.get("author") or {}).get("displayName", ""),
                    "body": str(c.get("body", ""))[:400],
                    "created": c.get("created", ""),
                })
            issues.append({
                "key": issue["key"],
                "summary": f.get("summary", ""),
                "status": (f.get("status") or {}).get("name", ""),
                "reporter": (f.get("reporter") or {}).get("displayName", ""),
                "reporter_email": (f.get("reporter") or {}).get("emailAddress", ""),
                "assignee": (f.get("assignee") or {}).get("displayName", ""),
                "issuetype": (f.get("issuetype") or {}).get("name", ""),
                "priority": (f.get("priority") or {}).get("name", ""),
                "labels": f.get("labels") or [],
                "description": str(f.get("description", "") or "")[:2000],
                "comments": comments,
            })
        return issues

    def get_issue(self, key: str) -> dict:
        """Get a single issue with all relevant fields."""
        fields = ["summary", "description", "comment", "reporter", "assignee",
                  "status", "labels", "issuetype", "priority", "components"]
        return self.search(f"issue = {key}", fields, max_results=1)[0] if True else {}

    # ── Writes ────────────────────────────────────────────────────────────────

    def add_comment(self, key: str, body: str) -> dict:
        """Add a plain-text comment (wrapped in ADF)."""
        return self._post(f"/rest/api/3/issue/{key}/comment", {
            "body": {
                "version": 1,
                "type": "doc",
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": body}]}],
            }
        })

    def transition(self, key: str, transition_id: str) -> None:
        """Change issue status via a transition."""
        self._post(f"/rest/api/3/issue/{key}/transitions", {"transition": {"id": transition_id}})

    def add_label(self, key: str, label: str) -> None:
        """Add a label to an issue."""
        self._put(f"/rest/api/3/issue/{key}", {"update": {"labels": [{"add": label}]}})

    def get_transitions(self, key: str) -> list[dict]:
        """List available transitions for an issue."""
        result = self._get(f"/rest/api/3/issue/{key}/transitions")
        return [{"id": t["id"], "name": t["name"]} for t in result.get("transitions", [])]

    def lookup_account_id(self, email: str) -> str | None:
        """Look up accountId by email."""
        result = self._get("/rest/api/3/user/search", {"query": email})
        users = result if isinstance(result, list) else []
        for u in users:
            if u.get("emailAddress", "").lower() == email.lower():
                return u["accountId"]
        return users[0]["accountId"] if users else None

    def assign(self, key: str, account_id: str) -> None:
        self._put(f"/rest/api/3/issue/{key}/assignee", {"accountId": account_id})

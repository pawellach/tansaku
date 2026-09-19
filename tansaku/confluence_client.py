"""Confluence REST API client (optional context enrichment)."""

from __future__ import annotations

import requests


class ConfluenceClient:
    def __init__(self, base_url: str, email: str, api_token: str, spaces: list[str]):
        self.base_url = base_url.rstrip("/")
        self.auth = (email, api_token)
        self.spaces = spaces

    def search(self, query: str, limit: int = 3) -> list[dict]:
        """Search Confluence by keywords, filtered to configured spaces."""
        if not self.spaces:
            return []
        space_filter = " OR ".join(f'space.key = "{s}"' for s in self.spaces)
        cql = f'text ~ "{query}" AND ({space_filter})'
        try:
            r = requests.get(
                f"{self.base_url}/wiki/rest/api/content/search",
                params={"cql": cql, "limit": limit},
                auth=self.auth,
                headers={"Accept": "application/json"},
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []

        results = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": self.base_url + "/wiki" + item.get("_links", {}).get("webui", ""),
                "excerpt": item.get("excerpt", "")[:300],
            })
        return results

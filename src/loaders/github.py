"""
Loader for GitHub.

It uses the GitHub REST API, fetching public repos for GITHUB_USERNAME.
Although no auth is required for public repos, GITHUB_TOKEN is provided
to increase rate limits.
"""

import os
import base64
import requests
from langchain_core.documents import Document
from .base import BaseLoader

GITHUB_API = "https://api.github.com"


class GitHubLoader(BaseLoader):
    source_id = "github"
    default_audience = ["technical"]

    # Boilerplate README patterns that indicate auto-generated content.
    # If a README consists mainly of these, the repo is treated as having no meaningful README.
    BOILERPLATE_MARKERS = [
        "create-next-app",
        "This is a [Next.js]",
        "Getting Started",
        "Learn More",
        "yarn dev",
        "npm run dev",
        "bootstrapped with",
        "This project was generated",
        "Edit `src/App",
    ]

    def __init__(self, username: str | None = None, token: str | None = None):
        self.username = username or os.getenv("GITHUB_USERNAME", "")
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        if not self.username:
            raise ValueError(
                "GITHUB_USERNAME must be set in environment or passed explicitly."
            )

        # Not used, but can be used if only certain repos want to be highlighted.
        whitelist_raw = []
        self.whitelist = (
            [r.strip() for r in whitelist_raw.split(",") if r.strip()]
            if whitelist_raw
            else None
        )

    def _headers(self) -> dict:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get_repos(self) -> list[dict]:
        """Fetch all owned, non-fork repos sorted by last updated."""
        url = f"{GITHUB_API}/users/{self.username}/repos"
        params = {"per_page": 100, "sort": "updated", "type": "owner"}
        resp = requests.get(url, headers=self._headers(), params=params, timeout=15)
        resp.raise_for_status()
        repos = resp.json()
        return [r for r in repos if not r.get("fork", False)]

    def _get_readme(self, repo_name: str) -> str:
        """Fetch README content for a repo. Returns empty string if none."""
        url = f"{GITHUB_API}/repos/{self.username}/{repo_name}/readme"
        resp = requests.get(url, headers=self._headers(), timeout=15)
        if resp.status_code == 404:
            return ""
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content", "")
        if data.get("encoding") == "base64" and content:
            return base64.b64decode(content).decode("utf-8", errors="ignore")
        return content

    def _is_boilerplate_readme(self, readme: str) -> bool:
        """Check if a README is mostly auto-generated boilerplate."""
        if not readme:
            return True
        # If more than 30% of the lines are just boilerplate, the README is ignored.
        lines = [l.strip() for l in readme.strip().split("\n") if l.strip()]
        if not lines:
            return True
        boilerplate_hits = sum(
            1 for line in lines
            if any(marker.lower() in line.lower() for marker in self.BOILERPLATE_MARKERS)
        )
        return boilerplate_hits / len(lines) > 0.3

    def _has_meaningful_content(self, repo: dict, readme: str) -> bool:
        """
        This is a quality filter: a repo must have a description or a meaningful README
        to be worth ingesting.
        """
        has_description = bool(repo.get("description"))
        has_readme = bool(readme) and not self._is_boilerplate_readme(readme)
        return has_description or has_readme

    def load(self) -> list[Document]:
        repos = self._get_repos()
        docs = []
        skipped = []

        for repo in repos:
            name = repo["name"]

            if self.whitelist and name not in self.whitelist:
                continue

            readme = self._get_readme(name)

            if not self.whitelist and not self._has_meaningful_content(repo, readme):
                skipped.append(name)
                continue

            if self._is_boilerplate_readme(readme):
                readme = ""

            lines = [
                f"# {name}",
                "",
                f"<!-- audience: technical -->",
                f"<!-- queries: {name} project, what did you build, {repo.get('language', '')} projects, github repos -->",
                "",
                f"## Overview",
                f"",
                f"**Description:** {repo.get('description') or 'No description'}",
                f"",
                f"**Language:** {repo.get('language') or 'Not specified'}",
                f"",
                f"**Topics:** {', '.join(repo.get('topics', [])) or 'None'}",
                f"",
                f"**Stars:** {repo.get('stargazers_count', 0)} | "
                f"**Forks:** {repo.get('forks_count', 0)} | "
                f"**Last updated:** {repo.get('updated_at', '')[:10]}",
                f"",
                f"**URL:** {repo.get('html_url', '')}",
            ]

            if readme:
                lines.append("")
                lines.append("## README")
                lines.append("")
                # If README chunks are long, they are truncated.
                max_readme_chars = 3000
                if len(readme) > max_readme_chars:
                    lines.append(readme[:max_readme_chars])
                    lines.append(
                        f"\n\n*[README truncated — full version at {repo.get('html_url', '')}]*"
                    )
                else:
                    lines.append(readme)

            doc = self._make_doc(
                "\n".join(lines),
                repo=name,
                language=repo.get("language", ""),
                url=repo.get("html_url", ""),
            )
            docs.append(doc)

        if skipped:
            print(
                f"[{self.source_id}] Skipped {len(skipped)} repo(s) with no meaningful content: "
                f"{', '.join(skipped[:5])}{'...' if len(skipped) > 5 else ''}"
            )
        if self.whitelist:
            print(f"[{self.source_id}] Whitelist active: ingesting {len(docs)} of {len(repos)} repos")

        return docs
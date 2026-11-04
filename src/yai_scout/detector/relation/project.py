from __future__ import annotations

import re

from ...retrieval.tavily import SearchResult

PROJECT_STOP = {
    "http", "https", "www", "com", "org", "github", "gitlab", "releases",
    "release", "tag", "tags", "latest", "current", "version", "api", "docs",
    "documentation", "official", "download", "downloads", "source",
}
PROJECT_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]+|[\u4e00-\u9fff]{2,}")


def project_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for match in PROJECT_TOKEN_RE.findall(text.lower()):
        for part in re.split(r"[-_.]", match):
            if len(part) >= 2 and part not in PROJECT_STOP and not part.isdigit():
                tokens.add(part)
    return tokens


def same_project(claim_text: str, result: SearchResult) -> bool:
    claim_project = project_tokens(claim_text)
    release_project = project_tokens(f"{result.url} {result.title}")
    if not claim_project or not release_project:
        return False
    return bool(claim_project & release_project)

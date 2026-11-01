"""真实历史快照：从 GitHub Releases（官方历史）抓取并入库。

用途：archive.org 不可达时，用官方 release 历史做"真实历史回放"——
每条 release 一个快照，published_at = 官方发布时间；replay 只用 target_time 之前的快照。
"""

from __future__ import annotations

from pathlib import Path

import httpx

from ..domain.models import EvidenceSnapshot
from ..store import Store
from .snapshot import save_snapshot

GITHUB_API = "https://api.github.com"


async def capture_github_releases(
    store: Store,
    repo: str,
    *,
    snapshots_dir: Path,
    max_releases: int = 30,
    client: httpx.AsyncClient | None = None,
) -> list[EvidenceSnapshot]:
    owns_client = client is None
    client = client or httpx.AsyncClient(
        timeout=30, headers={"Accept": "application/vnd.github+json"}
    )
    try:
        resp = await client.get(f"{GITHUB_API}/repos/{repo}/releases?per_page={max_releases}")
        if resp.status_code != 200:
            return []
        releases = resp.json()
    except httpx.HTTPError:
        return []
    finally:
        if owns_client:
            await client.aclose()

    snapshots: list[EvidenceSnapshot] = []
    for release in releases:
        tag = str(release.get("tag_name") or "")
        name = str(release.get("name") or tag)
        published = release.get("published_at") or release.get("created_at")
        url = str(release.get("html_url") or f"https://github.com/{repo}/releases/tag/{tag}")
        body = " ".join(str(release.get("body") or "").split())[:600]
        text = (
            f"release version {tag}\nname {name}\npublished_at {published}\nurl {url}\n"
            f"notes {body}"
        )
        snapshots.append(
            save_snapshot(
                store,
                url=url,
                text=text,
                origin="official_history",
                snapshots_dir=snapshots_dir,
                published_at=published,
            )
        )
    return snapshots

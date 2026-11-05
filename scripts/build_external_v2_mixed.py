"""Build a small mixed-source mechanical smoke set for external-v2.

This is intentionally a smoke set, not the 190-case L2/L3 target. It adds
real PyPI-vs-GitHub conflict cases and GitHub README insufficiency cases, plus
a few semantic/stable controls. Labels remain mechanical and non-independent.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from yai_scout.sources.snapshot import fetch_text, html_to_text

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmarks" / "external_v2"
PACKAGES = ("rich", "typer", "starlette", "jinja2", "anyio")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _get(url: str, accept: str = "application/json") -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": "yai-scout-external/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return response.read()


def _pypi(package: str) -> tuple[list[tuple[str, datetime]], str]:
    payload = json.loads(_get(f"https://pypi.org/pypi/{package}/json"))
    releases = []
    for version, files in payload.get("releases", {}).items():
        if not VERSION_RE.fullmatch(version) or not files:
            continue
        stamps = [
            item.get("upload_time_iso_8601") or item.get("upload_time")
            for item in files
            if item.get("upload_time_iso_8601") or item.get("upload_time")
        ]
        if not stamps:
            continue
        times = []
        for raw in stamps:
            try:
                times.append(datetime.fromisoformat(raw.replace("Z", "+00:00")))
            except ValueError:
                continue
        if times:
            releases.append((version, min(times).astimezone(UTC)))
    project_urls = payload.get("info", {}).get("project_urls") or {}
    repo = ""
    for value in project_urls.values():
        match = re.search(r"github\.com/([^/]+/[^/#?]+)", str(value))
        if match:
            repo = match.group(1).removesuffix(".git")
            break
    return sorted(releases, key=lambda item: item[1]), repo


def _github(repo: str) -> list[tuple[str, datetime]]:
    payload = json.loads(
        _get(f"https://api.github.com/repos/{repo}/releases?per_page=100")
    )
    result = []
    for release in payload if isinstance(payload, list) else []:
        tag = str(release.get("tag_name") or "").lstrip("vV")
        if not VERSION_RE.fullmatch(tag):
            continue
        raw = release.get("published_at") or release.get("created_at")
        if not raw:
            continue
        try:
            when = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            continue
        result.append((tag, when))
    return sorted(result, key=lambda item: item[1])


def _latest(releases: list[tuple[str, datetime]], date) -> str | None:
    values = [version for version, when in releases if when.date() <= date]
    return values[-1] if values else None


def _snapshot(package: str, latest: str, releases: list[tuple[str, datetime]], date) -> str:
    visible = [item for item in releases if item[1].date() <= date]
    lines = [f"Package: {package}", f"Latest version: {latest}", "Version history:"]
    lines.extend(f"{version} | {when.date().isoformat()}" for version, when in visible)
    return "\n".join(lines) + "\n"


def _add(
    cases: list[dict],
    labels: list[dict],
    *,
    case_id: str,
    family: str,
    claim_text: str,
    as_of: str,
    gold: str,
    current: str,
    support: str,
    evidence: list[dict],
    claim_type: str = "version",
    sensitivity: str = "sensitive",
) -> None:
    cases.append({
        "id": case_id,
        "split": "test",
        "source_family": family,
        "claim_text": claim_text,
        "claim_type": claim_type,
        "temporal_sensitivity": sensitivity,
        "as_of": as_of,
        "evidence": evidence,
        "notes": "mechanical mixed-source smoke case",
    })
    labels.append({
        "id": case_id,
        "gold_status": gold,
        "gold_current_value": current,
        "gold_support": support,
    })


async def _stable_cases(cases: list[dict], labels: list[dict]) -> None:
    facts = [
        (
            "https://docs.python.org/3.12/whatsnew/3.12.html",
            "Python 3.12 于 2023 年发布",
            "fresh",
            "",
        ),
        (
            "https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/404",
            "HTTP 404 表示 Not Found",
            "fresh",
            "",
        ),
        (
            "https://www.rfc-editor.org/rfc/rfc9110",
            "HTTP 404 表示 Not Found",
            "fresh",
            "",
        ),
    ]
    for index, (url, claim, status, current) in enumerate(facts):
        text = await fetch_text(url)
        if not text:
            continue
        text = html_to_text(text)[:5000]
        snapshot_id = f"mix_stable_{index}"
        path = OUT / "snapshots" / f"{snapshot_id}.txt"
        path.write_text(text, encoding="utf-8")
        evidence = [{
            "url": url,
            "published_at": "2025-01-01",
            "content_hash": "sha256:" + hashlib.sha256(text.encode()).hexdigest(),
            "snapshot_path": str(path.relative_to(OUT)),
        }]
        _add(
            cases, labels,
            case_id=snapshot_id, family=f"official:{url.split('/')[2]}",
            claim_text=claim, as_of="2026-11-01", gold=status,
            current=current, support="supports", evidence=evidence,
            claim_type="other", sensitivity="stable",
        )


async def build() -> None:
    (OUT / "snapshots").mkdir(parents=True, exist_ok=True)
    cases: list[dict] = []
    labels: list[dict] = []
    for package in PACKAGES:
        try:
            pypi, repo = _pypi(package)
        except Exception as exc:  # noqa: BLE001 - skip unavailable packages
            print(f"skip pypi {package}: {type(exc).__name__}")
            continue
        if not pypi:
            continue
        if repo:
            try:
                github = _github(repo)
            except Exception as exc:  # noqa: BLE001 - skip unavailable repo
                print(f"skip github {package}: {type(exc).__name__}")
                github = []
            dates = sorted({when.date() for _, when in [*pypi, *github]})
            for date in dates:
                p_latest = _latest(pypi, date)
                g_latest = _latest(github, date)
                if p_latest and g_latest and p_latest != g_latest:
                    text_p = _snapshot(package, p_latest, pypi, date)
                    text_g = _snapshot(package, g_latest, github, date)
                    p_path = OUT / "snapshots" / f"mix_{package}_pypi.txt"
                    g_path = OUT / "snapshots" / f"mix_{package}_github.txt"
                    p_path.write_text(text_p, encoding="utf-8")
                    g_path.write_text(text_g, encoding="utf-8")
                    evidence = [
                        {
                            "url": f"https://pypi.org/project/{package}/#history",
                            "published_at": date.isoformat(),
                            "content_hash": "sha256:" + hashlib.sha256(text_p.encode()).hexdigest(),
                            "snapshot_path": str(p_path.relative_to(OUT)),
                        },
                        {
                            "url": f"https://github.com/{repo}/releases",
                            "published_at": date.isoformat(),
                            "content_hash": "sha256:" + hashlib.sha256(text_g.encode()).hexdigest(),
                            "snapshot_path": str(g_path.relative_to(OUT)),
                        },
                    ]
                    _add(
                        cases, labels,
                        case_id=f"mix_{package}_conflict",
                        family=f"mixed:{package}",
                        claim_text=f"{package} 当前版本是 {p_latest}",
                        as_of=date.isoformat(),
                        gold="conflicted", current=p_latest, support="contradicts",
                        evidence=evidence,
                    )
                    break
    for index, claim in enumerate([
        "该项目将在 2030 年成为行业第一",
        "该团队明年会发布下一个大版本",
        "未来五年该项目不会改变许可证",
    ]):
        _add(
            cases, labels,
            case_id=f"mix_unknown_{index}", family="semantic:unverifiable",
            claim_text=claim, as_of="2026-11-01", gold="unknown",
            current="", support="mentions", evidence=[], claim_type="other",
        )
    for index, package in enumerate(PACKAGES[:3]):
        _add(
            cases, labels,
            case_id=f"mix_insufficient_{index}", family=f"semantic:{package}",
            claim_text=f"{package} 当前版本是 0.0.1", as_of="2026-11-01",
            gold="insufficient", current="", support="mentions", evidence=[],
        )
    await _stable_cases(cases, labels)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mixed.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in cases) + "\n",
        encoding="utf-8",
    )
    holdout = OUT / "mechanical_holdout"
    holdout.mkdir(parents=True, exist_ok=True)
    (holdout / "mixed_labels.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in labels) + "\n",
        encoding="utf-8",
    )
    print(f"mixed_cases={len(cases)} labels={len(labels)}")


if __name__ == "__main__":
    asyncio.run(build())

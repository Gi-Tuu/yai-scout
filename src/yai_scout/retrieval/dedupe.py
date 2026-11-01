"""URL 归一化与去重。

同一篇内容常以不同 URL 出现（utm 参数、锚点、www、尾斜杠、AMP 页面）。
G0 先做确定性归一化（canonical URL），近重复文本合并（SimHash）放到证据层迭代。
"""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {
    "gclid",
    "fbclid",
    "msclkid",
    "yclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "source",
    "spm",
    "from",
}


def canonicalize_url(url: str) -> str:
    """返回用于去重的 canonical URL；解析失败时原样返回去空白结果。"""
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw
    scheme = (parts.scheme or "https").lower()
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    netloc = host
    if parts.port and not (
        (scheme == "http" and parts.port == 80) or (scheme == "https" and parts.port == 443)
    ):
        netloc = f"{host}:{parts.port}"
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith(TRACKING_PREFIXES) and k.lower() not in TRACKING_KEYS
    ]
    query = urlencode(sorted(kept))
    return urlunsplit((scheme, netloc, path, query, ""))


def dedupe_sources[T](items: list[T], *, key: Callable[[T], str]) -> list[T]:
    """按 key 去重，保留首次出现顺序。"""
    seen: set[str] = set()
    out: list[T] = []
    for item in items:
        k = key(item)
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(item)
    return out

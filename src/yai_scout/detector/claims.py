"""Claim 抽取（规则版，可离线运行）。

设计：只抽"可能过时"的事实句——含价格/版本/法规/人事/日期/统计数据信号的句子。
有模型 key 时可替换为 LLM 抽取（接口不变）；规则版保证无 key 也能演示与测试。
"""

from __future__ import annotations

import re
import uuid

from ..claim_classification import classify
from ..domain.models import Claim, ClaimType

SENTENCE_SPLIT_RE = re.compile(r"(?<!\d)[.!?](?!\d)|[。！？]|\n+")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)+|\d[\d,]*")
MAX_CLAIM_CHARS = 400
MIN_CLAIM_CHARS = 12
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.I)
CITATION_RE = re.compile(r"^(?:来源|source|参考|链接|引用)\s*[:：]?\s*", re.I)


def normalize_number(raw: str) -> str:
    cleaned = raw.replace("$", "").replace("€", "").replace("£", "")
    return cleaned.replace("¥", "").replace(",", "").strip()


def extract_numbers(text: str) -> list[str]:
    out: list[str] = []
    for match in NUMBER_RE.finditer(text):
        value = normalize_number(match.group(0))
        if value and value not in out:
            out.append(value)
    return out


def split_sentences(text: str) -> list[str]:
    """按句末标点切分，但不切开版本号/小数或 URL。"""
    urls: list[str] = []

    def protect(match: re.Match[str]) -> str:
        urls.append(match.group(0))
        return f" __URL_{len(urls) - 1}__ "

    protected = URL_RE.sub(protect, text)
    parts = [
        part.strip()
        for part in SENTENCE_SPLIT_RE.split(protected)
        if part.strip()
    ]
    restored: list[str] = []
    for part in parts:
        for index, url in enumerate(urls):
            part = part.replace(f"__URL_{index}__", url)
        restored.append(part)
    return restored


def strip_urls(text: str) -> str:
    return URL_RE.sub(" ", text)


def is_citation_only(text: str) -> bool:
    """True when a sentence is just a citation/URL, not a factual claim."""
    residual = CITATION_RE.sub("", strip_urls(text))
    residual = residual.strip(" \t\r\n,，.。;；:：!?！？")
    if not residual:
        return True
    # Keep short fact-bearing text such as "0.24.0 来源：..." but drop
    # citation scaffolding that has no fact content.
    return len(residual) < MIN_CLAIM_CHARS and not re.search(r"\d", residual)


def extract_claims(answer: str, *, max_claims: int = 8) -> list[Claim]:
    """从一段 LLM 答案中抽取可能过时的事实句。"""
    claims: list[Claim] = []
    seen: set[str] = set()
    for text in split_sentences(answer):
        if not text or text.endswith("?") or text.endswith("？"):
            continue
        if not (MIN_CLAIM_CHARS <= len(text) <= MAX_CLAIM_CHARS):
            continue
        if is_citation_only(text):
            continue
        claim_type, signals = classify(text)
        if claim_type is ClaimType.OTHER:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        claims.append(
            Claim(
                id=f"cl_{uuid.uuid4().hex[:8]}",
                text=text,
                type=claim_type,
                numbers=extract_numbers(text),
                signals=signals,
            )
        )
        if len(claims) >= max_claims:
            break
    return claims


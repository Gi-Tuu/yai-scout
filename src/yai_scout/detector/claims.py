"""Claim 抽取（规则版，可离线运行）。

设计：只抽"可能过时"的事实句——含价格/版本/法规/人事/日期/统计数据信号的句子。
有模型 key 时可替换为 LLM 抽取（接口不变）；规则版保证无 key 也能演示与测试。
"""

from __future__ import annotations

import re
import uuid

from ..domain.models import Claim, ClaimType

SENTENCE_SPLIT_RE = re.compile(r"(?<!\d)[.!?](?!\d)|[。！？]|\n+")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)+|\d[\d,]*")
MAX_CLAIM_CHARS = 400
MIN_CLAIM_CHARS = 12

# 顺序即优先级：价格 > 版本 > 法规 > 人事 > 统计 > 日期
SIGNALS: list[tuple[ClaimType, re.Pattern[str], str]] = [
    (
        ClaimType.PRICING,
        re.compile(
            r"[$€£¥]\s?\d|\b(?:USD|EUR|CNY|RMB|dollars?|euros?)\b"
            r"|\b(?:pricing|price|cost|per month|/mo|subscription|billing|credits?)\b"
            r"|免费|价格|费用|收费|每月|每年|订阅|美元|人民币",
            re.I,
        ),
        "price",
    ),
    (
        ClaimType.VERSION,
        re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b|\bversion\b|\brelease\b|版本|发布|端口|port", re.I),
        "version",
    ),
    (
        ClaimType.LAW,
        re.compile(
            r"\b(?:law|act|regulation|directive|bill|policy|effective|compliance)\b"
            r"|\b(?:GDPR|AI Act|EU AI Act)\b|法律|法规|法案|生效|监管|合规|许可证|license",
            re.I,
        ),
        "law",
    ),
    (
        ClaimType.LEADERSHIP,
        re.compile(
            r"\b(?:CEO|CTO|CFO|COO|founder|president|chairman|head of"
            r"|appointed|resigned|steps down)\b|创始人|总裁|辞任|任命",
            re.I,
        ),
        "leadership",
    ),
    (
        ClaimType.STATISTIC,
        re.compile(
            r"\b\d+(?:\.\d+)?\s?(?:%|percent|million|billion|thousand"
            r"|users|customers|registrations|downloads)\b|用户|增长|占比",
            re.I,
        ),
        "statistic",
    ),
    (
        ClaimType.DATE,
        re.compile(
            r"\b(?:19|20)\d{2}\b|\b\d{4}年"
            r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b"
            r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b",
            re.I,
        ),
        "date",
    ),
]


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


def classify(text: str) -> tuple[ClaimType, list[str]]:
    for claim_type, pattern, label in SIGNALS:
        if pattern.search(text):
            return claim_type, [label]
    return ClaimType.OTHER, []


def split_sentences(text: str) -> list[str]:
    """按句末标点切分，但不切开 0.25.0 这类版本号/小数。"""
    return [part.strip() for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]


def extract_claims(answer: str, *, max_claims: int = 8) -> list[Claim]:
    """从一段 LLM 答案中抽取可能过时的事实句。"""
    claims: list[Claim] = []
    seen: set[str] = set()
    for text in split_sentences(answer):
        if not text or text.endswith("?") or text.endswith("？"):
            continue
        if not (MIN_CLAIM_CHARS <= len(text) <= MAX_CLAIM_CHARS):
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


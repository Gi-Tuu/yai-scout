from __future__ import annotations

import re

from ...domain.models import Claim, ClaimType
from ...retrieval.tavily import SearchResult
from ..claims import extract_numbers
from .patterns import (
    CURRENCY_CODES,
    CURRENCY_SYMBOLS,
    CURRENCY_WORDS,
    PERIODS,
    YEAR_TOKEN_RE,
)
from .types import Relation
from .versions import evidence_text


def claim_numbers(claim: Claim) -> list[str]:
    return [number for number in claim.numbers if not YEAR_TOKEN_RE.fullmatch(number)]


def result_numbers(text: str) -> list[str]:
    return [
        number
        for number in extract_numbers(text)
        if not YEAR_TOKEN_RE.fullmatch(number)
    ]


def unit_tokens(text: str) -> set[str]:
    units: set[str] = set()
    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in text:
            units.add(code)
    for code in CURRENCY_CODES:
        if re.search(rf"\b{code}\b", text):
            units.add(code)
    for word, code in CURRENCY_WORDS.items():
        if word in text:
            units.add(code)
    if re.search(r"\bcredits?\b", text):
        units.add("credits")
    if "%" in text:
        units.add("pct")
    for period in PERIODS:
        if re.search(rf"\b{period}\b", text):
            units.add(f"period:{period}")
    return units


def units_conflict(claim_units: set[str], result_units: set[str]) -> bool:
    if not claim_units or not result_units:
        return False
    if claim_units.isdisjoint(result_units):
        return True
    claim_periods = {unit for unit in claim_units if unit.startswith("period:")}
    result_periods = {unit for unit in result_units if unit.startswith("period:")}
    if claim_periods and result_periods and claim_periods != result_periods:
        return True
    claim_currencies = {unit for unit in claim_units if unit in CURRENCY_CODES}
    result_currencies = {unit for unit in result_units if unit in CURRENCY_CODES}
    if claim_currencies and result_currencies and claim_currencies != result_currencies:
        return True
    if "credits" in claim_units and result_currencies:
        return True
    return bool(claim_currencies) and "credits" in result_units


def classify_numeric_relation(claim: Claim, result: SearchResult) -> Relation:
    text = evidence_text(result)
    numbers = claim_numbers(claim)
    if not numbers:
        return "mentions"
    claim_units = unit_tokens(claim.text.lower())
    result_units = unit_tokens(text)
    if units_conflict(claim_units, result_units):
        return "contradicts"
    result_number_values = result_numbers(text)
    if all(number in result_number_values for number in numbers):
        if claim_units and not (claim_units & result_units):
            return "mentions"
        return "supports"
    if claim.type in {ClaimType.PRICING, ClaimType.STATISTIC} and result_number_values:
        return "contradicts"
    return "mentions"

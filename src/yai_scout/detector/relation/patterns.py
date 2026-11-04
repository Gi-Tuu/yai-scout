"""Regular expressions and unit/currency constants for relation classifiers."""
from __future__ import annotations

import re

VERSION_TOKEN_RE = re.compile(r"v?\d+\.\d+(?:\.\d+)?", re.I)
LATEST_RE = re.compile(r"latest|current|newest|最新|当前|现在", re.I)
RELEASE_URL_RE = re.compile(
    r"(?:releases?/tag|/tag/)(v?\d+\.\d+(?:\.\d+)?)", re.I
)
RELEASE_TITLE_RE = re.compile(
    r"^(?:release|version)\s+v?\d+\.\d+(?:\.\d+)?$", re.I
)
HISTORICAL_RE = re.compile(
    r"previous|prior|older|old|deprecated|历史|上一|旧版|旧版本", re.I
)
CURRENT_CLAIM_RE = re.compile(r"current|latest|最新|当前|现在", re.I)
HISTORICAL_CLAIM_RE = re.compile(r"previous|prior|older|历史|上一|旧版", re.I)
HISTORICAL_RELEASE_RE = re.compile(
    r"(?:于|在)\s*(?:19|20)\d{2}\s*年[^。；;]{0,24}(?:发布|推出|上线|成立)"
    r"|(?:released?|release date)\s*(?:in|:)?\s*(?:19|20)\d{2}",
    re.I,
)
YEAR_TOKEN_RE = re.compile(r"(?:19|20)\d{2}")

CURRENCY_CODES = {"usd": "usd", "eur": "eur", "gbp": "gbp", "cny": "cny", "jpy": "jpy"}
CURRENCY_SYMBOLS = {"$": "usd", "€": "eur", "£": "gbp", "¥": "cny"}
CURRENCY_WORDS = {"美元": "usd", "欧元": "eur", "英镑": "gbp", "人民币": "cny"}
PERIODS = {"month", "year", "day", "week", "quarter"}

"""Stale-answer Detector。"""

from .claims import extract_claims
from .service import StaleAnswerDetector

__all__ = ["StaleAnswerDetector", "extract_claims"]

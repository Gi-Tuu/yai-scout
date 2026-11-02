# YAI Scout v0.3.2 — typed candidates + capped live fetch

Follow-up to the 2026-11-02 audit.

## Fixed

- **B1**: candidate evidence is now the typed `CandidateEvidence` model, not `dict[str, Any]`.
- **B2**: `AnchorCandidate.gate_decision` is a `Literal["auto_update","review","reject","no_change"]`.
- **B3**: live anchor fetch streams via `aiter_bytes` and stops at `LIVE_MAX_BYTES`; the response is always closed.

## Verification

```text
ruff  : pass
mypy  : pass
pytest: 141 passed
```

No product-scope change: still one primary submission, Tavily Track Problem 05, with Tavily + Bifrost. `AUTO_UPDATE` remains false.

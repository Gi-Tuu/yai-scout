# Verify / Relation Layout

`verify.py` is orchestration only.

```text
verify.py
  ClaimVerifier.verify()
  compatibility proxies:
    _relation / _to_evidence / build_query

verify_steps.py
  fetch_anchors / search / failure_verdict
  prepare_results / upgrade_pages / dedupe
  build_evidence / score / attach_anchor

query.py       build_query
evidence.py    to_evidence / relation_reason / domain
llm_relation.py prompt + claim-level LLM relation

relation/
  types.py       Relation
  patterns.py    regex + currency/period constants
  versions.py    version parsing + version decision table
  project.py     project identity overlap
  numeric.py     numbers/units/currency/period
  dates.py       explicit-date rule
  classify.py    top-level relation dispatcher
```

Compatibility wrappers on `ClaimVerifier` remain so existing tests and callers
do not need to change. Pure classifiers do not import `verify`, `store` or `api`.

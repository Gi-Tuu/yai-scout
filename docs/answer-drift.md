# Answer Drift Diff

Existing endpoint: `GET /freshness/compare?left_id=...&right_id=...`.

Incremental changes:

- same-URL `content_hash` changed;
- evidence kind changed (`search_snippet` / `fetched_page` / ...);
- publication date changed;
- existing evidence-added / evidence-removed / numeric / status / score diff.

The `mode` warning is preserved: cross-as_of comparisons without snapshots are
`simulated`, not a claim of real historical retrieval.

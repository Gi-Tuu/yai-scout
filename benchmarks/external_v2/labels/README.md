# V2 Label Files

Do not put mechanical labels here.

For L2, create:

```text
labels/labeler_a.jsonl  {"id": "...", "status": "fresh|stale|conflicted|insufficient|unknown"}
labels/labeler_b.jsonl
labels/adjudicated.jsonl
```

Run:

```powershell
.\.venv\Scripts\python.exe scripts\check_external_labels.py `
  --a labels\labeler_a.jsonl `
  --b labels\labeler_b.jsonl `
  --adjudicated labels\adjudicated.jsonl
```

The command must report `passes_kappa: true` before L2 test labels are opened.

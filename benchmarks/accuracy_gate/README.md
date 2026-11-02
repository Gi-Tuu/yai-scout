# Accuracy Gate — labels and private worksheet

## Public 60-case set (compromised)

`labeled_cases.json`, `holdout_worksheet.json`, `holdout_key.json`, and
`independent_labels_001.json` are **public**. The key has been visible in the
repository, so:

- 60/60 agreement is **rule-following**, not independent generalization;
- do not use this set to claim Auto-update Precision or False Update Rate;
- keep `AUTO_UPDATE=false`.

## Private worksheet (no answers in repo)

`private_worksheet.json` contains **30 cases and no expected decisions**. It is
safe to serve publicly; the labels are the private part.

Open:

```text
https://yai-scout.onrender.com/label?worksheet=private
```

or locally `/label?worksheet=private`.

The annotator exports `accuracy_labels_private_<name>.json`; **do not commit
that file**. `.gitignore` excludes it.

## Evaluate

```powershell
python scripts/eval_accuracy_gate.py `
  --worksheet benchmarks/accuracy_gate/private_worksheet.json `
  --labels accuracy_labels_private_<name>.json
```

Reports agreement, Auto-update Precision, False Update Rate, Review Coverage.

## Two annotators / adjudication

```powershell
python scripts/adjudicate_labels.py `
  --a accuracy_labels_private_a.json `
  --b accuracy_labels_private_b.json `
  --out adjudication_disagreements.json
```

Only adjudicated labels should be used as ground truth. Keep both raw label
files, but do not commit them.

## Quality gate

```powershell
python scripts/check_label_quality.py `
  --worksheet benchmarks/accuracy_gate/private_worksheet.json `
  --labels accuracy_labels_private_<name>.json
```

Incomplete files or impossible `no_change` answers are rejected before evaluation.

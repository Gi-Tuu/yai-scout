"""Build a labeler packet with claim, as_of and frozen evidence; no gold labels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "benchmarks" / "external_v1"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(EXTERNAL / "test.jsonl"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    rows = [
        json.loads(line)
        for line in Path(args.data).read_text(encoding="utf-8").splitlines()
        if line
    ]
    packet = []
    for row in rows:
        evidence = []
        for item in row.get("evidence", []):
            snapshot = (EXTERNAL / item["snapshot_path"]).read_text(encoding="utf-8")
            evidence.append({
                "url": item["url"],
                "published_at": item.get("published_at"),
                "content_hash": item.get("content_hash"),
                "content": snapshot,
            })
        packet.append({
            "id": row["id"],
            "claim_text": row["claim_text"],
            "claim_type": row.get("claim_type"),
            "as_of": row["as_of"],
            "evidence": evidence,
        })
    Path(args.out).write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in packet) + "\n",
        encoding="utf-8",
    )
    print(f"packet_cases={len(packet)} out={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

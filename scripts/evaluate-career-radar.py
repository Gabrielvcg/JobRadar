"""Evaluate a saved public/synthetic RawJob sample without database or HTTP access."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.enums import RemoteType  # noqa: E402
from app.scoring.engine import ScoringEngine  # noqa: E402
from app.services.ingestion import _matches_search_scope  # noqa: E402
from app.services.normalizer import JobNormalizer  # noqa: E402
from app.sources.base import RawJob  # noqa: E402
from app.sources.registry import load_search_config  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample", type=Path)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    normalizer = JobNormalizer()
    engine = ScoringEngine(as_of=args.as_of)
    search = load_search_config()
    rows = []
    fields = RawJob.__dataclass_fields__
    for item in json.loads(args.sample.read_text(encoding="utf-8")):
        item = {key: value for key, value in item.items() if key in fields}
        for key in ("publication_date", "expiration_date"):
            if item.get(key):
                item[key] = datetime.fromisoformat(item[key].replace("Z", "+00:00"))
        item["remote_type"] = RemoteType(item.get("remote_type", "unknown"))
        raw = RawJob(**item)
        job = normalizer.normalize(raw)
        score = engine.score(job)
        rows.append(
            {
                "id": raw.source_name + ":" + str(raw.source_job_id),
                "title": job.title,
                "company": job.company_name,
                "url": job.url,
                "location": job.location,
                "scope": _matches_search_scope(job, search),
                "experience": job.experience_min_years,
                "technologies": job.technologies,
                "content_hash": job.content_hash,
                **asdict(score),
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2, ensure_ascii=True), encoding="utf-8")
    accepted = [
        row
        for row in rows
        if row["scope"] and row["score"] >= 35 and row["assessment"]["radar"] == "current"
    ]
    print(
        json.dumps(
            {
                "sample": len(rows),
                "current_35_plus": len(accepted),
                "radars": Counter(row["assessment"]["radar"] for row in rows),
                "blockers": Counter(b for row in rows for b in row["assessment"]["blockers"]),
                "top": [
                    {k: row[k] for k in ("id", "company", "title", "score", "location")}
                    for row in sorted(accepted, key=lambda row: row["score"], reverse=True)[:20]
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

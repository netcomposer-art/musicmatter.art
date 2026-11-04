#!/usr/bin/env python3
"""
Publish Peter's Library decisions on the VCSL seed (review.json): mark each reviewed manifest approved or rejected, and
merge them into library.json, the index NYX searches (approved sounds only, library/library.json). Sounds already
listed stay listed. Harvested (Freesound) batches use publish_harvest.py. Rejected sounds' audio and manifests are removed from the site; the
review record keeps them out of later harvests.

Usage:  python3 tools/library/publish.py decisions.json
decisions.json: {"<candidate id>": {"status": "approved"|"rejected"|"pending", "role"?: str, "tags"?: [str],
                 "at"?: ISO, "by"?: str}, ...}  (the review page's "decisions" collection, keyed by id)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog import LIB, SITE, entry_for, normalize_decisions, read_rejected, write_library, write_rejected  # noqa: E402



def main() -> int:
    decisions = normalize_decisions(json.loads(Path(sys.argv[1]).read_text()))
    review = json.loads((LIB / "review.json").read_text())
    rejected = read_rejected()
    approved: dict[str, dict] = {}
    removed: set[str] = set()
    keep_candidates = []
    for cand in review["candidates"]:
        cid = cand["id"]
        d = decisions.get(cid, {})
        status = d.get("status", "pending")
        man_path = SITE / cand["manifest"].split("musicmatter.art/", 1)[1]
        audio_path = SITE / cand["audio"].split("musicmatter.art/", 1)[1]
        if not man_path.exists():
            continue
        manifest = json.loads(man_path.read_text())
        role = d.get("role") or manifest["role"]
        tags = d.get("tags") or manifest["tags"]
        if status == "rejected":
            removed.add(cid)
            rejected[cid] = {"source": manifest["source"], "at": d.get("at"), "title": manifest["title"]}
            man_path.unlink()
            audio_path.unlink(missing_ok=True)
            continue
        if role != manifest["role"]:
            # Move the files under the new role so paths stay readable.
            new_audio = LIB / "audio" / role / audio_path.name
            new_man = LIB / "manifests" / role / man_path.name
            new_audio.parent.mkdir(parents=True, exist_ok=True)
            new_man.parent.mkdir(parents=True, exist_ok=True)
            audio_path.rename(new_audio)
            man_path.unlink()
            audio_path, man_path = new_audio, new_man
            manifest["audio"] = "https://musicmatter.art/" + new_audio.relative_to(SITE).as_posix()
        manifest["role"] = role
        manifest["tags"] = sorted(set(tags) | {role})
        if status == "approved":
            manifest["curation"] = {"status": "approved", "by": "Peter", "at": (d.get("at") or "")[:10]}
        else:
            manifest["curation"] = {"status": "pending"}
        man_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        man_url = "https://musicmatter.art/" + man_path.relative_to(SITE).as_posix()
        if status == "approved":
            approved[cid] = entry_for(cid, manifest, man_url, audio_path)
        else:
            removed.add(cid)
            keep_candidates.append({**cand, "role": role, "tags": manifest["tags"], "manifest": man_url,
                                    "audio": manifest["audio"]})
    listed = write_library(approved, removed)
    review["candidates"] = keep_candidates
    review["count"] = len(keep_candidates)
    (LIB / "review.json").write_text(json.dumps(review, indent=1) + "\n")
    write_rejected(rejected)
    print(f"{len(approved)} approved this run, {listed} in library.json, {len(keep_candidates)} still pending, {len(rejected)} rejected in total")
    return 0


if __name__ == "__main__":
    sys.exit(main())

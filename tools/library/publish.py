#!/usr/bin/env python3
"""
Publish Peter's Library decisions: mark each reviewed manifest approved or rejected, and write library.json, the
index NYX searches (approved sounds only). Rejected sounds' audio and manifests are removed from the site; the
review record keeps them out of later harvests.

Usage:  python3 tools/library/publish.py decisions.json
decisions.json: {"<candidate id>": {"status": "approved"|"rejected"|"pending", "role"?: str, "tags"?: [str],
                 "at"?: ISO, "by"?: str}, ...}  (the review page's "decisions" collection, keyed by id)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[2]
LIB = SITE / "library"


def main() -> int:
    decisions: dict = json.loads(Path(sys.argv[1]).read_text())
    review = json.loads((LIB / "review.json").read_text())
    rejected_log = LIB / "rejected.json"
    rejected = json.loads(rejected_log.read_text()) if rejected_log.exists() else {}
    entries = []
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
            entries.append({
                "id": cid, "role": role, "title": manifest["title"], "tags": manifest["tags"],
                "license": manifest["license"], "creator": manifest["creator"]["name"],
                "audio": manifest["audio"], "manifest": man_url, "sha256": manifest["sha256"],
                "measures": manifest["measures"],
            })
        else:
            keep_candidates.append({**cand, "role": role, "tags": manifest["tags"], "manifest": man_url,
                                    "audio": manifest["audio"]})
    entries.sort(key=lambda e: (e["role"], e["title"]))
    (SITE / "library.json").write_text(json.dumps({
        "nc_version": "0.2",
        "name": "musicmatter.art Library",
        "description": "Curated, openly licensed one-shots. Every sound keeps its original creator and license; "
                       "musicmatter.art is the curator. Approved by a person before listing.",
        "curator": {"name": "musicmatter.art", "link": "https://musicmatter.art/"},
        "licenses": ["CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0"],
        "count": len(entries),
        "sounds": entries,
    }, indent=1, ensure_ascii=False) + "\n")
    review["candidates"] = keep_candidates
    review["count"] = len(keep_candidates)
    (LIB / "review.json").write_text(json.dumps(review, indent=1) + "\n")
    rejected_log.write_text(json.dumps(rejected, indent=1) + "\n")
    print(f"{len(entries)} approved in library.json, {len(keep_candidates)} still pending, {len(rejected)} rejected in total")
    return 0


if __name__ == "__main__":
    sys.exit(main())

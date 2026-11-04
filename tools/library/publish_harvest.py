#!/usr/bin/env python3
"""
Publish Peter's decisions on a harvested batch (Freesound candidates pulled with fetch_review.py).

For every candidate in BATCH/batch.json:
  approved  copy BATCH/audio/<id>.flac to library/audio/<role>/<id>.flac (sha256 checked), write
            library/manifests/<role>/<id>.nc.json (curation approved, level-matched playback gain measured here the
            way level_match.py does), and add it to library.json
  rejected  log it in library/rejected.json (source, reason, date) so it is never harvested again
  pending   left alone; it stays in the Worker's queue for the next review
Then tell the Worker (POST /api/library/admin/decisions) so approved and rejected sounds leave the queue for good.

Credit stays with the original creator (Freesound username and link) under their license; musicmatter.art is the
curator. library.json is merged, so the VCSL seed and earlier batches stay listed.

Usage:  NC_ADMIN_TOKEN=... python3 tools/library/publish_harvest.py decisions.json BATCH [--api URL] [--no-notify]
        python3 tools/library/publish_harvest.py decisions.json BATCH --notify-only   (after a failed notify)
decisions.json: the review page's "decisions" collection ({id: {status, role?, tags?, at?, note?}}, or a list of docs).
Needs: ffmpeg, numpy, soundfile, pyloudnorm.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog import (LIB, SITE, entry_for, normalize_decisions, read_rejected, site_url,  # noqa: E402
                     write_library, write_rejected)
from measures import hit_db, playback_gain, playback_method  # noqa: E402

API = "https://nc-perform-api.psemme.workers.dev"
ROLES = {"kick", "snare", "clap", "hat", "tom", "perc", "cymbal", "fx", "tonal"}


def notify(api: str, token: str, decided: dict[str, dict]) -> dict:
    body = json.dumps({"decisions": decided}).encode()
    req = urllib.request.Request(f"{api.rstrip('/')}/api/library/admin/decisions", data=body, method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "musicmatter-library/1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def publish(decisions: dict, batch_dir: Path, site: Path = SITE, by: str = "Peter") -> tuple[dict[str, dict], list[str]]:
    """Write approved sounds and rejections into the site. Returns (what to tell the Worker, problems)."""
    lib = site / "library"
    batch = json.loads((batch_dir / "batch.json").read_text())
    rejected = read_rejected(lib)
    approved: dict[str, dict] = {}
    removed: set[str] = set()
    decided: dict[str, dict] = {}
    problems: list[str] = []
    for cand in batch.get("candidates", []):
        cid, manifest = cand["id"], dict(cand["manifest"])
        d = decisions.get(cid) or {}
        status = d.get("status", "pending")
        at = d.get("at") or ""
        if status == "rejected":
            removed.add(cid)
            rejected[cid] = {"source": manifest["source"], "at": at or None, "title": manifest["title"],
                             **({"reason": d["note"]} if d.get("note") else {})}
            decided[cid] = {"status": "rejected", **({"at": at} if at else {}), **({"note": d["note"]} if d.get("note") else {})}
            continue
        if status != "approved":
            continue
        src = batch_dir / "audio" / f"{cid}.flac"
        if not src.exists() or hashlib.sha256(src.read_bytes()).hexdigest() != manifest["sha256"]:
            problems.append(f"{cid}: audio missing or does not match its sha256; left pending")
            continue
        role = d.get("role") if d.get("role") in ROLES else manifest["role"]
        tags = d.get("tags") or manifest.get("tags") or []
        audio = lib / "audio" / role / f"{cid}.flac"
        man_path = lib / "manifests" / role / f"{cid}.nc.json"
        audio.parent.mkdir(parents=True, exist_ok=True)
        man_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, audio)
        # A harvested sound is its own family: its hit goes to the target, its peak stays under the ceiling.
        h, p = hit_db(audio)
        gain, limited = playback_gain(h, p)
        manifest["role"] = role
        manifest["tags"] = sorted(set(tags) | {role})
        manifest["audio"] = site_url(audio, site)
        manifest["measures"] = {**manifest["measures"], "hit_dbfs": round(h, 1)}
        manifest["playback"] = {"gain_db": gain, "method": playback_method(), **({"limited_by_peak": True} if limited else {})}
        manifest["curation"] = {"status": "approved", "by": by, "at": at[:10]}
        manifest.pop("review_note", None)
        man_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        approved[cid] = entry_for(cid, manifest, site_url(man_path, site), audio)
        decided[cid] = {"status": "approved", **({"at": at} if at else {})}
    write_library(approved, removed, lib)
    write_rejected(rejected, lib)
    return decided, problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("decisions", type=Path)
    ap.add_argument("batch", type=Path)
    ap.add_argument("--api", default=os.environ.get("NC_PERFORM_API", API))
    ap.add_argument("--by", default="Peter")
    ap.add_argument("--no-notify", action="store_true", help="write the site only; do not tell the Worker")
    ap.add_argument("--notify-only", action="store_true", help="only tell the Worker (after the site was written)")
    args = ap.parse_args(argv)
    decisions = normalize_decisions(json.loads(args.decisions.read_text()))
    if args.notify_only:
        batch = json.loads((args.batch / "batch.json").read_text())
        decided = {c["id"]: {"status": decisions[c["id"]]["status"]} for c in batch.get("candidates", [])
                   if (decisions.get(c["id"]) or {}).get("status") in ("approved", "rejected")}
        problems: list[str] = []
    else:
        decided, problems = publish(decisions, args.batch, by=args.by)
        n_ok = sum(1 for d in decided.values() if d["status"] == "approved")
        listed = json.loads((LIB / "library.json").read_text())["count"]
        print(f"{n_ok} approved, {len(decided) - n_ok} rejected; library.json lists {listed} sounds")
    for p in problems:
        print(f"! {p}", file=sys.stderr)
    if args.no_notify or not decided:
        return 1 if problems else 0
    token = os.environ.get("NC_ADMIN_TOKEN", "").strip()
    if not token:
        print("NC_ADMIN_TOKEN is not set: the site is written, the Worker was not told. "
              "Run again with --notify-only once it is set.", file=sys.stderr)
        return 2
    try:
        result = notify(args.api, token, decided)
    except (urllib.error.URLError, OSError) as e:
        print(f"Could not tell the Worker ({e}). The site is written; run again with --notify-only.", file=sys.stderr)
        return 2
    print(f"Worker: {len(result.get('approved', []))} approved, {len(result.get('rejected', []))} rejected"
          + (f", unknown {result['unknown']}" if result.get("unknown") else ""))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

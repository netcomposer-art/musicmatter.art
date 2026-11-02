#!/usr/bin/env python3
"""
Pull the Library harvester's review queue from nc-perform-api and build the review page for it.

The nightly harvest (nc-performer, service/worker/src/library/) searches Freesound, keeps openly licensed one-shots,
measures them and queues them for Peter. This script downloads that queue (pending candidates only) into OUT:

  OUT/index.html          the "Library Review" page, with these candidates (template: tools/library/review/template.html)
  OUT/previews/<id>.mp3   level-matched previews the page plays (publish them with the page, as files)
  OUT/audio/<id>.flac     the 24-bit FLAC each candidate becomes on approval (checked against its sha256)
  OUT/batch.json          the candidates' manifests, for publish_harvest.py

Then republish the Library Review artifact from OUT (index.html plus previews/*.mp3). Peter's choices land in the
page's "decisions" collection; export it to a JSON file and run publish_harvest.py.

Usage:  NC_ADMIN_TOKEN=... python3 tools/library/fetch_review.py OUT [--api https://nc-perform-api.psemme.workers.dev]
Needs:  Python 3.10+ (standard library only).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog import LIB, read_library, read_rejected  # noqa: E402

API = "https://nc-perform-api.psemme.workers.dev"
TEMPLATE = Path(__file__).resolve().parent / "review" / "template.html"
ROLE_ORDER = ["kick", "snare", "clap", "hat", "tom", "perc", "cymbal", "fx", "tonal"]


def get(url: str, token: str) -> bytes:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "User-Agent": "musicmatter-library/1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def https_or_none(url) -> str | None:
    return url if isinstance(url, str) and url.startswith("https://") else None


def card(cand: dict) -> dict:
    """What the review page shows for one candidate (the same fields the VCSL seed's page used, plus credit)."""
    m = cand["manifest"]
    measures = dict(m.get("measures") or {})
    measures["gain_db"] = (m.get("playback") or {}).get("gain_db", 0.0)
    src = m.get("source") or {}
    return {
        "id": cand["id"], "role": m["role"], "title": m["title"], "tags": m.get("tags") or [m["role"]],
        "measures": measures,
        "creator": (m.get("creator") or {}).get("name"), "creator_link": https_or_none((m.get("creator") or {}).get("link")),
        "license": m.get("license"), "license_url": https_or_none(m.get("license_url")),
        "source_url": https_or_none(src.get("url")), "quality": m.get("quality"),
        **({"note": cand["note"]} if cand.get("note") else {}),
    }


def subtitle(cards: list[dict]) -> str:
    roles = Counter(c["role"] for c in cards)
    parts = ", ".join(f"{roles[r]} {r}" for r in ROLE_ORDER if roles.get(r))
    previews = sum(1 for c in cards if c.get("quality") == "preview")
    note = f" {previews} came from Freesound's MP3 previews (marked) until the original-file login is connected." if previews else ""
    return (f"Harvested from Freesound: {len(cards)} openly licensed one-shots ({parts}), played level-matched. "
            f"Each keeps its creator and license.{note} Nothing reaches the Library until you approve it.")


def render(cards: list[dict], text: str) -> str:
    page = TEMPLATE.read_text()
    data = json.dumps(cards, ensure_ascii=False).replace("</", "<\\/")
    return page.replace("__CANDIDATES__", data).replace("__SUBTITLE__", html.escape(text))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("--api", default=os.environ.get("NC_PERFORM_API", API))
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args(argv)
    token = os.environ.get("NC_ADMIN_TOKEN", "").strip()
    if not token:
        print("Set NC_ADMIN_TOKEN (the Worker's admin token).", file=sys.stderr)
        return 2
    api = args.api.rstrip("/")
    try:
        doc = json.loads(get(f"{api}/api/library/admin/candidates?state=pending&limit={args.limit}", token))
    except urllib.error.HTTPError as e:
        print(f"Could not read the review queue: HTTP {e.code} {e.read()[:200]!r}", file=sys.stderr)
        return 1
    listed, rejected = read_library(LIB), read_rejected(LIB)
    out: Path = args.out
    (out / "previews").mkdir(parents=True, exist_ok=True)
    (out / "audio").mkdir(parents=True, exist_ok=True)
    kept, cards = [], []
    for cand in doc.get("candidates", []):
        cid, man = cand.get("id"), cand.get("manifest")
        if not cid or not man or not cand.get("files"):
            continue
        if cid in listed or cid in rejected:
            print(f"- {cid}: already decided on musicmatter.art, skipped")
            continue
        audio = get(cand["files"]["audio"], token)
        if hashlib.sha256(audio).hexdigest() != man.get("sha256"):
            print(f"! {cid}: audio does not match its sha256, skipped", file=sys.stderr)
            continue
        (out / "audio" / f"{cid}.flac").write_bytes(audio)
        (out / "previews" / f"{cid}.mp3").write_bytes(get(cand["files"]["preview"], token))
        kept.append({k: cand.get(k) for k in ("id", "batch", "quality", "query", "note", "manifest")})
        cards.append(card(cand))
        print(f"+ {man['role']:6} {cid}")
    cards.sort(key=lambda c: (ROLE_ORDER.index(c["role"]) if c["role"] in ROLE_ORDER else 99, c["title"].lower()))
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (out / "batch.json").write_text(json.dumps({"generated": now, "api": api, "count": len(kept), "candidates": kept},
                                               indent=1, ensure_ascii=False) + "\n")
    (out / "index.html").write_text(render(cards, subtitle(cards)))
    print(f"{len(kept)} candidates in {out}. Publish index.html with previews/*.mp3 as the Library Review page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

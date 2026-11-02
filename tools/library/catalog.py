"""
library.json and rejected.json: the parts publish.py (VCSL seed) and publish_harvest.py (Freesound harvest) share.

library.json is merged, never rebuilt from one batch: entries this run decides are added (approved) or removed
(rejected or back to pending), and every other entry stays. Before this, publish.py rebuilt library.json from
review.json alone, so a second run after review.json had emptied would have listed nothing.
"""
from __future__ import annotations

import json
from pathlib import Path

from measures import wave

SITE = Path(__file__).resolve().parents[2]
LIB = SITE / "library"
SITE_URL = "https://musicmatter.art"
BASE_LICENSES = ["CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0"]


def site_url(path: Path, site: Path = SITE) -> str:
    return f"{SITE_URL}/" + path.relative_to(site).as_posix()


def entry_for(cid: str, manifest: dict, man_url: str, audio_path: Path) -> dict:
    """One library.json row: enough for NYX to search, credit and play a sound without fetching its manifest."""
    return {
        "id": cid, "role": manifest["role"], "title": manifest["title"], "tags": manifest["tags"],
        "license": manifest["license"], "license_url": manifest.get("license_url"),
        "creator": manifest["creator"]["name"], "creator_link": manifest["creator"].get("link"),
        "source": {"origin": manifest["source"].get("origin"), "url": manifest["source"].get("url")},
        "audio": manifest["audio"], "manifest": man_url, "sha256": manifest["sha256"],
        # gain_db: the family level-match playback gain (the manifest's "playback"), so a player can sit the
        # sound at the uniform level without fetching its manifest.
        "measures": {**manifest["measures"],
                     "gain_db": (manifest.get("playback") or {}).get("gain_db", 0.0)},
        "wave": wave(audio_path),
        **({"quality": manifest["quality"]} if manifest.get("quality") else {}),
    }


def read_library(lib: Path = LIB) -> dict[str, dict]:
    path = lib / "library.json"
    if not path.exists():
        return {}
    return {e["id"]: e for e in json.loads(path.read_text()).get("sounds", [])}


def write_library(approved: dict[str, dict], removed: set[str], lib: Path = LIB) -> int:
    """Merge this run's decisions into library.json. Returns the number of sounds listed."""
    current = read_library(lib)
    for cid in removed:
        current.pop(cid, None)
    current.update(approved)
    entries = sorted(current.values(), key=lambda e: (e["role"], e["title"]))
    licenses = BASE_LICENSES + sorted({e["license"] for e in entries} - set(BASE_LICENSES))
    # Served at https://musicmatter.art/library/library.json, beside the audio and manifests it lists.
    (lib / "library.json").write_text(json.dumps({
        "nc_version": "0.2",
        "name": "musicmatter.art Library",
        "description": "Curated, openly licensed one-shots. Every sound keeps its original creator and license; "
                       "musicmatter.art is the curator. Approved by a person before listing.",
        "curator": {"name": "musicmatter.art", "link": "https://musicmatter.art/"},
        "licenses": licenses,
        "count": len(entries),
        "sounds": entries,
    }, indent=1, ensure_ascii=False) + "\n")
    return len(entries)


def read_rejected(lib: Path = LIB) -> dict:
    path = lib / "rejected.json"
    return json.loads(path.read_text()) if path.exists() else {}


def write_rejected(rejected: dict, lib: Path = LIB) -> None:
    (lib / "rejected.json").write_text(json.dumps(rejected, indent=1) + "\n")


def normalize_decisions(raw) -> dict[str, dict]:
    """The review page's "decisions" collection as {id: {status, role?, tags?, at?, by?, note?}}.

    Accepts the collection keyed by id (what publish.py always took), a list of {"id": ..., ...} or
    {"id": ..., "data": {...}} documents, or {"docs": [...]} / {"documents": [...]} as a db export returns them.
    """
    if isinstance(raw, dict):
        for key in ("docs", "documents", "items", "rows"):
            if isinstance(raw.get(key), list):
                return normalize_decisions(raw[key])
        return {str(k): (v if isinstance(v, dict) else {}) for k, v in raw.items()}
    out: dict[str, dict] = {}
    for doc in raw or []:
        if not isinstance(doc, dict):
            continue
        cid = doc.get("id") or doc.get("doc_id") or doc.get("key")
        if not cid:
            continue
        data = doc.get("data") if isinstance(doc.get("data"), dict) else {k: v for k, v in doc.items() if k not in ("id", "doc_id", "key")}
        out[str(cid)] = data
    return out

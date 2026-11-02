#!/usr/bin/env python3
"""
Seed the musicmatter.art Library (the curated commons shelf) from VCSL, the Versilian Community Sample Library (CC0).

Library design: Peter, 2026-10-31 ("NYX Library: a curated commons for samples, design v1"). Every sound here is
someone else's work: the creator is Versilian Studios (VCSL), musicmatter.art is only the curator. Nothing reaches
library.json (what NYX searches) until Peter approves it; this script writes candidates as `pending`.

What it does, per candidate:
  1. picks one-shots from the folders mapped to a role below (round-robin duplicates, rolls and swells left out),
  2. decodes to 48 kHz (a sample-rate conversion; no pitch shift, no time stretch, no normalising),
  3. trims leading silence to 2 ms before the onset and the tail below -60 dB of the peak (a 10 ms fade out),
  4. measures it (length, loudness, peak, attack, decay, brightness, low-end share, pitch),
  5. writes library/audio/<role>/<slug>.flac (24-bit) and library/manifests/<role>/<slug>.nc.json (NC manifest,
     curation pending), and library/review.json listing every candidate.

Usage:  python3 tools/library/seed_vcsl.py /path/to/VCSL [--previews DIR]
Needs:  ffmpeg, numpy, scipy, soundfile, pyloudnorm.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pyloudnorm
import soundfile as sf

VCSL_REPO = "https://github.com/sgossner/VCSL"
SITE = "https://musicmatter.art"
CREATOR = {"name": "Versilian Studios (VCSL)", "link": VCSL_REPO}
CURATOR = {"name": "musicmatter.art", "link": SITE + "/"}
SR = 48000

# Folder (relative to the VCSL root) -> (role, instrument name, how many to keep).
ROLES: list[tuple[str, str, str, int]] = [
    ("Membranophones/Struck Membranophones/Bass Drum 1", "kick", "Concert bass drum 1", 4),
    ("Membranophones/Struck Membranophones/Bass Drum 2", "kick", "Concert bass drum 2", 6),
    ("Membranophones/Struck Membranophones/Bass Drum 3 - Legacy", "kick", "Concert bass drum 3", 6),
    ("Membranophones/Struck Membranophones/Snare Drum, Modern 1", "snare", "Snare drum, modern 1", 6),
    ("Membranophones/Struck Membranophones/Snare Drum, Modern 2", "snare", "Snare drum, modern 2", 6),
    ("Membranophones/Struck Membranophones/Snare Drum, Modern 3", "snare", "Snare drum, modern 3", 5),
    ("Membranophones/Struck Membranophones/Snare Drum, Rope Tension", "snare", "Rope-tension snare", 6),
    ("Idiophones/Struck Idiophones/Claps", "clap", "Hand claps", 8),
    ("Idiophones/Struck Idiophones/Hi-Hat Cymbal", "hat", "Hi-hat", 10),
    ("Membranophones/Struck Membranophones/Tom 1", "tom", "Tom 1", 6),
    ("Membranophones/Struck Membranophones/Tom 2", "tom", "Tom 2", 6),
    ("Membranophones/Struck Membranophones/Legacy Toms", "tom", "Tenor toms", 5),
    ("Membranophones/Struck Membranophones/Bongos", "perc", "Bongos", 5),
    ("Membranophones/Struck Membranophones/Conga", "perc", "Conga", 6),
    ("Membranophones/Struck Membranophones/Darbuka", "perc", "Darbuka", 5),
    ("Membranophones/Struck Membranophones/Frame Drum", "perc", "Frame drum", 4),
    ("Idiophones/Struck Idiophones/Cajon", "perc", "Cajon", 5),
    ("Idiophones/Struck Idiophones/Agogo Bells", "perc", "Agogo bells", 4),
    ("Idiophones/Struck Idiophones/Claves", "perc", "Claves", 3),
    ("Idiophones/Struck Idiophones/Cowbells", "perc", "Cowbell", 5),
    ("Idiophones/Struck Idiophones/Woodblock", "perc", "Woodblock", 4),
    ("Idiophones/Struck Idiophones/Tambourine 1", "perc", "Tambourine 1", 3),
    ("Idiophones/Struck Idiophones/Tambourine 2", "perc", "Tambourine 2", 3),
    ("Idiophones/Struck Idiophones/Shaker, Small", "perc", "Shaker, small", 4),
    ("Idiophones/Struck Idiophones/Shaker, Large", "perc", "Shaker, large", 3),
    ("Idiophones/Struck Idiophones/Cabasa", "perc", "Cabasa", 3),
    ("Idiophones/Struck Idiophones/Guiro", "perc", "Guiro", 3),
    ("Idiophones/Struck Idiophones/Slapstick", "perc", "Slapstick", 2),
    ("Idiophones/Struck Idiophones/Triangles", "perc", "Triangle", 4),
    ("Idiophones/Struck Idiophones/Brake Drum", "perc", "Brake drum", 4),
    ("Idiophones/Struck Idiophones/Anvil", "perc", "Anvil", 3),
    ("Idiophones/Struck Idiophones/Slit Drum", "perc", "Slit drum", 3),
    ("Idiophones/Struck Idiophones/Clash Cymbals 1", "cymbal", "Clash cymbals 1", 4),
    ("Idiophones/Struck Idiophones/Clash Cymbals 2", "cymbal", "Clash cymbals 2", 3),
    ("Idiophones/Struck Idiophones/Suspended Cymbal 1", "cymbal", "Suspended cymbal 1", 4),
    ("Idiophones/Struck Idiophones/Suspended Cymbal 2", "cymbal", "Suspended cymbal 2", 3),
    ("Idiophones/Struck Idiophones/Finger Cymbals", "cymbal", "Finger cymbals", 1),
    ("Idiophones/Struck Idiophones/Gong 1", "fx", "Gong 1", 2),
    ("Idiophones/Struck Idiophones/Vibraslap", "fx", "Vibraslap", 2),
    ("Idiophones/Struck Idiophones/Ratchet", "fx", "Ratchet", 2),
    ("Idiophones/Struck Idiophones/Flexatone", "fx", "Flexatone", 2),
    ("Idiophones/Struck Idiophones/Mark Trees", "fx", "Mark tree", 2),
    ("Idiophones/Struck Idiophones/Bell Tree", "fx", "Bell tree", 2),
    ("Idiophones/Struck Idiophones/Sleigh Bells", "fx", "Sleigh bells", 2),
    ("Membranophones/Other Membranophones/Ocean Drum", "fx", "Ocean drum", 2),
    ("Aerophones/Edge-blown Aerophones/Train Whistle, Toy", "fx", "Toy train whistle", 2),
    ("Aerophones/Free Aerophones/Siren", "fx", "Siren", 2),
    ("Idiophones/Struck Idiophones/Marimba", "tonal", "Marimba", 4),
    ("Idiophones/Struck Idiophones/Vibraphone", "tonal", "Vibraphone", 4),
    ("Idiophones/Struck Idiophones/Glockenspiel", "tonal", "Glockenspiel", 3),
    ("Idiophones/Struck Idiophones/Xylophone", "tonal", "Xylophone", 3),
    ("Idiophones/Struck Idiophones/Tubular Bells 1", "tonal", "Tubular bells", 3),
    ("Idiophones/Struck Idiophones/Balafon", "tonal", "Balafon", 3),
    ("Idiophones/Struck Idiophones/Hand Chimes", "tonal", "Hand chimes", 3),
    ("Idiophones/Plucked Idiophones/Kalimba, Tanzania", "tonal", "Kalimba", 4),
    ("Electrophones/TX81Z/FM Piano", "tonal", "FM piano (Yamaha TX81Z)", 4),
]

# Long or multi-hit takes that aren't one-shots for a pad (an "fx" role keeps some longer sounds).
SKIP = re.compile(r"roll|cresc|swell|bow|trem|scrape|sustain|_rel\b|choke|legacy/legacy", re.I)
SOFT = re.compile(r"(^|[_\- ])(ppp|pp|p|mp|soft|v1|vl1|quiet)([_\- .]|$)", re.I)
HARD = re.compile(r"(^|[_\- ])(fff|ff|f|loud|hard|v[4-9]|vl[4-9])([_\- .]|$)", re.I)
NOTE = re.compile(r"(?:^|[_\- ])([A-G](?:#|b)?)(-?\d)(?:[_\- .]|$)")
DYN_ORDER = ["fff", "ff", "f", "loud", "mf", "med", "mp", "p", "pp", "ppp", "soft"]


def slugify(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


def variant_key(name: str) -> str:
    """The articulation a file plays: its name without round-robin and mic tokens."""
    stem = Path(name).stem
    stem = re.sub(r"[_\- ]?rr\d+", "", stem, flags=re.I)
    stem = re.sub(r"[_\- ](Mid|Main|Sum|Close|Room|Far)$", "", stem, flags=re.I)
    stem = re.sub(r"_0?1$", "", stem)
    return stem.lower()


def dynamic_rank(name: str) -> int:
    low = name.lower()
    m = re.search(r"(?:^|[_\- ])v[l]?(\d)(?:[_\- .]|$)", low)
    if m:
        return 10 - int(m.group(1))  # higher velocity layer first
    for i, word in enumerate(DYN_ORDER):
        if re.search(rf"(?:^|[_\- ]){word}\d*(?:[_\- .]|$)", low):
            return i
    return 5


def choose(files: list[Path], keep: int, tonal: bool) -> list[Path]:
    """One file per articulation (round robin 1 first), spread over articulations, louder layers first."""
    by_key: dict[str, Path] = {}
    for f in sorted(files):
        if SKIP.search(str(f)):
            continue
        if tonal:
            m = NOTE.search(f.stem.replace("#", "#"))
            if not m or m.group(1) not in ("C", "G"):
                continue
        k = variant_key(f.name)
        cur = by_key.get(k)
        if cur is None or ("rr1" in f.name.lower() and "rr1" not in cur.name.lower()):
            by_key[k] = f
    # Group articulations by their name without the dynamic, so one of each comes before a second dynamic.
    groups: dict[str, list[Path]] = {}
    for k, f in by_key.items():
        base = re.sub(r"[_\- ]?(v[l]?\d|fff|ff|mf|mp|ppp|pp|loud|med|soft|f|p)(?=[_\- ]|$)", "", k)
        groups.setdefault(base, []).append(f)
    for g in groups.values():
        g.sort(key=lambda p: dynamic_rank(p.name))
    picked: list[Path] = []
    round_ = 0
    while len(picked) < keep and any(len(g) > round_ for g in groups.values()):
        for base in sorted(groups):
            g = groups[base]
            if len(g) > round_ and len(picked) < keep:
                picked.append(g[round_])
        round_ += 1
    return picked


def decode(path: Path) -> np.ndarray:
    """Decode to 48 kHz float32 stereo-or-mono (frames x channels) with ffmpeg's soxr resampler."""
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-af", "aresample=resampler=soxr:precision=28",
         "-ar", str(SR), "-f", "f32le", "-acodec", "pcm_f32le", "-"],
        check=True, capture_output=True,
    ).stdout
    info = sf.info(str(path))
    ch = min(2, info.channels)
    data = np.frombuffer(out, dtype=np.float32).reshape(-1, info.channels)[:, :ch]
    return data.copy()


def envelope_db(mono: np.ndarray, hop: int = 48, window: int = 480) -> np.ndarray:
    """RMS level in dB over a 10 ms window, one value per 1 ms (smooth enough for low drums' long cycles)."""
    sq = np.concatenate([np.zeros(window), mono.astype(np.float64) ** 2])
    csum = np.cumsum(sq)
    idx = np.arange(window, len(sq), hop)
    rms = np.sqrt(np.maximum((csum[idx] - csum[idx - window]) / window, 1e-18))
    return 20 * np.log10(np.maximum(rms, 1e-9))


def trim(data: np.ndarray) -> tuple[np.ndarray, int]:
    mono = np.abs(data).max(axis=1)
    peak = float(mono.max())
    if peak <= 0:
        return data[:0], 0
    above = np.nonzero(mono > peak * 10 ** (-40 / 20))[0]
    start = max(0, int(above[0]) - int(0.002 * SR))
    tail = np.nonzero(mono > peak * 10 ** (-60 / 20))[0]
    end = min(len(data), int(tail[-1]) + int(0.02 * SR))
    out = data[start:end].copy()
    fade = min(len(out), int(0.01 * SR))
    if fade > 0:
        out[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
    return out, start


def measure(data: np.ndarray, note: str | None) -> dict:
    mono = data.mean(axis=1)
    n = len(mono)
    length = n / SR
    peak = float(np.abs(data).max())
    env = envelope_db(mono)  # 1 ms frames
    ipk = int(np.argmax(env)) if len(env) else 0
    # Attack: from the start (2 ms before the onset) to the first 1 ms frame within 3 dB of the peak sample.
    hop = 48
    frames = np.abs(mono[: (n // hop) * hop]).reshape(-1, hop).max(axis=1) if n >= hop else np.abs(mono)
    reach = np.nonzero(frames >= frames.max() * 10 ** (-3 / 20))[0] if len(frames) else np.array([0])
    attack_ms = float(reach[0])  # frames are 1 ms
    after = np.nonzero(env[ipk:] < env[ipk] - 30)[0]
    decay_s = float(after[0]) / 1000 if len(after) else length - ipk / 1000
    meter = pyloudnorm.Meter(SR, block_size=min(0.4, max(0.05, length)))
    try:
        lufs = float(meter.integrated_loudness(data if data.shape[1] > 1 else mono))
    except Exception:
        lufs = float("nan")
    head = mono[: min(n, int(0.3 * SR))]
    spec = np.abs(np.fft.rfft(head * np.hanning(len(head)))) if len(head) > 16 else np.zeros(2)
    freqs = np.fft.rfftfreq(len(head), 1 / SR) if len(head) > 16 else np.zeros(2)
    power = spec**2
    total = float(power.sum()) or 1.0
    centroid = float((freqs * power).sum() / total)
    low_share = float(power[freqs < 150].sum() / total)
    out = {
        "length_s": round(length, 3),
        "lufs": None if not np.isfinite(lufs) else round(lufs, 1),
        "peak_dbfs": round(20 * np.log10(max(peak, 1e-9)), 1),
        "attack_ms": round(attack_ms, 1),
        "decay_s": round(decay_s, 3),
        "centroid_hz": round(centroid),
        "low_share": round(low_share, 3),
    }
    if note:
        out["note"] = note
    else:
        band = (freqs > 30) & (freqs < 400)
        if band.any() and low_share > 0.05:
            out["pitch_hz"] = round(float(freqs[band][np.argmax(spec[band])]), 1)
    return out


def tags_for(role: str, instrument: str, name: str, m: dict) -> list[str]:
    t: set[str] = {"acoustic", role}
    t.update(w for w in re.findall(r"[a-z]+", instrument.lower()) if len(w) > 2 and w not in {"the", "and"})
    if SOFT.search(Path(name).stem):
        t.add("soft")
    if HARD.search(Path(name).stem):
        t.add("hard")
    short, long_ = m["length_s"] < 0.3, m["length_s"] > 1.5
    if short:
        t.add("short")
    if long_:
        t.add("long")
    if m["centroid_hz"] > 4000:
        t.add("bright")
    elif m["centroid_hz"] < 800:
        t.add("dark")
    if role in {"kick", "tom"}:
        if m["attack_ms"] <= 10 and m["decay_s"] < 0.6:
            t.add("punchy")
        if m["decay_s"] >= 0.9:
            t.add("boomy")
        if m.get("pitch_hz", 999) < 70:
            t.add("deep")
    if role in {"snare", "clap", "hat", "perc"}:
        if m["decay_s"] < 0.2:
            t.add("tight")
        if m["attack_ms"] <= 4 and m["centroid_hz"] > 2500:
            t.add("snappy")
    if role == "hat":
        lower = name.lower()
        if "open" in lower or "hito_" in lower or re.search(r"hit_?o\b|hito", lower):
            t.add("open")
        elif "close" in lower or "hitc" in lower:
            t.add("closed")
    if role in {"kick", "snare", "tom"} and "concert" in instrument.lower():
        t.add("orchestral")
    return sorted(t)


def title_for(instrument: str, name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[_\- ]?rr\d+", "", stem, flags=re.I)
    stem = re.sub(r"[_\- ](Mid|Main|Sum)$", "", stem, flags=re.I)
    words = re.sub(r"[_\-]+", " ", stem).strip()
    return f"{instrument} · {words}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("vcsl", type=Path)
    ap.add_argument("--commit", default="")
    ap.add_argument("--previews", type=Path, help="also write small MP3 previews here (for the review page)")
    args = ap.parse_args()
    root: Path = args.vcsl
    site = Path(__file__).resolve().parents[2]
    lib = site / "library"
    commit = args.commit or subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    review = []
    seen_hash: set[str] = set()
    for folder, role, instrument, keep in ROLES:
        files = [p for p in (root / folder).rglob("*.wav")]
        if not files:
            print(f"! nothing in {folder}", file=sys.stderr)
            continue
        for f in choose(files, keep, role == "tonal"):
            data = decode(f)
            data, _ = trim(data)
            if len(data) < int(0.02 * SR):
                print(f"- too short after trim: {f}", file=sys.stderr)
                continue
            peak = float(np.abs(data).max())
            if peak >= 0.999:
                print(f"- clipped: {f}", file=sys.stderr)
                continue
            limit = 6 if role in {"snare", "clap", "hat", "perc"} else 12
            if len(data) > limit * SR:
                print(f"- longer than {limit} s: {f}", file=sys.stderr)
                continue
            m_note = NOTE.search(f.stem)
            note = (m_note.group(1) + m_note.group(2)) if (role == "tonal" and m_note) else None
            m = measure(data, note)
            rel = f.relative_to(root).as_posix()
            slug = slugify(f"vcsl-{instrument}-{Path(f.name).stem}")[:80]
            audio_rel = f"library/audio/{role}/{slug}.flac"
            out = site / audio_rel
            out.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(out), data, SR, subtype="PCM_24", format="FLAC")
            digest = hashlib.sha256(out.read_bytes()).hexdigest()
            if digest in seen_hash:
                out.unlink()
                continue
            seen_hash.add(digest)
            if args.previews:
                prev = args.previews / f"{slug}.mp3"
                prev.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-b:a", "128k", str(prev)], check=True)
            manifest = {
                "nc_version": "0.2",
                "kind": "one-shot",
                "role": role,
                "title": title_for(instrument, f.name),
                "instrument": instrument,
                "tags": tags_for(role, instrument, f.name, m),
                "creator": CREATOR,
                "curator": CURATOR,
                "license": "CC0-1.0",
                "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "source": {
                    "origin": "vcsl",
                    "url": f"{VCSL_REPO}/blob/{commit}/{rel.replace(' ', '%20')}",
                    "path": rel,
                    "commit": commit,
                    "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                    "license_read_at": today,
                },
                "audio": f"{SITE}/{audio_rel}",
                "format": {"mime": "audio/flac", "lossless": True, "sample_rate": SR, "bit_depth": 24,
                           "channels": int(data.shape[1]), "frames": int(len(data))},
                "sha256": digest,
                "size_bytes": out.stat().st_size,
                "processing": ["resample to 48 kHz (soxr)", "trim silence: 2 ms before onset, tail below -60 dB",
                               "10 ms fade out"],
                "measures": m,
                "curation": {"status": "pending"},
            }
            man_rel = f"library/manifests/{role}/{slug}.nc.json"
            (site / man_rel).parent.mkdir(parents=True, exist_ok=True)
            (site / man_rel).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
            review.append({"id": slug, "role": role, "title": manifest["title"], "instrument": instrument,
                           "tags": manifest["tags"], "measures": m, "manifest": f"{SITE}/{man_rel}",
                           "audio": manifest["audio"], "preview": f"previews/{slug}.mp3"})
            print(f"+ {role:6} {slug}")
    lib.mkdir(exist_ok=True)
    (lib / "review.json").write_text(json.dumps({"generated": today, "source": "vcsl", "commit": commit,
                                                  "count": len(review), "candidates": review}, indent=1) + "\n")
    print(f"{len(review)} candidates", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Level-match the Library without touching the audio: each manifest gets a playback gain (dB) that NYX applies when it
loads the sound, so the files stay bit-identical to their source (clean provenance) and "as recorded" stays one
switch away.

How (Peter, 2026-10-31): sounds are matched by family, not one by one, so an instrument's soft and hard layers keep
their real dynamics. A family is one instrument and one articulation (a snare's centre hits, its rim shots): its
velocity layers. Its loudest sound is brought to the
target, and every sound in it gets that same gain. "Loudness" for a hit is how hard it hits: the loudest 50 ms of the
sound (RMS, dBFS), which a one-shot's integrated LUFS misreads. A gain never pushes a sound's peak past -1 dBFS; a
sound that would gets less gain, and the manifest says so.

Usage:  python3 tools/library/level_match.py [--target -14] [--previews DIR]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf

SITE = Path(__file__).resolve().parents[2]
LIB = SITE / "library"
CEILING_DB = -1.0


def hit_db(path: Path) -> tuple[float, float]:
    """(loudest 50 ms RMS in dBFS, sample peak in dBFS)."""
    data, sr = sf.read(str(path), dtype="float64", always_2d=True)
    mono = data.mean(axis=1)
    win = max(1, int(0.05 * sr))
    sq = np.concatenate([np.zeros(win), mono**2])
    csum = np.cumsum(sq)
    rms = np.sqrt(np.maximum((csum[win:] - csum[:-win]) / win, 1e-20))
    peak = float(np.abs(data).max())
    return 20 * np.log10(max(float(rms.max()), 1e-10)), 20 * np.log10(max(peak, 1e-10))


DYNAMICS = re.compile(r"(?:^|[_\- ])(v\d|vl\d|ppp|pp|p|mp|mf|f|ff|fff|loud|soft|med|quiet)(?=[_\- ]|$)", re.I)


def family_key(manifest: dict) -> str:
    """One instrument and one articulation: its velocity layers (v1..v9, pp..fff, soft/loud) share a family."""
    stem = Path(manifest["source"]["path"]).stem
    stem = re.sub(r"[_\- ]?rr\d+", "", stem, flags=re.I)
    stem = re.sub(r"[_\- ](Mid|Main|Sum|Close|Room|Far)$", "", stem, flags=re.I)
    stem = DYNAMICS.sub("", stem)
    stem = re.sub(r"[_\- ]?\d+$", "", stem)
    return f"{manifest['instrument']}|{stem.lower()}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=float, default=-14.0, help="dBFS for the loudest 50 ms of each family's loudest sound")
    ap.add_argument("--previews", type=Path, help="rewrite MP3 previews here, at the matched level")
    args = ap.parse_args()
    review = json.loads((LIB / "review.json").read_text())
    rows = []
    for cand in review["candidates"]:
        man_path = SITE / cand["manifest"].split("musicmatter.art/", 1)[1]
        audio_path = SITE / cand["audio"].split("musicmatter.art/", 1)[1]
        manifest = json.loads(man_path.read_text())
        h, p = hit_db(audio_path)
        rows.append((cand, manifest, man_path, audio_path, h, p))
    families: dict[str, list] = defaultdict(list)
    for row in rows:
        families[family_key(row[1])].append(row)
    for fam in families.values():
        loudest = max(r[4] for r in fam)
        family_gain = args.target - loudest
        for cand, manifest, man_path, audio_path, h, p in fam:
            gain = min(family_gain, CEILING_DB - p)
            limited = gain < family_gain - 0.05
            gain = round(gain, 1)
            manifest["measures"]["hit_dbfs"] = round(h, 1)
            manifest["playback"] = {
                "gain_db": gain,
                "method": "family level match: loudest 50 ms RMS of the family's loudest sound to "
                          f"{args.target:g} dBFS; peak kept under {CEILING_DB:g} dBFS",
                **({"limited_by_peak": True} if limited else {}),
            }
            man_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
            cand["measures"]["hit_dbfs"] = round(h, 1)
            cand["gain_db"] = gain
            if args.previews:
                out = args.previews / f"{cand['id']}.mp3"
                out.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(audio_path), "-af", f"volume={gain}dB",
                                "-b:a", "128k", str(out)], check=True)
    (LIB / "review.json").write_text(json.dumps(review, indent=1) + "\n")
    after = [r[4] + r[0]["gain_db"] for r in rows]
    print(f"{len(rows)} sounds, {len(families)} families; matched hit level {min(after):.1f} .. {max(after):.1f} dBFS "
          f"(was {min(r[4] for r in rows):.1f} .. {max(r[4] for r in rows):.1f})")


if __name__ == "__main__":
    main()

"""Library tools: measures stay identical to the harvester's copy; fetch_review -> review page -> publish_harvest.

Run:  python3 -m pytest tools/library    (or python3 tools/library/test_library_tools.py)
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import catalog  # noqa: E402
import fetch_review  # noqa: E402
import measures as M  # noqa: E402
import publish_harvest  # noqa: E402

# sha256 of this measures.py and of nc-performer's service/nc_perform/library_measures.py: one module, two repos.
# If this fails, copy the changed file across and update this constant and MEASURES_SHA256 in nc-performer
# service/tests/test_library.py together.
MEASURES_SHA256 = "ba4d537d497023933b310980cd12c5157ee7fda04efeb7e40c3bd61cbe2a996c"
# measure() on golden_signal(); the same literal is in nc-performer service/tests/test_library.py.
GOLDEN = {"length_s": 0.602, "lufs": -17.3, "peak_dbfs": -2.1, "attack_ms": 2.0, "decay_s": 0.48,
          "centroid_hz": 60, "low_share": 1.0, "pitch_hz": 56.7}


def golden_signal() -> np.ndarray:
    sr = M.SR
    t = np.arange(int(0.6 * sr)) / sr
    freq = 55 + 105 * np.exp(-t * 30)
    phase = 2 * np.pi * np.cumsum(freq) / sr
    body = np.sin(phase) * np.exp(-t * 7)
    click = np.exp(-t * 900) * 0.5
    mono = (0.7 * (body + click)).astype(np.float32)
    mono = np.concatenate([np.zeros(int(0.05 * sr), np.float32), mono])
    return np.stack([mono, mono * 0.9], axis=1)


class Measures(unittest.TestCase):
    def test_same_file_as_the_harvester(self):
        self.assertEqual(hashlib.sha256((HERE / "measures.py").read_bytes()).hexdigest(), MEASURES_SHA256)

    def test_golden(self):
        data, _ = M.trim(golden_signal())
        self.assertEqual(M.measure(data, None), GOLDEN)

    def test_gain_matches_level_match_formula(self):
        for loudest, peak, target in [(-20, -6, -14), (-30, -20, -14), (-10, -0.5, -14)]:
            family_gain = target - loudest
            want = min(family_gain, M.CEILING_DB - peak)
            self.assertEqual(M.playback_gain(loudest, peak, target), (round(want, 1), want < family_gain - 0.05))


def flac_bytes(seed: int) -> bytes:
    data, _ = M.trim(golden_signal() * (0.5 + 0.1 * seed))
    buf = io.BytesIO()
    sf.write(buf, data, M.SR, subtype="PCM_24", format="FLAC")
    return buf.getvalue()


def manifest(cid: str, role: str, audio: bytes, user: str, lic: str, quality: str = "preview") -> dict:
    lic_url = {"CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
               "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/"}[lic]
    fsid = cid.split("-")[1]
    return {
        "nc_version": "0.2", "kind": "one-shot", "role": role, "title": cid, "tags": ["electronic", role, "808"],
        "creator": {"name": user, "link": f"https://freesound.org/people/{user}/"},
        "curator": {"name": "musicmatter.art", "link": "https://musicmatter.art/"},
        "license": lic, "license_url": lic_url,
        "source": {"origin": "freesound", "id": fsid, "url": f"https://freesound.org/people/{user}/sounds/{fsid}/",
                   "license_read_at": "2026-11-03T04:16:00Z"},
        "quality": quality, "audio": f"https://musicmatter.art/library/audio/{role}/{cid}.flac",
        "format": {"mime": "audio/flac", "lossless": quality == "original", "sample_rate": 48000, "bit_depth": 24},
        "sha256": hashlib.sha256(audio).hexdigest(), "size_bytes": len(audio),
        "measures": {"length_s": 0.6, "lufs": -17.3, "peak_dbfs": -2.1, "attack_ms": 2.0, "decay_s": 0.48,
                     "centroid_hz": 60, "low_share": 1.0, "hit_dbfs": -10.0},
        "playback": {"gain_db": -4.0, "method": "x"}, "curation": {"status": "pending"},
    }


class FakeWorker:
    """nc-perform-api's Library admin routes, as recorded: three pending candidates."""

    def __init__(self):
        self.audio = {f"fs-10000{i}-808-kick-{i}": flac_bytes(i) for i in (1, 2, 3)}
        roles = {"fs-100001-808-kick-1": "kick", "fs-100002-808-kick-2": "kick", "fs-100003-808-kick-3": "hat"}
        users = {"fs-100001-808-kick-1": "analogfan", "fs-100002-808-kick-2": "beatsmith", "fs-100003-808-kick-3": "hatlover"}
        lics = {"fs-100001-808-kick-1": "CC0-1.0", "fs-100002-808-kick-2": "CC-BY-4.0", "fs-100003-808-kick-3": "CC0-1.0"}
        self.manifests = {cid: manifest(cid, roles[cid], a, users[cid], lics[cid]) for cid, a in self.audio.items()}
        self.notified: list[dict] = []
        worker = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                return

            def _send(self, status, body: bytes, ctype="application/json"):
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _auth(self) -> bool:
                if self.headers.get("Authorization") != "Bearer admin-secret":
                    self._send(401, b'{"error":"admin token required"}')
                    return False
                return True

            def do_GET(self):
                if not self._auth():
                    return
                base = f"http://{self.headers['Host']}"
                if self.path.startswith("/api/library/admin/candidates?"):
                    cands = [{"id": cid, "state": "pending", "batch": "n-1", "quality": "preview", "query": "808 kick",
                              "manifest": worker.manifests[cid],
                              **({"note": "Measures sound dark for a hat: check the role."} if cid.endswith("3") else {}),
                              "files": {k: f"{base}/api/library/admin/candidates/{cid}/{f}" for k, f in
                                        (("audio", "audio.flac"), ("preview", "preview.mp3"))}} for cid in worker.audio]
                    return self._send(200, json.dumps({"state": "pending", "count": 3, "candidates": cands}).encode())
                parts = self.path.split("/")
                cid, name = parts[-2], parts[-1]
                if name == "audio.flac":
                    return self._send(200, worker.audio[cid], "audio/flac")
                if name == "preview.mp3":
                    return self._send(200, b"ID3" + cid.encode(), "audio/mpeg")
                self._send(404, b"{}")

            def do_POST(self):
                if not self._auth():
                    return
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                worker.notified.append(body)
                out = {"approved": [], "rejected": [], "pending": [], "unknown": [], "not_reviewable": []}
                for cid, d in body["decisions"].items():
                    out[d["status"]].append(cid)
                self._send(200, json.dumps(out).encode())

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.api = "http://%s:%d" % self.httpd.server_address[:2]


class HarvestFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mm-lib-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.worker = FakeWorker()
        self.addCleanup(self.worker.httpd.server_close)
        os.environ["NC_ADMIN_TOKEN"] = "admin-secret"
        self.addCleanup(os.environ.pop, "NC_ADMIN_TOKEN", None)
        # A copy of the site's catalog, so the real library/ is never touched.
        self.site = self.tmp / "site"
        (self.site / "library").mkdir(parents=True)
        for name in ("library.json", "rejected.json"):
            shutil.copy(catalog.LIB / name, self.site / "library" / name)
        self.before = json.loads((self.site / "library" / "library.json").read_text())

    def test_fetch_review_then_publish(self):
        batch = self.tmp / "batch"
        self.assertEqual(fetch_review.main([str(batch), "--api", self.worker.api]), 0)
        page = (batch / "index.html").read_text()
        self.assertNotIn("__CANDIDATES__", page)
        self.assertNotIn("__SUBTITLE__", page)
        self.assertIn("Harvested from Freesound: 3 openly licensed one-shots (2 kick, 1 hat)", page)
        self.assertIn('"creator": "beatsmith"', page)
        self.assertIn('"license_url": "https://creativecommons.org/licenses/by/4.0/"', page)
        self.assertIn("previews/${c.id}.mp3", page)
        self.assertTrue((batch / "previews" / "fs-100001-808-kick-1.mp3").exists())
        self.assertEqual(len(json.loads((batch / "batch.json").read_text())["candidates"]), 3)

        decisions = [  # as a db export lists them
            {"id": "fs-100001-808-kick-1", "data": {"status": "approved", "at": "2026-11-04T10:00:00Z"}},
            {"id": "fs-100002-808-kick-2", "data": {"status": "rejected", "at": "2026-11-04T10:01:00Z", "note": "boxy"}},
            {"id": "fs-100003-808-kick-3", "data": {"status": "approved", "role": "kick", "tags": ["808", "deep"],
                                                     "at": "2026-11-04T10:02:00Z"}},
        ]
        decided, problems = publish_harvest.publish(catalog.normalize_decisions(decisions), batch, site=self.site)
        self.assertEqual(problems, [])
        lib = json.loads((self.site / "library" / "library.json").read_text())
        self.assertEqual(lib["count"], self.before["count"] + 2, "merged: the VCSL seed stays listed")
        ids = {e["id"] for e in lib["sounds"]}
        self.assertTrue({e["id"] for e in self.before["sounds"]} <= ids)
        e = next(e for e in lib["sounds"] if e["id"] == "fs-100001-808-kick-1")
        self.assertEqual(e["creator"], "analogfan")
        self.assertEqual(e["creator_link"], "https://freesound.org/people/analogfan/")
        self.assertEqual(e["license"], "CC0-1.0")
        self.assertEqual(e["source"], {"origin": "freesound", "url": "https://freesound.org/people/analogfan/sounds/100001/"})
        self.assertEqual(e["quality"], "preview")
        self.assertEqual(e["audio"], "https://musicmatter.art/library/audio/kick/fs-100001-808-kick-1.flac")
        self.assertEqual(len(e["wave"]), 48)
        self.assertIn("gain_db", e["measures"])
        self.assertEqual(set(e) - {"quality"}, set(self.before["sounds"][0]), "one format with the VCSL entries")
        moved = next(e for e in lib["sounds"] if e["id"] == "fs-100003-808-kick-3")
        self.assertEqual(moved["role"], "kick")
        self.assertEqual(moved["tags"], ["808", "deep", "kick"])
        man = json.loads((self.site / "library/manifests/kick/fs-100003-808-kick-3.nc.json").read_text())
        self.assertEqual(man["curation"], {"status": "approved", "by": "Peter", "at": "2026-11-04"})
        self.assertEqual(man["curator"]["name"], "musicmatter.art")
        self.assertEqual(man["playback"]["method"], M.playback_method())
        audio = self.site / "library/audio/kick/fs-100003-808-kick-3.flac"
        self.assertEqual(hashlib.sha256(audio.read_bytes()).hexdigest(), man["sha256"])
        rej = json.loads((self.site / "library" / "rejected.json").read_text())
        self.assertEqual(rej["fs-100002-808-kick-2"]["source"]["id"], "100002")
        self.assertEqual(rej["fs-100002-808-kick-2"]["reason"], "boxy")
        self.assertIn("vcsl-hand-claps-soloclap-vl1", rej)
        self.assertEqual(decided["fs-100002-808-kick-2"]["status"], "rejected")
        result = publish_harvest.notify(self.worker.api, "admin-secret", decided)
        self.assertEqual(sorted(result["approved"]), ["fs-100001-808-kick-1", "fs-100003-808-kick-3"])
        self.assertEqual(result["rejected"], ["fs-100002-808-kick-2"])
        # Running it again changes nothing.
        publish_harvest.publish(catalog.normalize_decisions(decisions), batch, site=self.site)
        self.assertEqual(json.loads((self.site / "library" / "library.json").read_text())["count"], lib["count"])

    def test_tampered_audio_is_left_pending(self):
        batch = self.tmp / "batch"
        fetch_review.main([str(batch), "--api", self.worker.api])
        (batch / "audio" / "fs-100001-808-kick-1.flac").write_bytes(b"not it")
        decided, problems = publish_harvest.publish({"fs-100001-808-kick-1": {"status": "approved"}}, batch, site=self.site)
        self.assertEqual(decided, {})
        self.assertIn("sha256", problems[0])
        self.assertEqual(json.loads((self.site / "library" / "library.json").read_text())["count"], self.before["count"])

    def test_needs_admin_token(self):
        os.environ.pop("NC_ADMIN_TOKEN")
        self.assertEqual(fetch_review.main([str(self.tmp / "b"), "--api", self.worker.api]), 2)


class Decisions(unittest.TestCase):
    def test_shapes(self):
        want = {"a": {"status": "approved"}}
        self.assertEqual(catalog.normalize_decisions({"a": {"status": "approved"}}), want)
        self.assertEqual(catalog.normalize_decisions([{"id": "a", "status": "approved"}]), want)
        self.assertEqual(catalog.normalize_decisions({"docs": [{"id": "a", "data": {"status": "approved"}}]}), want)


if __name__ == "__main__":
    unittest.main()

# musicmatter.art changelog

## v7.2 (2026-10-18)
- **Seamless loop.** With the ⟲ Loop toggle on, players now loop gaplessly and without clicks. `assets/loop.js` fetches and decodes the sound once and plays it through WebAudio (`AudioBufferSourceNode`, `loop=true`, `loopStart`/`loopEnd` from the manifest). The `<audio>` element stays the transport (play, pause, seek, volume) and runs silently underneath. If WebAudio, the manifest or the fetch fails, it falls back to the native `loop` attribute as in v7.1. Same button, same look.
- **Manifests gain a `loop` entry** (all 3,612 `.nc.json`: 1,356 home sounds, 2,256 full chord set v4). No audio file changed and no new audio files: the loop is a region of the canonical FLAC.
  - `loop_start`, `loop_end`: frames at `sample_rate`, end exclusive. One bar at 110 BPM (104,727 frames). Home sounds loop bar 2, from just before strike 2 to just before strike 3 (183 of them end up to 178 frames early to stay clear of strike 3's first samples at the very end of the file). Full chord set v4 loops bar 1, from just before the strike. `loop_start` is the lowest-amplitude sample in the 0.5–0.75 ms before the strike.
  - `crossfade` (frames), `crossfade_shape: "equal-power"`, `crossfade_mode: "tail-into-pre-roll"`. The player replaces the last `crossfade` frames of the region with `tail[i]*cos(π/2·t) + audio[loop_start−crossfade+i]*sin(π/2·t)`, where `t=(i+1)/crossfade` and frames before 0 count as silence. The wrap then lands on the recorded pair (`loop_start−1`, `loop_start`), so it's continuous in level and slope, and the strike itself is untouched. Length is 4 periods of the lowest played note, clamped to 5–50 ms.
  - `audio` names the file the region belongs to, plus `length_frames`, `length_s`, `bars`, `bpm` and `region`. `loopable` stays `false`, because it describes the file played end to end.
- Chord sounds decay, so a looped chord re-strikes once a bar. That's a pulse, not a click.

## v7.1 (2026-10-18)
- Loop toggle: a small ⟲ button (title "Loop", `aria-pressed`) next to every audio player on the home page and the 12 per-root `/fullchords/` pages. It switches the player's native `loop` (gapless with the FLAC files) and remembers the last choice in `localStorage` (`mm-loop`). New files `/assets/loop.js` and `/assets/loop.css`; each page gains one `<link>` and one `<script>` in `<head>`. No content, audio or manifests changed.

## v7 (2026-10-17)
- New collection **full chord set v4** (`collection: "full-chord-set-v4"`): 2,256 chord recordings, 12 roots × 188 clips (39 chord-type/voicing groups per root). Sliced from Petrus's 12 Bitwig bounces of the v4 chord sequences, lossless FLAC 24-bit/48 kHz, not pitch-shifted, time-stretched or normalized. Each clip starts 2 ms before the strike and runs to the end of its 2-bar slot (4.3636 s), keeping the natural release.
- Audio: `https://fullchords.musicmatter.art/<root>/<name>.flac` (separate GitHub Pages site, repo netcomposer-art/fullchords.musicmatter.art); manifests stay here at `/sounds/fullchords-v4/<root>/`. Pages: `/fullchords/` and one page per root. Home gains one paragraph linking `/fullchords/`.
- MIDI: `/midi/fullchords-v4/` with the exact clip that was played for every recording (`derived_from_audio: false`), the 12 sequence files and cue sheets, and a zip. `/midi/` links to it; home does not.
- Manifests add `collection`, a `chord` block (root, quality, family, voicing, notes, MIDI notes, bass note and degree), `performance` and `source` (sequence file and slot). `#` in chord names becomes `sharp` in file names (`F#` → `Fsharp`, `7#11` → `7sharp11`).
- netcomposer.json: 2,256 offerings appended (with `collection`), plus a top-level `collections` entry. Existing content unchanged.

## v6 (2026-10-17)
- New page **/midi/** with one MIDI file per audio clip (702 chords + 654 up/down arpeggios = 1,356 `.mid` files) and a zip of all of them (`/midi/musicmatter-midi-all.zip`). The MIDI files are transcriptions derived from the audio (`derived_from_audio: true`), not the original performance data. They're licensed CC BY-SA 4.0, credit Petrus.
- Every `.nc.json` gains a `midi` link and a `midi_info` block (method, confidence, notes, size, sha256). Each `netcomposer.json` offering gains `midi`.
- **Corrected note data.** The `register` blocks and arpeggio notes are rewritten from the verified transcription (the same notes as the MIDI). The 529 changed manifests carry `register_source: "verified_v6"`.
  - Chords (508 manifests): `register.high` was an overtone in v4/v5, not a played note. `c7-bounce-6` also changes `low`/`bass`/`inversion`/`root` (now first inversion, bass E4).
  - Arpeggios (21 manifests): octave errors fixed in `arpeggio.notes`, `arpeggio.cycle` and `register` (18 `high`, 5 `root`). The other 633 arpeggio manifests already matched the verified notes.
  - `bmaj-bounce-1` and `cm7-bounce-36` have best-evidence notes but are flagged `notes_confidence: "low"`.
- `key`, `chords`, `type` and audio fields are unchanged. `nc_version` stays "0.1".
- The home page captions are unchanged. One of them (`c7-bounce-6`, "root inversion, bass C4") is now out of date. Its manifest has the corrected values.

## v5
- All audio converted to lossless FLAC (24-bit/48 kHz). The 654 up/down arpeggios were added, and the manifests gained `type`, `format`, `size_bytes` and `sha256`.

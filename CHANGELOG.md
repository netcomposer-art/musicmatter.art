# musicmatter.art changelog

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

# Library tools

The Library is musicmatter.art's curated commons of one-shots (`library/library.json`), the shelf NYX's Library
searches. Every sound keeps its original creator and license; musicmatter.art is only the curator, and nothing is
listed until Peter approves it. Design: "NYX Library: a curated commons for samples, design v1" (Peter, 2026-10-31).

| Script | What it does |
|---|---|
| `measures.py` | Decode to 48 kHz, trim, measure (length, LUFS, peak, attack, decay, centroid, low share, pitch), hit level, playback gain, waveform outline. One module for every source. nc-performer's harvester runs a verbatim copy (`service/nc_perform/library_measures.py`); change both together (the tests pin both files' sha256). |
| `seed_vcsl.py` | The first seed: CC0 one-shots from VCSL, written as pending candidates (`library/review.json`). |
| `level_match.py` | Family level match for the seed: a playback gain in each manifest, no audio change. |
| `publish.py` | Publishes Peter's decisions on the seed (`review.json`) into `library.json` and `rejected.json`. |
| `fetch_review.py` | Pulls the harvester's pending queue from nc-perform-api and builds the Library Review page for it. |
| `publish_harvest.py` | Publishes Peter's decisions on a harvested batch and tells the Worker. |
| `catalog.py` | Shared by both publish scripts: `library.json` entries (merged, never rebuilt from one batch) and `rejected.json`. |

## The harvest loop (Freesound)

1. Every night at 04:15 UTC nc-perform-api harvests a small batch from Freesound (electronic drums first: 808/909
   kicks, hats, claps, snares, rims, percussion), keeps CC0 / CC BY / CC BY-SA one-shots of 3 s or less, measures them
   with `measures.py`'s copy, and queues them. Nothing in `library.json` or `rejected.json` is harvested again.
2. Pull the queue and build the review page:

   ```
   NC_ADMIN_TOKEN=... python3 tools/library/fetch_review.py /tmp/library-batch
   ```

   Republish the Library Review artifact from `/tmp/library-batch`: `index.html` plus every `previews/<id>.mp3` as a
   file. Peter listens, approves or rejects (or "Approve all" for what's left), and can change a role or tags.
3. Export the page's `decisions` collection to a JSON file and publish:

   ```
   NC_ADMIN_TOKEN=... python3 tools/library/publish_harvest.py decisions.json /tmp/library-batch
   ```

   Approved sounds are copied to `library/audio/<role>/` with manifests in `library/manifests/<role>/` and added to
   `library.json`; rejected ones go to `rejected.json` with their source and reason. The script then tells the Worker,
   so approved and rejected sounds leave the queue for good. Commit `library/` and open a PR.

A sound harvested before the original-file login was connected says `"quality": "preview"` (decoded from Freesound's
MP3 preview) in its manifest and library entry, so it can be replaced by the original later.

## Freesound terms

The harvester uses the Freesound API under its [terms of use](https://freesound.org/docs/api/terms_of_use.html):

- **Non-commercial use only.** The Library and NetComposer are a non-commercial, openly licensed art project.
  Commercial use of the Freesound API needs a separate licence from the Music Technology Group at UPF: **mtg@upf.edu**.
- **No replicating Freesound.** Small nightly batches, and a person approves every sound before it is listed.
- **Credit.** Every sound names its creator (Freesound username, linked) and its license, and links its Freesound page.
- **One API key.** No extra keys to get around the limits; ask MTG for higher limits instead.

Sounds themselves stay under their creators' licenses (CC0, CC BY, CC BY-SA): BY and BY-SA need the visible credit
NYX shows on the pad, in Credits and in saved patterns.

## Tests

```
python3 -m pytest tools/library
```

Needs ffmpeg, numpy, soundfile and pyloudnorm.

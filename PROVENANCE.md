# Provenance

Cutwright is a fork. This file records exactly what came from where, so the
originals never have to be trusted or touched again.

## Sources (read only, never modified)

| what | path | role |
|---|---|---|
| RecapStudio v2 | `C:\Users\user\Downloads\RecapStudio_v2_ui_videopad\RecapStudio_v2_ui` | engine + web UI + project template |
| videopad | `C:\Users\user\Downloads\videopad` | VideoPad automation research + tooling |

## What was copied

Code and text only, into `vendor/`. 89 files, 0.68 MB total.

**From RecapStudio** (42 files) -- `RecapStudio\**` filtered to
`.py .bat .json .md .txt .html .js .css .csv .vpj`, excluding `Projects\`
entirely:

* `_template\recap.py` (127 KB) -- the engine whose conventions this fork follows
* `studio.py`, `web\*` -- the local web UI
* every `.bat` step script, `config.json`, `project.json`, `segments.json`
* the `PASTE_THIS_TO_CLAUDE*.txt` prompt files

**From videopad** (47 files) -- `agent\`, `docs\`, `examples\`, `tools\`, root
`*.md`, excluding `.git\`, `out\`, `logs\`:

* `docs\HANDOFF.md`, `docs\vpj-format-findings.md`, `docs\AGENT-RUNBOOK.md`
* `tools\*.ps1`, `tools\NativeInput.cs`, `tools\effects.json`
* `examples\cut*.json` -- the recorded VideoPad command shapes

## What was deliberately NOT copied

* **All media.** 334 `.mp4`, 1 `.mkv`, 301 `.mp3`, 298 `.wav`, 35 `.srt`,
  24 `.ass` -- that is ~5.3 GB of footage, audio and subtitles. Source media is
  referenced by absolute path and read only.
* **`keys.env`** -- API keys. Not copied, not read into this fork.
* **`*.exe`** -- the bundled VideoPad installers (~6 MB).
* **`.git\`** -- history belongs to the original.
* **`Projects\`** -- per-project data, not code.
* **`out\`, `logs\`** -- generated artifacts.

## Manifest

`vendor\MANIFEST.sha256` holds a SHA256 for every vendored file, in
`hash  relative\path` form (relative to `vendor\`).

Verify the vendored tree against the manifest:

```powershell
cd C:\Users\user\Desktop\Cutwright
Get-Content vendor\MANIFEST.sha256 | ForEach-Object {
    $hash, $rel = $_ -split '  ', 2
    $now = (Get-FileHash (Join-Path 'vendor' $rel) -Algorithm SHA256).Hash.ToLower()
    if ($now -ne $hash) { "CHANGED: $rel" }
}
```

Verify the originals still match what was copied (proves nothing was altered in
either direction):

```powershell
$v = 'C:\Users\user\Desktop\Cutwright\vendor'
$m = 0
foreach ($p in @(@('recapstudio','C:\Users\user\Downloads\RecapStudio_v2_ui_videopad\RecapStudio_v2_ui'),
                 @('videopad','C:\Users\user\Downloads\videopad'))) {
  $dir = Join-Path $v $p[0]
  Get-ChildItem $dir -Recurse -File | ForEach-Object {
    $src = Join-Path $p[1] $_.FullName.Substring($dir.Length + 1)
    if ((Test-Path $src) -and
        ((Get-FileHash $_.FullName).Hash -ne (Get-FileHash $src).Hash)) { $m++ }
  }
}
"mismatches: $m"
```

## Binaries and models (installed here; not from the originals)

`vendor\MANIFEST.sha256` covers code and text only. These are executables and
weights, downloaded from their publishers and checked against the publisher's
own digest before first use:

| what | lives in | bytes | sha256 | checked against |
|---|---|---|---|---|
| whisper.cpp 1.9.5, Windows x64 build | `bin\whisper\Release\` (`whisper-cli.exe` + DLLs) | 8,928,640 (the zip, kept at `bin\_dl\whisper-bin-x64.zip`) | `6ba69e3482d7826214f90a6a9c84ca07782aec1e1d0c6a7c30c994fd5d816ccb` | GitHub's own `digest` for that release asset |
| `ggml-small.en.bin` (whisper small, English, f16) | `models\ggml-small.en.bin` | 487,614,201 | `c6138d6d58ecc8322097e0f987c32f1be8bb0a18532a3f88f734d1bbf9c41e5d` | the file's HuggingFace LFS pointer `oid` |

Kinocut is not downloaded by this repo: it is a pip package (Apache-2.0, pinned
`kinocut==1.16.4`) installed into `.venvs\kinocut`; the M1 licence and hash record
is in `docs/KINOCUT_FINDINGS.md` and `docs/evidence/`.

Sources:

```
https://github.com/ggml-org/whisper.cpp/releases/download/b5454/whisper-bin-x64.zip
https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin
```

**Why the b5454 nightly and not the v1.9.5 tag:** the v1.9.5 release ships no
binary assets at all (`assets: []`); its notes point at build `b5454`. That
build's `target_commitish` is `d1be6fde`, the same commit v1.9.5 names, and the
binary reports `whisper.cpp version: 1.9.5` when asked. So this is the official
Windows build of the stable release, not a different version.

Re-verify at any time:

```powershell
cd C:\Users\user\Desktop\Cutwright
(Get-FileHash 'models\ggml-small.en.bin' -Algorithm SHA256).Hash.ToLower()
(Get-Item 'models\ggml-small.en.bin').Length          # 487614201
(Get-FileHash 'bin\_dl\whisper-bin-x64.zip' -Algorithm SHA256).Hash.ToLower()
```

**Removed 2026-10-30 (M5, historical).** The editor backend's download, hash,
bundle inventory and the four demo-project hashes written by the old timeline
writer are kept verbatim in `docs/legacy/PROVENANCE_removed_editor.md`.

## Fork policy

* One-way. Code flows out of the originals into this fork. Nothing flows back.
* If a vendored file is changed here to fix a bug, note it in this file -- do not
  silently diverge.
* The originals stay on disk untouched so both pipelines keep working while this
  one is proven.


## 2026-10-29 merge: Recap Studio (phase 3 build) replaces the vendored v2 copy

- Source: owner upload `RecapStudio-phase0.zip` (the name is misleading: it contains the Phase 3 build with
  `authoring.py`, scene kit, Scenes tab). SHA256 of the zip:
  `95f59d711ac3fbfa3b48b2216e9170900d433a3989dca58872c69649f7bc212f`.
- Placed at `recapstudio/` (103 files, 1.2 MB, no secrets; `keys.env.example` only). It is live code, not vendored,
  so it has no manifest; use git.
- `vendor/recapstudio/` (v2, 42 files) was removed. `vendor/MANIFEST.sha256` now covers `vendor/videopad/` only
  (47 files; paths are relative to `vendor\`). The "verify the originals" snippet above no longer applies to
  RecapStudio.
- Cutwright source tree: owner upload `cutwright-main.zip` (GitHub main, no `.git` in the zip).


---

## Architecture change 2026-10-29 (consultant; nothing below was downloaded or run by the consultant)

* **The old editor backend** (262 MB portable bundle + its timeline writer): REMOVED 2026-10-30 in M5.
  Its download URL, hash, bundle inventory and demo-project hashes stay as history in
  `docs/legacy/PROVENANCE_removed_editor.md`.
* **Kinocut** `kinocut==1.16.4` (Apache-2.0 per repo page): NOT vendored. Installed by the user's agent into `.venvs\kinocut`. M1 must record: installed version,
  LICENSE text sha256, `pip list` snapshot.
* **FFmpeg**: installed by `winget Gyan.FFmpeg` (SETUP.bat). M1 must record the `ffmpeg -version` build line (GPL/LGPL flags).
* **OpenMontage** (AGPL-3.0 per repo page): ARCHITECTURAL REFERENCE ONLY. No file, schema, prompt or skill text copied. Any reuse requires the owner's written approval recorded here.
* **FireRed-OpenStoryline**: excluded; nothing used.
  * **HyperFrames**: not installed (benchmark M9 only; Apache-2.0 per its page).

## M1 2026-10-29: Kinocut installed and verified (agent, on the owner's PC)

* **Kinocut `1.16.4`** (pip, exact pin) installed into `.venvs\kinocut` (Python 3.11.9, venv,
  `include-system-site-packages = false`). Not vendored; `.venvs/` is gitignored. Install took
  199.4 s; the venv is 95.7 MB. Full `pip list` (38 packages) is recorded in
  `docs/KINOCUT_FINDINGS.md` section 1.
* **Kinocut LICENSE**: read from
  `https://raw.githubusercontent.com/KyaniteLabs/kinocut/master/LICENSE` on 2026-10-29. Text is the
  Apache License 2.0 (159 lines, "Apache License / Version 2.0, January 2004").
  sha256 = `733474B93E5DF2016FAC0B6DDAF0471850DA64F2ABDB5B45C410C96EC170D837`.
  Wheel metadata agrees: `License-Expression: Apache-2.0`. Home-page `https://kinocut.dev/`.
* **FFmpeg** used by Kinocut and by us: `ffmpeg version 7.1-full_build-www.gyan.dev`,
  configuration contains `--enable-gpl --enable-version3` -> **GPL-licensed build**, called only as
  an external process, never linked or redistributed.
* **OpenMontage LICENSE**: read from
  `https://raw.githubusercontent.com/calesthio/OpenMontage/main/LICENSE` on 2026-10-29. Text is
  "GNU AFFERO GENERAL PUBLIC LICENSE Version 3, 19 November 2007" (544 lines).
  sha256 = `0D96A4FF68AD6D4B6F1F30F713B18D5184912BA8DD389F86AA7710DB079ABCB0`.
  Clean-room policy unchanged: ideas only, no file copied, no source read beyond the LICENSE.
* Nothing from Kinocut or OpenMontage was copied into this repository. No `keys.env`, `voices\`,
  `models\` or `.venvs\` content is committed.


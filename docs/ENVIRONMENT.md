# ENVIRONMENT - measured facts about the owner's PC

Measured values below carry the command that produced them, run on **2026-10-29** (M0).
Two kinds of line are explicitly labelled and are NOT measurements:
`(derived ...)` = arithmetic on measured numbers; `(unverified ...)` = taken from a document
(HANDOFF/ROADMAP) and NOT checked on this PC. Anything not in this file is still unknown.

## Machine

```
[System.Environment]::OSVersion.VersionString -> "Microsoft Windows NT 10.0.26200.0"
      (verbatim string; which Windows release build 26200 corresponds to was NOT checked)
(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory -> 11.8 GB RAM
      (GPU: (unverified - from HANDOFF) no GPU on this PC; no Win32_VideoController query was run)
Get-PSDrive C -> Used 217,809,924,096 | Free 36,969,922,560
      (derived: Used+Free = 254,779,846,656 B total; doctor independently printed "disk free 34.4 GB")
```

## Interpreters, Node, git

```
py -0p
 -V:3.14 *        C:\Users\user\AppData\Local\Python\pythoncore-3.14-64\python.exe
 -V:3.13          C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe
 -V:3.11          C:\Users\user\AppData\Local\Programs\Python\Python311\python.exe

python --version  -> Python 3.11.9   (C:\Users\user\AppData\Local\Programs\Python\Python311\python.exe)
py -3 --version   -> Python 3.14.7   (C:\Users\user\AppData\Local\Python\pythoncore-3.14-64\python.exe)
node --version    -> v24.18.0        (C:\Program Files\nodejs\node.exe)
npm --version     -> 11.16.0
git --version     -> git version 2.47.1.windows.2
```

**Trap found (A1-adjacent):** `py -3` resolves to **3.14**, `python` resolves to **3.11**.
`recapstudio\SETUP.bat` and ROADMAP M0 step 7 use `py -3`, but `recap.py` runs on `python` (3.11).
Installing with `py -3` therefore installs into an interpreter Recap never uses. Install Recap's
Python packages with `python -m pip` (3.11) until the launchers are changed.

## FFmpeg (three copies on PATH - only the first is used)

```
where.exe ffmpeg ->
  C:\Users\user\scoop\shims\ffmpeg.exe                                  (used; 7.1)
  C:\ffmpeg\bin\ffmpeg.exe                                              (8.0-essentials_build)
  C:\Users\user\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe          (Gyan 9.0.2-full_build)
(Get-Command ffmpeg).Source -> C:\Users\user\scoop\shims\ffmpeg.exe

ffmpeg -version | Select-Object -First 3 ->
  ffmpeg version 7.1-full_build-www.gyan.dev Copyright (c) 2000-2024 the FFmpeg developers
  built with gcc 14.2.0 (Rev1, Built by MSYS2 project)
  configuration: --enable-gpl --enable-version3 --enable-shared ... --enable-libx264 --enable-libass ...
ffprobe -version | Select-Object -First 1 ->
  ffprobe version 7.1-full_build-www.gyan.dev Copyright (c) 2007-2024 the FFmpeg developers
```

A5 holds: the winning ffmpeg is a Gyan build, **not** Shotcut's bundled one (`shotcut\` does not exist:
`Test-Path shotcut -> False`). The scoop shim (`scoop\apps\ffmpeg-shared`) wins over the winget one,
so "Gyan.FFmpeg via winget" is on PATH but not first. All three are Gyan builds; behaviour differences
between 7.1 / 8.0 / 9.0.2 are unmeasured. Do not pin a version yet - M2 measures.

## FFmpeg features needed later (all present)

```
ffmpeg -hide_banner -encoders  -> " V....D libx264  ... (codec h264)", " A....D aac  AAC (Advanced Audio Coding)"
ffmpeg -hide_banner -filters   -> xfade, acrossfade, sidechaincompress, loudnorm, ebur128, subtitles, ass  (all listed)
```
Nothing missing from the M0 list.

## Paths checked

```
Test-Path shotcut               -> False
Test-Path .venvs\kinocut        -> False    (Kinocut not installed yet; M1)
Test-Path shotcut\Shotcut\melt.exe -> False (so M0 step 8 is skipped)
recapstudio\Projects            -> only .gitkeep and _projects_go_here.txt (0 projects at audit time);
                                   regress\ was created later in M0 by copying _template (git-ignored,
                                   see "Recap regression baseline" below)
recapstudio\_template\recap.py  -> 5493 lines
```

## `python -m cutwright doctor` (quoted, M0 step 4)

```
CUTWRIGHT 0.1.0  doctor
root        C:\Users\user\Desktop\Cutwright-kinocut-handoff\cutwright
python      3.11.9
[+] ffmpeg    C:\Users\user\scoop\shims\ffmpeg.EXE
             ffmpeg version 7.1-full_build-www.gyan.dev Copyright (c) 2000-2024 the FFmpeg developers
[+] ffprobe   C:\Users\user\scoop\shims\ffprobe.EXE
             ffprobe version 7.1-full_build-www.gyan.dev Copyright (c) 2007-2024 the FFmpeg developers
disk free   34.4 GB on the fork's drive
originals (read-only, never written to):
  MISSING  C:\Users\user\Downloads\RecapStudio_v2_ui_videopad
  MISSING  C:\Users\user\Downloads\videopad
vendored   48 file(s), 0.37 MB
Recap Studio engine (recapstudio/):
  [+] engine files present (103 files)
  [+] node   C:\Program Files\nodejs\node.EXE
  [+] npm    C:\Program Files\nodejs\npm.CMD
  [ ] remotion npm packages not installed: cd recapstudio/remotion && npm install
  [ ] python edge_tts        Edge-TTS voice (default)
  [ ] python PIL             Pillow: stills, comics, characters
  [ ] python faster_whisper  word timings fallback
  [ ] python requests        downloads
      [i] recap projects: 0 in recapstudio/Projects

write guard self-test:
  [+] inside the fork
  [+] refuses RecapStudio_v2_ui_videopad
  [+] refuses videopad
  [+] refuses outside the fork

transcription / render engines:
  [ ] whisper.cpp  offline transcription fallback   not installed
  [ ] model        ggml weights for whisper.cpp     not installed
  [ ] Shotcut      the .mlt renderer/writer         not installed
      [i] run: python -m cutwright transcribe <video>   for the exact steps
```

This block is verbatim, captured at M0 step 4, i.e. **before** the installs listed further down: the
`[ ]` dependency lines are the pre-install state, not the current one.

Expected/acceptable failures today: Shotcut absent (M5 deletes it anyway), whisper.cpp absent,
Recap Python deps, Remotion packages. Not acceptable after M0: Recap deps + Remotion, because the
regression pack needs a real render. Both are installed now and the real render passed (premiere,
remotion and timeline all exit 0) - see the baseline section below. Re-running
`python -m cutwright doctor` after the installs was NOT done, so its `[ ]` lines remain pre-install.

## Fixtures self-test (M0 step 5) - PASSED

```
python -m unittest discover -s tests -t . -v
  test_roundtrip (tests.test_media_fixtures.FixtureTest.test_roundtrip) ... ok
  Ran 1 test in 0.907s
  OK            (process exit code 0)
```

## Installed during M0 (free, local; nothing paid)

Python packages were installed with **`python -m pip` (3.11.9)** - the interpreter `recap.py` runs on,
*not* `py -3` (see the trap above). Commands run from the repo root:

```
python -m pip install --upgrade requests pillow numpy edge-tts
  -> "Successfully installed ... edge-tts-7.3.1 ... numpy-2.4.6 pillow-13.0.0 requests-2.34.2 ..."
python -m pip install --upgrade av faster-whisper
  -> "Successfully installed av-18.1.0 ... ctranslate2-4.8.4 faster-whisper-1.2.1 ... onnxruntime-1.31.1 ..."
python -c "import faster_whisper, av; ..." -> "faster_whisper 1.2.1" / "av 18.1.0"   (imports OK on 3.11)
```

**Deliberately not installed:** `yt-dlp` and `pymupdf` from SETUP.bat's base list (not needed by the
regression pack; add them when a download/PDF step is actually exercised).
`edge_tts` imports on 3.11 but **no TTS synthesis was run**, so it is installed-not-verified.

Remotion renderer (pinned, unchanged):

```
cd recapstudio\remotion ; npm install --no-audit --no-fund
  -> "added 259 packages in 3m"
  node_modules\remotion\package.json -> "version": "4.0.539"
```

**Remotion first-render download (measured):** the first render downloads *Chrome Headless Shell*, and the
download itself only appears as a file while it is running: a partial `chrome-headless-shell-win64.zip`
plus a `download.lock`, both inside
`recapstudio\remotion\node_modules\.remotion\chrome-headless-shell\`. Transfer samples from this PC:
47.0 MB -> 52.3 MB in 20 s (≈265 kB/s), later samples ≈120-180 kB/s, last sampled size ≥97 MB.
**On a successful download Remotion deletes the zip** and unpacks the browser to
`...\.remotion\chrome-headless-shell\win64\chrome-headless-shell-win64\chrome-headless-shell.exe`
(next to a `VERSION` file) - verified: that .exe exists on this PC and the zip is gone.
Rule of thumb: a *present* zip = still downloading; an *absent* zip beside `win64\` = installed.
Do not mistake that wait for a hang, and do not delete `node_modules\.remotion` afterwards.

Network speed on this PC (measured samples): pip 96-573 kB/s, npm 259 packages in 3 min, Chrome download
120-265 kB/s. This is the main cost driver for installs; budget minutes, not seconds.

## Recap regression baseline (M0 step 6, project `recapstudio\Projects\regress`)

Measured 2026-10-29 on this PC (`python` 3.11.9). Commands, quotes and exit codes: `LOG.md`.

```
recap_final.mp4        514 frames, 1920x1080, r_frame_rate 24/1, h264 + aac 48000/2,
                       6,834,110 B, duration 21.416667 s  (matches the Linux baseline 514 / 21.4 s / 6.8 MB)
timeline.json          6 segments, 514 frames (21.4 s at 24 fps, 1920x1080); captions karaoke;
                       2 chapters; transitions cut x5 + whip x1; pictures generated x3 / keywords x3
scene check            3 of 6 passed (d_01, d_02, d_03). d_04 + d_06 FAILED (x.toUpperCase is not a
                       function / the scene draws nothing), d_05 BLOCKED (uses 'fetch', line 10) ->
                       those 3 segments use the keywords scene. Expected baseline, not an M0 blocker.
premiere_sequence.xml  54,023 B, "6 segments, 0:21", exit 0 (3.6 s wall)
recap_remotion.mp4     "Encoded 514/514", 21.42 s, 5,915,527 B, "[+] PARITY CHECK PASSED" vs
                       recap_final.mp4 within one frame, exit 0 (96.4 s wall) -> DERIVED rate
                       514 / 96.4 = 5.33 fps for the whole command (no rate is printed by recap.py)
word timings           6 x "even". Whisper 'base' loads (6.50 s) and inference runs (0.96 s on one
                       segment) but returns 0 words on the fixture's tone-audio narration, so `even`
                       is used. Whisper word timing FROM REAL SPEECH: NOT verified (needs real voice).
timeline step          exit 0 (26.6 s); all six words/<id>.json byte-identical to the pre-run backup
```

Not measured, do not quote: scene-check-only duration (never captured - the `scenes` run went detached
and no step prints per-phase timings), and the exit codes of `demo`, `briefs`, `video` and the
standalone `scenes` runs.

## Still unknown after this file was written

- Kinocut install/behaviour on Windows (M1) - `.venvs\kinocut` does not exist.
- Remotion render *rate*: one DERIVED sample only (5.33 fps, see "Recap regression baseline"); no second
  sample, nothing measured at another resolution.
- Scene-check duration: NEVER CAPTURED - the `scenes` step ran detached and no recap.py step prints
  per-phase timings. Do not quote a scene-check time from this audit.
  `recap.py` exit codes for `premiere`, `remotion` and `timeline` WERE captured later in M0: all 0.
- Whisper word-timing generation from REAL SPEECH: not verified (the fixture's narration is tone audio).
- Which of the three FFmpeg builds the executor should pin (M2).

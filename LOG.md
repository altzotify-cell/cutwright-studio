# Log

Newest last. A timestamp is when the line was written, not when the work began;
`~` marks a time reconstructed from the transcript rather than read off a clock.
Everything before 2026-10-24 has no clock on it -- the log starts with the fade.

## 2026-10-24

```
~11:20  fade      wrote Project.set_fade / _fade_filters in cutwright/mlt.py:
                  brightness level 0->1 and volume level -60dB->0, both animated,
                  both on the tractor (producer-level filters do nothing here).
~11:35  fade      first demo_fade build: 4 checks pass, fade check fails. Head
                  measured 26 luma against 129 in the middle.
~11:50  probe     four spellings of the keyframe positions (relative, absolute,
                  clock-time, tractor vs playlist) all behaved identically, and
                  the "fade" appeared to start black 35 frames before it should.
~12:05  profile   cause found: melt ignores the .mlt's own <profile> and renders
                  at 25 fps unless -profile is passed. Proven with a hard cut:
                  a cut at source frame 377 showed up at render frame 63 (25 fps
                  x 0.52 s) instead of 77. Profile.write_file() now writes a
                  .prof beside every render and _melt_render passes -profile.
~12:20  profile   re-probed with -profile: the cut moved to frame 76 and the
                  "black tail" turned out to be the source's own scene change.
                  Nothing was wrong with the filter. All four old checks still
                  pass on demo_cuts, and demo_cuts.mlt is byte-identical
                  (4234355f...), so the fix changed renders, not the writer.
~12:40  fade      rewrote check_fade to measure against a control: the same
                  project re-rendered by this writer with the fade removed, then
                  divided frame by frame. The old yardstick (middle of the
                  timeline) read a brighter shot as "full brightness".
12:46  fade       demo_fade build: all five checks pass. Level 0.00 at frame 0,
                  0.28 half way into the fade in, 0.99 at frame 24, 1.00 at 279,
                  0.45 half way into the fade out, 0.01 at the last frame,
                  0.99-1.00 inside the body; sound -76.0 dB at the head against
                  -23.5 dB in the middle.
12:49  docs      README (five checks, fade section, the -profile finding),
                  PROVENANCE (demo_fade hash, and the note that demo_cuts' hash
                  did not move), REPORT.md and this log created.
~12:55 titles    titles were written into V2 and never appeared: melt 7.41 here
                  ignores a blend's a_track=0 for any track above V1 -- it
                  composites onto the *background* instead of the running
                  picture. Shotcut writes a_track=0 in its own files; this writer
                  had copied it. Three-track probe (black / green / red):
                  composite a=0 b=2 changed nothing, a=1 b=2 put red over green
                  in the requested half. Centre-band YMAX 195 -> 250 on the demo.
~13:05 titles    first control that "removed the titles" removed V2 with them:
                  cairo then moved every frame by 33 dB and melt skipped a blend
                  whose b-frame never arrived, which is louder than the defect
                  being looked for. Replaced with no_title_text: the same
                  producer, the same track, the same frames, one <filter> left
                  out. Frame 25 went to inf; frames 96/190/258 still read 32-36
                  dB.
~13:20 titles    that residue was the codec, not the text: under H.264 a bright
                  title is carried a little way into the frames after it through
                  inter prediction. check_titles now renders both sides itself at
                  crf=0 (about 8 MB and a few seconds a side); the quiet frames
                  are then bit-identical. The render check's own proof stays
                  lossy at 270 wide.
13:32  titles    demo_title build: all six checks pass -- band 23.3 / 20.0 / 20.6
                  dB against 29.5 / 26.2 / 26.8 dB whole-frame at the first,
                  middle and last frame of title 1, 23.8 / 26.3 / 21.3 against
                  29.9 / 32.4 / 27.5 dB for title 2, and frames 25, 96, 190, 258
                  identical to the control.
13:32  docs      README (six checks, Titles section, the a_track finding, plan
                  schema), REPORT (demo_title section and row), this log.
13:58  titles    cairoblend now defaults a_track to b_track - 1, but the audio
                  `mix` transitions pass a_track=0 explicitly: audio sums into
                  the background frame (Shotcut writes it that way) and only the
                  picture needs the running track as its a-frame. The blanket
                  default had rewritten the A1 mix line too and moved both older
                  demos' hashes for no measured gain; rebuilt at this commit,
                  demo_cuts and demo_fade are byte-identical again. demo_title
                  was rebuilt twice and is byte-identical to itself.
```

## 2026-10-24, afternoon: the titles the GUI could not see

```
14:02  tags      v0.1-cuts on de91e19, v0.2-fade on 72ee8f3, v0.3-titles on
                  ef24bf1, annotated, pushed; ls-remote shows all three.

14:10  report    from the GUI: with V1 hidden the title shows over black, with V1
                  visible it is covered. So in Shotcut's preview the text is
                  *below* V1, while melt draws it on top of V1 -- same file.

14:20  evidence  Shotcut also wrote over demo_title.mlt itself (13:59), and
                  demo_title_saved.mlt is a second save (14:07). Both are
                  Shotcut's rewrite: every a_track 0, the title blend included.
                  Held as PROVENANCE 22,464 / b5917c63....

~14:25 probes    rendering those rewrites settles which side is right. Frame 61,
                  band PSNR against the same file with the text filters removed:
                    ours (a_track 1)        20.0 dB  text drawn
                    Shotcut's save (a=0)    inf      no text at all
                    a=1 on Shotcut's save   20.0 dB  text drawn
                    a=0 + V1 hidden         inf      still no text
                    swapped track order     inf
                    qtblend a=0 / a=1       inf / 11.9 dB
                    composite a=0 / a=1     inf / 11.9 dB
                  So it is not the service and not the track order: MLT 7.41
                  composites into the a-frame, a=0 means the background frame,
                  and the background is painted before V1. Shotcut's own save
                  therefore contains no title -- its preview was telling the
                  truth about the file it had written.

14:35  decision  a title that rides a transition rides a number the editor owns.
                  Titles became dynamictext filters with in/out windows *inside
                  the V1 playlist*: a track filter, which Shotcut round-trips as
                  it finds it (it kept playlist0's audiolevel filter untouched).
                  V2 and its blends are gone; the file is 127 elements, 3 tracks.
                  Probe before writing it: window on at frames 61 and 224 (11.9
                  and 14.3 dB), off at 120 (inf).

14:40  check 7   `shotcut`: refuses any enabled blend whose b-track carries text,
                  then applies Shotcut's rewrite (a_track -> 0) and renders both
                  sides of it, asking the titles question again. Validated both
                  ways: on the old file with the guard bypassed it reports
                  "title 1 is gone after the rewrite ... frame 61 reads inf dB";
                  on the new file, "the rewrite changes no blend".

14:45  melt      the build then hung: 311 frames and 10.377 s written, process
                  alive minutes later with CPU frozen, both under the task
                  scheduler and once from a shell. Cause: eof=pause on every
                  producer plus a last entry that ends exactly on the last frame
                  -- V2's trailing blank used to supply the pull past the end.
                  Consumer now gets terminate_on_pause=1, and _melt_render trusts
                  only the file: a pass that has stopped writing, whose output
                  already holds the length asked for, is finished.

14:52  build     demo_title: all seven checks pass. Band 23.3 / 20.0 / 20.6 dB
                  against 29.5 / 26.2 / 26.8 whole-frame (title 1), 23.8 / 26.3 /
                  21.3 against 29.9 / 32.4 / 27.5 (title 2), frames 25/96/190/258
                  identical, shotcut "the rewrite changes no blend". Project
                  7,101 bytes / 28336a58....

14:55  hashes    demo_cuts and demo_fade rebuilt at this commit: 4234355f... and
                  ad9335d1..., byte-identical to PROVENANCE. Their checks.json and
                  digest.txt churn was only timestamps and render wall-clock, so
                  those four files were reverted rather than committed.

14:58  docs      README (seven checks, Titles section rewritten around the GUI
                  evidence, the track-filter mechanism, the fourth melt
                  behaviour), REPORT (demo_title section, check table with
                  shotcut), PROVENANCE (new hash, the Shotcut-saved copy and what
                  it proves), this log.

~19:20  dissolve  Crossfade renderer working shape found. Shotcut disables V1's
                  blend on every save (`disable=1`), which is why every flat
                  multitrack dissolve died in the GUI while melt drew it; the
                  whole story is in HANDOFF.md. Working layout: a nested tractor
                  played as one V1 entry, outgoing tail on track 0, incoming head
                  on track 1 with a `brightness` alpha ramp keyed to its own
                  frames, one `frei0r.cairoblend` a=0 b=1 inside the tractor. A
                  `luma` in the same place ramps wherever it likes (ten variants
                  tried), which cost most of the afternoon.
                  melt frames 34/40/48 = (214,0,234) / (229,55,239) / (252,255,252);
                  Shotcut at seek 0.25 / 0.60 / 0.85 = (255,0,254) / (253,108,253)
                  / (255,255,255). Both engines agree, and a Ctrl+S keeps the
                  filter, its keyframes and the inner blend.
                  Not yet wired into `Project.to_xml()`, which still emits the
                  `luma` shape -- so `projects\demo_cross` fails `gui_xfade` and
                  its checks.json is from an older run besides. Paused here at the
                  user's request; HANDOFF.md carries the edit and the order of
                  work.

```

## 2026-10-29 (merge; written by the Claude consultant, not the agent)

```
~14:50  merge     Cutwright + RecapStudio (phase 3 build, file name said phase0) joined in one tree.
                  recapstudio/ = full new engine (103 files); vendor/recapstudio/ (old v2) removed;
                  vendor/MANIFEST.sha256 regenerated for vendor/videopad only (47 files).
                  guard.py: RECAP constant. cli.py: doctor reports the engine (_doctor_recap).
                  .gitignore: recapstudio secrets/models/venvs/Projects/node_modules.
                  docs/: ARCHITECTURE, GOALS (G0-G16), TOOLS, CODEMAP, VISUAL_STANDARD, legacy/.
                  HANDOFF.md and .clinerules rewritten for the merged project.
proof   python -m cutwright doctor (Linux sandbox): "[+] engine files present (103 files)", Node found,
        remotion npm "not installed" (registry unreachable from the sandbox, so NO Remotion run).
proof   recap.py demo -> briefs --demo -> video -> timeline in a copy of _template, sandbox:
        "timeline.json: 6 segments, 514 frames (21.4s at 24fps)", "Timeline check passed",
        ffmpeg video 21.4 s expected 21.4 s. Scenes reported NOT CHECKED (Remotion missing) and fell back
        to keywords, as designed.
proof   python -m compileall on all recapstudio python: OK; node --check on app.js and the two .mjs tools: OK.
not run Remotion install/render, scenes check, Windows steps, anything in cutwright/ besides doctor.
note    doctor's "[!] refuses outside the fork" fails ONLY on Linux (the test path is C:\Windows\...).
```

## 2026-10-29 (plan revision, consultant)

```
~20:50  plan      Owner pointed out the Shotcut work was under-covered. Goal ladder rebuilt:
                  G1 crossfade (old Phase 0), G2 recon of borrow repos, G3 adopt cli-anything-shotcut,
                  then the Recap/Remotion track (G4-G7), G8 Blueprint + backend interface, G9 any-video,
                  G10 Hyperframes bake-off, G11-G16 SFX / polish / speed / MCP+skill / Studio / other modules.
                  Added docs/VISION_cutwright_v2.md (owner's master doc), docs/BORROW_notes.md.
                  Owner decisions: Shotcut track first; Hyperframes = bake-off, Remotion stays.
fact    cli-anything-shotcut: MIT, 1.0.0 Beta (PyPI 2026-03-13); HyperFrames: Apache-2.0, headless Chrome + FFmpeg.
        Source: web pages only (not repo code). Verified nothing by running it.
```

## 2026-10-29 (architecture change; written by the Claude consultant, not the agent)

```
~21:30  arch      Decision (owner): Kinocut is the primary editing infrastructure, used together with direct FFmpeg; Shotcut removed from the target
                  architecture; OpenMontage = architectural reference (clean-room, AGPL); FireRed excluded; Remotion kept; HyperFrames to be benchmarked.
                  Prepared for DeepSeek in Cline: HANDOFF.md, .clinerules, docs/{ARCHITECTURE,ROADMAP,MIGRATION_CHECKLIST,REFERENCES}.md,
                  docs/schemas/manifest.example.json, tests/media_fixtures.py (+ self-test). Old docs bannered as superseded.
proof   Linux sandbox, ffmpeg 6.1.1: cp -r recapstudio/_template; RECAP_NONINTERACTIVE=1 python3 recap.py demo / check / video / timeline ->
        "Done. recap_final.mp4  (21.4s, expected 21.4s)" ; "timeline.json: 6 segments, 514 frames (21.4s at 24fps, 1920x1080)" ; "Timeline check passed".
proof   python3 -m unittest discover -s tests -t . -v -> "Ran 1 test ... OK" (frame ids 0..95 read back exactly, 4 beeps on whole seconds, 96 frames).
not run Windows anything; Remotion; Kinocut install/CLI/Windows; HyperFrames; any Shotcut check; git (ZIP has no .git); whisper.
note    Kinocut could not be installed in the sandbox (no network). Every Kinocut statement is a README claim until M1/M2 verify it.
```

## 2026-10-29 (objective 1: rules migration + new GitHub repo; agent)

Scope: project housekeeping only. No dependencies installed, no implementation started.
```
TESTED      - rules split : Get-ChildItem .clinerules -> "d----- .clinerules" with 00-core-workflow.md (1805 B),
              01-architecture-and-constraints.md (1630 B), 02-testing-and-evidence.md (792 B), 03-session-boundaries.md (1594 B);
              old root file gone (Remove-Item, then Rename-Item .clinerules.new -> .clinerules).
TESTED      - every old rule kept : Select-String over .clinerules\*.md for 60 keywords from the old file
              (session start, pre-flight, editing, executor rule, exclusions, done steps, stuck, cost) -> no "MISSING:" lines,
              "coverage check done".
TESTED      - Cline support : docs.cline.bot Rules -> ".clinerules/ , .cline/rules/ Supported workspace rule directories";
              "Cline processes rule files inside either directory, combining them into a unified set of rules";
              "Numeric prefixes (like 01-coding.md) help organize files but are optional."
TESTED      - secret/asset audit before commit : 208 files / 1.83 MB, 0 files > 200 KB, 0 __pycache__, no venv/node_modules,
              no keys.env/.env/*.key/*.pem; `git grep --cached` for sk-/ghp_/github_pat_/AKIA/AIza/xox/PRIVATE KEY/password=
              -> no matches (exit 1).
TESTED      - first commit : git init -b main; git add -A; "210 files changed, 38069 insertions(+)",
              f621e5fde82d2fe89e4a04570fa6a447534475cd "Initial import: merged Cutwright + Recap Studio (Kinocut-first handoff)".
TESTED      - new repo + push : gh repo create altzotify-cell/cutwright-studio --public --source . --remote origin --push ->
              "https://github.com/altzotify-cell/cutwright-studio", "branch 'main' set up to track 'origin/main'",
              "* [new branch]      HEAD -> main".
TESTED      - remote URL + push verified : git remote -v -> "origin https://github.com/altzotify-cell/cutwright-studio.git
              (fetch|push)"; git ls-remote origin refs/heads/main -> f621e5f... (== local HEAD); git status -sb ->
              "## main...origin/main"; gh api .../contents/.clinerules -> the four .md files.
TESTED      - old repos untouched : gh repo list altzotify-cell -> cutwright pushedAt 2026-10-26T21:59:31Z,
              RecapStudio 2026-10-28T12:13:47Z (both unchanged).
FAILED      - none.
NOT TESTED  - Cline Rules panel listing the four files : no claude-dev extension in %USERPROFILE%\.vscode\extensions,
              so it cannot be inspected from this session. Path is the documented one; owner can confirm in the panel.
NOT TESTED  - everything else (M0 baseline, Kinocut, FFmpeg, Remotion, ffmpeg -version, python -m cutwright doctor).
DECISIONS   - repo name cutwright-studio, public (matches the owner's other project repos; flip with
              `gh repo edit --visibility private` if wanted).
DECISIONS   - one file stays untracked by design: recapstudio/Projects/_projects_go_here.txt, because recapstudio/.gitignore
              "Projects/*" overrides the root negation (`git check-ignore -v` quote). Not fixed; not needed.
DECISIONS   - commit message file kept outside the repo (..\commitmsg-initial.txt) so it is not part of the tree.
```

## 2026-10-29 (M0: environment audit + baseline; agent)

Scope: M0 steps 2-7 only. Installed local, free dependencies (Python 3.11 packages + Remotion packages);
no application code edited. Facts table: `docs/ENVIRONMENT.md`. M0 is NOT complete (see NOT TESTED).
```
TESTED      - git : git status -sb -> "## main...origin/main"; git log --oneline -5 -> "c1ba7df", "b9bf336",
              "f621e5f"; git rev-parse --show-toplevel -> the repo root; remote = altzotify-cell/cutwright-studio.
TESTED      - versions : py -0p -> "-V:3.14 *", "-V:3.13", "-V:3.11"; python --version -> "Python 3.11.9";
              py -3 -c -> "3.14.7" (so `py -3` != `python`); node -> "v24.18.0"; npm -> "11.16.0";
              git -> "2.47.1.windows.2"; OSVersion.VersionString -> "Microsoft Windows NT 10.0.26200.0";
              RAM 11.8 GB; C: Free 36,969,922,560 B.
TESTED      - ffmpeg : where.exe ffmpeg -> "C:\Users\user\scoop\shims\ffmpeg.exe", "C:\ffmpeg\bin\ffmpeg.exe",
              winget Links; (Get-Command ffmpeg).Source -> the scoop shim; ffmpeg -version ->
              "7.1-full_build-www.gyan.dev"; ffprobe -> "7.1-full_build-www.gyan.dev". Not Shotcut's build
              (Test-Path shotcut -> False; shotcut\Shotcut\melt.exe -> False).
TESTED      - ffmpeg features : -encoders -> libx264, aac; -filters -> xfade, acrossfade, sidechaincompress,
              loudnorm, ebur128, subtitles, ass -> nothing from the M0 list is missing.
TESTED      - doctor : python -m cutwright doctor -> "[+] ffmpeg", "[+] ffprobe", "disk free 34.4 GB",
              guard "[+] inside the fork / refuses RecapStudio_v2_ui_videopad / refuses videopad / refuses
              outside the fork"; "[ ] whisper.cpp", "[ ] Shotcut" (expected). Full output in ENVIRONMENT.md.
TESTED      - fixtures : python -m unittest discover -s tests -t . -v -> "Ran 1 test in 0.907s", "OK", exit 0.
TESTED      - recap demo/briefs : python recap.py demo -> "Demo media + audio + segments.json created.";
              python recap.py briefs --demo -> "Added 3 motion briefs (d_02, d_04, d_06) and a demo theme."
TESTED      - recap video : "Done. recap_final.mp4  (21.4s, expected 21.4s)"; ffprobe -> nb_frames=514,
              1920x1080, r_frame_rate=24/1, h264 + aac 48000/2, size=6834110, duration=21.416667. Equal to the
              Linux baseline (21.4 s / 514 frames / 6.8 MB).
TESTED      - recap timeline + scene test : "Test render (5 scene(s); the first run downloads a headless
              browser)...", "tested d_01/d_02/d_03/d_04/d_06", "[ok] d_01", "[ok] d_02", "[ok] d_03",
              "[FAILED] d_04 - x.toUpperCase is not a function", "[BLOCKED] d_05 - line 10: uses 'fetch'
              (network access)", "[FAILED] d_06 - the scene draws nothing",
              "3 scene(s) passed, 3 replaced by the keywords scene.", "timeline.json: 6 segments, 514 frames
              (21.4s at 24fps, 1920x1080)", "Timeline check passed: every file exists and every clip matches
              its frame count."
              Completion evidence (exit code NOT captured - launched detached): stdout ends with "Next: run
              'Render with Remotion'" (mtime 21:51:48), stderr 0 bytes, scenes\_work removed at the end,
              22 check PNGs written 21:51:27-21:51:45, timeline.json + scenes\_cache.json at 21:51:47.
TESTED      - dependencies : python -m pip install --upgrade requests pillow numpy edge-tts ->
              "Successfully installed ... edge-tts-7.3.1 ... numpy-2.4.6 pillow-13.0.0 requests-2.34.2";
              python -m pip install --upgrade av faster-whisper -> "... av-18.1.0 ... ctranslate2-4.8.4
              faster-whisper-1.2.1 ... onnxruntime-1.31.1"; import check on 3.11 -> "faster_whisper 1.2.1",
              "av 18.1.0".
TESTED      - remotion packages : cd recapstudio\remotion; npm install --no-audit --no-fund -> "added 259
              packages in 3m"; node_modules\remotion\package.json -> "version": "4.0.539" (pin unchanged).
TESTED      - headless browser : first render downloaded Chrome Headless Shell (47.0 -> 52.3 MB in 20 s,
              >=97 MB sampled); after unpacking the zip is gone and
              ...\.remotion\chrome-headless-shell\win64\chrome-headless-shell-win64\chrome-headless-shell.exe
              exists. So "zip absent" means installed, not failed.
FAILED      - nothing failed outright. Two tool-level interruptions occurred, neither produced an error from
              recap.py: (a) the first `video` run was killed by a 30 s tool timeout at segment 4/6 and was
              re-run to completion; (b) a polling loop was stopped as repetitive after the scene run had
              already finished.
NOT TESTED  - WHISPER (M0 step 7) : faster-whisper is installed but was NEVER EXECUTED. The scene run printed
              "[+] word timings: 6 cached" - those are the 'even' timings cached from the pre-install run, so
              cached output is NOT proof of Whisper. The line "word timings ...: whisper" was never seen.
NOT TESTED  - PREMIERE EXPORT : `python recap.py premiere` was not run.
NOT TESTED  - REMOTION PARITY : `python recap.py remotion` ("PARITY CHECK PASSED") was not run.
NOT TESTED  - M0 step 8 : shotcut\Shotcut\melt.exe is absent, so the Shotcut check table is skipped by design.
NOT TESTED  - exit codes of recap.py steps; edge_tts synthesis (installed, imports, never used); Kinocut (M1);
              yt-dlp + pymupdf (deliberately not installed).
DECISIONS   - installed Recap's Python packages with `python -m pip` (3.11), not ROADMAP's `py -3`, because
              `py -3` is 3.14 on this PC while recap.py runs on 3.11. Verified by importing every package on 3.11.
DECISIONS   - ran the installs myself instead of asking the owner to run SETUP.bat (rule: never ask the owner to
              run what the agent can run). SETUP.bat's yt-dlp + pymupdf were skipped as unused by the pack.
DECISIONS   - created recapstudio\Projects\regress by copying _template (git-ignored via recapstudio/.gitignore
              "Projects/*"), as the regression pack's "create once" step asks.
DECISIONS   - reverted recapstudio/remotion/src/generated/registry.ts to HEAD. scenes.py had regenerated it with
              regress-project data ("demo noir" theme, d_01-d_03 metas) importing the git-ignored s_d_*.tsx files,
              so committing it would break typecheck and leak scratch state. Verified: `git diff` empty, file
              size 287 B == HEAD.
DECISIONS   - package-lock.json (146,002 B, lockfileVersion 3, remotion pins 4.0.539 == package.json) is left
              UNTRACKED and unmodified: lockfile policy is the owner's decision (DEFERRED, not decided here).
```

## 2026-10-29 (M0 follow-up: Premiere / Remotion / Whisper; agent; accepted by the owner)

Runs on the regress project (`recapstudio\Projects\regress`, `python` 3.11.9), one check at a time, each
launched so its real exit code landed in a file (this shell kills its process tree at ~30 s).
Logs: `%TEMP%\m0\*.out.txt|.err.txt|.code.txt`. This entry SUPERSEDES the "NOT TESTED - PREMIERE
EXPORT" and "NOT TESTED - REMOTION PARITY" lines of the entry above, and PARTLY SUPERSEDES its "NOT
TESTED - WHISPER (M0 step 7)" line: Whisper now runs, but the `word timings ...: whisper` mode still never
appeared (see below). It also narrows that entry's "exit codes of recap.py steps" note: premiere, remotion
and timeline exit codes are now captured (0), while demo, briefs, video and the standalone `scenes` run
still are not. M0 is still NOT complete.

```
TESTED     - Premiere XML export : python recap.py premiere -> exit 0 (3.6 s), stderr 0 bytes,
             "Done. 'premiere_sequence.xml' written: 6 segments, 0:21."; file 54,023 B, 22:03:36. PASS
TESTED     - Remotion parity : python recap.py remotion -> exit 0 (96.4 s; render 1.2 min),
             "Encoded 514/514", "Done. ...recap_remotion.mp4  (21.42s, expected 21.42s ...)",
             "[+] PARITY CHECK PASSED: length matches the timeline within one frame.",
             "vs recap_final.mp4: 21.42s -> within one frame"; output 5,915,527 B, 22:07:25.
             Duration matches the timeline within one frame. PASS
TESTED     - Whisper EXECUTION only : the same runs printed "[i] loading the Whisper 'base' model for
             word timings (first time downloads it)...", and a read-only probe on d_01 gave
             "WhisperModel('base') loaded (6.50s)", "info: lang=nn p=0.22 dur=3.21 (0.96s)",
             "total segments=0" (identical on audio\d_01.mp3). Model loaded and inference ran; ZERO
             words returned because the fixture's narration is synthetic tone audio (recap.py:4502,
             step_demo: aevalsrc=0.6*sin(2*PI*220*t)...). So faster-whisper 1.2.1 + av 18.1.0 do work
             on this PC, and the old `metadata_errors` failure did not recur.
TESTED     - Timeline check : python recap.py timeline -> exit 0 (26.6 s), "[+] Timeline check passed:
             every file exists and every clip matches its frame count."; all six words/<id>.json stayed
             byte-identical (SHA-256) to the pre-run backup in %TEMP%\m0\backup_words; timeline.json
             differs from the backup only in its "generated" timestamp. PASS
NOT TESTED - WHISPER WORD-TIMING GENERATION FROM REAL SPEECH. The line "word timings <id>: whisper" was
             never produced; the `whisper` timing path is NOT verified and must not be claimed as passed.
             It is unreachable with the current fixture: the audio is a tone, Whisper correctly returns
             no words, and wordtimes falls back to "even" ("[+] word timings: 6 even"). Needs real
             narration - an owner decision, not something M0 could settle.
SKIPPED    - Shotcut / melt check : NOT AVAILABLE - shotcut\Shotcut\melt.exe is absent (Test-Path ->
             False), so the M0 step 8 table is skipped by design (Shotcut is deleted in M5 anyway).

Baseline numbers (M0 step 6; machine facts live in docs/ENVIRONMENT.md):

- Remotion render rate: 514 frames / 96.4 s = 5.33 fps  (derived: frame count from "Encoded 514/514"
  in the run above, wall time from the same run's 96.4 s; recap.py printed no rate, so this is arithmetic
  over two quoted numbers. Whole-command wall time, so it includes Node/Remotion start-up. ROADMAP's
  expectation for this PC is "~5.7 fps" - same order, not a discrepancy to chase.)
- Scene-check duration: NOT CAPTURED. No duration exists in any log: the `scenes` step in the entry above
  was launched detached, so its start time and exit code were never recorded (only file mtimes), and no
  recap.py step prints per-phase timings. Bounds that do exist, none of them a scene-check figure: the 22
  check PNGs of that run span 21:51:27-21:51:45 (that run spent >= 18 s there), and the later `timeline`
  run - which runs the same 6-scene check - took 26.6 s in total (segment build + Whisper load + scene
  check + timeline check). Do not report 18 s or 26.6 s as the scene-check time.

Limitations to carry forward:
- Cache bypass used, nothing deleted: wordtimes.ensure() ignores an existing "even" entry once
  faster_whisper is importable and captions.whisper_model != "off" (here "base") - wordtimes.py:228-230.
  Cache unit = words/<id>.json (CACHE_VERSION|mp3 size+mtime|caption text|model|frames|fps|raw-edge).
  No other cache invalidated; the fixture, audio/ and audio_trim/ were left as they were.
- The `remotion` and `timeline` steps regenerate the tracked recapstudio/remotion/src/generated/
  registry.ts; restored to HEAD after each run (git diff empty).
- The scene check inside the remotion step still replaces 3 of 6 demo scenes with the keywords scene
  (d_04 "x.toUpperCase is not a function", d_05 uses 'fetch', d_06 "draws nothing"): pre-existing demo
  state, not an M0 result.
- Not done here: no installs, no lockfile policy change, no HANDOFF milestone change, no stage/commit/push.
```


## 2026-10-29 (M0 CLOSED: documentation close-out; agent)

Closes M0 against `docs/ROADMAP.md:84` (all commands run and quoted; every failure listed; commit
hash recorded), using the evidence already in this file. **No test was re-run, nothing was
reinstalled, no cache invalidated** - every figure below is quoted from the two entries above, and
arithmetic says "derived". The two entries above stand as written; only the status closing here.

```
TESTED     - (no new runs) This entry adds no measurements. Sources: the entry above (premiere,
             remotion, whisper probe, timeline) and the entry before it (git, versions, ffmpeg,
             doctor, fixtures, demo/briefs, video, scene test, dependencies).
DECISIONS  - M0 accepted as complete although Whisper word timing FROM REAL SPEECH is NOT verified.
             Basis: ROADMAP step 7 is explicitly "not a blocker", step 8 is "optional, skip if absent"
             (melt.exe absent), and ROADMAP:84 asks only that every failure be listed. The gap is
             stated in three places: LOG (below), docs/ENVIRONMENT.md ("Still unknown"),
             HANDOFF.md ("Known unverified").
DECISIONS  - `recapstudio/remotion/package-lock.json` stays UNTRACKED: the lockfile policy is the
             owner's decision and no rule requires it for M0, so it is not part of this commit.
DECISIONS  - the diff is documentation only; no application or generated file was edited, and
             recapstudio/remotion/src/generated/registry.ts remains at HEAD.
```

Final M0 baseline (summary; quotes above, machine facts in `docs/ENVIRONMENT.md`):

| Item | Result | Exit code |
|---|---|---|
| `recap_final.mp4` | 514 frames, 1920x1080, 24/1 fps, 6,834,110 B, 21.416667 s | not captured (detached run) |
| `timeline.json` | 6 segments, 514 frames (21.4 s), karaoke captions, 2 chapters, cut x5 + whip x1 | 0 (`timeline` step, 26.6 s) |
| scene check | 3 of 6 pass; d_04 + d_06 FAILED, d_05 BLOCKED -> those 3 use the keywords scene (expected baseline) | not captured (same detached run) |
| `premiere_sequence.xml` | 54,023 B, "6 segments, 0:21" | 0 (3.6 s) |
| `recap_remotion.mp4` | "Encoded 514/514", 21.42 s, 5,915,527 B, parity vs `recap_final.mp4` within one frame | 0 (96.4 s) |
| Remotion rate | 514 / 96.4 = 5.33 fps (derived, whole command incl. start-up) | - |
| scene-check time | NOT CAPTURED - no timing exists anywhere; do not quote one | - |

| Whisper | 'base' loads in 6.50 s, inference 0.96 s on one segment, 0 words on the fixture's tone audio -> `even`; real-speech word timing NOT verified | 0 (probe) |
| fixtures self-test | "Ran 1 test in 0.907s", OK | 0 |

Documentation updated in this close-out:
- `docs/ENVIRONMENT.md` - new "Recap regression baseline" section (all numbers above); the stale
  "render speed unknown" and "exit code not captured" claims replaced; `recapstudio\Projects` now
  records that `regress\` exists. Nothing probed for `bin\`/`models\` was invented.
- `HANDOFF.md` - status DONE, M0 row ticked, next step M1, Whisper wording corrected (executes,
  real-speech timing still unverified), 3-of-6 scene fallback kept as the expected baseline.
- `docs/MIGRATION_CHECKLIST.md` - section A 8-13 ticked with evidence; 14 left open.
- `LOG.md` - this entry. Entries above unchanged.

Explicitly outstanding, non-blocking: real-speech Whisper word timings (needs owner narration);
scene-check-only duration never captured; 3 of 6 demo scenes still fall back to the keywords scene;
`doctor` not re-run after the installs; lockfile policy undecided; Kinocut untouched (M1);
`shotcut\`, `bin\`, `models\` presence only partly probed (checklist A:14).

Commit: the close-out commit's hash, the push result and the final `git status` are recorded in the
short entry appended below, because a commit cannot contain its own hash.


## 2026-10-29 (M0 close-out commit recorded)

```
TESTED     - commit : git commit -F msg.txt (msg.txt written with the editor, deleted after use, never
             committed) -> "[main e9fb668] M0 close-out: environment facts, baseline numbers, checklist",
             "4 files changed, 427 insertions(+), 20 deletions(-)",
             "create mode 100644 docs/ENVIRONMENT.md"; git rev-parse HEAD ->
             e9fb66808de8fe3870fc94cda5296a9fb19e2199
TESTED     - push : git push origin main -> "To https://github.com/altzotify-cell/cutwright-studio.git"
             (PowerShell rendered git's progress lines as error text and returned exit 1, so the exit
             code alone was NOT trusted). Confirmed on the server instead:
             git ls-remote origin refs/heads/main -> "e9fb66808de8fe3870fc94cda5296a9fb19e2199
             refs/heads/main" (exit 0); git status -sb -> "## main...origin/main" (no ahead/behind);
             origin/main = e9fb668.
NOT TESTED - nothing beyond the commit/push above: no code changed, no test re-run.
DECISIONS  - staged only the four M0 documents (HANDOFF.md, LOG.md, docs/ENVIRONMENT.md,
             docs/MIGRATION_CHECKLIST.md). recapstudio/remotion/package-lock.json stays UNTRACKED: no
             project rule requires it for M0 and the lockfile policy is the owner's decision.
             recapstudio/remotion/src/generated/registry.ts is unmodified (not in the commit).
```

Final `git status` after the close-out: only `?? recapstudio/remotion/package-lock.json` (expected,
untracked by decision) plus this follow-up commit.


## 2026-10-29 (M1: Kinocut isolated install and interface discovery)

Scope: roadmap M1 steps 1-4, 6 and 8-9. No application code touched, no Shotcut code deleted, nothing
staged/committed/pushed. Raw captures in `out/m1/` (gitignored).

```
TESTED     - .venvs ignored before creation : git check-ignore -v .venvs -> ".gitignore:76:/.venvs/"
             exit 0
TESTED     - venv : py -3.11 -m venv .venvs\kinocut -> "venv-exit=0", "=== venv seconds: 75.4 ===",
             "venv-pip-exists=True"; pyvenv.cfg "include-system-site-packages = false", python 3.11.9
TESTED     - install : .venvs\kinocut\Scripts\python -m pip install "kinocut==1.16.4" ->
             "Successfully installed ... kinocut-1.16.4 ...", "kinocut-install-exit=0",
             "=== kinocut install seconds: 199.4 ===", "=== kino.exe present: True ===";
             venv-size-MB=95.7; pip list = 38 packages (venv only, global Python untouched)
TESTED     - doctor : .venvs\kinocut\Scripts\kino.exe doctor -> exit 0, "Kinocut doctor - OK", 9.7 s;
             kino --format json doctor -> success=true, summary.required_ok=true, missing_required=[],
             total_checks=37, passed=10; required checks Kinocut 1.16.4 / mcp-server-import / ffmpeg /
             ffprobe / mcp 1.30.0 / pydantic 2.14.2 / rich 15.0.0 all OK
TESTED     - capabilities : kino --format json video-capabilities -> exit 0; video_edit, subtitles,
             audio, c2pa_signing available; ai_transcribe + still_plates "unavailable"
             (required_dep_missing openai_whisper / pillow)
TESTED     - CLI surface : kino --help -> exit 0, ~200 subcommands, global
             "--format {text,json,auto}" and "--overwrite"; 23 subcommand --help runs all exit 0
TESTED     - trim : kino --format json trim out\fx\a.mp4 -s 1 -d 3 -o ... -> exit 0, 1.7 s,
             {"success": true, "duration": 3.0, "resolution": "160x90"}; ffprobe -count_frames ->
             "nb_read_frames=72" (24 fps x 3 s), audio 141 packets; --accurate identical
TESTED     - merge crossfade : kino --format json merge s1 s2 -t fade -td 1 -> exit 0, 3.5 s;
             ffprobe -> duration 3.000000, 72 frames, audio 3.01 s; frames at 0.5/1.5/2.5 s show one
             bar -> grey 50%-blended bar -> two bars (real blend)
TESTED     - composite-layers : --dry-run then real render of video + 35% magenta solid -> exit 0,
             2.0 s / 48 frames, output has NO audio stream (video-only confirmed); frame at 1.0 s
             shows the magenta band
TESTED     - release-checkpoint : --min-score 80 -> exit 1 "quality_gate_failed: score 59.0 < 80.0";
             --min-score 50 -> exit 0 in 7.0 s, wrote rc50\thumbnail.jpg + rc50\storyboard\frame_0*.jpg
TESTED     - guardrails : second trim to the same -o -> exit 1 {"code": "output_exists"}; with
             --overwrite -> exit 0; kino info missing file -> exit 1 "invalid_input"; layer src
             "../fx/a.mp4" -> exit 1 {"code": "unsafe_layer_source"}
TESTED     - Windows paths : "out\fx dir\café.mp4" info + trim -> both exit 0, output 9648 B on disk;
             253-character nested path -> trim exit 0
TESTED     - no TTY : every probe ran with piped stdout/stderr (no console), exit codes + JSON correct
TESTED     - licences : Kinocut LICENSE (raw.githubusercontent, master) = Apache 2.0, 159 lines,
             sha256 733474B93E5DF2016FAC0B6DDAF0471850DA64F2ABDB5B45C410C96EC170D837; pip metadata
             "License-Expression: Apache-2.0". OpenMontage LICENSE = GNU AGPL v3, 544 lines,
             sha256 0D96A4FF68AD6D4B6F1F30F713B18D5184912BA8DD389F86AA7710DB079ABCB0.
             ffmpeg -version -> "7.1-full_build-www.gyan.dev", "--enable-gpl --enable-version3"
FAILED     - first venv attempt : py -3.11 -m venv .venvs\kinocut was killed by the 30 s tool timeout
             after ensurepip had started; the venv looked complete but "python -m pip" ->
             "No module named pip" (exit 1) for both the upgrade and the install. Recreated the venv in
             a background process (75.4 s) -> pip 24.0 present, install succeeded. Recorded as a rule in
             docs/KINOCUT_FINDINGS.md 7.1.
FAILED     - first Unicode path probe : my probe script passed the literal text "caf\u00e9.mp4" (raw
             string), so Kinocut correctly reported "File not found (archivo no encontrado)". Not a
             Kinocut defect; re-ran with a real "café" name -> exit 0. Also learned that printing
             Kinocut's stderr panel to a cp1252 console raises UnicodeEncodeError (finding 7.4).
NOT TESTED - mix-audio / duck-audio / normalize-audio / subtitles / add-text / fade / resize / crop /
             speed / convert / export / batch / detect-scenes / workflow-validate|plan|render|inspect /
             overlay-video / split-screen / otio-export|import: only --help was checked. Equivalence
             tests are M2.
NOT TESTED - the MCP tool count behind --mcp, and receipts/--resume behaviour of the workflow engine.
NOT TESTED - HDR / 10-bit / non-24-fps sources, and audio behaviour when a composite plan has an audio
             layer.
DECISIONS  - A1 taken with 3.11.9 (owner approved; no 3.12 on this PC). Venv creation and pip install
             must run in a detached/background process: both exceed the 30 s command limit here. A2
             unchanged: subprocess CLI only, no "import kinocut" in cutwright/ (Client() used solely for
             discovery). Global flags go BEFORE the subcommand (measured: exit 2 otherwise), so the
             adapter must emit argv in that order. Prefer --format json (text mode garbles under
             cp1252). Never invoke bare kino (it starts an MCP server and exits 0 on stdin EOF).
             composite-layers needs absolute -o / --save-layer-plan paths and inputs inside the spec
             directory. Per-call start-up is ~1.3-1.8 s, which M3 must design around.
```

Docs written: `docs/KINOCUT_FINDINGS.md` (new), `PROVENANCE.md` (M1 section with licence sha256s),
`docs/REFERENCES.md` (licence table filled). `HANDOFF.md` status block deliberately NOT ticked yet -
the owner has not approved committing M1, and M2 has not started.


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

## 2026-10-29 - M2: equivalence verification (Kinocut vs current code vs direct FFmpeg)

New: `tests/kinocut_vs_current/` (harness + 12 test modules, measurement only),
`docs/CAPABILITY_MATRIX.md`, `docs/evidence/m2_*.json` (20 files). `cutwright/` and
`recapstudio/` were NOT modified and Shotcut code was not deleted (owner constraint).
Fixtures/outputs live under `out/m2/` (gitignored).

TESTED     - whole M2 suite : `python -m unittest discover -s tests -t . -v` ->
             "Ran 21 tests in 328.937s" / "OK" (0 failures, 0 errors, 0 skips)
TESTED     - evidence count : `Get-ChildItem docs\evidence\m2_*.json` -> 20 files
TESTED     - trim frame accuracy : kino trim on a 240-frame 24 fps counter clip at starts
             0/1/37/119 -> ids exactly range(start, start+len) in 2.09-3.48 s; direct ffmpeg
             (`-ss` after `-i`) also exact in 0.64-0.94 s; `--accurate` identical to default
TESTED     - fit to N frames : kino speed -f 120/N -> 120/119/120 frames (no effect), kino trim
             -> 53/97/120 (truncates at source length); current render_video_clip and direct
             ffmpeg -> exactly 53/97/241 at 1920x1080 yuv420p 24 fps, ids monotonic, no black
             first/last frame. Still image (PNG -> 53/97): current render_image_clip exact,
             ffmpeg exact, kinocut has no op
TESTED     - reframe 16:9 -> 9:16 : pad = 1080x600 centred (aspect 1.80, no stretch); blur
             fills 1080x1920; current "crop" == pad (no crop branch); explicit ffmpeg crop
             fills; kino resize -a 9:16 letterboxes 1080x600 centred. Anamorphic SAR 2:1
             source: all three letterbox as 16:9 (content_h 600 instead of 304)
TESTED     - concat : 20 x 120 frames -> kinocut 2400 frames (0 missing, 1 duplicate),
             current join_av 2400 (0 missing), ffmpeg reference 2399 (last frame lost).
             Mixed 24/30 fps + 160x90/320x180 -> kinocut 119 frames + "MERGE GUARDRAIL: Clips
             have different frame rates ... may stutter"; current 82 frames with NO warning
TESTED     - transitions : kino merge -t fade -td 0.5 -> 228/228 frames, head/tail ids intact,
             linear 255->21 luma ramp over 12 frames, no gap > 10 ms, step at the join
             -46.3 dB vs -42.9 dB elsewhere; wipe-left identical; ffmpeg xfade identical

TESTED     - audio : kino duck-audio -> 16.36 dB of duck, onsets 0.3 ms, -3.2 dBTP;
             kino normalize-audio -> -15.9 LUFS / -9.0 dBTP with the duck preserved;
             kino mix-audio control -> 0.04 dB duck. ffmpeg sidechaincompress 13.94 dB,
             loudnorm -15.3 LUFS. current join_av -> 0.22 dB duck, voice 21.6 ms late,
             -0.3 dBTP (no ducking, near clipping)
TESTED     - composite : kino composite-layers overlay on frames 12-23 only (region luma 0.0
             at frame 11, 33.67 at 12, 0.03 at 24), alpha honoured, base audio DROPPED;
             kino overlay-video keeps audio (has_audio true); ffmpeg overlay keeps audio
TESTED     - burn-in : kino subtitles on a UTF-8 SRT with accented + Japanese text in a
             non-ASCII directory -> bright pixels 0 before / 372 and 239 on the cues / 0 after;
             ffmpeg subtitles 0/203/146/0
TESTED     - export : 60 s 1080p24 -> kino export -q high 54.09 s, H.264 High yuv420p,
             AAC 48000 Hz 2 ch, moov before mdat, `-v error` decode silent; ffmpeg reference
             29.79 s, 24/1 fps; current copy path 1.66 s
TESTED     - QC : kino video-quality-check -> score 35.9, all_passed false; detects clipping
             ("Audio is clipping (-0.2 dBTP)") but NOT the black flash or the silence gap;
             ffmpeg blackdetect 1.0-1.125, silencedetect at 2.0, max_volume -0.2 dB;
             cutwright.frames.luma_at = 0.00 at the flash vs 82.0 on a clean frame
TESTED     - reliability : 10/10 trim, 10/10 resize, 10/10 merge with stable frame counts
             (1.62-6.27 s per call); read-only output dir -> exit 1
             {"code": "unsafe_path", "message": "Atomic output could not preserve directory
             identity: PermissionError"} and no file written; killed 1.2 s into a trim ->
             exit 1, zero leftover files
TESTED     - workflow : workflow-render -> exit 0, output + receipt (spec_hash, steps,
             sources, outputs, resume_cursor, sha256 of the output); delete an intermediate
             and --resume -> exit 0, step rebuilt; edit the spec and --resume -> exit 1
             "resume_spec_mismatch ... this is a different job"
FAILED     - (capability gaps, recorded in the matrix, not test failures)
             kino has no "exactly N frames" op and `speed -f` did not change the frame count;
             kino composite-layers is video-only; kino QC cannot see a per-frame black frame
             or a silence gap; kino resize has no crop
FAILED     - (defects in the current code, measured)
             render_video_clip is one frame late at every non-zero start (`-ss` before `-i`:
             start 1 -> ids [2,3,4]); join_av does not duck (0.22 dB) and lands the voice
             21.6 ms late with a -0.3 dBTP peak; fit_graph has no crop branch
FAILED     - (audio sync budget) 42 ms is missed at every merge: 13.4 ms per join with PCM,
             26 ms per join with AAC -> 0.27-0.49 s over 20 clips
NOT TESTED - HDR/10-bit sources, non-24 fps timelines, `kino batch`, the MCP tool surface,
             Remotion-rendered overlay clips inside composite-layers, blend modes/masks
NOT TESTED - whisper word timings and scene authoring: unchanged by M2
DECISIONS  - executor per operation fixed by measurement (table: docs/CAPABILITY_MATRIX.md):
             kinocut = trim, fade/wipe, duck, mix, normalize, subtitles, export, pad/blur
             resize, concat join, workflow engine; ffmpeg = fit-to-N-frames, crop, per-frame QC
             detectors, mixed-input normalisation; current = still-image clips; hybrid =
             composite + separate audio pass, release-checkpoint + ffmpeg detectors.
             Fixture design invalidated two measurements before they were trusted: a 300 Hz
             music bed was masked by 1 kHz voice leakage (moved to 100 Hz -> 1 dB became
             16.4 dB), and loudnorm had to run as a separate pass or it flattened the duck.
             Long runs must start as background processes (30 s tool limit); on timeout the
             scoop ffmpeg shim leaves a live child holding the pipe, so the harness kills the
             process tree with `taskkill /T` and runs everything with stdin=DEVNULL.
             M2 was NOT committed: the owner asked for the matrix and evidence to be reviewed
             before anything is staged.


## 2026-10-30 - M3 phase 3B: FFmpeg executor, op table, registry

New (uncommitted until phase 3C, the owner reviewed it first):
`cutwright/engine/executors/__init__.py` (ExecResult, typed ExecutorError with a `transient` flag,
one shared kill_tree/first_json), `cutwright/engine/executors/ffmpeg.py` (`fit_to_frames`,
`crop_to_size`, `overlay_audio`), `cutwright/engine/ops.py` (12 OpSpec rows: name, stage, params,
validator, the executor `docs/CAPABILITY_MATRIX.md` measured, its evidence file and the reason in
words), `cutwright/engine/registry.py` (list / describe / envelope / route, plus the installed
probes), `cutwright/engine/__init__.py`, `tests/test_engine_registry.py`. `cutwright/` stays
stdlib only; every write still goes through `guard.py`.

TESTED     - whole tree before phase 3C : `python -m unittest discover -s tests -t . -v` ->
             "Ran 82 tests in 408.551s" / "OK" (0 failures, 0 errors, 0 skips). The "62 tests"
             previously noted in HANDOFF.md was stale; 82 is the real number at this commit.
TESTED     - FFmpeg executor on real media : FfmpegRealTest ->
             "test_fit_clones_the_last_frame_to_hit_an_exact_count ... ok",
             "test_fit_letterboxes_into_a_size_without_stretching ... ok",
             "test_crop_fills_the_target_size ... ok",
             "test_audio_pass_attaches_sound_without_touching_the_frames ... ok",
             "test_audio_pass_warns_when_it_falls_back_to_shortest ... ok",
             "test_timeout_is_transient ... ok"
TESTED     - Kinocut adapter on real media (3A, re-run in the same suite) : KinocutRealTest ->
             "test_trim_is_frame_exact_after_the_adapter ... ok",
             "test_merge_crossfade_keeps_the_frame_maths ... ok",
             "test_mix_audio_accepts_json_tracks ... ok",
             "test_output_exists_needs_an_explicit_overwrite ... ok",
             "test_timeout_is_transient_and_kills_the_call ... ok",
             "test_info_returns_stream_facts ... ok"
TESTED     - the op table as data : OpsTableTest ->
             "test_executors_come_from_the_matrix_not_from_taste ... ok",
             "test_no_op_names_an_executor_without_passing_evidence ... ok",
             "test_every_op_names_a_real_target_in_its_executor ... ok",
             "test_names_are_unique_and_stages_are_known ... ok",
             "test_cross_parameter_rules ... ok"
TESTED     - routing and discovery : RegistryTest ->
             "test_route_uses_the_matrix_executor ... ok",
             "test_route_refuses_a_silent_executor_swap ... ok",
             "test_route_allows_an_override_only_past_the_reason_gate ... ok",
             "test_route_reports_an_uninstalled_executor_instead_of_switching ... ok",
             "test_envelope_is_capped_and_marks_truncation ... ok",
             "test_installed_reports_the_five_tools ... ok"
FAILED     - nothing at this phase. Two design gaps were found LATER, in 3C, and are recorded
             there: an optional param filled in as null could not be re-validated, and op param
             names did not map 1:1 onto executor kwargs (`trim_exact` speaks frames, `kino trim`
             speaks seconds).
NOT TESTED - Remotion executor (the roadmap's `executors/remotion.py` is not written yet), the
             `current` executor (recap helpers, M4), Kinocut `composite_layers`/`workflow_*`
             wrappers end to end through the engine, HDR/10-bit and non-24 fps media
DECISIONS  - the executor for each op is DATA in `ops.py`, copied from the matrix, with the
             evidence file checked by a test: a row that names Kinocut without a passing evidence
             file fails the suite, so the table cannot drift from the measurements.
             FFmpeg video passes are video-only (`-an`) on purpose: M2 measured 13.4-26 ms of
             drift per join, so a timeline's audio is built as ONE continuous track later.
             An existing output is refused unless the caller passes `overwrite=True`; the engine
             (manifest.py, 3C) is the only caller that decides when a re-render may replace one.


## 2026-10-30 - M3 phase 3C: execution manifest state machine + atomic checkpoints

New: `cutwright/engine/manifest.py` (load / validate / derive / run / status: ops, params, refs,
outputs and cache keys derived from data; the `pending|running|done|failed|skipped` state machine;
retry policy; gates block from data), `cutwright/engine/checkpoint.py` (temp-then-replace JSON, a
corrupt or schema-mismatched state refused instead of trusted, per-step cache key, the resume rule,
the cursor), `tests/test_engine_manifest.py` (40 tests). `ops.py` gained `executor_kwargs()` and a
null param now means "not set". `docs/evidence/m2_*.json` were rewritten by re-running the M2 tests
(wall-clock `seconds` only) and were RESTORED, not committed.

TESTED     - phase 3C module : `python -m unittest tests.test_engine_manifest -v` ->
             "Ran 40 tests in 6.979s" / "OK"
TESTED     - whole tree : `python -m unittest discover -s tests -t . -v` ->
             "Ran 122 tests in 377.413s" / "OK" (0 failures, 0 errors, 0 skips)
TESTED     - a real 2-step manifest, Kinocut then ffmpeg (`out/_demo_3c.py`, throwaway) :
             "validate: {\"ok\": true, \"steps\": 2, \"cost_usd\": 0.0, \"run_dir\": \"out\\\\runs\\\\demo\"}",
             "run: [[\"cut\", \"done\"], [\"fit\", \"done\"]]", "frames: 48 24",
             "resume: [[\"cut\", \"skipped\", \"cached (cache key unchanged, outputs intact)\"],
             [\"fit\", \"skipped\", \"cached (cache key unchanged, outputs intact)\"]]",
             "cursor: {\"next\": \"\", \"total\": 2, \"done\": [\"cut\", \"fit\"], \"pending\": []}"
             -> the second run re-encoded nothing and both steps stayed `done`
TESTED     - cache keys carry the tool version : `manifest.tool_versions()` -> kinocut "Kinocut
             1.16.4", ffmpeg "7.1-full_build-www.gyan.dev", node "v24.18.0", remotion "4.0.539"
TESTED     - the roadmap's rejections, as tests : unknown op, missing/unknown input, bad param, a
             paid step under a $0 cap, an AI-origin VISUAL asset (audio origins such as `user_audio`
             are exempt), forward reference, output outside the fork, output collision, executor
             override without a reason, unknown executor, gate before an unknown step, duplicate ids
TESTED     - resume/retry edges : a deleted output re-runs only that step; a changed param re-runs
             only that step; `only=` leaves the cursor at the next step; a dry run writes nothing; a
             truncated checkpoint raises CheckpointError(code="corrupted"); a transient failure is
             retried once (attempts 2, overwrite only on the retry) and ends `done`; a deterministic
             failure is not retried (attempts 1, `failed`, the error code recorded)
FAILED     - three defects my own tests/demo found BEFORE anything was staged; all fixed, each has
             a test now:
             1. re-validating a derived step rejected a null default -> "trim_exact rejected (code
                bad_type) [duration]: expected a number, got None". A null param now means "not
                set"; only a REQUIRED param given null is `missing_param`.
             2. op params do not map 1:1 onto executor kwargs (`trim_exact` speaks frames, `kino
                trim -s/-d` speaks seconds) -> `ops.executor_kwargs()`; a test pins 37/24 and 50/24.
             3. a cached resume overwrote `done` with `skipped`, so the NEXT resume re-rendered
                everything (the demo showed the cursor going back to `next: "cut"`). A cached skip
                now keeps status `done` and records the reason; regression test added.
FAILED     - `docs/schemas/manifest.example.json` does NOT validate against the real op table:
             "ERROR fit_1 invalid_params | fit_to_frames rejected (code unknown_param) [size]" and
             "ERROR export invalid_params | export_h264 rejected (code unknown_param) [crf]" (it also
             asks for fill="blur" and crf/audio/faststart). Not touched in 3C - the roadmap says to
             keep the example in sync with the validator, so it is phase 3D's first job.
NOT TESTED - media/quality validation after a render (validate.py), approval FILES (gates.py; only
             the manifest's own gate data blocks a step today), production_report.json (report.py),
             the run-id helpers (ids.py), the seven CLI verbs, the "remotion" executor (not
             written), Kinocut ops other than `trim` driven through the engine, multi-output ops
             (refused: every executor writes one file per call)
DECISIONS  - the cache key is computed when a step is about to run, not when the plan is derived: a
             step's input is usually the previous step's output, so deriving it early made every
             chained step look changed on the next resume (caught by test_resume_skips_cached_steps).
             `strict_files=True` for a run (a missing input fails before any encode), False for
             `validate` (a plan may be checked before its footage exists); an input produced by an
             EARLIER step of the same plan is never "missing".
             A step's declared validation checks are carried through as `not_run` rows - validate.py
             fills them, so a media check has exactly one implementation.
             Gates block from manifest data only (id, before_step, approved); approval files are
             gates.py's job. A blocked step is `skipped`, the run stops, `ok` is false.
             Checkpoint output paths are repo-relative and resolved against `guard.ROOT`, so
             `status` works from any CWD and no absolute user path is stored.
             Outputs are hashed below 64 MiB and identified by size+mtime above it (the rule
             guard.py already documents): a resume must never re-hash a multi-GB film.
             `MAX_ATTEMPTS = 2` for transient failures only; a deterministic failure (bad params,
             refused overwrite, failed validation) is never retried.

## 2026-10-30 - M3 phase 3D: engine CLI verbs, post-render validation, gates, production report (M3 CLOSED)

Scope: the six roadmapped CLI verbs, media validation after a render, approval FILES, the production
report, the run-id helpers, and the whole acceptance ladder on real media - then close M3.
Started at commit 1f2f2cf ("M3 3C close-out") on `main`.

TESTED     - full suite : `python -m unittest discover -s tests -t . -v` -> "Ran 166 tests in 360.362s" / "OK"
             (166 = M0..M3 + the 20 M2 areas + 84 engine tests: 38 manifest+checkpoint, 19 validate,
             9 gates, 16 CLI, plus env/flags/fixtures). First time the suite is green as a whole.
TESTED     - tool discovery : `python -m cutwright tools list --stage edit --json` -> exit 0,
             "count": 10 (trim_exact, fit_to_frames, concat, mix_audio, export_h264, ...), each row
             naming its executor and evidence status.
TESTED     - one op in detail : `python -m cutwright tools describe trim_exact --json` -> exit 0,
             executor "kinocut", executor_reason citing the M2 evidence file, params + checks listed.
TESTED     - plan validation : `python -m cutwright validate docs\schemas\manifest.example.json` ->
             "status OK - this plan can run", exit 0, 3 steps, 2 assets, 1 warning (voice_1.wav does
             not exist yet, and `validate` is allowed to pass a plan whose footage is not there).
             The example was rewritten to the real op vocabulary first; my draft's `export_h264`
             input was called `video` and the validator rejected it (`unknown_input`).
TESTED     - run + gate : `python -m cutwright run out\fx\demo_manifest.json --json` -> exit 1,
             ok=false, "stopped": "gate 'final_ok' is not approved", steps trim/fit/concat/mix done,
             export skipped. Then `python -m cutwright approve out\runs\demo final_ok` ->
             "APPROVED final_ok -> out\runs\demo\approvals\final_ok.json".
TESTED     - re-run after approval : same `run` command -> exit 0, ok=true; the four earlier steps
             report "cached (cache key unchanged, outputs intact)" and export runs, so one flow proves
             the gate blocks, the approval releases it, and the cache skips work.
TESTED     - status : `python -m cutwright status out\runs\demo --json` -> exit 0, ok=true, 5 steps
             done, each with inputs_digest/outputs_digest and its validation rows.
TESTED     - resume after a kill : killed the process during step 3 (`join`), `status` showed
             cut/fit done and join "running"; after approving, `python -m cutwright resume
             out\runs\demo --json` reported cut/fit "cached (cache key unchanged, outputs intact)",
             re-ran join (attempts 2, over its partial file), then mix + export.
TESTED     - the media itself : final.mp4 decodes to 60 frames, ids 24..47 then 1000..1035, 24.0 fps,
             160x90, AAC 48 kHz stereo, mix bed beeps at 0.0 / 1.0 / 2.0 s (frame_count, size,
             constant_fps, decodes_clean, has_audio, frame_ids_contiguous all `pass` in the manifest
             and in production_report.json).
FAILED     - `constant_fps` passed a 24 fps file asked for 30 fps : it compared each step against
             `1/want` and so tested uniformity only. Fixed: the rate is asserted outright
             (`abs(fps - want) > FPS_SLACK`) plus a 1 ms jitter test; the new failing case is
             `test_constant_fps_fails_when_the_rate_is_wrong`. Found by writing the check, not by a
             run - the demo never asked for a rate it did not get.
FAILED     - concat of a silent clip + an audio clip : `kino merge` re-timed the output to 30.0 fps /
             44.1 kHz, 75 frames instead of 60, so the step failed with validation_failed
             ("frame_count: expected 60 frames, decoded 75") - the validator doing its job. The demo
             now builds picture first and one audio track after; finding recorded in C-007.
FAILED     - mix bed inaudible : my own mixing level put the bed below the beep onsets we measure, so
             the onset test found nothing. Fixed in the fixture (`make_beep_bed`), not in the check.
FAILED     - `guard.rel()` re-relativised an already-relative path against the CWD : the M2 harness
             imports `recapstudio/_template/recap.py`, which chdir()s the process and never restores
             it, so in the full suite an asset resolved to
             `recapstudio\_template\out\engine_gates\src.mp4`
             ("manifest rejected (code asset_missing): asset 'src' is missing on disk: ...") and 3
             gate tests ERRORed, while each passed in isolation. Fixed in two places: `rel()` now
             resolves a relative input against `ROOT` (its own documented contract, and it makes
             rel(rel(x)) == rel(x)), and the test helper returns absolute paths instead of
             double-relativising. Verified by forcing the cwd into `recapstudio/_template`:
             `RUN_TESTS_CWD=recapstudio/_template python out\run_tests.py tests.test_engine_gates
             tests.test_engine_manifest tests.test_engine_cli tests.test_engine_validate` ->
             "RESULT: OK  (84 run, 0 failures, 0 errors)".
FAILED     - clearing `reason` on a successful step : broke two 3C contract tests that pin the "why it
             ran" explanation ('missing' and 'cache key' not found in ''). Reverted the `reason=""`;
             the explanation is now phrased as a reason to RUN ("step was skipped, so it runs again"),
             because "step is skipped" on a row that had just run read like a contradiction.
NOT TESTED - `executors/remotion.py`, `pipelines/*.json`, `skills/*.md` : not in the confirmed 3D
             scope (no op routes to a remotion executor yet) - C-007 decision 2.
NOT TESTED - Kinocut ops other than trim/concat/mix/export through the engine, and every multi-output
             op (refused by design: one executor call writes one file).
NOT TESTED - `slideshow_risk` on real footage : measured on fixtures only (a cloned still scores 1.0,
             the counter clip under 0.1); the M8 benchmark reel is where it gets a real subject.
NOT TESTED - M2's concat clips that carry audio : the 30 fps re-time is measured only for a silent plus
             an audio clip at 24 fps; other combinations are unmeasured.
DECISIONS  - DECISION 1 = (a): the example was rewritten to the real validator vocabulary instead of
             loosening the validator; the rewrite is itself evidence (it caught `export_h264`'s input
             name). The demo deliberately carries a gate before export, so one flow proves blocking,
             release and cache-skip together. `validate.py` reports provenance but does not decide it
             (the manifest owns the policy) so there is one verdict, not two that can disagree.
             Validation rows stay `not_run` until a media check fills them, and a failed check is a
             DETERMINISTIC failure (`validation_failed`, attempts stay at 1): the same params cannot
             fix a wrong frame count, so it must not be retried. `resume` reuses the `run` path (same
             state machine, same cache rule) instead of being a second implementation; it only skips
             re-deriving the plan. M3 is CLOSED here; M4 starts only on the owner's go.

Commit     - b831112 "M3 close-out: engine skeleton, CLI verbs, validation gates, and manifest runner"
             (19 files, +1921/-56), pushed to origin main; `git ls-remote origin refs/heads/main` ->
             "b831112244f142ac12b953a8e6a2f9d16cc7892d  refs/heads/main" == local HEAD. The commit that
             follows this entry only records that hash in HANDOFF.md + here.

## 2026-10-30 - M4 phase 4A: mix tracks as declared inputs, Recap's picture join on the engine (agent)

Objective (owner-approved, phase 4A only): (1) make `mix_audio`'s track files explicitly declared
inputs and prove a cache-key change when a track changes; (2) wire the replacement of superseded
`recap.py` editing functions to `cutwright.engine` with a picture-only concat + one continuous audio
track; (3) re-run `recapstudio\Projects\regress` on the swapped path and compare duration, frame
count and audio with the M0 baseline. Nothing deleted from `recap.py` (that is 4B).

TESTED     - the new op contract : `python -m unittest tests.test_engine_mix_inputs -v` ->
             "Ran 7 tests in 0.973s" / "OK" - `mix_audio` declares inputs ("src","tracks"),
             `positional_inputs` keeps the file out of the argument list, files pair with settings by
             position, a count mismatch is `invalid_combination`, replacing a track changes the
             step's cache key and restoring the identical bytes restores the key (sha256, not mtime).
TESTED     - the bridge : `python -m unittest tests.test_engine_bridge -v` -> "Ran 5 tests in
             0.039s" / "OK" - `repo_root()` resolves the fork from `_template` and from a copied
             `Projects\<job>` folder, a folder outside the fork has no engine, and each call declares
             the right op/inputs/params.
TESTED     - the engine's own table : `python -m unittest tests.test_engine_registry
             tests.test_engine_mix_inputs -v` -> "Ran 43 tests in 19.969s" / "OK".
TESTED     - five-step demo on real media, fresh run dir : `python -m cutwright run
             out\fx\m4_manifest.json` -> mix "done", validations "ok decodes_clean measured clean"
             and "ok has_audio measured True", then `approve` + re-run -> "export export_h264 done"
             with "ok frame_count measured 60" and "ok constant_fps measured {'frames': 60,
             'interval': 0.041667, 'fps': 24.0, 'jitter': 1e-06}"; `python -m cutwright status
             out\runs\m4demo --json` -> "\"done\": [\"cut\",\"fit\",\"join\",\"mix\",\"export\"]" and
             executors "kinocut", "ffmpeg", "kinocut", "kinocut", "kinocut", `"ok": true`.
TESTED     - the cache-key fix on real media : replaced `out\fx\music.wav` with a same-length 320 Hz
             bed (`python out\m4\swap_track.py swap`) and re-ran ->
             "[+] mix mix_audio done cache key changed (inputs, params or executor version)" while
             cut/fit/join stayed "cached (cache key unchanged, outputs intact)", and export re-ran
             too. The new tone really landed in the output: Goertzel over the first 50 ms of
             `out\runs\m4demo\final.mp4` -> "320 Hz: 3526719 | 1000 Hz: 755". Restoring the fixture
             re-ran mix again -> "320 Hz: 3139 | 1000 Hz: 5787335". Before the fix that step was
             skipped, which is exactly COMMS C-007 finding 3.
TESTED     - the regression project on the swapped path : copied the updated `recap.py` +
             `engine_bridge.py` into `recapstudio\Projects\regress` (the copy differed from
             `_template` by these 5 lines only: `git diff --no-index` shows one hunk in `join_av`),
             ran `python recap.py video` -> "Done. recap_final.mp4  (21.4s, expected 21.4s)", all six
             clips "cached", no warnings. ffprobe -> "nb_read_frames=514", "r_frame_rate=24/1",
             "width=1920", "height=1080", "duration=21.416667", "size=6834110", "codec_name=aac",
             "sample_rate=48000", "channels=2" - every number equal to the M0 baseline in
             `docs/ENVIRONMENT.md`. Stronger than equal: the streams are BYTE-IDENTICAL to the
             pre-change file - video "MD5=c671f7a76da05927d9a41d4742779268" and audio
             "MD5=0064ff59fa0debbc9a47f17cccbb322b" before and after - and loudness is unmoved
             ("I: -11.3 LUFS", "LRA: 0.4 LU", "Peak: -6.9 dBFS" both runs).
TESTED     - that the engine actually did the join : `tiktok_temp\full_picture.mp4` exists with
             "nb_read_frames=514" and a 10/30 09:32:35 timestamp, while the old concat list
             `tiktok_temp\full_video.txt` still carries 10/29 21:42:49 and was never rewritten.
TESTED     - what is still in `recap.py` : `Select-String -Path recapstudio\_template\recap.py
             -Pattern "write_concat_list|join_av|fit_graph"` -> only `fit_graph` (647, used at 2467
             and 2477), `write_concat_list` (4056, now audio lists only at 4080/4090), `join_av`
             (4068) and its two call sites (4126, 4320). Nothing was deleted.
TESTED     - the whole suite : `python out\run_tests.py` -> "Ran 178 tests in 364.720s" / "RESULT:
             OK  (178 run, 0 failures, 0 errors)"; that is every module, including the 12 new tests
             (7 mix-input, 5 bridge). The M2 evidence JSONs were rewritten by that run (wall-clock
             only) and restored, not committed - the C-006 practice.


FAILED     - `python -m cutwright approve out\runs\m4demo final_ok --note "M4 4A: mix track ..."` :
             PowerShell split the note on its spaces -> "cutwright: error: unrecognized arguments:
             4A: mix track declared as input". Re-ran with a hyphenated note
             (`M4-4A-mix-track-input`) -> "APPROVED final_ok in out\runs\m4demo".
FAILED     - measuring the swapped tone with an ffmpeg filter string : `-af
             "bandpass=f=320:width_type=h:w=120,volumedetect"` -> "[Parsed_bandpass_0] ... Unable to
             parse option value \"=h\"" (PowerShell/ffmpeg quoting). Replaced with a stdlib Goertzel
             in `out\m4\tone_check.py` (decode to mono wav, two magnitudes) - the number quoted above.
FAILED     - process hygiene, not code : the first full-suite run was started in the background, a
             second one overlapped it, and two suites competed for the same `out\` folders; both were
             killed and the clean single run is the one quoted.
NOT TESTED - `recap.py`'s music path through the engine's `mix_audio`: the regress project has
             `project.json` "music": false, so `join_av` receives `music=None` and never mixes a bed.
             The op is proven on the demo above instead; wiring `make_music_bed` -> `mix_audio` is 4B.
NOT TESTED - the TikTok variant (`step_tiktok` -> `join_av`) and the Premiere XML / Remotion steps:
             not touched in 4A, not re-run.
NOT TESTED - a project copied OUTSIDE the fork: the bridge raises "no cutwright/engine found". No
             such project exists here; `repo_root("C:\\Windows")` is unit-tested to return None.
NOT TESTED - `fit_to_frames` as a replacement for `render_video_clip`: it has no start offset
             (`-ss`), no `loop` and no `fill="blur"`, so the per-segment fit stays in `recap.py`.
DECISIONS  - 1. The mix track FILE is a declared input and only its settings stay params; pairing is
             by position and a mismatch is refused at plan time. A `path` inside a setting is REFUSED
             (`unknown_param`) rather than silently overridden, because the old form was exactly what
             hid the file from the cache key. 2. The bridge imports `cutwright.engine` in-process
             from the fork root (the roadmap allows "path-safe import or subprocess"); the manifest
             runner stays the tool for a whole production plan (M6), so neither is a second
             implementation of an op. 3. Only the picture concat moved: `render_video_clip`,
             `fit_graph`, `fit_audio` and the audio chain stay until an op can express what they do -
             a half-moved op is worse than a late one. 4. No runtime fallback or "legacy" switch: if
             the engine is unreachable, the recap step raises. 5. Parity was judged on frames,
             duration, stream parameters, stream md5s and loudness, and came out byte-identical -
             stronger than the roadmap's "within one frame / 0.5 LU" bar. 6. Kinocut's own warning
             ("Tracks sum at unity without normalization and may clip") is surfaced in the step's
             warnings and NOT auto-corrected; it needs a rule when SFX arrive (M12).

Commit     - d072280 "M4 4A: mix tracks are declared inputs; Recap's picture join runs on the engine"
             (13 files, +609/-39), pushed to origin main; `git ls-remote origin refs/heads/main` ->
             "d0722807e7dc356c38d2f15300faf5c2d36c8731  refs/heads/main" == local HEAD. The commit
             that follows this entry only records that hash in HANDOFF.md + here.
             `recapstudio/remotion/package-lock.json` stays UNTRACKED as instructed (C-006).



## 2026-10-30 - M4 phase 4B: ffmpeg's music mix deleted, `mix_audio` mixes the bed, 79 s real job (agent)

Objective (owner decisions C-008 / the 4B go): (1) delete the superseded editing code left in
`recap.py` and wire `make_music_bed` -> `mix_audio`; (2) build and run a 60-90 s real job from
`recapstudio\Projects\regress\footage\demo_a.mp4` (looped, owner's call), voice by Edge-TTS, captions
via Remotion, final through the engine; (3) review six frames. One commit, then STOP.

TESTED     - what was actually left of the picture join : `Select-String -Path
             recapstudio\_template\recap.py -Pattern "write_concat_list|join_av|fit_graph"` (the
             roadmap's M4 acceptance grep) -> "647: def fit_graph ... | 2467/2477: g = fit_graph(...)
             | 4060: def write_concat_list ... | 4072: def join_av ... | 4084/4094:
             write_concat_list(alist/olist, ...) | 4136/4330: join_av(...)". Nothing else matches:
             the old picture demuxer branch (`vlist`, `-f concat -safe 0 -i vlist`) was already
             deleted in 4A (`git show d072280 -- recapstudio/_template/recap.py` shows the removal),
             so what is left is three deliberate keeps (DECISIONS 1) - `fit_graph`/`render_video_clip`
             (no op can express them yet), `write_concat_list` (AUDIO lists only) and `join_av`
             itself.
TESTED     - Kinocut refuses an audio-only mix source (the assumption behind the first design) :
             `python out\m4b\probe_mix_wav.py` -> exit 1 for .wav/.m4a/.mp4 outputs, stderr
             `{"success": false, "error": {"type": "validation_error", "code":
             "missing_video_stream", "message": "mix_audio requires a video stream"}}`. So the bed
             cannot be mixed under a bare narration wav; the program audio is muxed FIRST and the
             bed is mixed under the muxed file.
TESTED     - the shape that 4B uses, through the bridge, before any edit : `python out\m4b\probe2.py`
             -> `mix_tracks -> kinocut`, warning "Tracks sum at unity without normalization and may
             clip. Listen before publishing."; 72 frames at 24/1 both sides, 3.000000 s both sides,
             aac 48000/2 both sides, and the VIDEO PACKETS unchanged: draft md5 b41de32a... ==
             mixed md5 b41de32a...; loudness moved -21.8 -> -18.9 LUFS (the bed arrived).
TESTED     - the regression project after the change, byte-identical to the M0 baseline :
             `python recap.py video` in `recapstudio\Projects\regress` (with the updated `recap.py` +
             `engine_bridge.py` copied in) -> "Done. recap_final.mp4  (21.4s, expected 21.4s)", six
             clips "cached". ffprobe both the before-copy and the new file: "nb_read_frames=514",
             "r_frame_rate=24/1", "1920/1080", "duration=21.416667", "size=6834110", "aac
             48000/2"; video packets c671f7a76da05927d9a41d4742779268 and audio packets
             0064ff59fa0debbc9a47f17cccbb322b identical, and the two FILES have the same sha256
             (817BA0EA4805F7F96B00D127570D6C7B67CD8E7633C63135226B17C4807E4479). The music-off path
             is untouched by 4B, exactly as designed (DECISIONS 2).
TESTED     - the whole suite : `python -m unittest discover -s tests -t . -v` -> "Ran 178 tests in
             424.901s" / "OK" (0 failures, 0 errors, 0 skips). The M2 evidence JSONs were rewritten
             by that run (wall-clock `seconds` only) and restored with `git checkout`, not committed,
             the C-006 practice.

TESTED     - the 60-90 s real job, built and rendered : `recapstudio\Projects\m4job` (new project, copied
             from `regress`, outputs removed; 15 segments, 269 narration words, Edge-TTS
             `en-US-ChristopherNeural`, `project.json` "music": true) -> `python recap.py tts --engine
             edge` -> "All audio generated." / "actual narration: 1:19"; `python recap.py video` ->
             "Done. recap_final.mp4  (79.2s, expected 79.2s)". ffprobe: "nb_read_frames=1900",
             "r_frame_rate=24/1", "1920x1080", "duration=79.166667", "size=56943664", audio "aac
             48000 Hz 2 ch". `python recap.py timeline` -> "timeline.json: 15 segments, 1900 frames
             (79.2s at 24fps, 1920x1080)" / "Timeline check passed: every file exists and every clip
             matches its frame count." The numbers live in `out\m4b\job_receipt.json`; the job folder
             itself is gitignored (`recapstudio/Projects/*`).
TESTED     - the bed really is mixed by Kinocut, and the picture is untouched on the real job :
             `python out\m4b\verify_job.py` -> mix source `tiktok_temp\full_picture_av.mp4` and the

## 2026-10-30 - M5 close-out: the old editor backend leaves the code

```
TESTED     - grep, roadmap M5 acceptance: git grep -n -i "shotcut|melt\.exe|\.mlt" -- . ":!LOG.md"
             ":!COMMS.md" ":!docs/legacy" ":!docs/MIGRATION_CHECKLIST.md" ":!docs/REFERENCES.md"
             ":!docs/ROADMAP.md" ":!docs/ARCHITECTURE.md" ":!docs/GOALS.md" ":!docs/BORROW_notes.md"
             ":!PROVENANCE.md"  -> no output (exit 1). The only surviving substring anywhere is
             `meltysynth` in docs/KINOCUT_FINDINGS.md, a different package.
TESTED     - code only: git grep -c -i shotcut -- tests cutwright -> no matches (exit 1);
             git grep -c -i mlt -- tests -> no matches (exit 1);
             git grep -n -i shotcut -- '*.py' '*.bat' '*.js' '*.json' '*.ps1' '*.cmd' -> no matches (exit 1).
TESTED     - doctor: python -m cutwright doctor -> "[+] ffmpeg    C:\Users\user\scoop\shims\ffmpeg.EXE",
             "[+] Kinocut      Kinocut 1.16.4 (editing toolkit, called by subprocess)", under the heading
             "transcription / editing engines:"; there is no editor line any more; exit 0.
TESTED     - the verb is gone: python -m cutwright --help -> the STEP list has no `build`;
             python -m cutwright build x -> "usage: cutwright [-h] [--version] STEP ..." (argparse exit 2).
TESTED     - suite: python -m unittest discover -s tests -t . -v -> "Ran 178 tests in 380.037s" and "OK".
TESTED     - nothing left to delete outside git: Test-Path shotcut -> False; Test-Path 'bin\_dl' -> False.
FAILED     - nothing failed in this objective.
NOT TESTED - the recapstudio regression pack (roadmap M5 acceptance line 3: demo, briefs --demo, video,
             timeline, scenes, remotion, premiere): not run. Reason: this session's task list named the
             doctor and the suite only, and the pack is a multi-minute Remotion render chain; C-010 asks
             whether it gates M5 or the start of M6. The earlier attempt's HANDOFF line ("regression pack
             green") had no log entry behind it and was corrected, not inherited.
NOT TESTED - listening to an output: M5 deletes code, it renders nothing new.
NOT TESTED - MLT-generation tests: there are none to remove. git grep -i mlt -- tests and -- cutwright
             both return no matches, so no test ever asserted the timeline writer's output. The four

```
DECISIONS  - 1. What went: cutwright/mlt.py (2,573 lines), cutwright/gui.py (433), 
             cutwright/tools/shotcut_window.ps1 (255), the four projects/demo_* folders (17 tracked files,
             1,776 lines, measured with git diff --cached --numstat -- projects), plus the `build` verb,
             its sub-parser and the doctor block in cutwright/cli.py, which now prints a Kinocut line
             built from `kino.available()/kino_exe()` + `kino --version`. Nothing was ported out of the
             writer: every helper the checklist section C listed was already an engine op by M2/M3
             (fit_to_frames, concat, mix_audio, overlay_audio, export_h264).
             2. One commit, not one per checklist item: the working tree arrived with the earlier attempt's
             code and doc edits interleaved and its deletions already staged. Splitting that into invented
             intermediate commits would have meant committing states nobody ran; the tree went in whole and
             section F of docs/MIGRATION_CHECKLIST.md is ticked per item with the evidence instead. The
             recommendation of "one commit per item" stands for future milestones that start clean.
             3. History is MOVED, not deleted: REPORT.md -> docs/legacy/REPORT_shotcut_era.md,
             docs/VISION_cutwright_v2.md -> docs/legacy/, and the editor's provenance block (download URL,
             sha256, the five demo-file hashes) verbatim in docs/legacy/PROVENANCE_removed_editor.md, with
             PROVENANCE.md carrying a "Removed 2026-10-30 (M5, historical)" pointer. The four plan.json
             files were NOT converted to examples/: they are shaped around the writer's clip/in/out model
             and docs/schemas/manifest.example.json already teaches the engine manifest.
             4. Tests: 178 before, 178 after. That is the check on item 3 - if deleting the writer had
             removed a test, the count would have dropped; no test ever referenced it.
             5. Left UNSTAGED on purpose: docs/evidence/m2_*.json (20 files). The suite rewrites them on
             every run (the equivalence tests emit their own evidence, "[evidence] docs/evidence/m2_*.json"
             in the test output), so they are run artifacts, not M5 edits; and
             recapstudio/remotion/package-lock.json stays untracked (C-006).
             6. The earlier attempt's unbacked HANDOFF claim ("M5 DONE ... 178 tests green, regression pack
             green") was replaced with what this session measured, including the un-run regression pack.
Commit     - 4528c51 "M5 close-out: remove obsolete Shotcut MLT backend, GUI, and tests" on main, pushed to
             origin main; `git ls-remote origin refs/heads/main` -> 4528c5117f1de4dd78a934a93840feaf4f419e8b.
             The message names the removed editor, which is why it is quoted here (an excluded file) and
             not in HANDOFF/TOOLS, so the roadmap's acceptance grep stays empty.
```

             projects/demo_* folders it produced were data, not tests, and are deleted.
```

             final: video packets BOTH 854df8a7ed5f1b631e560fb7724788db (also equal to the engine's
             concat output `tiktok_temp\full_picture.mp4`), audio packets 90132b3a... -> 2e343715...
             (changed: the mix happened), loudness -20.1 -> -19.2 LUFS. Goertzel over the first
             second: final {220: 21,395,632 | 277: 17,708,382 | 330: 13,872,649 | 180: 119,195} vs
             draft {220: 3,711,065 | 277: 1,496,660 | 330: 21,193,218 | 180: 162,005} - the 220/277 Hz
             bed tones arrive with the mix; 330 Hz is the footage's own tone (it is a test pattern).
TESTED     - captions via Remotion on the same timeline : `python recap.py remotion` -> "Done.
             ...\m4job\recap_remotion.mp4  (79.17s, expected 79.17s, rendered in 8.6 min)" and
             "[+] PARITY CHECK PASSED: length matches the timeline within one frame." / "vs
             recap_final.mp4: 79.17s -> within one frame". ffprobe: 1900 frames, 24/1, 79.168 s,
             69,786,262 B. Frames `08_remotion_captions_20s.png` (t=20.0) and
             `09_remotion_cut_42s.png` (t=42.6) show the karaoke captions ("two audio sources to
             balance" with the current word on a yellow pill) and the per-segment lower third
             ("Original sound kept low"), so captions really are burned in the Remotion render;
             `recap_final.mp4` is unchanged by that run (video packets still 854df8a7...).
TESTED     - six frames looked at (I can see images in this session) : `out\m4b\frames\01_start.png`
             (t=1.0 s), `02_25pct.png` (t=19.8), `03_50pct.png` (t=39.6), `04_75pct.png` (t=59.4),
             `05a_cut_before.png` + `05b_cut_after.png` (last frame of `clips\s_07.mp4` / first frame
             of `clips\s_08.mp4`, i.e. the join at frame 1020), `06_end.png` (t=78.6), plus
             `07_character_s09.png` (t=46.5, the character beat). What they show, honestly:
             (a) frames are complete, sharp, 1920x1080, correctly framed - no black frame, no tear,
             no half-rendered transition at the join; (b) the four-by-three segment is padded with
             real BLACK bars (measured RGB (0,0,0) at x=0 in `clips\s_07.mp4`, content 1440x1080
             centred) while the still-image segment next to it uses a BLURRED backdrop
             (`render_image_clip` hard-codes "blur", `render_video_clip` uses `config.json` fill) -
             the cut at 1020 therefore jumps from black bars to blurred bars: a real cosmetic
             inconsistency, code-level, cheap to fix in M8; (c) the character segment works (grey
             robot, right side, ~1/3 frame height, no halo, transparent edges clean); (d) the demo
             FOOTAGE burns its own timecode/counter ("00:00:03.625 / 87") and the testsrc2 grey
             marker into the picture - that is the fixture, not the pipeline, but it means every
             frame carries junk text in the top-left; (e) `recap_final.mp4` has NO captions or
             graphics by design ("Number/caption graphics are NOT burned into the mp4 - use the
             Premiere XML"), so the captioned deliverable is the Remotion render, not this file;
             that render was checked too - `recap_remotion.mp4` (1900 frames, 79.168 s) carries the
             karaoke captions and the per-segment lower third, and (f) two cosmetic issues there:
             the karaoke words that are not yet spoken render in a dim grey that loses contrast over
             the yellow/blue bars, and the character at `char_pos: "right"` sits flush against the
             right edge (a few pixels of its body are cut). Both are M8 material, not 4B.
NOT TESTED - the TikTok variant (`step_tiktok` -> `join_av` with `fill="blur"`) and the VideoPad /
             Premiere exports: not re-run in 4B. They call the same (now shorter) `join_av`, but
             "same code path" is not a test.
NOT TESTED - a project copied OUTSIDE the fork: the bridge still raises instead of falling back;
             nothing changed in 4B and no such project exists here.
NOT TESTED - listening: the numbers say the bed is there and the mix sits at -19.2 LUFS, but only
             the owner's ears can accept a mix. Kinocut's "sum at unity" warning is surfaced, not
             auto-corrected (C-008 finding 1).

DECISIONS  - 1. What 4B deletes, and why only that: the roadmap's "delete the superseded functions"
             collided with reality - 4A had already removed the picture demuxer branch, so the only
             superseded code left was the ffmpeg MUSIC arm in `join_av` (`-i music` + the `n_audio`
             count feeding `amix`). That arm is a second implementation of the engine's `mix_audio`,
             so it is gone and the bed now goes through `engine_bridge.mix_tracks` ->
             `mix_audio` (Kinocut). Deleting more would have meant deleting code no op can replace
             (`fit_graph`, `write_concat_list`), which the roadmap's step 3 forbids. 2. Order of
             passes, forced by Kinocut and chosen to keep the verified baseline intact:
             picture (engine `concat`, video-only) -> program audio (ffmpeg concat lists +
             `amix` for narration/original) -> ONE mux (`-c:v copy`, aac 192k, 48 kHz, `-shortest`,
             `+faststart`) -> `mix_audio` only when a bed exists. With music off, `muxed` IS `out`,
             so the music-free path issues the exact same command as before 4B - that is why the
             regress project is still byte-identical. 3. Kinocut cannot mix under an audio-only
             source (`missing_video_stream`, measured), so the bed is mixed under the muxed file
             and not under the narration wav; the price is `+faststart` on music-on projects
             (`mix_audio`'s own muxer does not add it) - recorded, not hidden. 4. The mix level is
             still baked into the bed by `make_music_bed` (loop to length, `music_volume`, fades),
             not passed as `mix_audio`'s per-track volume: one op owns one decision, and the fade
             timing needs the total length, which the op does not know. 5. The final mux stays in
             `recap.py` rather than moving to `overlay_audio`: that op has no `-ar`, no
             `-movflags +faststart`, and the same pass has to produce the file `mix_audio` reads.
             A duplicated pass with different parameters is not the same op, but it is on the list
             for M5/M13. 6. The real job reuses the demo fixtures (test pattern + grey robot) and a
             code-made music bed: no AI media, no licensed asset on this PC, and the point of the
             run is the ENGINE path at length, not art. 7. Parity of the mix was judged on video
             PACKET md5 (identical) plus loudness and two tone magnitudes, because the container
             bytes legitimately change when `mix_audio` rewrites the mux.
Commit     - 0755d92 "M4 4B: the ffmpeg music mix is deleted; mix_audio mixes the bed" (7 files,
             +224/-34), pushed to origin main; `git ls-remote origin refs/heads/main` -> see the
             commit that follows this entry, which only records that hash in HANDOFF.md, COMMS.md
             and here. `recapstudio/remotion/package-lock.json` stays UNTRACKED as instructed
             (C-006). The job under `recapstudio/Projects/m4job` and the stills under `out/m4b/` are
             gitignored: they are working evidence, not source.


## 2026-10-30 - M5.5A: a Remotion executor behind the op registry, measured cold/warm, first vision test (agent)

Objective (owner decisions in C-010, answered by the owner's brief): (1) docs only, own commit, to add
M5.5 between M5 and M6; (2) run the recapstudio regression project as the "before"; (3) build
`cutwright/engine/executors/remotion.py` with `render_still` and `render_range`, registered like the
other executors, outputs + hashes in the manifest, the scene declared as an input; (4) MEASURE cold and
warm wall time at 1920x1080 and 1080x1920; (5) look at the stills and check one specific detail;
(6) record and stop. Not in scope: CONTRACT.md, any kit file, primitives, scene prompts, the critic
loop, M6.

TESTED     - docs commit first, on its own : `git commit -F msg.txt` -> "2ae8f60 Docs: insert M5.5
             (creative rendering slice) between M5 and M6", 2 files, +54/-10 (HANDOFF.md,
             docs/ROADMAP.md). It first went in WITH msg.txt (3 files); `git rm --cached msg.txt` +
             `git commit --amend` removed it before anything was pushed.
TESTED     - the regress project's Python is already the current code : sha256 of
             `recapstudio\_template\{recap,engine_bridge,scenes,timeline,authoring,wordtimes}.py`
             equals the same file in `recapstudio\Projects\regress` (6 files; e.g. recap.py
             4ebd59db11aa7007 on both sides). No copy was needed.
TESTED     - the regression pack, in roadmap order, all exit 0 : in `recapstudio\Projects\regress`,
             `python recap.py video` -> "Done. recap_final.mp4  (21.4s, expected 21.4s)" (10.7 s wall,
             six clips cached); `timeline` -> "6 segments, 514 frames (21.4s at 24fps, 1920x1080)" +
             "Timeline check passed" (25.4 s); `scenes` -> 3 ok / 3 keywords (1.1 s, cached);
             `remotion` -> "Encoded 514/514" + "PARITY CHECK PASSED ... within one frame" (1.4 min);
             `premiere` -> exit 0 (4 s). Scene verdicts are the M0 baseline exactly (d_01, d_02, d_03
             pass; d_04 "x.toUpperCase is not a function"; d_05 BLOCKED on 'fetch'; d_06 "draws
             nothing"). `demo` and `briefs --demo` were NOT re-run: `demo` refuses a project that
             already has segments and `--force` is forbidden unattended.
TESTED     - the video against the M0 baseline, byte for byte : `ffprobe -count_frames` ->
             "nb_read_frames=514", "r_frame_rate=24/1", "1920x1080", "duration=21.416667",
             "size=6834110"; `ffmpeg -map 0:v -c copy -f md5 -` ->
             "MD5=c671f7a76da05927d9a41d4742779268", `-map 0:a` ->
             "MD5=0064ff59fa0debbc9a47f17cccbb322b"; file sha256 817BA0EA...4479. All equal
             `docs/ENVIRONMENT.md`'s baseline.
TESTED     - the Remotion render re-ran and still matches within one frame, but NOT in bytes :
             `recap_remotion.mp4` -> 514 frames, 24/1, 1920x1080, "duration=21.419000",
             "size=5904274", video md5 17fd8e0f..., audio md5 4e7a90b5...; the M0 line says
             5,915,527 B - 11,253 B smaller (0.19%) with the same frames and duration. The `video`
             step ran BEFORE this re-render, so the byte-identical `recap_final.mp4` above came from
             the previous render; the order is stated in `docs/ENVIRONMENT.md`.
FAILED     - the first measured `render_still` run : `python -m cutwright run
             out\m55\still_16x9.json --json` -> step failed, code `render_failed`, message "Command
             ...\\recapstudio\\remotion\\src\\index.ts not found.". Cause: I put the entry point
             BEFORE the command; `@remotion/cli` takes the command first. Fixed in `build_argv()`
             (the docstring now says so) and re-run. The same failed attempt exposed two smaller
             defects, both fixed: the error text carried ANSI colour escapes (now stripped) and the
             props file was written before the availability check (now after it).
FAILED     - my own probe one-liners, not the project : `python -c "..."` was mangled by PowerShell
             quoting twice ("SyntaxError: '(' was never closed") and once the `>&2` traceback was
             swallowed by the pipe; fixed by putting every probe in a script file under `out\m55\`.


TESTED     - the two ops exist and route : `python -m cutwright tools describe render_still --json` ->
             executor "remotion", inputs ["scene"], outputs ["still"], evidence
             `docs/evidence/m55_remotion.json`; `registry.list_ops("graphics")` ->
             "['burn_subtitles', 'render_still', 'render_range']"; `envelope("graphics")` returned 3;
             total ops 14; `registry.installed()` reports remotion "4.0.539", ok True.
TESTED     - the measured cost, through `python -m cutwright run <manifest> --json`
             (cold = run folder AND output removed; warm = output removed only; cached = nothing
             removed):
             ```
             still 1920x1080   cold 7.77 s (wall 9.79)   warm 8.26 s (wall 9.69)   cached 0.97 s
             still 1080x1920   cold 7.39 s (wall 8.69)   warm 6.95 s (wall 8.44)   cached 1.04 s
             range 1 s 16:9    cold 13.20 s (wall 14.83) warm 9.63 s (wall 11.19)  cached 1.34 s
             range 1 s 9:16    cold 10.96 s (wall 12.78) warm 11.99 s (wall 13.56) cached 1.01 s
             ```
             all 12 runs rc=0; the stills passed `size` (measured [1920,1080] / [1080,1920]); the
             ranges passed `frame_count` 24, `size` and `decodes_clean`. The cached run's reason is
             literally "cached (cache key unchanged, outputs intact)". Raw rows:
             `docs/evidence/m55_remotion.json` and `out\m55\measurements.json`.
TESTED     - the still is a picture, not a blank frame : `python out\m55\blank_check.py` (ffmpeg
             decodes each PNG to 64x36 gray, then min/max/mean/stdev/distinct) ->
             "still_16x9.png ... distinct=133 stdev=26.9", "still_9x16.png ... distinct=145
             stdev=30.7"; a blank frame is one tone and zero spread.
TESTED     - the range really is one second : `ffprobe -count_frames` on `range_16x9.mp4` ->
             "1920,1080,24/1,24," then "1.000000,136500"; `range_9x16.mp4` -> "1080,1920,24,".
TESTED     - the executor's own tests, 12 of them, no render : `python -m unittest
             tests.test_engine_remotion -v` -> "Ran 12 tests in 1.353s" / "OK". They pin the measured
             CLI order (command BEFORE the entry point), the props file (none for landscape), the
             inclusive frame range, the four refusals (missing scene, existing output, outside the
             fork, Remotion absent) and that editing the scene file changes the step's cache key.
TESTED     - the registry and CLI suites still pass with a third executor :
             `tests.test_engine_registry` -> "Ran 36 tests in 5.509s" / "OK"; `tests.test_engine_cli`
             -> "Ran 16 tests in 10.648s" / "OK".
TESTED     - the whole suite, at the end : `python -m unittest discover -s tests -t . -v` ->
             "Ran 190 tests in 355.182s" / "OK" (178 before + 12 new; 0 failures, 0 errors, 0 skips).
             The FIRST full run had 1 failure and it was a real find: see FAILED below.
FAILED     - the first full suite run : 1 failure in `tests.test_engine_manifest`
             (`test_unknown_executor_is_rejected` -> "AssertionError: [] is not true"). That test used
             `executor="remotion"` as its example of an executor the engine has NOT wired - which
             stopped being true in this session. The rule it protects (a name no module answers to is
             refused with `unknown_executor`) is unchanged; the fixture now says
             `executor="not_an_executor"`. Re-ran that suite: "Ran 40 tests in 5.530s" / "OK", then
             the whole suite above.
TESTED     - the vision test (protocol in DECISIONS 6) : looked at `still_16x9.png` and
             `still_9x16.png` and wrote the answer down BEFORE reading the scene source. What I was
             shown and what I answered: a dark frame with a violet-brown vignette; one thick orange
             ring, ~70 % of it filled starting at 12 o'clock and running clockwise to about 8
             o'clock, the remainder a dim grey track; an orange glow behind the ring; inside it the
             number "70" in large white bold digits with a smaller orange "%" to its right; under the
             ring the label "OF PLAYERS DISAGREED" in white uppercase; focal point = the number;
             nothing else in the frame and the bottom third-to-40 % empty; at 9:16 the same
             composition scaled up, the label running almost edge to edge. Ground truth read
             afterwards from `scenes_examples/stat_ring.tsx` + `index.ts`: props `{value: 70, label:
             'of players disagreed', unit: '%'}`, label rendered `uppercase`, ring `p.accent` with the
             track at 12 % alpha, number `AnimatedCounter` at `fontSize size*0.27`, unit at
             `size*0.15` in accent colour, backdrop a radial accent glow. Every answered detail
             matches.
NOT TESTED - whether a second Remotion render of the SAME timeline reproduces the bytes: the M5.5A
             re-render is 11 KB smaller than the M0 file with identical frames and duration, so
             something is not deterministic (encoder threading is a hypothesis, not a measurement).
             One more `recap.py remotion` run would settle it; parked for 5.5B because the editing
             path - the part that must be reproducible - IS byte-identical.
NOT TESTED - `render_still`/`render_range` against a scene inside a PROJECT (`scene-<segment id>`):
             only the two example scenes were rendered. The regress project's own scenes exist, but
             3 of 6 are keywords fallbacks, so the first honest target is 5.5B's new primitives.
NOT TESTED - a render on a machine without Chromium: `ensureBrowser()` is never exercised by this
             executor (the browser came from M0); the CLI would download it, as it did in M0.
NOT TESTED - the 5.5B hook (a scene importing a footage/still file), the primitives, the critic loop:
             that is the next session and nothing of it was started.

```
DECISIONS  - 1. The executor calls the pinned CLI as `node
             recapstudio/remotion/node_modules/@remotion/cli/remotion-cli.js`, NOT `npx remotion`:
             npx can resolve another version out of the registry and prints its own noise, and the
             `.cmd` shim re-parses quotes on Windows. cwd is `recapstudio/remotion` because
             `remotion.config.ts` resolves the `@kit` alias from `process.cwd()`.
             2. `--props` gets a PATH to a JSON file written beside the output, never an inline JSON
             string; and a landscape render passes NO props at all, because SceneLab's defaultProps
             already say `portrait: false`, so a 16:9 render leaves no extra file. A 9:16 render
             leaves `<output>.props.json` next to the still: one tiny undeclared file, recorded here
             rather than hidden. The manifest still declares exactly one output.
             3. The SCENE FILE is the op's declared input (`inputs=("scene",)`), so the engine digests
             it into the cache key. Measured both ways in `tests.test_engine_remotion`: same scene +
             same params -> same key; edited scene -> different key; changed `frame` -> different key.
             4. Cold vs warm is DEFINED, because "cold" otherwise means anything: cold = run folder
             and output removed, warm = output removed only (the engine re-runs the same step),
             cached = nothing removed. The finding that matters for the critic loop: warm is not
             cheaper than cold (7-8 s either way) - that ~8 s is webpack bundling, not the frame. So
             one look costs ~10 s wall, and a CACHED re-run of the same scene costs ~1 s. Affordable;
             a per-frame loop through the CLI is not, which 5.5B has to design around.
             5. Evidence: the two ops point at `docs/evidence/m55_remotion.json`, not an M2 file. The
             M2 matrix measures EDITING; nothing in it draws. `tests.test_engine_registry` now allows
             `docs/evidence/m55_*` for the remotion executor only and still demands `m2_*` for
             kinocut and ffmpeg - the M3 rule ("no executor without passing evidence") is unchanged
             in strength, and `evidence_status` proves the new file has rows and verdict PASS.
             6. Vision-test protocol, so a later session can repeat it: render a still, LOOK at it and
             write the answer down (composition, focal point, the `docs/VISUAL_STANDARD.md` section 4
             warning signs, one specific detail), and only THEN read the scene source to check.
             Reading the source first would have made the test worthless.
             7. What the stills actually show, in the standard's own words: one centred ring over a
             dark gradient, a number and a caption under it, nothing else in the frame; at 9:16 the
             same composition scaled up, the label nearly edge to edge, the bottom 35 % empty. That is
             the "sentence over a gradient + a stat" default from section 2 and the "same title +
             subtitle over the same composition" sign in section 4 - so M5.5 is correctly aimed, and
             the cause is the contract (no footage, no layered media), not the author of this scene.
             8. Scope kept: no CONTRACT.md, no kit file, no primitive, no scene prompt, no critic
             loop, no M6. `cutwright/engine/` gained one new file and two lines in `ops.py` +
             five in `registry.py`; `guard.py`, `probe.py`, `subs.py`, `moments.py`, `frames.py`
             and every other engine module are untouched (`git diff --stat` in the session report).
             9. Two kinds of TRACKED file are rewritten by merely RUNNING things, and both were
             `git checkout`-ed before this commit (the C-006 practice): `docs/evidence/m2_*.json`
             (the equivalence tests write their own evidence) and
             `recapstudio/remotion/src/generated/registry.ts` (scenes.py writes the project's scene
             registry into the shared renderer folder - the pack run turned the committed stub back
             into the regress project's three scenes + "demo noir" theme). Neither is an M5.5A edit.
             The next session will see both reappear the moment it runs the pack or the suite; that is
             expected, not a regression.
Commit     - see the closing docs commit of this session (the C-009/C-010 pattern: the code commit
             lands first, then one small docs commit records its hash here and in HANDOFF/COMMS).
```


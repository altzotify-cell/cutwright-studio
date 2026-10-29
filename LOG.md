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


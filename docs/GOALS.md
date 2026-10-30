> **SUPERSEDED IN PART (2026-10-29).** Goal ORDER and anything about Shotcut are replaced by `docs/ROADMAP.md`
> (Kinocut-first). G1, G2, G3 are CANCELLED. G0 -> M0, G4 -> M6, G5 -> M7, G6 -> M8, G7 -> M10, G8/G9 -> M11,
> G10 -> M9 (HyperFrames benchmark), G11-G16 -> M12-M16. Use the sections below only as DETAIL for the milestones that point
> at them; where a section mentions Shotcut, `.mlt`, `cli-anything-shotcut` or "two backends", ignore it.

# Goals (read ONE section; find it with `grep -n "^## " docs/GOALS.md`)

Status lives in `HANDOFF.md`, not here. This file is the spec. Every goal has: Why, Depends on,
Read first, Build, Done when, Owner needed, Traps. "Done when" must be shown with quoted output.
Paths are relative to the repo root; `RS` = `recapstudio/`. A recap project lives in
`RS/Projects/<name>/` and has its own copy of `recap.py` (run it from there).

Standard finish of every goal: LOG entry with proof, tick in HANDOFF.md, status block, commit
(`git commit -F`), push, tell the owner to start a new session.

---

## G0 - Baseline on the PC

Why: the merge was tested only on Linux without Remotion. Recap Studio Phase 3 (scene engine,
Scenes tab) was never run on Windows. Everything after this stands on it. You run Windows, so
you can do what the earlier Claude sandbox could not.

Depends on: nothing.
Read first: `docs/ARCHITECTURE.md` (Data flow), `docs/CODEMAP.md` (recap.py steps).

Build / do:
1. Commit the merged tree on its own commit, before touching anything:
   message "merge: Recap Studio (phase 3) into Cutwright; remove vendor/recapstudio".
   Check `git status` shows no `keys.env`, `Projects/*`, `node_modules`, `models/`, `bin/`, `shotcut/`.
2. `python -m cutwright doctor`. Quote the Recap Studio section. If Node or the npm packages are
   missing, ask the owner to run `recapstudio\SETUP.bat` (installs Node, runs `npm install` in
   `recapstudio\remotion`), then re-run doctor.
3. New project: copy `recapstudio\_template` to `recapstudio\Projects\g0test` (or use
   `NEW_PROJECT.bat`). In that folder with `set RECAP_NONINTERACTIVE=1`:
   `python recap.py demo`, `python recap.py briefs --demo`, `python recap.py video`,
   `python recap.py timeline`, `python recap.py scenes`, `python recap.py remotion`.
4. Phase 3 reference check (from `docs/legacy/RECAPSTUDIO_GAMEPLAN_rev9.md`, the "Phase 2" and
   "Phase 3 check" lists): the three example scenes `[ok]`, the crash / network / blank demo
   scenes replaced by the keywords scene with readable messages, second `scenes` run instant
   (cache), `recap_remotion.mp4` plays, `PARITY CHECK PASSED`.
4b. Cutwright half (only what exists on the PC): `python -m cutwright doctor`; if Shotcut is installed
   (`shotcut\Shotcut\melt.exe`), `python -m cutwright build projects/demo_cuts/plan.json` and quote the check table
   (the old demos must still pass after the merge). If Shotcut/whisper are not installed, say so; do not skip silently.
5. Try the Whisper fix from HANDOFF "Known unverified" (upgrade `av` + `faster-whisper`), rebuild
   the timeline, look for `word timings ...: whisper`. If it still fails, note it, move on.
6. Record render time (frames/s) and scene-check time in LOG.

Done when: LOG has quoted lines for: doctor Recap section, `[ok]` x3 / fallback x3, `PARITY CHECK
PASSED`, render seconds, and the git commit hash of the merge. Anything that failed twice is a
BLOCKED entry, not a silent skip.

Owner needed: run `SETUP.bat` if Node is missing; say yes/no to "does recap_remotion.mp4 look right".
Traps: do not open `recap.py` whole. A project's `recap.py` is a COPY of `_template/recap.py`;
after changing the template, refresh the project copy (UI "sync" or copy the files).

---

## G1 - Shotcut crossfade (the old, already-authorised milestone)

Why: this was the active milestone of the Cutwright handoff and the V2 master doc says never to skip it.
It is designed and measured on paper; `Project.to_xml()` still emits the old `luma` shape, so
`projects/demo_cross` fails `gui_xfade`. Shotcut sets `disable=1` on V1's `frei0r.cairoblend` on every
Ctrl+S, which silently kills any flat multitrack dissolve.

Depends on: G0. Needs the owner's Shotcut portable install (`shotcut\Shotcut\`, not in git) and melt.
Read first: `docs/legacy/HANDOFF_FULL_cutwright_2026-10-26.md`, sections "The shape that works -- in both
engines", "The edit to make", "Gotchas worth keeping", and the last 40 lines of the legacy LOG entry for
2026-10-24 (in `LOG.md`).

Build: apply "The edit to make" to `Project.to_xml()`, `check_xml()` and the docstring in `cutwright/mlt.py`
(work in small edits; the file is 2,573 lines, read only the ranges you need). Working shape: a nested tractor
played as one V1 entry, outgoing tail on track 0, incoming head on track 1 with a `brightness` alpha ramp
keyed to its own frames, one `frei0r.cairoblend` a=0 b=1 inside the tractor. Rebuild `projects/demo_cross`.

Done when: `python -m cutwright build projects/demo_cross/plan.json` shows all nine checks passing including
`crossfade` and `gui_xfade`; the owner opens the file in Shotcut, presses Ctrl+S, and the dissolve is still there
(or the `shotcut` check proves it after the rewrite). Quote the check table. Then COMMS BREAKTHROUGH.

Traps: melt ignores the .mlt's own `<profile>` unless `-profile` is passed (already fixed; do not undo). A `luma`
in the same place "works" in melt but not after Shotcut saves. Do not borrow transitions from other repos before
this lands.

---

## G2 - Reconnaissance of the borrow repos (read only, no code)

Why: the owner wants Cutwright to stop hand-building editor controls and adopt what exists. The old handoff's
borrow list came from the owner's notes and was never verified. A first web check (consultant, 2026-10-29,
product pages only, not the code) is in `docs/BORROW_notes.md`; this goal replaces it with real findings.

Depends on: G1 (so borrowed features can be judged against a working crossfade).
Read first: `docs/BORROW_notes.md`, legacy HANDOFF_FULL sections "Borrow list" and "Consultant's adjustments".

Do: clone read-only into a scratch folder OUTSIDE the repo (never inside `recapstudio/` or `cutwright/`):
`HKUDS/CLI-Anything` (package `cli-anything-shotcut`), the Shotcut MCP the owner named (`NoBanks/shotcut-mcp`;
a search showed other `shotcut-mcp` repos, confirm which exists), `linyqh/NarratoAI`, and `mltframework/shotcut`
only as a reference for XML shapes. For each: read the LICENSE file first, then the commands/tools list. Write
`docs/BORROW.md`: one table row per borrow-list item with a verdict: `depend` (pip install), `copy shape`
(copy the MLT XML shape, write code fresh), `copy code` (licence allows, record in PROVENANCE.md),
`reimplement`, or `drop`, plus effort and risk. Verify the unverified claims: does cli-anything-shotcut really have
ducking / volume envelopes, preview bundles, a SKILL.md? (the PyPI page lists none of these).

Done when: `docs/BORROW.md` exists, every row has a verdict with the evidence (file path or command in the cloned
repo), licences are recorded in `PROVENANCE.md`, and the COMMS entry lists the 3 decisions the owner must make
(dependency vs copy; lxml/click dependency vs stdlib-only; which repo is the MCP reference).

Traps: licence unknown = no code copied, shape only. No network downloads from inside the repo folders.
Do not install anything without the owner's approval.

---

## G3 - Adopt the Shotcut CLI layer: all editor controls through `cli-anything-shotcut`

Why (owner's goal): do not implement every editing control by hand. `cli-anything-shotcut` (MIT, Beta 1.0.0, PyPI;
`lxml` + `click`, drives `melt`/`ffmpeg`) already offers project/timeline (add, remove, move, trim, split clips,
tracks, gaps), filters (list/add/set/remove), 11 transitions (dissolve, wipes, clock, iris-circle, crossfade),
compositing (blend modes, track opacity, picture-in-picture), media probe/thumbnails, export presets and render,
undo/redo, and `--json` output. Cutwright's job is to wrap it with verification: Cutwright's checks are what
make it trustworthy (the "one invariant").

Depends on: G1, G2 (verdicts in `docs/BORROW.md`; if the verdict is not `depend`, follow what G2 decided).
Read first: `docs/BORROW.md`, README section "What works today" (the seven checks), `cutwright/mlt.py` class
`Project` public methods only (`grep -n "    def " cutwright/mlt.py | head -80`).

Build, one feature at a time; each is a separate commit with its own check:
1. `cutwright/backends/shotcut_cli.py`: thin adapter, optional import (Cutwright core stays standard-library
   only; the owner approves the `lxml`/`click` dependency in G2). `cutwright doctor` reports it.
2. Define the backend interface (see G8) and register this as the `shotcut` backend next to the existing
   `mlt.py` writer; plans can say which writes the file. Keep the old writer working (its checks stay).
3. For each borrowed control in this order: transitions (11 types) -> blend / opacity / PIP -> filters ->
   ducking / volume envelope (implement ourselves if the repo lacks it: a second audio track with keyframed
   `volume`, dB checks) -> media thumbnails / probe -> export presets. For each: add a Cutwright check (not just a
   successful exit), and prove it survives a real Ctrl+S in Shotcut (Shotcut rewrites the file and disables flat
   blends). `not_run` is not a pass.
4. `--json` on every Cutwright command (stable keys, exit codes 0 ok / 1 failed check / 2 bad input).
5. Bridge: Recap Studio `timeline.json` (+ audio + captions as titles) -> Cutwright `plan.json` -> `.mlt`, so an
   engine-made video can be opened and hand-polished in Shotcut. Decide first whether comic camera moves stay in
   the Remotion/ffmpeg render (simplest).

Done when: each borrowed control has (a) a plan example in `projects/`, (b) a passing check quoted in LOG,
(c) a note whether it survived Ctrl+S, and the demo projects still pass their old checks. No control is
hand-rolled that the dependency already provides.

Owner needed: Shotcut portable installed; one Ctrl+S test per control (the agent can use `cutwright/tools/shotcut_window.ps1`
where it works); approval to `pip install cli-anything-shotcut`.
Traps: the dependency is Beta and one-maintainer: pin the version, never auto-update. Its output is NOT trusted
until Cutwright's checks pass on it. Do not let it write into the owner's footage folders (guard rules apply to
wrapped calls: run it with outputs inside `projects/`).

---

## G4 - Agent bridge: `python -m cutwright recap <step> --json`

Why: right now the engine is driven by .bat menus, a web UI and prompts to a human. An agent needs
one non-interactive command surface with machine-readable output and guard rails.

Depends on: G0.
Read first: `docs/legacy/HANDOFF_FULL_cutwright_2026-10-26.md`, section "Second-pass findings from
`recap.py`" (items 1-8; they describe exactly how to drive it), `docs/TOOLS.md`, `cutwright/cli.py`
(the argparse layout) and `cutwright/guard.py`.

Build (new module `cutwright/recap.py`; thin wiring in `cli.py`; stdlib only):
1. `recap projects` - list `RS/Projects/*` with module, segment count, which outputs exist.
2. `recap new <name> --module movie_recap|show_recap|... [--topic ...]` - copy `_template`, write
   `project.json` directly (fields in findings item 2). Never call `init`.
3. `recap run <project> <step> [--only ids] [--engine edge --yes]` - runs the project's own
   `recap.py <step>` as a subprocess with `RECAP_NONINTERACTIVE=1`, `cwd` = project. Whitelist:
   `subs index sheets check missing say tts srt video timeline scenes remotion briefs preview demo`.
   Refuse (exit code 2, clear message) `init`, `collect`, `comic --force`, any `--force`, unless the
   caller passes `--i-know-this-destroys-work` AND a COMMS entry id.
4. `--json` on every command: `{ok, step, project, exit_code, seconds, stdout_tail (last 40 lines),
   files_changed: [...], problems: [...]}`. `problems` comes from parsing known lines (the timeline
   validator's plain-English list, scene report, "MISSING SHOT").
5. `recap status <project>` - read `STATE.md` + `timeline.json` + `scenes_report.json` and return
   one JSON: counts, slates, failed scenes, missing audio, next suggested step.
6. Stale-copy check: warn when the project's `recap.py`/`timeline.py`/`scenes.py` differ from
   `_template/` (hash compare).
7. Extend `doctor` is already done; add `cutwright recap doctor` only if cheap.
8. Tests in `tests/test_recap_bridge.py` (unittest, stdlib): refuses forbidden steps, builds a demo
   project through the bridge, JSON keys exist. Do not depend on Remotion in unit tests.

Done when (quote output): `python -m cutwright recap new g1 --module movie_recap --json`, then
`recap run g1 demo`, `recap run g1 timeline`, `recap run g1 remotion`, `recap status g1` all return
`ok: true` JSON; `recap run g1 init` and `recap run g1 tts --force` are refused; unit tests pass.

Owner needed: nothing.
Traps: recap.py calls `reveal()` (recap.py line 367), which opens an Explorer window on Windows. It is harmless
but noisy; if it bothers the owner, add one `RECAP_NO_REVEAL` env check inside `reveal()` (the only allowed recap.py edit).
`tts` rewrites `config.json` (saves the engine): that is expected. Never put the owner's keys in JSON output.

---

## G5 - Agent-owned scene loop (replaces the Claude paste for pass 2)

Why: Phase 3 asks the owner to copy a prompt to Claude and paste scenes back. The agent should write
the scenes itself, check them, LOOK at the rendered frames, and revise only the weak ones.

Depends on: G0, G4.
Read first: `RS/remotion/kit/CONTRACT.md` (whole, 97 lines), `RS/_template/authoring.py` functions
`build_prompt`, `import_reply`, `status`, `action`; `RS/_template/scenes.py` `_check_generated`,
`_judge`; `RS/remotion/tools/check_scenes.mjs` header; `docs/VISUAL_STANDARD.md` section 1 only.

Build:
1. **Vision probe first (30 minutes, cheap).** Render one scene frame PNG (use an example scene), give
   it to the agent's own image input and ask "describe what you see: colours, text, layout". Record the
   result in LOG. If you cannot see images: set the review mode to `metrics+human` (below) and say so.
2. `cutwright scene brief <project> [--id ...] --json`: the pass-2 inputs for each pending scene
   (brief, data, narration, measured frames, neighbours, theme path) WITHOUT a giant prompt.
   (`authoring.build_prompt` already computes this; reuse, do not duplicate.)
3. `cutwright scene write <project> <id> --file x.tsx`: validates the name, runs the static check,
   saves to `scenes/<id>.tsx`, moves the old one to `scenes/_old/`, records the brief hash
   (`authoring.import_reply` logic). You may also just write the file yourself and call `scene check`.
4. `cutwright scene check <project> <id> --json`: static check + single-scene test render
   (start / 40% / 75% / last frame, plus the other aspect ratio). Returns verdict, readable errors, and
   the PNG paths. Reuse `scenes.py` + `test_scenes.mjs`; add an `--only <id>` path if missing.
5. `cutwright scene sheet <project> <id>`: ONE contact-sheet PNG of 8 evenly spaced frames (so a
   vision model needs a single image, which is cheaper than 8). Use Pillow if present, else ffmpeg tile.
6. `cutwright scene metrics`: simple numeric review of those frames: contrast range, fraction of
   pixels that changed between frames (is there real movement?), content outside the safe area,
   largest flat region. It reports; it never decides "good".
7. Review loop rule written in `docs/TOOLS.md`: write -> check -> sheet -> LOOK -> revise at most 2
   times per scene -> if still weak, mark `needs_owner` and keep the best version.
8. Keep the fallback: `authoring.action` (use keywords instead / use the scene / write again) stays.
9. Keep the Claude-chat path working (`briefs` step + `SCENE_REPLY.txt` import) - do not delete it.

Done when: from the three demo briefs (`recap.py briefs --demo`) the agent writes 3 scenes; >= 2 pass
the check first try; for one scene the agent looks at the sheet, states in LOG what is weak, revises it,
and the second sheet shows the change; the cache makes a rerun instant; a deliberately broken scene still
falls back. Quote the commands and the pass counts.

Owner needed: look at one sheet and say "better / not better".
Traps: scenes may import only `remotion`, `react`, `@kit` (see CONTRACT rule 1-3). Kit names must exist
(common mistake: guessing prop names; read `kit/index.ts` and the file you use). A scene that passes is not
a scene that looks good: that is G6. Changing `kit/` invalidates every cached scene (kit hash).

---

## G6 - Visual quality overhaul + benchmark

Why: the owner's verdict (2026-10-29) is that scenes look like PowerPoint: boxes, labels, fades. Passing
checks does not fix that. The standard and method are in `docs/VISUAL_STANDARD.md` (READ IT ALL for this
goal). Do not add SFX or other phases before this passes.

Depends on: G5 (needs the frame-review tools).
Read first: `docs/VISUAL_STANDARD.md`, `RS/remotion/kit/*` (all, ~700 lines), `RS/remotion/scenes_examples/*`,
`RS/_template/PASTE_THIS_TO_CLAUDE_scene_authoring.txt`, `authoring.build_prompt`.

Build, in this order, one commit each:
1. **Audit (no code change).** Write `docs/AUDIT_visuals.md`: confirmed findings vs hypotheses. Start from
   these CONFIRMED facts and add more: (a) `CONTRACT.md` rules forbid `Img`, `Video`, `OffthreadVideo`,
   `staticFile`: scenes can only draw SVG/CSS, so no photos, footage, cut-outs or textures: that alone
   produces slide-like output; (b) the kit has charts, counters, ring, reveal text, 80 particles, one
   `SceneFrame` background: no camera/parallax, masks/wipes, layered media, light/grain, trails, kinetic type
   beyond `RevealText`; (c) the three example scenes (stat ring, timeline, quote) are card/ring layouts and
   the authoring prompt shows them as the model to follow; (d) `motion` is only `brief+data+cost`, with no
   art-direction fields; (e) checks only judge "works", never "looks good". Mark hypotheses as such.
2. **Safe media in scenes.** Add `kit` primitives `Media` (image or video from the project's staged assets)
   and `Footage`, resolved by the tool (scene gets asset keys from `props.assets`, the tool maps them to
   `staticFile` paths). Update `check_scenes.mjs` so scenes may use ONLY these kit wrappers, not raw `Img`
   or `staticFile`. Keep every other ban (network, eval, Date, Math.random, DOM, timers). Add tests with a
   scene that tries raw `Img` (must fail) and one using `Media` (must pass).
3. **Kit expansion**, only primitives you will use in the benchmark: camera/parallax (`Camera`, `Layer` with
   depth), masks and wipes (`Reveal` with shape/direction), kinetic type (per-word/char transform, stretch,
   track, slam on a narration word), light (`LightSweep`, `Vignette`, `Grain` deterministic), motion trails,
   text-on-path via `DrawPath`. Each has a docstring in `kit/` and a line in `CONTRACT.md`. Keep `cost` honest.
4. **Art-direction brief.** Extend the `motion` object (back-compatible, optional): `concept`, `composition`
   (focal point, foreground/middle/background), `beats` (what happens when, tied to narration words),
   `assets` (names of stills/footage to use), `transition_in/out`, `medium` (typography | footage | still |
   infographic | illustration | atmospheric). Update `authoring.validate_script`, the movie-recap prompt and
   `PASTE_THIS_TO_CLAUDE_scene_authoring.txt`. Rule inside the prompt: choose the MEDIUM per moment; not every
   line needs a motion graphic; cards/boxes only when they are the best solution.
5. **Benchmark** in `RS/remotion/scenes_benchmark/` (5 scenes, own sample assets, no invented film footage;
   use generated gradients/noise/silhouettes or CC0 images with a `CREDITS.txt`): cinematic reveal, kinetic
   typography, story timeline (not a row of cards), data/stat explainer, atmospheric narrative. Each at least
   6 s so movement can be judged. Render each at 16:9 and 9:16 (use `scene sheet`) and a short mp4.
6. **Before/after.** Put the old `stat_ring`/`timeline_reveal` sheets next to the benchmark sheets in
   `docs/benchmark/` and write 10 lines on what changed.
7. **Owner review gate.** Send the sheets (or tell the owner which folder). Record the owner's verdict per
   scene in LOG. If a scene is "still a slide", fix the kit/prompt, not just that scene.

Done when: five benchmark scenes pass the checks at both ratios AND the owner approves at least four of the
five as "not PowerPoint". The audit file, the new kit docs and updated prompts are committed. A scene that
uses footage or a still works end to end in a full render with captions on top.

Owner needed: visual verdict (required); optionally 2 reference videos/links of the look they want
(ask once at the start; it saves a lot of rework).
Traps: more effects != better art direction. Particles/blur/large SVG filters are slow on the i5: use
`cost` and keep the benchmark rendering at a reasonable speed (record frames/s). Do not replace one rigid
template list with another. Do not weaken the static check to allow complexity. Changing `kit/` clears the
scene cache: say so in the commit message. If flash cannot reach the quality bar, write a BLOCKED entry
proposing the Claude-chat consultant pass for the five benchmark scenes (export prompts with the existing
`briefs` step) rather than lowering the bar.

---

## G7 - Perception to script (video in, valid script out)

Why: the agent should read footage itself instead of the owner pasting subtitles into a chat. This merges
Cutwright's perception tools (subtitle gate, moments, frame verification, whisper) with Recap Studio's
`subs`/`index`/`sheets` and its `segments.json`.

Depends on: G4 (and G5/G6 are NOT required; can run in parallel only if the owner asks).
Read first: legacy HANDOFF_FULL sections "Versatility target: English footage of any kind", "Phase 2:
coverage sheets", "Phase 2b", and the owner's footage-type table; `cutwright/subs.py`, `moments.py`,
`frames.py` headers; `RS/_template/PASTE_THIS_TO_CLAUDE_movie_recap.txt`; `authoring.validate_script`.

Build:
1. `cutwright analyze <video|folder> --project <name>`: runs `probe`, the `subs` gate (it owns subtitle
   trust), `transcribe` when there is no usable transcript, `moments`, and writes
   `RS/Projects/<name>/analysis/{digest.txt, stretches.json, moments.json}`. Stretch types:
   dialogue | mixed | no-speech (decide per stretch, not per video).
2. **Coverage sheets** (old Phase 2): a contact sheet at every shot boundary with no overlapping dialogue,
   plus a floor of one per N minutes. A check FAILS if a silent stretch has no sheet.
3. **No-transcript modes** (old Phase 2b): whisper fallback, visual-only mode, commentary-driven footage is
   low-trust for "what happened" (sample more sheets).
4. `cutwright script check <project> --json`: wrap `authoring.validate_script` + schema checks
   (ids unique, timings inside the source duration, every `src` exists, no slate-causing gaps, `motion`
   count <= a third) with plain-English messages. Run it before the voice step.
5. The agent writes `segments.json` itself using the module's prompt text as a profile
   (`PASTE_THIS_TO_CLAUDE_<module>.txt`). Make `cutwright profile show <module>` print it.
6. Optional: `recap.py index` already makes contact sheets (4x4 tiles, ~1 per 5 min); keep it as the coarse
   layer, add the shot-boundary sheets on top.

Done when: given only a video path, the agent produces `analysis/` and a `segments.json` that passes
`script check`; works on (a) a dialogue clip and (b) a silent clip; log both with the sheet counts. The vision
dependence is declared (if no vision, sheets are for the owner / consultant and the agent uses transcript +
metrics only).

Owner needed: two short English test clips (one dialogue, one silent). Footage rights are theirs.
Traps: the subtitle track may be picture-based (PGS/DVD): that needs OCR, out of scope, say so. Never copy the
footage into the repo (reference by path, read-only). Burned-in subtitles are a known gap (note it).

---

## G8 - Backend interface + Production Blueprint (the AI Director's plan format)

Source: `docs/legacy/VISION_cutwright_v2.md` sections B, E and the Blueprint list (moved there in M5). Why: so the
Director, the CLI and later the UI do not care which renderer draws a scene.

Depends on: G3 (Shotcut backend exists) and G6 (Remotion scenes proven); G7 helps.
Read first: the vision doc "Production Blueprint" and "Rendering architecture"; `docs/ARCHITECTURE.md`.

Build:
1. `cutwright/blueprint.py` + JSON schema `docs/blueprint.schema.json`: creative brief and audience, genre and
   visual direction, narrative structure and scene sequence, duration / aspect / fps / resolution, per-scene timing
   and transitions, required footage / generated assets / graphics, typography-composition-colour-lighting-animation
   direction, voice-music-SFX requirements, chosen backend per scene, validation criteria, known limitations.
   Backend independent. Reuse existing contracts: a Blueprint compiles DOWN to `segments.json` + `theme.json` (Recap
   Studio) or to `plan.json` (Shotcut); do not create a third timeline format.
2. Backend interface `cutwright/backends/base.py`: `capabilities()`, `plan(blueprint) -> backend plan`,
   `render(plan) -> artifacts`, `validate(artifacts) -> report`. Adapters: `remotion` (wraps the engine via the G4
   bridge), `shotcut` (G3). A failure in one backend must not break the other.
3. `cutwright blueprint check <file> --json` (schema + plain-English problems) and `cutwright direct` as the
   orchestrator skeleton: interpret brief -> blueprint -> choose backend per scene -> build -> validate -> report
   what succeeded, failed and needs human review. It never claims success without a verified artifact.
4. Creative QA report next to technical validation: sampled frames/contact sheets, readable typography check
   (size/contrast metrics), pacing (visual change interval), brief compliance checklist; unresolved = "needs human
   review".

Done when: one blueprint compiles to a Remotion recap AND to a Shotcut project; the report lists technical checks
(duration, media present, audio present, resolution, fps) and the creative checklist with limitations stated.

Traps: do not build a universal timeline; compile to the existing formats. Do not claim a genre is supported until
a workflow for it passed (see G9).

---

## G9 - Any kind of video

Why: "movie recap" must stop being the only shape. Different video kinds need different scripts, pacing,
visual mix and themes, from the same engine.

Depends on: G6 (visual kit), G7 (script tools).
Read first: `docs/VISUAL_STANDARD.md` sections 2 and 6; all `PASTE_THIS_TO_CLAUDE_*.txt` file names and the
movie one in full; `RS/_template/project.json` `module` field and where `module` is read
(`grep -n "module" RS/_template/recap.py | head -40`).

Build:
1. **Format profiles**: `RS/_template/profiles/<name>.json` + prompt: movie_recap, show_recap, documentary,
   explainer, sports_story (nba_*), data_story, ranking, history, real_story. A profile holds: script
   prompt, default theme presets (2-3), caption style, pacing (seconds per beat, visual change interval),
   default medium mix (footage/still/motion/typography), default transitions, scene-authoring hints.
   Load by `project.json` `module`; unknown module falls back to movie_recap.
2. **No-footage mode**: a project with zero video can render from stills + motion scenes + voice. Missing
   footage becomes a designed scene (`keywords` or a generated scene), never a slate. Test with an explainer.
3. **Asset providers** behind one interface `providers/` (search, filter, fetch, cache, credit):
   local folder first; then free stock (Pexels/Pixabay free API keys) for stills/video; license filter on;
   everything credited to `credits.txt`. No paid or AI-image service without the owner's yes; leave a clean
   hook (`providers/generated.py`) so one can be added later.
4. `cutwright make "<one-line request>" --profile <name> [--source ...]` as the single entry the owner can
   type: creates the project, runs analysis (if a source), asks the agent-side steps in order, and prints what
   is left for the agent. It orchestrates; it does not hide errors.

Done when: three videos from three one-line requests: (1) a movie recap from a clip + subs, (2) an explainer
with no footage, (3) a stats-driven story. Each: `timeline.json` validates, Remotion render completes, the
three look visibly different (themes and scene mixes), `credits.txt` correct. Owner confirms "different looks".

Owner needed: free Pexels/Pixabay keys if wanted; a verdict on the look.
Traps: do not build a template per genre; a profile only biases the choices. Keep Premiere/VideoPad exports
working (run `recap.py premiere` on one profile as a regression).

---

## G10 - Hyperframes bake-off (vision doc "Phase 7", scoped small)

Facts (consultant read the project page 2026-10-29; verify): HeyGen's HyperFrames turns HTML/CSS + seekable
animations into MP4 by seeking frames in headless Chrome and encoding with FFmpeg; Node 22+; Apache-2.0; CLI
`init / preview / render`; ships agent "skills"; page does not mention alpha/transparent output. That is the
same mechanism as Remotion, so it is NOT added by default. The question: does plain HTML/CSS make agent-written
scenes easier and prettier than Remotion's React/TSX, and is it as fast on the i5?

Depends on: G6 (the five benchmark scenes) and G8 (backend interface).
Phases (from the vision doc): 7A recon (docs, licence, install, formats; record in `PROVENANCE.md`; no assumed
commands) -> 7B proof of concept (one animated title + one overlay; check size, duration, fps, render success;
test transparent output) -> 7C adapter behind the G8 interface, only if the bake-off says so -> 7D tests, failure
handling, missing-dependency messages, existing tests still pass.
Bake-off: render the same 5 benchmark scenes in HyperFrames; compare first-try pass rate for an agent writer,
look (owner verdict), render frames/s on the i5, and failure modes. Write `docs/BAKEOFF_hyperframes.md`.

Done when: the bake-off doc exists with numbers and a recommendation (`adopt as backend` / `keep as optional` /
`drop`), and the owner decides. Do not replace Remotion without that decision and a migration plan.

---

## G11 - SFX engine

Source: `docs/legacy/RECAPSTUDIO_GAMEPLAN_rev9.md` section 5 and Phase 4 in section 7. Summary: provider interface;
Freesound (free key; previews first; verify its CURRENT API and license rules before building); bundled starter
pack of ~50 CC0 sounds so it works offline; global index with loudness-normalised files; sound themes mapping
events to sounds (transition -> whoosh, title -> impact, caption pop -> tick, chapter -> riser); semantic `sfx`
cues in segments (`at`: start|end|seconds|word index); scenes may declare audio hooks; review step to audition
and swap; mixing: voice on top, music ducked 12-18 dB, SFX on its own bus; Remotion `<Audio>` per cue; Premiere /
VideoPad get an extra audio track. Default license filter CC0 + CC-BY; CC-BY written to `credits.txt`.
Done when: a project with automatic transition/title SFX plus 5 scripted cues renders with consistent loudness;
CC-BY credits appear; works offline from the starter pack. Depends on G6.

---

## G12 - Polish and real 9:16

Source: gameplan Phase 5. Theme refinement (fonts, colours, caption styles, motion energy, grain, grade),
real 9:16 layouts with safe zones passed to scenes through `layout`, intro/outro. Done when the same timeline
(with generated scenes) renders cleanly at 16:9 and 9:16 with captions inside safe zones. Depends on G6.

---

## G13 - Speed

Source: gameplan Phase 6. Overlay-only render path (Remotion draws only the overlay/scene layer, ffmpeg
composites the footage), per-segment render cache, concurrency tuning for the i5 (test 3), cost-budget
enforcement, Player preview in the UI, preview quality setting. Done when re-rendering after editing one
segment takes < 20% of the full render. Depends on G6, ideally G12.

---

## G14 - MCP server and portable agent skill

Source: vision doc section C. Only after the operations they expose are stable (G3-G9 done).
Build: a `SKILL.md` (instructions, workflows, safety rules, command examples, recovery procedures) so other agents
can operate Cutwright; then, if the owner still wants it, an MCP server exposing documented operations (inspect,
transcribe, moments, blueprint, build, render, validate) as tools over the same CLI/engine. The CLI with `--json`
remains the source of truth; MCP is a thin wrapper. Done when a second agent (not the one that built it) completes a
small job using only the skill/MCP. Do not claim MCP exists because a folder does.

---

## G15 - Cutwright Studio (human UI on the same engine)

Source: vision doc section D. Inspect FIRST: `recapstudio/studio.py` + `web/` (the existing web UI, with Scenes
tab) and `cutwright/gui.py`; decide extend vs refactor vs replace in a short COMMS entry. The UI must call the same
engine/CLI as the agent; never a second implementation. Wanted: project list, import footage, review transcripts and
candidate moments, preview/edit the plan, manage titles/captions/graphics/audio, watch renders and validation, review
failures, export or open in Shotcut. Done when a human completes one full video without the command line.

---

## G16 - Other modules and optional borrows

Extend format profiles to the remaining modules (nba, real story, ranking, comic recap incl. the comic path in
`recap.py comic`), `--json` everywhere that is left, optional NarratoAI borrows (all off by default, each a config
flag + its own module; licences read in G2 and recorded in `PROVENANCE.md`; e.g. Tavily plot-search pre-step, subtitle
mask for hard-subbed footage, keyframe batching for coverage sheets, cheap hosted captioning). Retire or slim the
qtrle character pipeline only after an avatar component exists.
Done when every module has a preset and an updated prompt profile, and each optional borrow passes its own check
or is dropped in `docs/BORROW.md`.

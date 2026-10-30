# Migration checklist: Shotcut out, Kinocut + FFmpeg in

Tick boxes in this file as you go (edit the line, commit with the milestone). Milestone numbers refer to `docs/ROADMAP.md`.
Rule: INSPECT -> REPLACE -> TEST -> PRESERVE -> DELETE, in that order. Never delete before the replacement test passed.

## A. Inspect first (M0/M1; read-only)

- [x] Git: repo? remote? branch? clean? (`git status`, `git remote -v`, `git branch --show-current`). ZIP had NO `.git`. -> M0: repo created, remote `altzotify-cell/cutwright-studio`, branch `main`, clean before the audit edits.
- [x] Versions: Python (`py -0p`), Node, npm, FFmpeg/ffprobe (and `where.exe ffmpeg` is NOT inside `shotcut\`), Git, Windows, RAM, disk. -> M0: py -0p has 3.14/3.13/3.11, `python` = 3.11.9 but `py -3` = 3.14.7; Node v24.18.0; npm 11.16.0; ffmpeg/ffprobe 7.1 (scoop shim, not Shotcut's); git 2.47.1; Windows 10.0.26200.0; RAM 11.8 GB; 36.97 GB free (`docs/ENVIRONMENT.md`).
- [x] FFmpeg features: libx264, aac, xfade, acrossfade, sidechaincompress, loudnorm, subtitles/libass, ebur128. -> M0: all present, none missing.
- [x] `python -m cutwright doctor` output saved. -> M0: quoted verbatim in `docs/ENVIRONMENT.md` (captured pre-install; NOT re-run after the installs, so its `[ ]` lines are stale).
- [x] Remotion installed and 4.0.539 (`recapstudio\remotion\node_modules\remotion\package.json`); render speed recorded. -> M0: "version": "4.0.539"; rate is DERIVED 5.33 fps (514 frames / 96.4 s wall), `LOG.md` + `docs/ENVIRONMENT.md`.
- [x] Existing projects in `recapstudio\Projects\` (do not touch their contents; list names). -> M0: only `.gitkeep` + `_projects_go_here.txt` at audit time; `regress\` created from `_template` for the baseline (git-ignored).
- [ ] Is `shotcut\` present locally? is `bin\`, `models\` present? (untracked, owner's machine) - M0: `shotcut\` -> False and `shotcut\Shotcut\melt.exe` -> False; `bin\` and `models\` were NOT probed, so this stays open.
- [ ] Kinocut installed in `.venvs\kinocut`, `kino doctor` output saved, interface table written (M1).
- [ ] Licence texts read and recorded in `PROVENANCE.md`: Kinocut, FFmpeg build, OpenMontage (ideas only), Remotion.

## B. PRESERVE (do not delete, do not rewrite)

Perception and trust: `cutwright/probe.py`, `subs.py`, `moments.py`, `frames.py`, `transcribe.py`, `guard.py`.
Recap engine: `recapstudio/` entire (studio.py, web UI, `_template/` modules, Remotion kit, scenes, TTS, setup scripts).
Exporters: Premiere XML (`write_premiere_xml`), VideoPad (`write_videopad_project`), `vendor/videopad/` and `vendor/MANIFEST.sha256`.
History/docs: `docs/legacy/`, `LOG.md`, `COMMS.md`, `docs/VISION_cutwright_v2.md` (vision; where it says Shotcut, the ROADMAP wins), `docs/VISUAL_STANDARD.md`.
Free-first stack: Edge-TTS, whisper.cpp / faster-whisper, Remotion 4.0.539.
Tests/fixtures: `tests/` (new).

## C. Shotcut capabilities and their replacements (every row needs a replacement that PASSED, or an owner-approved "dropped")

| Shotcut-era capability (where) | Why it existed | Replacement | Test (ROADMAP) | Done |
|---|---|---|---|---|
| Plan -> `.mlt` timeline writer (`mlt.py` `Project`, `build`) | editable timeline + proof | manifest + executor ops; humans get Premiere XML / VideoPad (exist); optional OTIO if Kinocut's export works (M2, optional) | M3 run/resume; M4 regression | [ ] |
| `check_xml`, `check_effects`, `check_lengths` | file well-formed, names real, lengths add up | manifest validation (`validate.py`): refs resolve, ids unique, params schema, durations/frame sums match `timeline.json` | M3 tests | [ ] |
| `check_render` (small render vs source, PSNR with negative control) | the output really contains the claimed source frames | `validate.py: frames_match_source()` using frame ids on fixtures and PSNR + deliberate-mismatch control on real footage | M2 trim/concat | [ ] |
| `check_fade` (head/tail dark, loudness ramps) | fades really happen | `validate.py: fade_ok()` on luma curve + loudness at ends; executor for fade chosen in M2 | M2 transition/audio | [ ] |
| `check_titles` (text inside band, on given frames only, vs titles-off render) | overlays/titles land where planned | same technique against Remotion overlays: render with and without, diff only inside expected window/band | M2 composite; M4 | [ ] |
| `check_crossfade`, `crossfade_probe`, G1 | crossfade between clips | crossfade op, executor chosen by evidence (Kinocut transition or ffmpeg `xfade`+`acrossfade`) | M2 transition | [ ] |
| Ducking / PIP / blend (planned G3) | editor controls | `mix_audio` (sidechain) and `overlay_composite` ops | M2 audio/composite | [ ] |
| `check_shotcut` / `gui.py` (editor re-save rewrote blends; preview photographed) | Shotcut-specific bug class | NOT NEEDED (no editor in the loop). Dropped | n/a | [ ] |
| `render_video`, `render_audio` via melt | small proof renders | `extract_frames`, low-res preview via ffmpeg op | M3 | [ ] |
| `doctor` Shotcut/melt line (`cli.py` L160-175) | machine report | doctor reports Kinocut venv + version, ffmpeg path/version/features, Node, Remotion | M5 | [ ] |
| `projects/demo_*` (plan.json, .mlt, checks) | demos of the old backend | convert useful `plan.json` to `examples/*.json` manifests; delete the rest | M5 | [ ] |
| Frame-count-as-integer discipline (mlt.py docstring) | no float timecodes | KEEP as a rule: manifests use integer frames | M3 | [ ] |

### Helpers worth porting OUT of `mlt.py` before it is deleted (own code, reuse is fine)
`_frame` (extract frame), `_psnr`, `_loudness`, `_luma_curve`, `_crop`, `_still_luma`, the negative-control idea in `check_render`, `_sample_clips`.
Port to `cutwright/engine/validate.py` (or `frames.py` if it fits) WITH tests, then delete the originals with the rest of `mlt.py`.

## D. Editing code in Recap Studio: replace only where M2 proved parity

Locations (see `docs/CODEMAP.md` for current line numbers; re-grep, lines drift):

| Function in `recap.py` | What it does | Decide from M2 | Action |
|---|---|---|---|
| `render_video_clip`, `fit_graph` | cut + fit footage to voice length (frame-exact, pad/blur fill, speed) | trim/fit/resize tests | replace by op if passes; else keep as named ffmpeg op |
| `render_image_clip` | still -> clip with motion | fit test | same |
| `fit_audio` | fit voice audio to frames | audio test | same |
| `join_av`, `write_concat_list` | concat clips + music | concat/audio tests | picture concat -> `concat` op (M4 4A, `engine_bridge.concat_picture`); the one continuous audio track stays (M2 gap 3: no op concatenates bare audio files); the music bed -> `mix_audio` (M4 4B) |
| `make_music_bed` | music loop/fade | audio test | KEPT: it PREPARES the bed (loop to length, level, fades); `join_av` hands the file to `mix_audio` (M4 4B) |
| `burn_character`, comic compose | character/comic layers | composite test | only if parity; comics stay "only if asked" |
| `write_premiere_xml`, `write_videopad_project` | exports | none | PRESERVE |
| Remotion render/captions/overlays/scenes | motion graphics | none | PRESERVE (M9 may add HyperFrames data, nothing earlier) |

M4 status (phases 4A + 4B, both 2026-10-30): `recapstudio/_template/engine_bridge.py` is the only bridge
to `cutwright.engine`. 4A moved the picture join to `concat` (Kinocut merge) and made mix tracks declared
op inputs. 4B DELETED the ffmpeg music input/amix arm (a second implementation of `mix_audio`): the program
audio is muxed first and `mix_audio` (Kinocut) mixes the bed under it, stream-copying the video (identical
video packet md5 before/after the mix on a 79 s job). Kept on purpose, each for a stated reason:
`write_concat_list` (audio-only concat lists), the final mux (`overlay_audio` has no
`-movflags +faststart` / `-ar`, and the same pass produces the file `mix_audio` consumes),
`render_video_clip` + `fit_graph` (`fit_to_frames` has no start offset, no loop, no blur fill), `fit_audio`.

Do not leave two implementations of one op. Do not add runtime switches (`legacy`/`new`): use git history as the fallback.

## E. TEST (what must be green, with commands)

```powershell
python -m unittest discover -s tests -t . -v                 # fixtures, M2 equivalence, engine, validators
python -m cutwright doctor
# Regression pack from docs/ROADMAP.md (demo, briefs --demo, video, timeline, scenes, remotion, premiere)
python -m cutwright run <manifest> --json ; python -m cutwright resume <run-dir> --json
```
Every claim in the final LOG is one of TESTED / FAILED / NOT TESTED with the quoted command.
Real-render checks required before M5: a 60-90 s job viewed at 6 frames; audio listened to by the owner (one yes/no question).

## F. DELETE (M5 only, in this order, each its own commit; run the Regression pack after each)

Status 2026-10-30: DONE, but as ONE close-out commit ("M5 close-out: remove obsolete Shotcut MLT backend,
GUI, and tests"). An earlier attempt was stopped early and left the tree half-reverted; committing it whole
was safer than fabricating the per-item commit split. Evidence and quoted output: `LOG.md`, entry
"2026-10-30 - M5 close-out".

1. [x] `cutwright/gui.py` and `cutwright/tools/shotcut_window.ps1` (nothing else imports them except `cli.py`'s `build --checks gui`). Deleted; `cutwright/tools/` is now empty and gone.
2. [x] In `cutwright/cli.py`: remove `from . import mlt` (line ~21), the Shotcut block of `cmd_doctor` (~L160-175), `cmd_build` (~L591-660), the `build` sub-parser (~L717-732), and `build` in the module docstring (L10). Replace the doctor block with Kinocut/ffmpeg lines. Run `python -m cutwright doctor` and `python -m cutwright probe <file>`. Done: `doctor` exit 0 with ffmpeg/ffprobe/Kinocut lines and no editor line; `python -m cutwright build x` -> argparse usage error (the verb no longer exists).
3. [x] `cutwright/mlt.py` (after the helpers in section C were ported and tested). Deleted (2,573 lines). The helpers section C listed were already re-implemented on the engine in M2/M3 (`fit_to_frames`, `concat`, `mix_audio`, `overlay_audio`, `export_h264`), so nothing was ported in M5.
4. [x] `projects/demo_cuts`, `demo_fade`, `demo_cross`, `demo_title` (convert useful `plan.json` first). Deleted (4 projects, 17 tracked files, 1,776 lines). Nothing converted: those plans were shaped around the timeline writer's clip/in/out model, and `docs/schemas/manifest.example.json` already teaches the engine manifest.
5. [x] Local `shotcut\` folder and `bin\_dl\shotcut-win64-*.zip` (owner's disk, ~735 MB; ask once, then delete; they are untracked so no commit). Both already gone on this PC: `Test-Path shotcut` -> False, `Test-Path 'bin\_dl'` -> False. Nothing to delete, nothing committed.
6. [x] `.gitignore`: remove the Shotcut block; keep `/models/`, `/bin/` (whisper), add `.venvs/`, `bench/`, `out/` already ignored. Done: no `/shotcut/`, no `/projects/*/check/`; `/.venvs/` (L67), `/bench/` (L68), `/out/` (L23 and L70), `/models/`, `/bin/` all present.
7. [x] `PROVENANCE.md`: move the Shotcut download/hash section under a heading "Removed 2026-xx (historical)"; keep hashes for history; add Kinocut, FFmpeg, OpenMontage-reference entries. Done: the verbatim section is `docs/legacy/PROVENANCE_removed_editor.md`; `PROVENANCE.md` L115-117 says "Removed 2026-10-30 (M5, historical)" and points at it; the Kinocut paragraph (L89-91) and the FFmpeg `winget Gyan.FFmpeg` entry (L150) are in place.
8. [x] `README.md`: replace the Shotcut-specific Cutwright half (about lines 20-420: build, checks, Shotcut layout, usage) with a short description of the engine and a pointer to `docs/`. Remove "Shotcut portable" setup text. Keep any still-true probe/subs/moments/frames/transcribe usage docs. Done: 495 lines changed down to the engine description + `docs/` pointers; probe/subs/moments/verify/frames/transcribe usage kept.
9. [x] Docs: `docs/TOOLS.md` (build row removed, engine commands added), `docs/CODEMAP.md` (drop mlt.py/gui.py, add engine files), `docs/GOALS.md` (already carries a superseded banner; leave history), `docs/BORROW_notes.md` (superseded banner stays), `.clinerules` (remove `cutwright/mlt.py` from "never read whole" and the Shotcut mention), `HANDOFF.md` (status), `REPORT.md` (historical: leave, add one line "superseded"). Done, with one deviation: `REPORT.md` was MOVED to `docs/legacy/REPORT_shotcut_era.md` (same as `docs/VISION_cutwright_v2.md` -> `docs/legacy/`) instead of keeping a dead file at the root; `docs/TOOLS.md`, `docs/CODEMAP.md` and `docs/GOALS.md` carry the M5 note, `.clinerules/00` + `01` no longer mention the writer, `HANDOFF.md` status is updated.
10. [x] Dependencies: nothing Shotcut-related remains in code, config, `doctor`, tests, SETUP scripts. Check `recapstudio\setup_engines.py` and `.bat` files (expected: none). Done: `git grep -n -i shotcut -- '*.py' '*.bat' '*.js' '*.json' '*.ps1' '*.cmd'` -> no matches (exit 1); `recapstudio/setup_engines.py` installs voice engines and Python extras (edge-tts, kokoro-onnx, pocket, faster-whisper) and nothing else.

Final check (must print nothing):
```powershell
git grep -n -i "shotcut\|melt\.exe\|\.mlt" -- . ":(exclude)LOG.md" ":(exclude)COMMS.md" ":(exclude)docs/legacy" ":(exclude)docs/MIGRATION_CHECKLIST.md" ":(exclude)docs/REFERENCES.md" ":(exclude)docs/ROADMAP.md" ":(exclude)docs/ARCHITECTURE.md" ":(exclude)docs/GOALS.md" ":(exclude)docs/BORROW_notes.md" ":(exclude)PROVENANCE.md" ":(exclude)REPORT.md" ":(exclude)docs/VISION_cutwright_v2.md"
```

## G. Other cleanups tied to the new architecture

- [ ] `cutwright/engine/` exists and is the only place that calls Kinocut or direct editing ffmpeg.
- [ ] No `import kinocut` anywhere under `cutwright/` (grep).
- [ ] No AI-image provider, generator call, or dependency anywhere (`git grep -n -i "stable.diffusion\|dall-e\|midjourney\|flux\|imagen\|text-to-image"` -> only docs that forbid them).
- [ ] No FireRed reference except the exclusion notes (`git grep -n -i firered`).
- [ ] No OpenMontage code: `git grep -n -i openmontage` appears only in docs; no files copied (`PROVENANCE.md` states "ideas only").
- [ ] `docs/CAPABILITY_MATRIX.md` and `docs/evidence/` committed; matrix agrees with `engine/ops.py` (test enforces it).
- [ ] `.gitignore` covers `.venvs/`, `bench/`, `out/`, `production/*/work/`, `*.part`; ZIP excludes secrets, caches, `node_modules`, models, footage.
- [ ] `LOG.md` final entry lists TESTED / FAILED / NOT TESTED honestly.

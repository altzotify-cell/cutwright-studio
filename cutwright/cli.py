"""Cutwright -- agent-grade control of a Desktop video-editing fork.

Steps:
  doctor   What this machine has, and proof the write guard works
  probe    One source file: streams, duration, subtitle tracks -> stdout
  subs     Subtitle gate: find the best subtitle source and prove it is usable
  moments  Transcript -> ranked candidate moments + agent digest
  verify   Grade picks against frames: verified / retimed / replaced
  transcribe  whisper.cpp fallback: produce a transcript, then gate it

Engine verbs (M3 -- every decision lives in cutwright/engine/, these only parse and print):
  tools    list|describe|envelope   what the engine can do, and what is installed
  validate Pre-render check of a manifest: plan, params, budget, asset provenance
  run      Execute a manifest (--dry-run, --only); cached steps are skipped on a re-run
  resume   Continue a run from its checkpoint
  status   What a run folder's checkpoint says, step by step
  approve  Write the approval file that opens a gate in a run folder
  blueprint generate|compile   Design the beats from a brief, compile them to a manifest (M8)

Recap Studio bridge (M6 -- logic in cutwright/recap.py, refusals included):
  recap    projects | new <name> | status --project X | <step> --project X     (all --json)
           `--force`, `init` and `collect` are refused unless the caller passes both
           --i-know-this-destroys-work and --comms <COMMS id>.

The legacy steps are dry by default. The engine verbs write only inside this folder, and only
through cutwright/guard.py.
"""
import argparse
import json
import os
import shutil
import sys

from . import guard
from . import frames
from . import moments
from . import probe
from . import recap as bridge
from . import subs
from . import transcribe
from .engine import (blueprint, checkpoint, gates, manifest, ops, registry, report,
                     scenecraft, validate)
from .engine.executors import kinocut as kino

VERSION = "0.1.0"


def out_dir_for(video, override=None):
    if override:
        return guard.ensure_dir(os.path.abspath(override))
    stem = os.path.splitext(os.path.basename(video))[0]
    return guard.ensure_dir(os.path.join(guard.OUT, stem))


def print_table(rows, cols):
    """rows = [dict]; cols = [(key, header, width)] -- fixed width, ASCII."""
    if not rows:
        return
    head = "  ".join(str(h).ljust(w) for _k, h, w in cols)
    print("  " + head)
    print("  " + "-" * len(head))
    for row in rows:
        cells = []
        for key, _h, width in cols:
            value = str(row.get(key, ""))
            cells.append(value[:width].ljust(width))
        print("  " + "  ".join(cells))


def rule(char="-", width=74):
    print(char * width)


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


def _doctor_recap():
    """Report the merged Recap Studio engine (recapstudio/): files, Node, Remotion, Python modules."""
    import importlib.util
    print("")
    print("Recap Studio engine (recapstudio/):")
    recap = guard.RECAP
    must = ["studio.py", os.path.join("_template", "recap.py"),
            os.path.join("_template", "timeline.py"), os.path.join("_template", "scenes.py"),
            os.path.join("_template", "authoring.py"), os.path.join("remotion", "package.json"),
            os.path.join("remotion", "kit", "CONTRACT.md")]
    missing = [m for m in must if not os.path.isfile(os.path.join(recap, m))]
    if missing:
        print("  [!] engine files missing: %s" % ", ".join(missing))
    else:
        print("  [+] engine files present (%d files)" % _count_files(recap))
    for tool in ("node", "npm"):
        path = shutil.which(tool)
        print("  [%s] %-6s %s" % ("+" if path else " ", tool,
                                  path or "not found (Remotion rendering needs Node 18+)"))
    nm = os.path.join(recap, "remotion", "node_modules", "remotion")
    print("  [%s] remotion npm packages %s" % (
        "+" if os.path.isdir(nm) else " ",
        "installed" if os.path.isdir(nm) else "not installed: cd recapstudio/remotion && npm install"))
    for mod, why in (("edge_tts", "Edge-TTS voice (default)"), ("PIL", "Pillow: stills, comics, characters"),
                     ("faster_whisper", "word timings fallback"), ("requests", "downloads")):
        ok = importlib.util.find_spec(mod) is not None
        print("  [%s] python %-15s %s" % ("+" if ok else " ", mod, why))
    n = 0
    pdir = os.path.join(recap, "Projects")
    if os.path.isdir(pdir):
        n = len([d for d in os.listdir(pdir) if os.path.isdir(os.path.join(pdir, d))])
    print("      [i] recap projects: %d in recapstudio/Projects" % n)


def cmd_doctor(args):
    rule("=")
    print("CUTWRIGHT %s  doctor" % VERSION)
    rule("=")
    print("root        %s" % guard.ROOT)
    print("python      %s" % sys.version.split()[0])

    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        if not path:
            print("[!] %-9s NOT FOUND on PATH" % tool)
            continue
        r = probe.run([tool, "-version"])
        first = (r.stdout or "").splitlines()[0] if r.stdout else "?"
        print("[+] %-9s %s" % (tool, path))
        print("             %s" % first[:110])

    free = shutil.disk_usage(guard.ROOT).free / (1024.0 ** 3)
    print("disk free   %.1f GB on the fork's drive" % free)

    print("")
    print("originals (read-only, never written to):")
    for original in guard.ORIGINALS:
        print("  %s  %s" % ("present" if os.path.isdir(original) else "MISSING",
                            original))
    print("vendored   %d file(s), %.2f MB" %
          (_count_files(guard.VENDOR),
           _tree_size(guard.VENDOR) / (1024.0 * 1024.0)))

    _doctor_recap()

    print("")
    print("write guard self-test:")
    tests = []
    try:
        guard.assert_writable(os.path.join(guard.OUT, "_probe.tmp"))
        tests.append(("inside the fork", True))
    except guard.GuardError:
        tests.append(("inside the fork", False))
    for original in guard.ORIGINALS:
        try:
            guard.assert_writable(os.path.join(original, "_probe.tmp"))
            tests.append(("refuses %s" % os.path.basename(original), False))
        except guard.GuardError:
            tests.append(("refuses %s" % os.path.basename(original), True))
    try:
        guard.assert_writable(r"C:\Windows\_probe.tmp")
        tests.append(("refuses outside the fork", False))
    except guard.GuardError:
        tests.append(("refuses outside the fork", True))
    for label, ok in tests:
        print("  [%s] %s" % ("+" if ok else "!", label))

    print("")
    print("transcription / editing engines:")
    binary = transcribe.find_binary()
    model = transcribe.find_model()
    if binary:
        print("  [+] %-12s %s" % ("whisper.cpp", transcribe.version_of(binary)))
        print("                 %s" % guard.rel(binary))
    else:
        print("  [ ] %-12s %-32s %s" % ("whisper.cpp", "offline transcription fallback",
                                        "not installed"))
    if model:
        print("  [+] %-12s %s, %.0f MB" % ("model", os.path.basename(model),
                                           os.path.getsize(model) / (1024.0 * 1024.0)))
    else:
        print("  [ ] %-12s %-32s %s" % ("model", "ggml weights for whisper.cpp",
                                        "not installed"))
    if kino.available():
        exe = kino.kino_exe()
        r = probe.run([exe, "--version"])
        lines = (r.stdout or "").strip().splitlines()
        print("  [+] %-12s %s" % ("Kinocut", "%s (editing toolkit, called by subprocess)"
                                  % (lines[0] if lines else "installed")))
        print("                 %s" % guard.rel(exe))
    else:
        print("  [ ] %-12s %-32s %s" % ("Kinocut", "editing toolkit",
                                        "not installed: see docs/KINOCUT_FINDINGS.md 1"))
    if binary and model:
        print("      [i] transcribe needs no further setup")
    else:
        print("      [i] run: python -m cutwright transcribe <video>   for the "
              "exact steps")
    return 0 if all(ok for _l, ok in tests) else 3


def _count_files(folder):
    return sum(len(files) for _d, _s, files in os.walk(folder))


def _tree_size(folder):
    total = 0
    for dirpath, _dirs, files in os.walk(folder):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                pass
    return total


# ---------------------------------------------------------------------------
# probe
# ---------------------------------------------------------------------------
def cmd_probe(args):
    video = os.path.abspath(args.video)
    if not os.path.isfile(video):
        print("[!] no such file: %s" % video)
        return 3
    info = probe.media_info(video)
    print("[i] %s" % info["name"])
    print("    duration  %s  (%.3fs)" % (moments.fmt_mmss(info["duration"]),
                                         info["duration"]))
    print("    picture   %dx%d @ %.3g fps, %s" %
          (info["width"], info["height"], info["fps"], info["video_codec"] or "?"))
    print("    size      %.1f MB   format %s" %
          (info["size"] / (1024.0 * 1024.0), info["format"]))
    print("    audio     %s" % (", ".join(
        "%s/%dch/%dHz/%s" % (a["codec"], a["channels"], a["sample_rate"], a["language"])
        for a in info["audio"]) or "none"))
    if not info["subs"]:
        print("    subs      none")
    for s in info["subs"]:
        kind = "text" if s["text"] else ("PICTURE" if s["picture"] else "?")
        print("    subs      #%d %-18s %-4s %s%s" %
              (s["index"], s["codec"], s["language"], kind,
               " (forced)" if s["forced"] else ""))
    return 0


# ---------------------------------------------------------------------------
# the gate, for humans
# ---------------------------------------------------------------------------
def _print_gate(report):
    rule()
    print("SUBTITLE GATE")
    rule()
    if not report["ladder"]:
        print("  no candidates found")
    for row in report["ladder"]:
        mark = "[+]" if row.get("ok") else "[!]"
        name = os.path.basename(row.get("path", "?"))
        print("  %s rung %d  %-9s %s" %
              (mark, row.get("rank", 0), row.get("origin", "?"), name))
        if row.get("error"):
            print("       error    %s" % row["error"])
            continue
        if "metrics" in row:
            m = row["metrics"]
            checks = row.get("checks") or {}
            ok = sum(1 for v in checks.values() if v == "ok")
            print("       format   %s, decoded as %s" % (row["format"], row["encoding"]))
            print("       metrics  %d cues, %.1f cues/min, mean %.2fs, %.0f wpm, "
                  "%d words" % (m["cues"], m["cues_per_min"], m["mean_dur"],
                                m["wpm"], m["words"]))
            print("       checks   %d of %d passed" % (ok, len(checks)))
            if row.get("language_detail") and checks.get("language") == "ok":
                print("       language %s" % row["language_detail"])
            dropped = row.get("dropped") or {}
            if dropped.get("drawings") or dropped.get("styles"):
                print("       cleaned  %d drawing cue(s), %d non-dialogue cue(s) "
                      "removed of %d before checks"
                      % (dropped.get("drawings", 0),
                         sum((dropped.get("styles") or {}).values()),
                         dropped.get("input", 0)))
        for fail in row.get("fails") or []:
            print("       FAIL     %s" % fail)
        for warn in row.get("warns") or []:
            print("       warn     %s" % warn)
        for ex in (row.get("examples") or [])[:2]:
            stamp = ("%.1fs" % ex["start"]) if "start" in ex else ("%.1fs" % ex.get("at", 0))
            print("       e.g.     %s  %s  %s" % (stamp, ex.get("why", ""),
                                                  (ex.get("text") or "")[:60]))
    print("")
    print("  status   %s" % report["status"].upper())
    print("  note     %s" % report["note"])
    rule()


def _run_gate_for(args, video, info, out):
    return subs.run_gate(video, info, args.subs, args.expect,
                         os.path.join(out, "subs_extracted"), guard)


def cmd_subs(args):
    video = os.path.abspath(args.video)
    if not os.path.isfile(video):
        print("[!] no such file: %s" % video)
        return 3
    info = probe.media_info(video)
    out = out_dir_for(video, args.out)
    report = _run_gate_for(args, video, info, out)
    report["video"] = {"path": video, "name": info["name"],
                       "duration": info["duration"]}
    path = guard.write_json(os.path.join(out, "subs_report.json"), report)
    _print_gate(report)
    print("[i] wrote %s" % guard.rel(path))
    if report["status"] == "verified":
        return 0
    print("[!] no trustworthy transcript. Do not proceed to moments.")
    print("    Either transcribe the audio, or supply a subtitle file with --subs.")
    return 2


# ---------------------------------------------------------------------------
# moments
# ---------------------------------------------------------------------------
def cmd_moments(args):
    video = os.path.abspath(args.video)
    if not os.path.isfile(video):
        print("[!] no such file: %s" % video)
        return 3

    info = probe.media_info(video)
    out = out_dir_for(video, args.out)
    gate = _run_gate_for(args, video, info, out)
    guard.write_json(os.path.join(out, "subs_report.json"),
                     dict(gate, video={"path": video, "name": info["name"],
                                       "duration": info["duration"]}))

    if gate["status"] != "verified":
        _print_gate(gate)
        print("[!] refusing to build moments from an unverified transcript.")
        print("    The gate exists so a wrong or garbage subtitle file cannot quietly")
        print("    become the spine of your edit.")
        return 2

    chosen = gate["chosen"]
    loaded = subs.load_cues(chosen["path"])
    transcript = {"origin": chosen["origin"], "path": chosen["path"],
                  "format": loaded["format"], "encoding": loaded["encoding"],
                  "cues": len(loaded["cues"]), "bytes": loaded["bytes"],
                  "language": chosen.get("language", "unknown")}

    doc = moments.build_doc(info, gate, transcript, loaded["cues"],
                            args.top, args.acts, args.min_gap)
    json_path = guard.write_json(os.path.join(out, "moments.json"), doc)
    digest_path = guard.write_text(os.path.join(out, "moments_digest.txt"),
                                   moments.digest(doc))

    rule()
    print("MOMENTS / %s" % info["name"])
    rule()
    print("  duration    %s   %dx%d%s" % (
        moments.fmt_mmss(info["duration"]), info["width"], info["height"],
        "  vertical" if info["height"] > info["width"] else ""))
    print("  transcript  %s from %s (%s), %d cues" % (
        loaded["format"], chosen["origin"], loaded["encoding"],
        len(loaded["cues"])))
    print("  gate        %s" % gate["note"])
    print("  beats       %d -> %d candidates" % (doc["beats"],
                                                len(doc["candidates"])))
    print("")
    print_table(moments.digest_table(doc),
                [("rank", "#", 3), ("at", "starts", 8), ("len", "len", 6),
                 ("score", "score", 6), ("hits", "what fires", 26),
                 ("quote", "what is said", 60)])
    print("")
    print("[i] wrote %s" % guard.rel(json_path))
    print("[i] wrote %s" % guard.rel(digest_path))
    rule()
    return 0


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------
def cmd_verify(args):
    video = os.path.abspath(args.video)
    if not os.path.isfile(video):
        print("[!] no such file: %s" % video)
        return 3

    info = probe.media_info(video)
    out = out_dir_for(video, args.out)
    moments_path = (os.path.abspath(args.moments) if args.moments
                    else os.path.join(out, "moments.json"))
    doc = guard.read_json(moments_path)
    if not doc or not doc.get("candidates"):
        print("[!] no moments at %s" % guard.rel(moments_path))
        print("    run: cutwright moments \"%s\"" % video)
        return 2

    claims_path = (os.path.abspath(args.claims) if args.claims
                   else os.path.join(out, "claims.json"))
    claims = frames.load_claims(claims_path)
    missing = frames.unclaimed(doc, claims)
    if missing:
        if not os.path.isfile(claims_path):
            frames.template(doc, claims, claims_path)
        rule()
        print("VERIFY / %s" % info["name"])
        rule()
        print("  %d of %d pick(s) have no expected claim -- refusing to grade them."
              % (len(missing), len(doc["candidates"])))
        print("")
        for c in missing:
            print("  %-6s %-8s %s" % (c["id"], moments.fmt_mmss(c["t_start"]),
                                      " ".join(c["quote"].split())[:62]))
        print("")
        print("  A pick is worth exactly what its claim is worth. Fill in")
        print("    %s" % guard.rel(claims_path))
        print("  then run verify again. Claims come from the transcript; the")
        print("  frames decide whether the claim survives.")
        rule()
        return 2

    gate = _run_gate_for(args, video, info, out)
    if gate["status"] != "verified":
        _print_gate(gate)
        print("[!] refusing to verify against an unverified transcript.")
        return 2
    cues = subs.load_cues(gate["chosen"]["path"])["cues"]

    review_path = (os.path.abspath(args.review) if args.review
                   else os.path.join(out, "review.json"))
    review = frames.load_review(review_path)

    print("[i] grading %d pick(s) against %s ..."
          % (len(doc["candidates"]), info["name"]))
    report = frames.run_verify(video, info, doc, claims, cues, out,
                               write_back=True, review=review)

    json_path = guard.write_json(os.path.join(out, "frames.json"), report)
    digest_path = guard.write_text(os.path.join(out, "verify_digest.txt"),
                                   frames.digest(report))
    if args.write_back:
        guard.write_json(moments_path, doc)

    s = report["summary"]
    rule()
    print("VERIFY / %s" % info["name"])
    rule()
    print("  duration    %s   %dx%d" % (moments.fmt_mmss(info["duration"]),
                                        info["width"], info["height"]))
    print("  frames      %s" % report["frame_dir"])
    print("  graded      %s" % ", ".join("%d %s" % (s[k], k) for k in frames.STATUSES))
    if report.get("reviewed"):
        print("  reviewed    %d of %d pick(s): the agent looked at the frames"
              % (report["reviewed"], len(report["candidates"])))
    print("")
    print_table(frames.digest_table(report),
                [("rank", "#", 3), ("id", "id", 6), ("status", "status", 10),
                 ("at", "starts", 8), ("luma", "luma", 12),
                 ("warns", "warn", 4), ("why", "why", 40)])
    print("")
    warned = [r for r in report["candidates"] if r.get("warns")]
    if warned:
        print("  warnings -- kept as warnings, none of these changes a grade:")
        for r in warned:
            for warn in r["warns"]:
                print("    %-6s %s" % (r["id"], warn))
        print("")
    if s["retimed"]:
        print("  %d pick(s) retimed: the picture is there, the cut is not. New"
              % s["retimed"])
        print("  in-points are proposed above, not applied.")
    if s["replaced"]:
        print("  [!] %d pick(s) replaced: what is on screen is not what the claim"
              % s["replaced"])
        print("      said. Drop them or re-describe them -- do not ship them.")
    if s["unverified"]:
        print("  [!] %d pick(s) still unverified." % s["unverified"])
    print("")
    print("[i] wrote %s" % guard.rel(json_path))
    print("[i] wrote %s" % guard.rel(digest_path))
    if args.write_back:
        print("[i] wrote %s  (statuses patched back)" % guard.rel(moments_path))
    rule()
    return 2 if (s["unverified"] or s["replaced"]) else 0


# ---------------------------------------------------------------------------
# transcribe
# ---------------------------------------------------------------------------
def cmd_transcribe(args):
    video = os.path.abspath(args.video)
    if not os.path.isfile(video):
        print("[!] no such file: %s" % video)
        return 3
    info = probe.media_info(video)
    out = out_dir_for(video, args.out)

    rule("=")
    print("CUTWRIGHT TRANSCRIBE / %s" % info["name"])
    rule("=")
    if not info["audio"]:
        print("[!] this file has no audio stream -- nothing to transcribe")
        return 3
    index, stream = transcribe.choose_audio(info, args.language)
    print("audio      stream %d (%s, %s, %dch) of %d"
          % (index, stream.get("language", "und"), stream.get("codec", "?"),
             stream.get("channels", 0), len(info["audio"])))
    print("engine     whisper.cpp + %s, language %s"
          % (os.path.basename(args.model) if args.model else transcribe.DEFAULT_MODEL,
             args.language))
    cached = None
    if not args.fresh:
        cached = transcribe.cached_run(
            out, transcribe.cache_key(video, info, args.language,
                                      transcribe.find_binary(args.whisper),
                                      transcribe.find_model(args.model)))
    if cached:
        print("[i] a transcript for these exact inputs already exists (%s) -- "
              "reusing it, no model run." % (cached.get("ran_at") or "earlier"))
    else:
        print("[i] this is the slow step: roughly a quarter of real time on 8 CPU "
              "threads.")
    print("[i] nothing is written outside this fork.")
    print("")

    report = transcribe.run_transcribe(
        video, info, out, language=args.language, expect=args.expect,
        binary=args.whisper, model=args.model, threads=args.threads,
        reference=args.subs, fresh=args.fresh)

    if report["status"] == "blocked":
        print("[!] cannot transcribe yet:")
        for problem in report["problems"]:
            print("    - %s" % problem)
        print("")
        for line in report.get("hints") or []:
            print("  " + line)
        rule()
        return 3
    if report["status"] == "error":
        print("[!] %s" % report["note"])
        rule()
        return 3

    json_path = guard.write_json(os.path.join(out, "transcript.json"), report)
    digest_path = guard.write_text(os.path.join(out, "transcript_digest.txt"),
                                   transcribe.digest(report))

    counts = report["counts"]
    m = report["metrics"]
    if report["engine"].get("cached"):
        print("whisper    reused %d cached segment(s); no model run (original pass "
              "%s, %.1fs)" % (counts["segments"],
                              report["engine"].get("ran_at") or "earlier",
                              report["engine"].get("wall_s") or 0.0))
    else:
        print("whisper    %d segment(s) in %.1fs, %d thread(s)"
              % (counts["segments"], report["engine"]["wall_s"],
                 report["engine"]["threads"]))
    print("cues       %d kept, %d dropped as non-speech"
          % (counts["kept"], counts["dropped_nonspeech"]))
    print("metrics    %.1f cues/min  mean %.2fs  %.0f wpm  %d words  covers %.0f%%"
          % (m["cues_per_min"], m["mean_dur"], m["wpm"], m["words"],
             m["coverage"] * 100))
    checks = report["checks"]
    print("gate       %d of %d check(s) passed"
          % (sum(1 for value in checks.values() if value == "ok"), len(checks)))
    for line in report["fails"]:
        print("  FAIL     %s" % line)
    for line in report["warns"]:
        print("  warn     %s" % line)
    for check in report["signals"]["checks"]:
        print("  %-8s %s" % ("signal" if check["ok"] else "signal!",
                             "%s: %s" % (check["name"], check["detail"])))
    ref = report.get("reference")
    if ref and not ref.get("error"):
        print("reference  %d of %d line(s) found in %s (%.0f%% match)"
              % (ref["matched"], ref["cues"], os.path.basename(ref["path"]),
                 ref["rate"] * 100))
        if ref.get("offset_s") is not None:
            print("           offset %+.1fs agreed by %d line(s)"
                  % (ref["offset_s"], ref["offset_support"]))
    elif ref and ref.get("error"):
        print("reference  could not be read: %s" % ref["error"])
    print("")
    for cue in report["cues_preview"][:6]:
        print("  %7.2f  %s" % (cue["start"], cue["text"][:64]))
    print("")
    print("  status   %s" % report["status"].upper())
    print("  note     %s" % report["note"])
    rule()
    print("[i] wrote %s" % guard.rel(json_path))
    print("[i] wrote %s" % guard.rel(digest_path))
    print("[i] srt     %s  (checked copy; raw whisper output kept beside it)"
          % report["artifacts"]["srt"])
    if report["ok"]:
        print("[i] next: python -m cutwright moments \"%s\" --subs \"%s\""
              % (video, os.path.join(out, "transcript.srt")))
        return 0
    print("[!] the gate did not pass. Do not build a subtitle track from this.")
    print("    Re-run with --fresh, a bigger model, or supply a real subtitle file.")
    return 2


# ---------------------------------------------------------------------------
# engine verbs: tools, validate, run, resume, status, approve  (M3)
#
# Thin on purpose: every decision lives in `cutwright/engine/` (ops, registry, manifest,
# checkpoint, gates, validate, report). These functions only parse, call and print, so the same
# behaviour is reachable from a test, an agent, or a human at a prompt.
# ---------------------------------------------------------------------------
def _json_mode(args):
    return bool(getattr(args, "json", False))


def _dump(data):
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _reject(args, kind, exc):
    """One rejected request, the same shape with or without --json. Returns the exit code 2."""
    data = {"ok": False, "error": kind, "code": getattr(exc, "code", "error"),
            "message": str(exc), "suggested": getattr(exc, "suggested", "")}
    if hasattr(exc, "to_dict"):
        data["details"] = exc.to_dict()
    if _json_mode(args):
        _dump(data)
    else:
        print("[!] %s" % str(exc))
        if data["suggested"]:
            print("    %s" % data["suggested"])
    return 2


def _mark(status):
    return {"done": "[+]", "skipped": "[=]", "failed": "[!]", "would_run": "[>]"}.get(status, "[ ]")


def _print_tool_list(data):
    rule()
    print("ENGINE OPS  %d" % data["count"])
    rule()
    if data["ops"]:
        print_table([{"name": row["name"], "stage": row["stage"], "executor": row["executor"],
                      "what": row["description"]} for row in data["ops"]],
                    [("name", "op", 20), ("stage", "stage", 8), ("executor", "executor", 8),
                     ("what", "does", 34)])
        print("")
    print("  per stage  %s" % "  ".join("%s:%d" % (name, count)
                                        for name, count in data["stages"].items()))
    for name, row in sorted(data["installed"].items()):
        print("  [%s] %-8s %s" % ("+" if row["ok"] else " ",
                                  name, row.get("version") or row.get("install", "")))
    rule()


def _print_op(data):
    rule()
    print("%s  (%s, executor %s)" % (data["name"], data["stage"], data["executor"]))
    rule()
    print("  does      %s" % data["description"])
    print("  inputs    %s" % ", ".join(data["inputs"]))
    print("  outputs   %s" % ", ".join(data["outputs"]))
    print("  why       %s" % data["executor_reason"])
    evidence = data.get("evidence_status") or {}
    print("  evidence  %s  %s" % (data["evidence"],
                                  "ok" if evidence.get("ok") else evidence.get("reason", "")))
    ready = data.get("executor_ready") or {}
    print("  installed %s" % ("yes" if ready.get("ok") else "NO -> %s" % ready.get("reason", "")))
    if data["params"]:
        print("")
        print_table([{"name": key, "type": param["type"],
                      "req": "yes" if param["required"] else "",
                      "def": "" if "default" not in param else str(param["default"]),
                      "doc": param["doc"]}
                     for key, param in data["params"].items()],
                    [("name", "param", 14), ("type", "type", 6), ("req", "req", 3),
                     ("def", "default", 8), ("doc", "what", 34)])
    rule()


def _print_envelope(data):
    rule()
    print("ENVELOPE %s  %d op(s) of %d + %d command(s)%s"
          % (data["stage"], data["returned"], data["count"], len(data["commands"]),
             "" if not data["truncated"] else "  (truncated)"))
    rule()
    print("  %s" % data["why"])
    print("")
    for row in data["ops"]:
        print("  op      %-16s %s" % (row["name"], row["executor"]))
        print("          %s" % row["description"])
        if row["required"]:
            print("          needs %s" % ", ".join(row["required"]))
    for row in data["commands"]:
        print("  command %-16s %s" % (row["name"], row["description"]))
        print("          %s" % row["usage"])
    print("")
    print("  run      %s" % data["how_to_run"])
    print("  installed %s" % "  ".join("%s:%s" % (name, "yes" if ok else "NO")
                                       for name, ok in data["installed"].items()))
    rule()


def cmd_tools(args):
    action = getattr(args, "action", "") or "list"
    try:
        if action == "describe":
            data = registry.describe(args.op)
            data["ok"] = True
            if _json_mode(args):
                _dump(data)
            else:
                _print_op(data)
            return 0
        if action == "envelope":
            data = registry.envelope(args.stage)
            data["ok"] = True
            if _json_mode(args):
                _dump(data)
            else:
                _print_envelope(data)
            return 0
        rows = registry.list_ops(getattr(args, "stage", None))
        data = registry.tools_report()
        data.update({"ok": True, "stage": getattr(args, "stage", None) or "",
                     "ops": rows, "count": len(rows)})
    except registry.RegistryError as exc:
        return _reject(args, "registry", exc)
    if _json_mode(args):
        _dump(data)
    else:
        _print_tool_list(data)
    return 0


def cmd_scene(args):
    """The authoring loop's two cheap halves: the brief before writing, the check after (M7)."""
    action = getattr(args, "action", "") or "brief"
    handles = list(getattr(args, "handle", None) or [])
    try:
        if action == "check":
            data = scenecraft.check(args.file, handles)
            data["files"] = list(args.file)
            if _json_mode(args):
                _dump(data)
            else:
                _print_scene_check(data)
            return 0 if data["ok"] else 2
        data = scenecraft.brief(handles[0] if handles else "",
                                getattr(args, "composition", "") or "",
                                getattr(args, "duration", 192) or 192)
        data["ok"] = True
        if _json_mode(args):
            _dump(data)
        else:
            _print_scene_brief(data)
        return 0
    except scenecraft.SceneError as exc:
        return _reject(args, "scene", exc)


def _print_scene_brief(data):
    rule()
    print("SCENE BRIEF   %d frames   imports: %s" % (data["duration_frames"],
                                                     ", ".join(data["imports"])))
    rule()
    for row in data["primitives"]:
        print("  %-13s %-18s %s" % (row["name"], row["file"], row["job"]))
        print("      props  %s" % ", ".join(row["props"]))
    print("  handle       %s" % data["handles"]["rule"])
    print("  composition  %s" % data["composition"]["rule"])
    print("  stills       %s" % ", ".join("%s@%d" % (row["look"], row["frame"])
                                          for row in data["stills"]))
    print("  critic       %s" % "; ".join(row["check"] for row in data["review"]))
    print("  revisions    at most %d, then mark it needs_owner (%s)"
          % (data["max_revisions"], data["standard"]))
    rule()


def _print_scene_check(data):
    rule()
    print("SCENE CHECK   %d error(s), %d warning(s), %ss"
          % (data["errors"], data["warnings"], data["seconds"]))
    rule()
    for name, row in sorted((data.get("scenes") or {}).items()):
        row = row or {}
        print("  %-16s cost=%-6s default=%s" % (name, row.get("cost"), row.get("hasDefault")))
        for kind in ("errors", "warnings"):
            for item in row.get(kind) or []:
                print("    %-8s line %-5s %s" % (kind[:-1], item.get("line", "?"),
                                                 item.get("message", "")))
    rule()


def _print_plan(data):
    rule()
    print("PLAN  %s   %d step(s), $%s" % (data.get("run_dir", ""), data.get("steps", 0),
                                          data.get("cost_usd", 0)))
    rule()
    for row in (data.get("provenance") or {}).get("assets") or []:
        print("  asset  %-12s %-14s %s" % (row["id"], row["origin"] or "(no origin)",
                                          "ok" if row["ok"] else "; ".join(row["problems"])))
    for row in data.get("errors") or []:
        print("  ERROR  %s%s | %s" % ("%s " % row["step"] if row["step"] else "",
                                      row["code"], row["message"]))
        if row.get("suggested"):
            print("         -> %s" % row["suggested"])
    for row in data.get("warnings") or []:
        print("  warn   %s%s | %s" % ("%s " % row["step"] if row["step"] else "",
                                      row["code"], row["message"]))
    print("")
    print("  status %s" % ("OK - this plan can run" if data["ok"] else "REJECTED"))
    rule()


def cmd_validate(args):
    """Pre-render check. Provenance is REPORTED here; `manifest.validate` owns the verdict."""
    try:
        document = manifest.load(args.manifest)
    except manifest.ManifestError as exc:
        return _reject(args, "manifest", exc)
    data = manifest.validate(document, manifest_path=args.manifest)
    data["provenance"] = validate.provenance(document)
    if _json_mode(args):
        _dump(data)
    else:
        _print_plan(data)
    return 0 if data["ok"] else 1


def _check_line(check):
    """One validation row as a line: pass / FAIL / not measured yet, with the number when there is one."""
    status = check.get("status") or "not_run"
    mark = {"pass": "ok  ", "fail": "FAIL", "not_run": " -- "}.get(status, " ?  ")
    detail = check.get("message") or ""
    if not detail and check.get("measured") is not None:
        detail = "measured %s" % (check.get("measured"),)
    return "       %s %-20s %s" % (mark, check.get("check"), detail)


def _print_run(data):
    rule()
    print("RUN %s   %s%s" % (data["run_id"], data["run_dir"],
                             "   (dry run: nothing written)" if data["dry_run"] else ""))
    rule()
    for row in data["steps"]:
        print("  %s %-12s %-9s %-9s %s" % (_mark(row["status"]), row["id"], row["op"],
                                           row["status"], row.get("reason") or ""))
        for check in row.get("validation") or []:
            print(_check_line(check))
    if data.get("stopped"):
        print("  stopped    %s" % data["stopped"])
    cursor = data.get("cursor") or {}
    print("  cursor     next %s, %d of %d done" % (cursor.get("next") or "(none)",
                                                   len(cursor.get("done") or []),
                                                   cursor.get("total") or 0))
    for key in ("checkpoint", "production_report"):
        if data.get(key):
            print("  %-10s %s" % (key, data[key]))
    rule()


def cmd_blueprint(args):
    """The production blueprint (M8): design the beats from a brief, then compile them to a manifest."""
    action = getattr(args, "action", "") or "generate"
    try:
        if action == "compile":
            data = blueprint.compile(args.blueprint, getattr(args, "out", "") or "")
            data["blueprint"] = args.blueprint
            if _json_mode(args):
                _dump(data)
            else:
                _print_compiled(data)
            return 0
        brief = guard.read_json(args.brief, default=None)
        if not isinstance(brief, dict):
            raise blueprint.BlueprintError("not a brief: %s" % args.brief, code="not_json",
                                           suggested="a brief is a JSON object "
                                                     "(title, project, assets, beats)")
        document, path = blueprint.generate(
            brief, out=getattr(args, "out", "") or "",
            narration=getattr(args, "narration", "") or "",
            tts=False if getattr(args, "no_tts", False) else None)
    except blueprint.BlueprintError as exc:
        return _reject(args, "blueprint", exc)
    data = {"ok": True, "blueprint": guard.rel(path), "title": document["title"],
            "slug": document["slug"], "fps": document["fps"], "size": document["size"],
            "narration": document["narration"], "beats": document["beats"],
            "assets": document["assets"], "audio": document["audio"],
            "deliver": document["deliver"]}
    if _json_mode(args):
        _dump(data)
    else:
        _print_blueprint(data)
    return 0


def _print_blueprint(data):
    rule()
    print("BLUEPRINT  %s  (%s)" % (data["title"] or data["slug"], data["blueprint"]))
    rule()
    narration = data["narration"]
    print("  narration  %.2fs, %d words, %s, timing %s"
          % (narration["seconds"], narration["words"], narration["engine"], narration["timing"]))
    for order, row in enumerate(data["beats"], start=1):
        print("  beat %-2d %-12s %-16s f%04d-%04d  %5.2fs  %s"
              % (order, row["id"], row["shot"], row["starts_at"],
                 row["starts_at"] + row["frames"] - 1, row["seconds"], row["composition"]))
        print("          %s" % row["say"])
        if row.get("assets"):
            print("          assets %s" % ", ".join(row["assets"]))
    for row in data["assets"]:
        print("  asset      %-12s %-12s %s" % (row["id"], row["origin"], row["path"]))
    print("  audio      music %s   duck %s" % (data["audio"]["music"] or "(none)",
                                               data["audio"]["duck"] or "(defaults)"))
    print("  deliver    %s" % data["deliver"]["output"])
    rule()


def _print_compiled(data):
    rule()
    print("MANIFEST   %s   %d steps, %d frames, %.2fs"
          % (data["manifest"], len(data["steps"]), data["frames"], data["seconds"]))
    rule()
    for row in data["beats"]:
        print("  %-12s %-16s f%04d +%d" % (row["id"], row["shot"], row["starts_at"],
                                           row["frames"]))
    print("  steps      %s" % " -> ".join(data["steps"]))
    print("  output     %s" % data["output"])
    print("  next       python -m cutwright validate %s --json" % data["manifest"])
    rule()


def cmd_run(args):
    dry = bool(getattr(args, "dry_run", False))
    try:
        plan = manifest.load_plan(args.manifest, versions=manifest.tool_versions(),
                                  strict_files=not dry)
    except manifest.ManifestError as exc:
        return _reject(args, "manifest", exc)
    try:
        data = manifest.run(plan, only=getattr(args, "only", None), dry_run=dry)
    except (checkpoint.CheckpointError, guard.GuardError) as exc:
        return _reject(args, "run", exc)
    if _json_mode(args):
        _dump(data)
    else:
        _print_run(data)
    return 0 if data["ok"] else 1


def cmd_resume(args):
    folder = os.path.abspath(args.run_dir)
    if not os.path.isdir(folder):
        print("[!] no such run folder: %s" % folder)
        return 3
    try:
        data = manifest.resume(folder, versions=manifest.tool_versions())
    except (manifest.ManifestError, checkpoint.CheckpointError, guard.GuardError) as exc:
        return _reject(args, "resume", exc)
    if _json_mode(args):
        _dump(data)
    else:
        _print_run(data)
    return 0 if data["ok"] else 1


def _print_status(data):
    rule()
    print("STATUS %s   %s" % (data["run_id"], data["run_dir"]))
    rule()
    for row in data["steps"]:
        note = row.get("stale") and "STALE: %s" % row["stale"] or row.get("reason") or ""
        print("  %s %-12s %-9s %-8s %s" % (_mark(row["status"]), row["id"], row["op"],
                                           row["status"], note))
        digests = (data.get("output_digests") or {}).get(row["id"]) or []
        if digests:
            print("       digests %s" % ", ".join(digests))
    cursor = data.get("cursor") or {}
    print("  cursor     next %s, %d of %d done" % (cursor.get("next") or "(none)",
                                                   len(cursor.get("done") or []),
                                                   cursor.get("total") or 0))
    print("  report     %s" % ("production_report.json present" if data.get("production_report")
                               else "no production_report.json yet"))
    rule()


def cmd_status(args):
    folder = os.path.abspath(args.run_dir)
    if not os.path.isdir(folder):
        print("[!] no such run folder: %s" % folder)
        return 3
    try:
        data = manifest.status(folder)
        state = checkpoint.load(folder)
    except checkpoint.CheckpointError as exc:
        return _reject(args, "status", exc)
    data["output_digests"] = {step_id: sorted(entry.get("output_digests") or {})
                              for step_id, entry in (state.get("steps") or {}).items()}
    data["production_report"] = report.load(folder) is not None
    data["ok"] = bool(data["steps"]) and all(row["status"] == "done" and not row["stale"]
                                             for row in data["steps"])
    if _json_mode(args):
        _dump(data)
    else:
        _print_status(data)
    return 0 if data["ok"] else 1


def cmd_approve(args):
    folder = os.path.abspath(args.run_dir)
    if not os.path.isdir(folder):
        print("[!] no such run folder: %s" % folder)
        return 3
    try:
        record = gates.approve(folder, args.gate, by=getattr(args, "by", "owner"),
                               note=getattr(args, "note", ""))
    except (guard.GuardError, checkpoint.CheckpointError, OSError, ValueError) as exc:
        return _reject(args, "gate", exc)
    data = {"ok": True, "approved": record, "gates": [], "pending_gates": []}
    saved = report.load(folder)
    if saved:
        rows = []
        for gate in saved.get("gates") or []:
            if gate.get("id") == record["gate"]:
                gate = dict(gate, approved=True, source="approval file",
                            by=record["by"], at=record["at"])
            rows.append(gate)
        data["gates"] = rows
        data["pending_gates"] = [row["id"] for row in rows if not row["approved"]]
    if _json_mode(args):
        _dump(data)
    else:
        rule()
        print("APPROVED %s in %s" % (record["gate"], guard.rel(folder)))
        print("  by %s at %s" % (record["by"], record["at"]))
        print("  file %s" % record.get("path", ""))
        if data["pending_gates"]:
            print("  still closed: %s" % ", ".join(data["pending_gates"]))
        rule()
    return 0


# ---------------------------------------------------------------------------
# the Recap Studio bridge (M6 / G4): one pipeline step, machine-readable
#
# Thin on purpose again: the refusals, the subprocess, the stale check and the file diff all live
# in `cutwright/recap.py`. This only parses, calls and prints.
# ---------------------------------------------------------------------------
def _print_recap(data, action):
    rule()
    if action == "projects":
        print("PROJECTS  %d  (recapstudio\\Projects)" % data["count"])
        rule()
        if data["projects"]:
            print_table([{"name": row["name"], "module": row["module"],
                          "seg": row["segments"], "audio": row["audio_files"],
                          "next": row["next"], "stale": ",".join(row["stale"]["stale"])}
                         for row in data["projects"]],
                        [("name", "project", 18), ("module", "module", 13),
                         ("seg", "segs", 4), ("audio", "audio", 5), ("next", "next", 24),
                         ("stale", "stale", 18)])
        rule()
        return
    if action == "new":
        print("CREATED %s  (%s, %d segment(s))" % (data["project"], data["module"],
                                                   data["segments"]))
        print("  folder  %s" % data["path"])
        print("  next    %s" % data["next"])
        rule()
        return
    if action == "status":
        print("PROJECT %s  (%s)  %s" % (data["project"], data["module"], data["project_dir"]))
        rule()
        print("  segments %d   audio %d" % (data["segments"], data["audio_files"]))
        timeline = data.get("timeline") or {}
        if timeline:
            print("  timeline %s frame(s) at %s fps, %sx%s"
                  % (timeline["total_frames"], timeline["fps"], timeline["width"],
                     timeline["height"]))
        print("  outputs  %s" % "  ".join("%s:%s" % (name, "yes" if ok else "-")
                                          for name, ok in data["outputs"].items()))
        if data["stale"]["stale"]:
            print("  STALE    %s" % ", ".join(data["stale"]["stale"]))
        for line in data["problems"]:
            print("  [!] %s" % line)
        print("  next     %s" % data["next"])
        if data["state_md_tail"]:
            print("")
            print("\n".join("  " + line for line in data["state_md_tail"].splitlines()[-6:]))
        rule()
        return
    print("STEP %s  in %s  ->  %s  (exit %s, %ss)"
          % (data["step"], data["project"], "ok" if data["ok"] else data.get("code", "failed"),
             data["exit_code"], data["seconds"]))
    rule()
    print("  ran      %s" % " ".join(data["command"]))
    print("  files    %d changed" % data["files_changed_count"])
    for name in data["files_changed"][:10]:
        print("    + %s" % name)
    for line in data["problems"]:
        print("  [!] %s" % line)
    if data.get("stdout_tail"):
        print("")
        print("\n".join("  " + line for line in data["stdout_tail"].splitlines()[-12:]))
    if not data["ok"] and data.get("suggested"):
        print("")
        print("  fix      %s" % data["suggested"])
    rule()


def cmd_recap(args):
    """projects | new | status | <step> over ONE Recap Studio project. Logic in cutwright/recap.py."""
    action = getattr(args, "action", "") or ""
    try:
        if action == "projects":
            data = bridge.projects()
        elif action == "new":
            data = bridge.new(args.name, module=args.module,
                              topic=getattr(args, "topic", "") or "")
        elif action == "status":
            data = bridge.status(args.project)
        else:
            data = bridge.run(args.project, action, only=getattr(args, "only", "") or "",
                              engine=getattr(args, "engine", "") or "",
                              preview=getattr(args, "preview", False),
                              yes=getattr(args, "yes", False),
                              demo=getattr(args, "demo", False),
                              force=getattr(args, "force", False),
                              override=getattr(args, "i_know_this_destroys_work", False),
                              comms=getattr(args, "comms", "") or "",
                              timeout=getattr(args, "timeout", bridge.DEFAULT_TIMEOUT))
    except (bridge.BridgeError, guard.GuardError) as exc:
        return _reject(args, "recap", exc)
    if _json_mode(args):
        _dump(data)
    else:
        _print_recap(data, action)
    return 0 if data.get("ok") else 1


def _add_recap_step(rsub, step, help_text):
    """One `recap <step>` parser. The flags are the bridge's surface: no `--force` without the gate."""
    q = rsub.add_parser(step, help=help_text)
    q.add_argument("--project", required=True, help="folder under recapstudio\\Projects")
    q.add_argument("--only", help="tts: comma-separated segment ids to (re)voice")
    q.add_argument("--engine", help="tts: edge|kokoro|chatterbox|pocket|elevenlabs|minimax")
    q.add_argument("--preview", action="store_true",
                   help="tts: voice a few segments into audio_preview/")
    q.add_argument("--yes", action="store_true", help="auto-confirm re-voice prompts")
    q.add_argument("--demo", action="store_true", help="scenes|briefs: use the demo set")
    q.add_argument("--force", action="store_true",
                   help="REFUSED unless --i-know-this-destroys-work and --comms are both given")
    q.add_argument("--i-know-this-destroys-work", action="store_true",
                   dest="i_know_this_destroys_work", help="first half of the --force override")
    q.add_argument("--comms", metavar="ID", help="COMMS entry id that records the override")
    q.add_argument("--timeout", type=int, default=bridge.DEFAULT_TIMEOUT,
                   help="seconds before the step is stopped (default %d)"
                        % bridge.DEFAULT_TIMEOUT)
    q.add_argument("--json", action="store_true", help="print JSON")
    q.set_defaults(func=cmd_recap)
    return q


def build_parser():
    ap = argparse.ArgumentParser(
        prog="cutwright",
        description="Transcript-first editing control. Writes only inside this folder.")
    ap.add_argument("--version", action="version", version="cutwright %s" % VERSION)
    sub = ap.add_subparsers(dest="step", metavar="STEP")

    p = sub.add_parser("doctor", help="what this machine has; proves the write guard")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("probe", help="streams and duration of one file")
    p.add_argument("video")
    p.set_defaults(func=cmd_probe)

    for name, func, help_text in (
            ("subs", cmd_subs, "validate the best available subtitle source"),
            ("moments", cmd_moments, "rank candidate moments from the transcript")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("video")
        p.add_argument("--subs", metavar="FILE",
                       help="a subtitle file to trust above everything else")
        p.add_argument("--expect", default="english",
                       help="language the subtitles should be in (default: english)")
        p.add_argument("--out", metavar="DIR",
                       help="output folder (default: out/<video name>/)")
        p.set_defaults(func=func)
        if name == "moments":
            p.add_argument("--top", type=int, default=12,
                           help="how many candidates to shortlist (default 12)")
            p.add_argument("--acts", type=int, default=5,
                           help="split the runtime into this many acts (default 5)")
            p.add_argument("--min-gap", type=float, default=20.0, dest="min_gap",
                           help="minimum seconds between two picks (default 20)")
    p = sub.add_parser("verify",
                       help="grade picks against frames: verified/retimed/replaced")
    p.add_argument("video")
    p.add_argument("--subs", metavar="FILE",
                   help="a subtitle file to trust above everything else")
    p.add_argument("--expect", default="english",
                   help="language the subtitles should be in (default: english)")
    p.add_argument("--out", metavar="DIR",
                   help="output folder (default: out/<video name>/)")
    p.add_argument("--moments", metavar="FILE",
                   help="moments.json to grade (default: <out>/moments.json)")
    p.add_argument("--claims", metavar="FILE",
                   help="expected claims per pick (default: <out>/claims.json)")
    p.add_argument("--review", metavar="FILE",
                   help="agent verdicts on frames actually looked at "
                        "(default: <out>/review.json)")
    p.add_argument("--write-back", action="store_true", dest="write_back",
                   help="patch status and expected back into moments.json")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("transcribe",
                       help="whisper.cpp fallback: transcribe the audio, gate it")
    p.add_argument("video")
    p.add_argument("--language", default="en",
                   help="spoken language code to transcribe (default: en)")
    p.add_argument("--expect", default=None,
                   help="language the checks expect (default: derived from "
                        "--language)")
    p.add_argument("--whisper", metavar="EXE",
                   help="whisper-cli.exe to use (default: bin\\whisper\\Release\\)")
    p.add_argument("--model", metavar="BIN",
                   help="ggml model to use (default: models\\%s)"
                        % transcribe.DEFAULT_MODEL)
    p.add_argument("--threads", type=int, default=None,
                   help="CPU threads for whisper (default: up to 8)")
    p.add_argument("--subs", metavar="FILE",
                   help="reference subtitles to cross-check the wording against; "
                        "these do not set timing")
    p.add_argument("--fresh", action="store_true",
                   help="re-extract the 16 kHz WAV instead of reusing it")
    p.add_argument("--out", metavar="DIR",
                   help="output folder (default: out/<video name>/)")
    p.set_defaults(func=cmd_transcribe)

    # --- the engine (M3): thin verbs over cutwright/engine/* -------------------------------
    p = sub.add_parser("scene", help="write a scene: the authoring brief, then the static check")
    ssub = p.add_subparsers(dest="action", metavar="ACTION")
    ssub.required = True
    q = ssub.add_parser("brief", help="the four primitives, the handle rule, the stills, the critic")
    q.add_argument("--handle", action="append", default=[],
                   help="a footage handle the step will declare (repeatable)")
    q.add_argument("--composition", default="", help="the composition id the step will name")
    q.add_argument("--duration", type=int, default=192, help="frames (192 = 8 s at 24 fps)")
    q.add_argument("--json", action="store_true", help="print JSON")
    q.set_defaults(func=cmd_scene)
    q = ssub.add_parser("check", help="static check of scene .tsx files with the real TypeScript")
    q.add_argument("file", nargs="+", help="one or more scene files")
    q.add_argument("--handle", action="append", default=[],
                   help="a handle the scene may name (repeatable)")
    q.add_argument("--json", action="store_true", help="print JSON")
    q.set_defaults(func=cmd_scene)

    p = sub.add_parser("tools", help="what the engine can do, and what is installed")
    p.add_argument("--json", action="store_true", help="print JSON")
    tsub = p.add_subparsers(dest="action", metavar="ACTION")
    q = tsub.add_parser("list", help="every op, or one stage")
    q.add_argument("--stage", help="one of: %s" % "|".join(ops.STAGES))
    q.add_argument("--json", action="store_true", help="print JSON")
    q.set_defaults(func=cmd_tools)
    q = tsub.add_parser("describe", help="one op in full: params, executor, evidence")
    q.add_argument("op")
    q.add_argument("--json", action="store_true", help="print JSON")
    q.set_defaults(func=cmd_tools)
    q = tsub.add_parser("envelope", help="at most 10 op descriptions for ONE stage")
    q.add_argument("--stage", default="edit")
    q.add_argument("--json", action="store_true", help="print JSON")
    q.set_defaults(func=cmd_tools)
    p.set_defaults(action="list")

    p = sub.add_parser("blueprint", help="design a production (beats) and compile it to a manifest")
    bsub = p.add_subparsers(dest="action", metavar="ACTION")
    bsub.required = True
    q = bsub.add_parser("generate", help="brief (beats + shots + assets) -> blueprint.json")
    q.add_argument("brief", help="the brief: title, project, assets, beats (see docs/TOOLS.md)")
    q.add_argument("--out", metavar="FILE", help="where to write the blueprint")
    q.add_argument("--narration", metavar="FILE",
                   help="use this narration file instead of synthesising one")
    q.add_argument("--no-tts", action="store_true", dest="no_tts",
                   help="never synthesise: the narration file must already exist")
    q.add_argument("--json", action="store_true", help="print JSON")
    q.set_defaults(func=cmd_blueprint)
    q = bsub.add_parser("compile", help="blueprint.json -> manifest.json (validated before writing)")
    q.add_argument("blueprint", help="the blueprint file `blueprint generate` wrote")
    q.add_argument("--out", metavar="FILE", help="where to write the manifest")
    q.add_argument("--json", action="store_true", help="print JSON")
    q.set_defaults(func=cmd_blueprint)

    p = sub.add_parser("validate", help="pre-render check of a manifest: plan + asset provenance")
    p.add_argument("manifest")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("run", help="execute a manifest, reusing steps whose cache key matches")
    p.add_argument("manifest")
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="report what would run; write nothing at all")
    p.add_argument("--only", action="append", metavar="STEP",
                   help="execute only these step ids (repeatable)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("resume", help="continue a run from its checkpoint")
    p.add_argument("run_dir")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_resume)

    p = sub.add_parser("status", help="what a run folder's checkpoint says, step by step")
    p.add_argument("run_dir")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("approve", help="open an approval gate in a run folder")
    p.add_argument("run_dir")
    p.add_argument("gate", help="the gate id the manifest declared")
    p.add_argument("--by", default="owner", help="who approved it (default: owner)")
    p.add_argument("--note", default="", help="what was approved, in words")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_approve)

    # --- the Recap Studio bridge (M6 / G4): whitelisted steps, JSON, refusals -----------------
    p = sub.add_parser("recap", help="run ONE Recap Studio pipeline step and get JSON back")
    rsub = p.add_subparsers(dest="action", metavar="STEP")
    rsub.required = True

    q = rsub.add_parser("projects", help="every project: module, segments, audio, outputs, stale?")
    q.add_argument("--json", action="store_true", help="print JSON")
    q.set_defaults(func=cmd_recap)

    q = rsub.add_parser("new", help="copy _template into Projects/<name> (never runs init)")
    q.add_argument("name")
    q.add_argument("--module", default="movie_recap",
                   help="movie_recap|show_recap|comic_recap|nba_minidoc|nba_story|real_story|ranking")
    q.add_argument("--topic", default="", help="what the video is about")
    q.add_argument("--json", action="store_true", help="print JSON")
    q.set_defaults(func=cmd_recap)

    q = rsub.add_parser("status", help="one project: counts, outputs, stale code, next step")
    q.add_argument("--project", required=True, help="folder under recapstudio\\Projects")
    q.add_argument("--json", action="store_true", help="print JSON")
    q.set_defaults(func=cmd_recap)

    for step in bridge.STEPS:
        _add_recap_step(rsub, step, "run `recap.py %s` inside the project" % step)
    for step, why in sorted(bridge.WHY_REFUSED.items()):
        _add_recap_step(rsub, step, "REFUSED - %s" % why)
    return ap


def main(argv=None):
    # Subtitles are multilingual by nature; a cp1252 console must not be able to
    # crash the tool (or mangle the report) just because a line is Japanese.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "step", None):
        ap.print_help()
        return 0
    return args.func(args) or 0



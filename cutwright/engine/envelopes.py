"""Stage envelopes: the focused tool set an agent gets while working ONE stage (M6).

Why this file exists: the catalogue is 14 engine ops plus the agent commands. Handing an agent all
of it, every turn, spends context on tools it cannot use where it is standing. An envelope is the
focused subset one production stage needs, and nothing else.

The unit is a TOOL, and there are two kinds:

  * an engine op (`cutwright/engine/ops.py`) - a step in a manifest: params, inputs, executor
  * an agent command (`cutwright/cli.py`) - a verb the agent itself calls: probe, verify, ...

An op lives in exactly ONE stage (`OpSpec.stage`); that is its home, and `tools list --stage S`
shows the same set the envelope shows. A command may appear in more than one envelope: it is one
implementation, reached from several stages (the same `probe` answers a question at plan time and
at deliver time), which is discovery, not a second implementation of anything.

Stages are the production stages, in order: plan, edit, graphics, review, deliver.
"""
from cutwright.engine import ops


class EnvelopeError(ValueError):
    """A stage envelope that would hand an agent more than it should."""


# Every envelope also carries the ONE way to execute a plan, so no stage has to spend a tool slot
# on the executor itself.
HOW_TO_RUN = ("python -m cutwright validate <manifest> --json  ->  "
              "python -m cutwright run <manifest> [--only STEP] [--json]")

# One entry per agent command: usage, the positional arguments, the flags, and one line saying
# what it answers. `tests/test_engine_registry.py` checks these against the live argparse parser,
# so a renamed flag fails a test instead of silently misinforming an agent.
COMMANDS = {
    "blueprint": {"usage": "python -m cutwright blueprint generate <brief.json> [--out FILE] "
                           "[--narration FILE] [--no-tts] [--json] | blueprint compile "
                           "<blueprint.json> [--json]",
                  "args": (), "flags": ("--out", "--narration", "--no-tts", "--json"),
                  "description": "design: beats + shot types + assets -> blueprint.json, then "
                                 "compile it to a validated manifest.json"},
    "scene": {"usage": "python -m cutwright scene brief [--handle H] [--composition ID] [--json]"
                       " | scene check <file...> [--handle H] [--json]",
              "args": (), "flags": ("--handle", "--composition", "--duration", "--json"),
              "description": "authoring: the four primitives + handle rule + critic checks, then "
                             "the real TypeScript static check"},
    "tools": {"usage": "python -m cutwright tools list|describe <op>|envelope --stage <stage> [--json]",
              "args": (), "flags": ("--stage", "--json"),
              "description": "discovery: every op, one op in full, or one stage in focus"},
    "probe": {"usage": "python -m cutwright probe <video>",
              "args": ("video",), "flags": (),
              "description": "one source file: streams, duration, subtitle tracks"},
    "subs": {"usage": "python -m cutwright subs <video> [--subs FILE] [--expect TEXT] [--out DIR]",
             "args": ("video",), "flags": ("--subs", "--expect", "--out"),
             "description": "subtitle trust gate: the best subtitle source, proven usable"},
    "moments": {"usage": "python -m cutwright moments <video> [--top N] [--acts N] [--min-gap S]",
                "args": ("video",), "flags": ("--top", "--acts", "--min-gap", "--subs", "--out",
                                              "--expect"),
                "description": "transcript -> beats -> ranked candidate moments + agent digest"},
    "verify": {"usage": "python -m cutwright verify <video> --moments FILE [--claims FILE]",
               "args": ("video",), "flags": ("--moments", "--subs", "--claims", "--review",
                                             "--expect", "--write-back", "--out"),
               "description": "grade picks against frames: verified / retimed / replaced"},
    "transcribe": {"usage": "python -m cutwright transcribe <video> [--language en]",
                   "args": ("video",), "flags": ("--language", "--model", "--threads", "--subs",
                                                 "--whisper", "--fresh", "--out", "--expect"),
                   "description": "whisper.cpp fallback transcript, then gated (needs bin/, models/)"},
    "validate": {"usage": "python -m cutwright validate <manifest> [--json]",
                 "args": ("manifest",), "flags": ("--json",),
                 "description": "pre-render check: ops, params, refs, budget, asset provenance"},
    "status": {"usage": "python -m cutwright status <run-dir> [--json]",
               "args": ("run_dir",), "flags": ("--json",),
               "description": "a run's checkpoint step by step, and which outputs went stale"},
    "approve": {"usage": "python -m cutwright approve <run-dir> <gate> [--by WHO] [--note TEXT]",
                "args": ("run_dir", "gate"), "flags": ("--by", "--note", "--json"),
                "description": "write the approval file that releases the step behind a gate"},
    "recap": {"usage": "python -m cutwright recap <step> --project <name> [--only IDS] [--json]",
              "args": (), "flags": ("--project", "--only", "--engine", "--preview", "--yes",
                                           "--demo", "--force", "--i-know-this-destroys-work",
                                           "--comms", "--timeout", "--json"),
              "description": "the Recap Studio pipeline through the agent bridge: one step, JSON back"},
}

# What each stage is FOR (one line of intent, so the agent knows why the set is this small), and
# the commands that stage reaches for. Ops are not listed here: an op's stage IS its home, and
# `ops.by_stage()` is the only place that decides.
STAGE_FOCUS = {
    "plan": {
        "why": "read the source and choose the cut: what the file is, what it says, which moments "
               "carry the story - then design the production as beats and compile it",
        "commands": ("tools", "blueprint", "probe", "subs", "moments", "transcribe", "verify"),
    },
    "edit": {
        "why": "turn chosen moments into a frame-exact picture: cut, join, reframe, fit, mix and "
               "normalise the sound",
        "commands": (),
    },
    "graphics": {
        "why": "draw over the picture: write a scene from the brief, burn captions, render ONE "
               "still to look at, render a range",
        "commands": ("scene", "recap"),
    },
    "review": {
        "why": "judge the result before it ships: validate the plan, read the run state, grade the "
               "picks, open an approval gate",
        "commands": ("validate", "status", "verify", "approve"),
    },
    "deliver": {
        "why": "encode the final file and prove it decodes",
        "commands": ("probe", "status"),
    },
}


def command(name):
    """The one command row, with its kind attached (the same key an op row carries)."""
    row = COMMANDS[name]
    return {"kind": "command", "name": name, "args": list(row["args"]),
            "flags": list(row["flags"]), "usage": row["usage"],
            "description": row["description"]}


def op_row(spec, lean=True):
    """One op as an envelope shows it: enough to write a step, not the whole describe.

    `params` keeps type/required/default/choices/bounds and drops the prose: a stage that needs
    the prose asks for `tools describe <op>` for the one op it is unsure about.
    """
    params = {}
    for name, param in spec.params.items():
        data = param.to_dict()
        if lean:
            data.pop("doc", None)
        params[name] = data
    row = {"kind": "op", "name": spec.name, "stage": spec.stage,
           "executor": spec.executor, "description": spec.description,
           "inputs": list(spec.inputs), "outputs": list(spec.outputs),
           "required": [name for name, param in spec.params.items() if param.required],
           "params": params}
    if spec.optional_inputs:
        row["optional_inputs"] = list(spec.optional_inputs)
    return row


def build(stage, limit=ops.MAX_ENVELOPE):
    """The focused tool set for ONE stage: at most `limit` ops, plus the commands it needs.

    Raises EnvelopeError when a stage would hand out more than `ops.MAX_ENVELOPE` tools in total:
    the cap is the point of the envelope, so it is checked over ops AND commands, not per list.
    """
    if stage not in STAGE_FOCUS:
        raise EnvelopeError("no envelope for stage %r" % (stage,))
    focus = STAGE_FOCUS[stage]
    specs = ops.by_stage(stage)
    shown = specs[:max(1, int(limit))]
    rows = [op_row(spec) for spec in shown]
    commands = [command(name) for name in focus["commands"]]
    if len(rows) + len(commands) > ops.MAX_ENVELOPE:
        raise EnvelopeError(
            "stage %r would expose %d tools (cap %d); narrow the command list or the op limit"
            % (stage, len(rows) + len(commands), ops.MAX_ENVELOPE))
    return {"schema": 1, "stage": stage, "why": focus["why"],
            "count": len(specs), "returned": len(rows),
            "truncated": len(specs) > len(rows),
            "ops": rows, "commands": commands,
            "tools": len(rows) + len(commands), "max_tools": ops.MAX_ENVELOPE,
            "how_to_run": HOW_TO_RUN}

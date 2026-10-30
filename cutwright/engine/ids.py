"""Run ids and the safe names derived from them, so `status`, `approve` and the report agree.

Two rules, both cheap and both tested:

  * an id, a gate name or a report name must be filesystem-safe on Windows (no `:`, no spaces, no
    path separators) -- a manifest is written by an agent, and an agent will happily call a gate
    `final ok: v2`;
  * two runs started in the same second must not collide, so a run id carries four hex characters
    on top of the UTC stamp.

Nothing here hashes media. `guard.sha256_file` (full hash) and `checkpoint.digest_file`
(size+mtime above 64 MiB) already own that rule; a third implementation would drift.
"""
import os
import re
import time
import uuid

_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_BAD = re.compile(r"[^a-z0-9._-]+")
_DASHES = re.compile(r"[-_.]{2,}")


def slug(value, fallback="run"):
    """`value` as a lowercase, separator-free name: 'Final OK: v2' -> 'final-ok-v2'."""
    text = _BAD.sub("-", str(value or "").strip().lower())
    text = _DASHES.sub("-", text).strip("-._")
    return (text[:60].strip("-._")) or str(fallback)


def is_slug(value):
    """True when `value` is already safe (a path built from it needs no slug())."""
    return bool(_SLUG.match(str(value or "")))


def stamp(when=None):
    """UTC '20261030-153012': sorts chronologically in a folder listing or a log."""
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime(when))


def new_run_id(prefix="run", when=None):
    """'demo-20261030-153012-4f2a' -- readable, sortable, unique within one second."""
    return "%s-%s-%s" % (slug(prefix, "run"), stamp(when), uuid.uuid4().hex[:4])


def run_dir_for(run_id, root):
    """`<root>/<slug(run_id)>`: the folder a run id names, without creating it."""
    return os.path.join(os.path.abspath(root), slug(run_id, "run"))

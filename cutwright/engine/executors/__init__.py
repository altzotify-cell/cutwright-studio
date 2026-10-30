"""Executor contract shared by every backend (kinocut | ffmpeg | remotion | python).

An executor exposes typed calls, never a free-form command string. A call either returns an
`ExecResult` or raises an `ExecutorError` that names the executor, the op, the error code and a
suggested fix. `transient` decides M3's retry policy: at most 2 attempts for transient failures
(subprocess timeout, locked file), no retry at all for deterministic ones (bad params, failed
validation, refused overwrite).

`first_json` lives here because both Kinocut and the Remotion bridge print log lines around
their JSON, so the parser must be the same one everywhere.
"""
import dataclasses
import json
import subprocess

KILL_TIMEOUT = 20


def kill_tree(proc, timeout=KILL_TIMEOUT):
    """Kill a process AND its children: the scoop ffmpeg shim leaves a live child otherwise.

    One implementation for every executor. Falls back to `proc.kill()` when taskkill is absent
    or itself hangs, so a stuck render can always be cleaned up.
    """
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       stdin=subprocess.DEVNULL, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        try:
            proc.kill()
        except OSError:
            pass


def decode_bytes(data):
    """Bytes -> text. Kinocut writes UTF-8 on a cp1252 console (KINOCUT_FINDINGS 7.4)."""
    if not data:
        return ""
    if isinstance(data, str):
        return data
    return data.decode("utf-8", "replace")


def first_json(text):
    """First JSON object in `text`, or None. Tolerates log lines before and after it."""
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return None


@dataclasses.dataclass
class ExecResult:
    """What one executed op produced: provenances, raw capture and the parsed payload."""
    executor: str = ""      # "kinocut" | "ffmpeg" | "remotion" | "python"
    op: str = ""
    argv: list = dataclasses.field(default_factory=list)
    returncode: int = 0
    seconds: float = 0.0
    stdout: str = ""
    stderr: str = ""
    output_path: str = ""
    receipt_path: str = ""
    warnings: list = dataclasses.field(default_factory=list)
    payload: dict = dataclasses.field(default_factory=dict)

    @property
    def ok(self):
        return self.returncode == 0

    def to_dict(self):
        """Manifest-shaped record. Hashes/validation are added by manifest.py, not here."""
        return {"executor": self.executor, "op": self.op, "argv": list(self.argv),
                "returncode": self.returncode, "seconds": round(self.seconds, 3),
                "output": self.output_path, "receipt": self.receipt_path,
                "warnings": list(self.warnings)}


class ExecutorError(RuntimeError):
    """A typed executor failure. `str(err)` is one line naming the op, the code and the fix."""

    def __init__(self, executor, op, message, code="failed", argv=(), returncode=None,
                 suggested="", error_type="", stdout="", stderr="", transient=False):
        self.executor = executor
        self.op = op
        self.message = message
        self.code = code
        self.argv = list(argv)
        self.returncode = returncode
        self.suggested = suggested
        self.error_type = error_type
        self.stdout = stdout
        self.stderr = stderr
        self.transient = transient
        super().__init__(self._line())

    def _line(self):
        line = "%s %s failed (code %s)" % (self.executor, self.op, self.code)
        if self.message:
            line += ": %s" % self.message
        if self.suggested:
            line += " -> %s" % self.suggested
        return line

    def __str__(self):
        return self._line()

    def to_dict(self):
        return {"executor": self.executor, "op": self.op, "code": self.code,
                "type": self.error_type, "message": self.message,
                "suggested": self.suggested, "returncode": self.returncode,
                "transient": self.transient, "argv": list(self.argv)}


class ExecutorUnavailable(ExecutorError):
    """The backend is not installed (no kino.exe, no ffmpeg on PATH). Never transient."""


class ExecutorTimeout(ExecutorError):
    """The call exceeded its timeout and its process tree was killed. Always transient."""

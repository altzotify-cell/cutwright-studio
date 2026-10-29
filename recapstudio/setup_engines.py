"""Recap Studio - voice engine installer (started by SETUP.bat).

Every voice engine and every model download goes through here, so nothing is fetched behind your back later.
Run SETUP.bat again any time to add more engines or models; what is already installed is shown and skipped.

Uses only the Python standard library, so it works before anything else is installed.
Test without installing anything:   python setup_engines.py --dry-run
"""
import json
import os
import shutil
import subprocess
import sys
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(BASE, "models")
STATE_FILE = os.path.join(MODELS, "engines.json")
VENVS = os.path.join(BASE, "venvs")
HF_HOME = os.path.join(MODELS, "hf")
DRY = "--dry-run" in sys.argv

KOKORO_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
KOKORO_FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")

# key, label, size note
CHATTERBOX_MODELS = [
    ("nano", "Nano 110M       - LIGHTEST, runs on a plain CPU (about 3x real time), English, [laugh] tags", "~0.6 GB"),
    ("turbo", "Turbo 350M      - English, [laugh] tags, best speed/quality with a GPU", "~1.5 GB"),
    ("english", "Original 500M   - English, Exaggeration + Pacing sliders", "~2 GB"),
    ("multilingual", "Multilingual 500M - 23 languages", "~2 GB"),
]


# ---------------------------------------------------------------- state
def load_state():
    st = {"edge": False, "kokoro": False, "pocket": False, "chatterbox": [], "languages": "en"}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            st.update(json.load(f))
    except Exception:
        pass
    return st


def save_state(st):
    if DRY:
        print(f"   (dry run) would write {STATE_FILE}: {json.dumps(st)}")
        return
    os.makedirs(MODELS, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2)


# ---------------------------------------------------------------- helpers
def say(msg=""):
    print(msg, flush=True)


def run(cmd, env=None):
    say("   > " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    if DRY:
        return 0
    return subprocess.call(cmd, env=env)


def ask(prompt, default=""):
    try:
        v = input(prompt).strip()
    except EOFError:
        v = ""
    return v or default


def yes_no(prompt, default=False):
    v = ask(prompt + (" [Y/n]: " if default else " [y/N]: "), "y" if default else "n").lower()
    return v.startswith("y")


def pick_many(prompt, count, default):
    """'1 3', '1,3', '13' or 'all' -> sorted list of 1-based numbers."""
    raw = ask(prompt, default).lower()
    if raw in ("a", "all"):
        return list(range(1, count + 1))
    nums = sorted({int(c) for c in raw if c.isdigit() and 1 <= int(c) <= count})
    return nums


def venv_python(name):
    base = os.path.join(VENVS, name)
    for rel in (("Scripts", "python.exe"), ("bin", "python")):
        p = os.path.join(base, *rel)
        if os.path.isfile(p):
            return p
    return None


def model_env():
    env = dict(os.environ)
    env.update({"HF_HOME": HF_HOME, "HF_HUB_DISABLE_SYMLINKS_WARNING": "1", "PYTHONIOENCODING": "utf-8"})
    return env


def find_python(versions):
    """Return a command list for the first available interpreter among e.g. ['3.11', '3.10']."""
    for v in versions:
        cands = [["py", f"-{v}"], [f"python{v}"]]
        for c in cands:
            if shutil.which(c[0]) is None:
                continue
            try:
                r = subprocess.run(c + ["--version"], capture_output=True, text=True)
                if r.returncode == 0 and v in (r.stdout + r.stderr):
                    return c
            except OSError:
                pass
    return None


def has_nvidia():
    return shutil.which("nvidia-smi") is not None


def make_venv(name, py_cmd):
    if venv_python(name):
        say(f"   Environment venvs/{name} already exists - reusing it.")
        return True
    os.makedirs(VENVS, exist_ok=True)
    return run(py_cmd + ["-m", "venv", os.path.join(VENVS, name)]) == 0


def pip(vpy, *args):
    return run([vpy, "-m", "pip", "install"] + list(args)) == 0


# ---------------------------------------------------------------- engines
def install_edge(st):
    say("\n=== Edge-TTS (online, free, Microsoft voices) ===")
    if run([sys.executable, "-m", "pip", "install", "--upgrade", "edge-tts"]) != 0:
        return False
    st["edge"] = True
    return True


def download_file(url, dest):
    if os.path.isfile(dest) and os.path.getsize(dest) > 1_000_000:
        say(f"   {os.path.basename(dest)} already downloaded.")
        return
    say(f"   Downloading {os.path.basename(dest)} ...")
    if DRY:
        return
    tmp = dest + ".part"
    with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got, last = 0, -1
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if total and got * 100 // total != last:
                last = got * 100 // total
                print(f"\r   {last:3d}%  ({got // (1 << 20)} / {total // (1 << 20)} MB)", end="", flush=True)
    print()
    os.replace(tmp, dest)


def install_kokoro(st):
    say("\n=== Kokoro (offline, runs on your PC, ~350 MB model) ===")
    if run([sys.executable, "-m", "pip", "install", "--upgrade", "kokoro-onnx", "soundfile"]) != 0:
        return False
    folder = os.path.join(MODELS, "kokoro")
    if not DRY:
        os.makedirs(folder, exist_ok=True)
    try:
        for name in KOKORO_FILES:
            download_file(KOKORO_BASE + name, os.path.join(folder, name))
    except Exception as e:
        say(f"   [!] Download failed: {e}")
        return False
    st["kokoro"] = True
    return True


def download_models(vpy, spec):
    cmd = [vpy, os.path.join(BASE, "tts_worker.py"), "--download", spec]
    if DRY:
        say("   > " + " ".join(cmd) + "   (HF_HOME=" + HF_HOME + ")")
        return True
    return subprocess.call(cmd, env=model_env()) == 0


def _has_hf_token():
    if os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        return True
    try:
        for line in open(os.path.join(BASE, "keys.env"), "r", encoding="utf-8"):
            line = line.strip()
            if line.startswith("HF_TOKEN=") and line.split("=", 1)[1].strip() not in ("", "paste_your_token_here"):
                return True
    except OSError:
        pass
    return False


def install_pocket(st):
    say("\n=== Pocket TTS (offline, CPU-friendly, voice cloning) ===")
    py = find_python(["3.12", "3.11", "3.13", "3.10"]) or [sys.executable]
    if not make_venv("pocket", py):
        return False
    vpy = venv_python("pocket") or os.path.join(VENVS, "pocket", "Scripts", "python.exe")
    ok = (pip(vpy, "--upgrade", "pip", "wheel")
          and pip(vpy, "torch", "--index-url", "https://download.pytorch.org/whl/cpu")
          and pip(vpy, "pocket-tts", "soundfile"))   # soundfile lets Pocket read MP3/FLAC/OGG/M4A clips
    if not ok:
        return False
    say("   Downloading the Pocket TTS model and its built-in voices ...")
    if not download_models(vpy, "pocket"):
        return False
    st["pocket"] = True
    if not _has_hf_token():
        say("\n   NOTE: Pocket TTS voice CLONING needs a free Hugging Face token.\n"
            "   1) Accept the terms at https://huggingface.co/kyutai/pocket-tts\n"
            "   2) Make a Read token at https://huggingface.co/settings/tokens\n"
            "   3) Add  HF_TOKEN=hf_yourtoken  to keys.env, then run SETUP.bat again (pick Pocket TTS).\n"
            "   Built-in voices work without it.")
    return True


def install_chatterbox(st, variants, gpu):
    say("\n=== Chatterbox (offline, voice cloning, emotion) ===")
    py = find_python(["3.11", "3.10"])
    if py is None:
        say("   Chatterbox needs Python 3.11 (3.10 also works); 3.12+ is not supported yet.")
        if os.name == "nt" and yes_no("   Install Python 3.11 now with winget?", True):
            run(["winget", "install", "-e", "--id", "Python.Python.3.11"])
            say("\n   Python 3.11 installed. CLOSE this window and run SETUP.bat again to finish Chatterbox.")
        return False
    if not make_venv("chatterbox", py):
        return False
    vpy = venv_python("chatterbox") or os.path.join(VENVS, "chatterbox", "Scripts", "python.exe")
    index = "cu124" if gpu else "cpu"
    ok = (pip(vpy, "--upgrade", "pip", "setuptools<81", "wheel")
          and pip(vpy, "torch", "torchaudio", "--index-url", f"https://download.pytorch.org/whl/{index}")
          and pip(vpy, "--upgrade", "chatterbox-tts"))
    if not ok:
        return False
    if "nano" in variants and not DRY:
        # Nano is only in the GitHub master branch (same version number 0.1.7 as PyPI, so pip must be FORCED).
        probe = ("import inspect; from chatterbox.tts_turbo import ChatterboxTurboTTS as C; "
                 "ok = 'nano' in inspect.signature(C.from_pretrained).parameters or 'nano' in inspect.getsource(C.from_pretrained); "
                 "raise SystemExit(0 if ok else 1)")
        if subprocess.call([vpy, "-c", probe]) != 0:
            say("   The PyPI release of chatterbox-tts has no Nano - installing the GitHub 'master' version over it.")
            done = False
            for branch in ("master", "main"):
                if pip(vpy, "--force-reinstall", "--no-deps",
                       f"https://github.com/resemble-ai/chatterbox/archive/refs/heads/{branch}.zip"):
                    done = True
                    break
            if not done or subprocess.call([vpy, "-c", probe]) != 0:
                say("   [!] Could not get a Chatterbox build with Nano. The other models are unaffected.")
                variants = [v for v in variants if v != "nano"]
    if not variants:
        return False
    say(f"   Downloading model weights: {', '.join(variants)} (this is the big download) ...")
    if not download_models(vpy, "chatterbox:" + ",".join(variants)):
        return False
    st["chatterbox"] = sorted(set(st.get("chatterbox", [])) | set(variants))
    return True


# ---------------------------------------------------------------- menu
def main():
    st = load_state()
    say("=" * 64)
    say("  RECAP STUDIO - voice engine setup")
    say("  Pick what you want. Nothing is downloaded that you do not choose.")
    say("  Run SETUP.bat again any time to add more.")
    say("=" * 64)

    def mark(ok):
        return "  [installed]" if ok else ""

    cb = st.get("chatterbox", [])
    say("\n  1  Edge-TTS     online, free, no GPU, ~1 MB, many voices" + mark(st["edge"]))
    say("  2  Kokoro       offline, free, any CPU, ~350 MB, good narrator voices" + mark(st["kokoro"]))
    say("  3  Pocket TTS   offline, free, any CPU (faster than real time), voice cloning, ~1 GB"
        + mark(st["pocket"]))
    say("  4  Chatterbox   offline, free, voice cloning + emotion tags, you choose the model size next"
        + (f"  [installed: {', '.join(cb)}]" if cb else ""))
    say("\n  (ElevenLabs / MiniMax are online services: only paste your key in the app's API keys screen.)")
    picks = pick_many("\nType the numbers to install, e.g. 2 3   (or 'all', Enter = skip engines): ", 4, "")

    want_languages = None
    variants, gpu = [], False
    if 4 in picks:
        say("\n--- Chatterbox ---")
        multi = yes_no("Do you need languages other than English?", False)
        want_languages = "all" if multi else "en"
        models = CHATTERBOX_MODELS if multi else [m for m in CHATTERBOX_MODELS if m[0] != "multilingual"]
        say("\nWhich Chatterbox model(s)? You can pick several; each one is a separate download.")
        for i, (_, label, size) in enumerate(models, 1):
            say(f"  {i}  {label}   {size}")
        say("  Tip: no NVIDIA graphics card -> choose 1 (Nano). With a GPU -> 2 (Turbo).")
        gpu_default = "2" if has_nvidia() else "1"
        nums = pick_many(f"Numbers (Enter = {gpu_default}): ", len(models), gpu_default)
        variants = [models[n - 1][0] for n in nums]
        if has_nvidia():
            gpu = yes_no("NVIDIA GPU detected - use it (much faster)?", True)
        else:
            say("\n  No NVIDIA GPU found: Chatterbox will run on the CPU. Nano is the only model that is fast there.")

    if not picks:
        say("\nNo engines chosen - nothing to install.")
        return 0

    results = {}
    for n in picks:
        if n == 1:
            results["Edge-TTS"] = install_edge(st)
        elif n == 2:
            results["Kokoro"] = install_kokoro(st)
        elif n == 3:
            results["Pocket TTS"] = install_pocket(st)
        elif n == 4:
            results["Chatterbox"] = install_chatterbox(st, variants, gpu)
        save_state(st)           # keep progress even if a later engine fails
    if want_languages:
        st["languages"] = "all" if (want_languages == "all" or st.get("languages") == "all") else "en"
    save_state(st)

    say("\n" + "=" * 64)
    for name, ok in results.items():
        say(f"  {'OK    ' if ok else 'FAILED'}  {name}")
    say("=" * 64)
    if not all(results.values()):
        say("Something failed - read the messages above, fix it (internet / disk space) and run SETUP.bat again.")
        return 1
    say("Done. Start the app with START_UI.bat and pick your engine in the Voice tab.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("\nCancelled.")
        sys.exit(1)

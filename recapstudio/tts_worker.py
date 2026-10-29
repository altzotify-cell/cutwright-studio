"""Recap Studio TTS worker - runs INSIDE an engine's own virtual environment.

Why a separate process: Chatterbox and Pocket TTS pull in PyTorch and pin their own versions of
numpy & friends. Running them in their own venv (venvs/chatterbox, venvs/pocket) means they can
never break the rest of Recap Studio, and the model stays loaded between clips (loading takes
10-30 s, a clip takes a few seconds).

Protocol: one JSON object per line on stdin, one JSON reply per line on stdout.
    {"cmd": "load", "engine": "chatterbox"|"pocket", "params": {...}}   -> {"ok": true, "info": "..."}
    {"cmd": "say",  "text": "...", "out": "x.wav", "params": {...}}     -> {"ok": true, "seconds": 3.2}
    {"cmd": "quit"}
Everything the libraries print goes to stderr so stdout stays clean.
"""
import inspect
import json
import os
import sys
import traceback

REAL_OUT = sys.stdout
sys.stdout = sys.stderr          # libraries love to print(); keep stdout for the protocol only


BASE = os.path.dirname(os.path.abspath(__file__))


def find_hf_token():
    """Hugging Face token for gated models (Pocket TTS voice cloning).
    Order: HF_TOKEN env var -> HF_TOKEN= line in keys.env (this folder, then its parents).
    Never printed or logged."""
    for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        if os.environ.get(name, "").strip():
            return os.environ[name].strip()
    for d in (BASE, os.path.dirname(BASE), os.path.dirname(os.path.dirname(BASE))):
        p = os.path.join(d, "keys.env")
        if not os.path.isfile(p):
            continue
        try:
            for line in open(p, "r", encoding="utf-8"):
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == "HF_TOKEN":
                    v = v.strip().strip("\"'")
                    if v and v != "paste_your_token_here":
                        return v
        except Exception:
            pass
    return None


_tok = find_hf_token()
if _tok:
    os.environ["HF_TOKEN"] = _tok          # huggingface_hub reads this automatically


CLONE_HELP = (
    "Voice cloning needs Kyutai's gated weights. Do this once: (1) open "
    "https://huggingface.co/kyutai/pocket-tts and click 'Agree and access repository', "
    "(2) make a Read token at https://huggingface.co/settings/tokens, "
    "(3) add a line  HF_TOKEN=hf_yourtoken  to keys.env, "
    "(4) run  venvs\\pocket\\Scripts\\python tts_worker.py --download pocket  and restart the app."
)


def reply(obj):
    REAL_OUT.write(json.dumps(obj) + "\n")
    REAL_OUT.flush()


def pick_kwargs(fn, wanted):
    """Only pass the keyword arguments this version of the library actually accepts."""
    try:
        accepted = set(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        return dict(wanted)
    return {k: v for k, v in wanted.items() if k in accepted and v is not None}


def best_device(pref):
    import torch
    pref = (pref or "auto").lower()
    if pref != "auto":
        return pref
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def save_wav(path, tensor_or_array, sr):
    import numpy as np
    import wave
    a = tensor_or_array
    if hasattr(a, "detach"):
        a = a.detach().cpu().float().numpy()
    a = np.asarray(a, dtype="float32").squeeze()
    if a.ndim > 1:                 # (channels, samples) -> mono
        a = a.mean(axis=0)
    a = np.clip(a, -1.0, 1.0)
    pcm = (a * 32767.0).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes(pcm.tobytes())
    return len(pcm) / float(sr)


# --------------------------------------------------------------------------------------
# Chatterbox
# --------------------------------------------------------------------------------------
class Chatterbox:
    def __init__(self, p):
        import torch
        self.torch = torch
        self.variant = (p.get("variant") or "turbo").lower()
        self.device = best_device(p.get("device"))
        if self.variant in ("turbo", "nano"):
            from chatterbox.tts_turbo import ChatterboxTurboTTS as Cls
        elif self.variant == "multilingual":
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS as Cls
        else:
            from chatterbox.tts import ChatterboxTTS as Cls
            self.variant = "english"
        # Checkpoints saved on CUDA fail to load on CPU/MPS unless map_location is patched
        if self.device != "cuda" and not getattr(torch.load, "_recap_patched", False):
            _orig = torch.load
            dev = torch.device(self.device)

            def _load(*a, **k):
                k.setdefault("map_location", dev)
                return _orig(*a, **k)
            _load._recap_patched = True
            torch.load = _load
        if self.variant == "nano":
            if "nano" not in inspect.signature(Cls.from_pretrained).parameters:
                raise RuntimeError("This Chatterbox install has no Nano model. Run SETUP.bat again and choose Chatterbox > Nano.")
            self.model = Cls.from_pretrained(device=self.device, nano=True)
        else:
            self.model = Cls.from_pretrained(device=self.device)
        self.sr = int(getattr(self.model, "sr", 24000))
        self.info = f"Chatterbox {self.variant} on {self.device} ({self.sr} Hz)"

    def say(self, text, out, p):
        seed = p.get("seed")
        if seed not in (None, "", 0, "0"):
            self.torch.manual_seed(int(seed))
        want = {
            "audio_prompt_path": (p.get("voice_ref") or None),
            "exaggeration": _f(p.get("exaggeration")),
            "cfg_weight": _f(p.get("cfg_weight")),
            "temperature": _f(p.get("temperature")),
            "repetition_penalty": _f(p.get("repetition_penalty")),
            "min_p": _f(p.get("min_p")),
            "top_p": _f(p.get("top_p")),
            "top_k": _i(p.get("top_k")),
        }
        if self.variant == "multilingual":
            want["language_id"] = (p.get("language") or "en")
        if self.variant in ("turbo", "nano"):
            # Turbo / Nano ignore exaggeration / cfg_weight (it warns); don't send them
            want.pop("exaggeration", None)
            want.pop("cfg_weight", None)
            want.pop("min_p", None)
        kw = pick_kwargs(self.model.generate, want)
        wav = self.model.generate(text, **kw)
        return save_wav(out, wav, self.sr)


# --------------------------------------------------------------------------------------
# Pocket TTS (Kyutai)
# --------------------------------------------------------------------------------------
class Pocket:
    def __init__(self, p):
        from pocket_tts import TTSModel
        want = {
            "temp": _f(p.get("temperature")),
            "temperature": _f(p.get("temperature")),
            "lsd_decode_steps": _i(p.get("lsd_decode_steps")),
            "eos_threshold": _f(p.get("eos_threshold")),
        }
        kw = pick_kwargs(TTSModel.load_model, want)
        # "temp" and "temperature" are the same knob across versions - never send both
        if "temp" in kw and "temperature" in kw:
            kw.pop("temperature")
        self.model = TTSModel.load_model(**kw)
        self.sr = int(getattr(self.model, "sample_rate", 24000))
        self.states = {}
        self.info = f"Pocket TTS on CPU ({self.sr} Hz)"

    def voice_state(self, voice):
        voice = (voice or "alba").strip()
        if voice not in self.states:
            try:
                self.states[voice] = self.model.get_state_for_audio_prompt(voice)
            except ValueError as e:
                if "voice cloning" in str(e).lower():
                    why = ("No Hugging Face token was found (HF_TOKEN in keys.env). " if not find_hf_token()
                           else "A token was found, but the cloning weights were not downloaded - "
                                "make sure you accepted the terms on the kyutai/pocket-tts page. ")
                    raise RuntimeError(why + CLONE_HELP) from None
                raise
        return self.states[voice]

    def say(self, text, out, p):
        state = self.voice_state(p.get("voice") or p.get("voice_ref"))
        audio = self.model.generate_audio(state, text)
        return save_wav(out, audio, self.sr)


def _f(v):
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        return None if v in (None, "") else int(float(v))
    except (TypeError, ValueError):
        return None


def _clone_selftest(model):
    """Feed a 1-second test tone through the voice encoder to see if cloning weights are present."""
    import tempfile
    import wave
    import math
    import struct
    path = os.path.join(tempfile.gettempdir(), "recap_pocket_clonetest.wav")
    try:
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 220 * i / 24000)))
                                   for i in range(24000)))
        model.get_state_for_audio_prompt(path)
        print("  voice cloning: READY", file=sys.stderr)
    except ValueError as e:
        if "voice cloning" in str(e).lower():
            print("  [!] voice cloning: NOT available yet. " + CLONE_HELP, file=sys.stderr)
        else:
            print(f"  (clone self-test inconclusive: {e})", file=sys.stderr)
    except Exception as e:
        print(f"  (clone self-test inconclusive: {type(e).__name__}: {e})", file=sys.stderr)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def download(spec):
    """SETUP.bat calls:  tts_worker.py --download chatterbox:nano,turbo   or   --download pocket"""
    kind, _, rest = spec.partition(":")
    if kind == "pocket":
        from pocket_tts import TTSModel
        if not find_hf_token():
            print("  [!] No HF_TOKEN found (env var or keys.env). Built-in voices will work, "
                  "but voice cloning will NOT.", file=sys.stderr)
        m = TTSModel.load_model()
        for v in ("alba", "marius", "javert", "jean", "fantine", "cosette", "eponine", "azelma"):
            try:
                m.get_state_for_audio_prompt(v)
                print(f"  voice {v} ready", file=sys.stderr)
            except Exception as e:
                print(f"  (voice {v} skipped: {e})", file=sys.stderr)
        _clone_selftest(m)
        print("Pocket TTS ready.", file=sys.stderr)
        return 0
    bad = 0
    for v in [x for x in rest.split(",") if x]:
        try:
            print(f"Downloading Chatterbox {v} ...", file=sys.stderr)
            Chatterbox({"variant": v, "device": "cpu"})
            print(f"Chatterbox {v} ready.", file=sys.stderr)
        except Exception as e:
            bad += 1
            print(f"[!] Chatterbox {v} failed: {e}", file=sys.stderr)
    return 1 if bad else 0


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--download":
        sys.exit(download(sys.argv[2]))
    engine = None
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            cmd = msg.get("cmd")
            if cmd == "quit":
                reply({"ok": True})
                return
            if cmd == "load":
                which = msg.get("engine")
                params = msg.get("params") or {}
                engine = Chatterbox(params) if which == "chatterbox" else Pocket(params)
                reply({"ok": True, "info": engine.info})
            elif cmd == "say":
                if engine is None:
                    raise RuntimeError("model not loaded")
                secs = engine.say(msg["text"], msg["out"], msg.get("params") or {})
                reply({"ok": True, "seconds": round(secs, 2)})
            else:
                reply({"ok": False, "error": "unknown command"})
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            reply({"ok": False, "error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    main()

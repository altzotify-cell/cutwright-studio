"""Narration for a blueprint: edge-tts audio + the WORD TIMINGS behind it (M8).

Why this is a script and not part of `cutwright/`: `.clinerules/01` keeps the agent package
stdlib-only (assumption A8). This file is the only place that imports `edge_tts`, and the engine
reaches it through `subprocess` (`cutwright/engine/blueprint.py:narrate`), the same boundary the
scene checker uses for node.

    python tools/narrate.py request.json

`request.json` = {"text": "...", "wav": "<abs path>", "voice": "...", "rate": "+0%"}

Writes, next to the wav:
  narration.mp3   what edge-tts returned (kept: it is the original of the voice)
  narration.wav   48 kHz stereo pcm_s16le - one format for every later op
  narration.json  {"seconds", "words": [{"word", "start", "end"}], ...}

The word timings are the point: they are what makes a beat end where its sentence ends instead of on
an average. edge-tts reports them as `WordBoundary` metadata during synthesis, in 100 ns ticks.
"""
import asyncio
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from cutwright import probe   # noqa: E402  (tiny ffprobe wrapper, stdlib only)

TICKS = 10_000_000.0        # edge-tts offsets are 100 ns units


def fail(message, code=2):
    print(json.dumps({"ok": False, "error": message}))
    return code


async def synthesize(text, voice, rate, mp3_path):
    """Audio bytes + word cues from one edge-tts request."""
    import edge_tts
    try:
        speech = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    except TypeError:                     # older edge-tts without the boundary argument
        speech = edge_tts.Communicate(text, voice, rate=rate)
    audio, words = bytearray(), []
    async for chunk in speech.stream():
        if chunk.get("type") == "audio":
            audio.extend(chunk["data"])
        elif chunk.get("type") == "WordBoundary":
            start = float(chunk.get("offset") or 0) / TICKS
            words.append({"word": str(chunk.get("text") or ""), "start": round(start, 4),
                          "end": round(start + float(chunk.get("duration") or 0) / TICKS, 4)})
    if not audio:
        raise RuntimeError("edge-tts returned no audio for %r" % voice)
    with open(mp3_path, "wb") as handle:
        handle.write(bytes(audio))
    return words


async def _synthesize_with_timeout(text, voice, rate, mp3_path):
    """`synthesize` bounded in time: a dead network must fail the run, not hang it."""
    return await asyncio.wait_for(synthesize(text, voice, rate, mp3_path), timeout=120)


def to_wav(mp3_path, wav_path):
    """mp3 -> 48 kHz stereo wav with ffmpeg, so every later audio op sees one format."""
    argv = ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", mp3_path,
            "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", wav_path]
    done = subprocess.run(argv, capture_output=True, text=True, timeout=300)
    if done.returncode != 0:
        raise RuntimeError("ffmpeg failed: %s" % (done.stderr or "").strip()[-400:])


def main(argv):
    if len(argv) < 2:
        return fail("usage: python tools/narrate.py request.json")
    with open(argv[1], "r", encoding="utf-8") as handle:
        request = json.load(handle)
    text = str(request.get("text") or "").strip()
    wav_path = os.path.abspath(request.get("wav") or "")
    if not text or not wav_path.endswith(".wav"):
        return fail("a request needs 'text' and a 'wav' path ending in .wav")
    os.makedirs(os.path.dirname(wav_path), exist_ok=True)
    mp3_path = os.path.splitext(wav_path)[0] + ".mp3"
    voice = str(request.get("voice") or "en-US-ChristopherNeural")
    rate = str(request.get("rate") or "+0%")
    try:
        words = asyncio.run(_synthesize_with_timeout(text, voice, rate, mp3_path))
        to_wav(mp3_path, wav_path)
    except ImportError:
        return fail("edge-tts is not installed: python -m pip install edge-tts")
    except Exception as error:                    # network, a bad voice, a refused request
        return fail("%s: %s" % (type(error).__name__, error))
    info = probe.media_info(wav_path)
    document = {"ok": True, "engine": "edge", "voice": voice, "rate": rate, "text": text,
                "seconds": float(info.get("duration") or 0.0),
                "source": os.path.basename(mp3_path), "words": words}
    with open(os.path.splitext(wav_path)[0] + ".json", "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(json.dumps({key: document[key] for key in ("ok", "engine", "voice", "seconds")} |
                     {"words": len(words)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

# Recap Studio

Local studio for making recap videos: collect footage, write the script with Claude, generate the voice-over, and render.

## Voice engines (all optional, installed from `SETUP.bat`)

| Engine | Runs | Cloning | Notes |
|---|---|---|---|
| Edge-TTS | online, free | no | many voices |
| Kokoro | offline, any CPU | no | ~350 MB |
| Pocket TTS | offline, any CPU | yes | English, 8 built-in voices |
| Chatterbox | offline | yes | Nano 110M / Turbo 350M / Original 500M / Multilingual 500M, `[laugh]` tags |
| ElevenLabs / MiniMax | online, paid | - | add your key in the app |

## Install (Windows)

1. Double-click `SETUP.bat`. It installs the base tools, then asks which voice engines and models to download.
2. Copy `keys.env.example` to `keys.env` if you use ElevenLabs or MiniMax (or paste keys in the app's API keys screen).
3. Double-click `START_UI.bat`.

Run `SETUP.bat` again at any time to add engines. Chatterbox needs Python 3.11 or 3.10; Nano is installed from the GitHub `master` branch because the PyPI release does not include it yet.

## Character animation

Add transparent PNG cut-outs in the **Characters** tab (or `characters/` in a project). A segment with `"character": "name"` shows the character in a corner over the clip; a `"commentary": true` segment with no footage becomes a solo scene (character centered on a background). A `talk` pose follows the voice-over. In the Premiere XML and VideoPad project the character is its own video track; the mp4 / TikTok builds bake it in. Fields: `character`, `char_pos`, `char_layout`, `char_pose`, `char_anim`, `char_enter`, `char_exit`, `char_bg`, `char_scale`, `char_flip`, `char_outline`, `char_shadow`, `char_x`, `char_y`. Needs Pillow (installed by `SETUP.bat`).

## Pocket TTS voice cloning (one-time setup)

Cloning uses Kyutai's gated weights. Built-in Pocket voices work without this.

1. Accept the terms at https://huggingface.co/kyutai/pocket-tts ("Agree and access repository").
2. Create a Read token at https://huggingface.co/settings/tokens.
3. Paste the token in the app under **🔑 API keys → Hugging Face token** (or add `HF_TOKEN=hf_yourtoken` to `keys.env`).
4. Run `SETUP.bat` and pick Pocket TTS again (or `venvs\pocket\Scripts\python tts_worker.py --download pocket`). It prints `voice cloning: READY` when it worked.

## Reference clip format

Use a **16-bit WAV** for voice cloning (5-15 s, one speaker). The app's **Upload clip** button converts mp3/m4a/flac/ogg to WAV automatically (needs ffmpeg), and non-WAV files dropped into `voices/` are converted when you generate.

If Pocket TTS reports `soundfile is required to read non-WAV or non-16-bit WAV audio files`, either install the helper once (new Pocket installs from `SETUP.bat` already include it):

```
venvs\pocket\Scripts\python -m pip install soundfile
```

or convert the clip yourself:

```
ffmpeg -i myclip.mp3 -ac 1 -ar 24000 -c:a pcm_s16le myclip.wav
```

## Notes

- Chatterbox output carries Resemble AI's Perth watermark.
- Only clone voices you have the right to use. Reference clips go in `voices/` (git-ignored).
- Models and engines live in `models/` and `venvs/` (git-ignored); do not move the folder after running setup.
- Each engine and model has its own license; check them before redistributing audio or models.

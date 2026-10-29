REFERENCE VOICES (voice cloning)
================================
Drop a clean recording of the voice you want to clone in this folder.

AUDIO FORMAT: use a plain 16-bit WAV (.wav). That is the format voice cloning reads reliably.
  - The Upload button in the app converts any clip (mp3, m4a, flac, ogg) to WAV for you (needs ffmpeg, which the app has).
  - A non-WAV file you drop in this folder by hand is converted automatically when you generate.
  - If you ever see "soundfile is required to read non-WAV or non-16-bit WAV audio files", do ONE of these:

    Option 1 - install soundfile once (then mp3/flac/ogg/m4a are read directly). In the Recap Studio folder,
               open a terminal (click the address bar, type cmd, press Enter) and run:
                   venvs\pocket\Scripts\python -m pip install soundfile
               then restart START_UI.bat. (SETUP.bat now installs it for new Pocket installs.)

    Option 2 - convert the clip to a normal WAV with FFmpeg and put the .wav in this folder:
                   ffmpeg -i myclip.mp3 -ac 1 -ar 24000 -c:a pcm_s16le myclip.wav

Good reference clip:  5-15 seconds, ONE speaker, no music or background noise, normal speaking pace,
                      no echo. The model copies the tone and pacing of the clip, so a calm clip gives a calm narrator.

Then in Recap Studio: Voice tab -> engine Chatterbox or Pocket TTS -> type the file name (no extension needed)
into "Reference voice" - or use the Upload button there, which puts the file in this folder for you.

Only clone voices you have the right to use (your own, or with the speaker's permission).

POCKET TTS CLONING NEEDS A HUGGING FACE TOKEN (one time, free)
  1) Accept the terms at https://huggingface.co/kyutai/pocket-tts  ("Agree and access repository")
  2) Make a Read token at https://huggingface.co/settings/tokens
  3) Recap Studio -> API keys -> Hugging Face token -> paste -> Save (or HF_TOKEN=hf_... in keys.env)
  4) Restart START_UI.bat.  Chatterbox cloning does not need this.

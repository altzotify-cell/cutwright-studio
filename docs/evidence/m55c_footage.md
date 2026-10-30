# M5.5C benchmark footage - provenance

The directed benchmark shot needs REAL footage (the M5.5B note "does it look like real footage cannot be
judged here - a real clip is needed" is what this closes).

**Local path**: `recapstudio/Projects/regress/footage/real_sample.mp4` - NOT tracked by git
(`recapstudio/.gitignore` ignores `Projects/*`: project media is per-machine working data). Re-create it with
the command below if the folder is fresh.

- **File**: 1588x892, 30 fps, 240 frames, 8.000 s, H.264, no audio, 885,128 B.
- **Source**: NASA/JPL-Caltech imagery from the Perseverance rover, posted by Andrea Luck on Wikimedia
  Commons as *"Video - Pre - Sunrise on Mars a few hours ago NASA's Perseverance Rover SOL 738
  (52757034776).webm"* (1080p VP9 derivative, 6.0 MB, 30.4 s).
  <https://commons.wikimedia.org/wiki/File:Video_-_Pre_-_Sunrise_on_Mars_a_few_hours_ago_NASA%27s_Perseverance_Rover_SOL_738_(52757034776).webm>
- **Licence**: Public domain (read from the Commons API `extmetadata.LicenseShortName`).
- **What it is**: the Martian sky a few hours before sunrise - real recorded footage, not a render and not
  AI-generated. Ridge line as a silhouette along the bottom, thin clouds drifting right of centre. That is
  the `ai_generated_images: false` constraint satisfied by construction, not by promise.
- **Preparation** (reproducible; the host rate-limits `Invoke-WebRequest`, `curl.exe` works):

  ```powershell
  curl.exe -sSL -A "CutwrightBench/1.0" -o src.webm "<the .1080p.vp9.webm URL from the page above>"
  ffmpeg -y -ss 1.5 -t 8 -i src.webm -an -vf "crop=1588:893:0:187" `
         -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p -movflags +faststart real_sample.mp4
  ```

  Why the crop: the 1080p source is 1588x1080 (1.47:1) and it is the ONLY 1080p derivative. Rendered into a
  16:9 frame with `object-fit: cover` it loses ~112 px off the top AND the bottom - which removes the ridge,
  the one dark foreground band the type needs for contrast. So the 16:9 framing is baked in here (crop 893
  rows, keep the bottom) and the scene does not fake it with a zoom, which would also soften the picture.
  One file serves many shots: the scene reads it from `startFrom`.

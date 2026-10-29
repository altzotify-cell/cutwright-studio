@echo off
cd /d "%~dp0"
title Recap Studio - Setup
echo.
echo  RECAP STUDIO SETUP
echo  Everything is installed from here: base tools first, then YOU choose which voice engines
echo  and models to download. Run this file again any time to add more.
echo.

echo [1/4] Checking Python...
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto nopython
%PY% --version

echo.
echo [2/4] Installing base packages (requests, yt-dlp, pillow, numpy, pymupdf)...
%PY% -m pip install --upgrade requests yt-dlp pillow numpy pymupdf
if errorlevel 1 goto pipfail

echo.
echo [3/4] Checking FFmpeg...
where ffmpeg >nul 2>nul
if errorlevel 1 goto noffmpeg
where ffprobe >nul 2>nul
if errorlevel 1 goto noffmpeg
echo FFmpeg OK.

echo.
echo [4/4] Node.js + Remotion renderer (optional - for animated captions and motion graphics)...
where node >nul 2>nul
if errorlevel 1 goto nonode
node --version
if exist "%~dp0remotion\package.json" (
    pushd "%~dp0remotion"
    call npm install
    if errorlevel 1 echo [!] npm install failed - Remotion is optional, the normal video build still works.
    popd
)
goto afternode
:nonode
echo Node.js not found - installing with winget (optional)...
winget install -e --id OpenJS.NodeJS.LTS
echo Close this window and run SETUP.bat again so Node.js is on PATH. Remotion stays off until then.
:afternode
echo.
echo Optional: exact caption word timings for non-Edge voices (Kokoro, ElevenLabs...) - local Whisper.
%PY% -m pip install --upgrade faster-whisper
if errorlevel 1 echo [!] faster-whisper not installed - captions will use estimated timings for non-Edge voices. Edge-TTS is exact either way.

echo.
%PY% setup_engines.py
echo.
echo ===== Setup finished. Double-click NEW_PROJECT.bat to start. =====
goto end

:nopython
echo Python not found - installing with winget...
winget install -e --id Python.Python.3.12
echo.
echo Close this window and run SETUP.bat again once the install finishes.
goto end

:pipfail
echo [!] pip failed. Check your internet connection and try again.
goto end

:noffmpeg
echo FFmpeg not found - installing with winget...
winget install -e --id Gyan.FFmpeg
echo.
echo Close this window and run SETUP.bat again so FFmpeg is on PATH.

:end
echo.
pause

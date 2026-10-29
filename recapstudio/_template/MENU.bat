@echo off
setlocal
cd /d "%~dp0"
title Recap Studio
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
set "MODULE=movie_recap"
if defined PY for /f "delims=" %%m in ('%PY% recap.py module') do set "MODULE=%%m"
set "RECAP=0"
set "COMIC=0"
if "%MODULE%"=="movie_recap" set "RECAP=1"
if "%MODULE%"=="show_recap" set "RECAP=1"
if "%MODULE%"=="comic_recap" set "COMIC=1"
:menu
cls
echo ==============================================
echo   RECAP STUDIO      [%MODULE%]
echo ==============================================
echo.
if "%RECAP%"=="1" echo   1  Extract subtitles from video
if "%COMIC%"=="1" echo   21 Import comic / manga       (.cbz .cbr .pdf - makes the numbered PDF for Claude)
if "%RECAP%%COMIC%"=="00" echo   13 Collect footage            (guided: paste links / drag files)
if "%RECAP%%COMIC%"=="00" echo   12 Index footage              (contact sheets for every clip)
if "%COMIC%"=="0" echo   2  Make contact sheets        (segments marked need_visual)
echo.
echo   22 Check characters          (PNG cut-outs in characters\ + preview picture)
echo   15 Export narration sheet     (review / edit text + tags in Excel)
echo   16 Import narration edits
echo   14 Preview voice              (first 3 segments, before spending credits)
echo   3  Generate voice-over        (only new / edited segments are re-voiced)
echo.
echo   4  Build Premiere XML         (also writes .srt, chapters, shot list)
echo   19 Build VideoPad project     (.vpj - same timeline for VideoPad)
echo   20 VideoPad project, simple   (fallback: picture + voice only)
if "%RECAP%%COMIC%"=="10" echo   5  Build FULL VIDEO           (one finished .mp4)
if "%COMIC%"=="1" echo   5  Build FULL VIDEO           (camera moves over the panels -> one .mp4)
if "%RECAP%%COMIC%"=="10" echo   23 Build timeline.json         (contract for the Remotion renderer)
if "%RECAP%%COMIC%"=="10" echo   24 Render with Remotion        (-^> recap_remotion.mp4, needs Node - see SETUP)
if "%RECAP%%COMIC%"=="10" echo   25 Check scenes               (custom scenes: safety check + test render, falls back if broken)
if "%RECAP%%COMIC%"=="10" echo   26 Preview scenes             (opens Remotion Studio: one scene at a time, 16:9 and 9:16)
if "%RECAP%%COMIC%"=="10" echo   27 Demo scenes                (use in a DEMO project: 3 good + 3 deliberately broken scenes)
if "%RECAP%%COMIC%"=="10" echo   28 Scene prompt for Claude    (pass 2: briefs -^> SCENE_AUTHORING_PROMPT.txt; imports SCENE_REPLY.txt)
if "%RECAP%%COMIC%"=="10" echo   29 Demo briefs                (use in a DEMO project: 3 motion briefs + a theme, to test the Claude round trip)
echo   6  Build subtitles only       (.srt for Premiere)
if "%RECAP%%COMIC%"=="10" echo   7  Build TikTok videos        (also writes .srt per part)
if "%COMIC%"=="1" echo   7  Build TikTok videos        (9:16, also writes .srt per part)
echo.
echo   8  Change voice / engine, then generate
echo   9  Redo ALL audio from scratch
echo   10 Status check               (also updates STATE.md)
echo   11 Open this folder
echo   17 Project settings           (module, target length, voice mode)
echo   18 Demo / test media          (use in a FRESH project)
echo   0  Exit
echo.
set "C="
set /p "C=Pick a number: "
if "%C%"=="1" call "%~dp0_run.bat" subs
if "%C%"=="2" call "%~dp0_run.bat" sheets
if "%C%"=="3" call "%~dp0_run.bat" tts
if "%C%"=="4" call "%~dp0_run.bat" premiere
if "%C%"=="5" call "%~dp0_run.bat" video
if "%C%"=="6" call "%~dp0_run.bat" srt
if "%C%"=="7" call "%~dp0_run.bat" tiktok
if "%C%"=="8" call "%~dp0_run.bat" tts --pick
if "%C%"=="9" call "%~dp0_run.bat" tts --force
if "%C%"=="10" call "%~dp0_run.bat" check
if "%C%"=="11" start "" "%~dp0"
if "%C%"=="12" call "%~dp0_run.bat" index
if "%C%"=="13" call "%~dp0_run.bat" collect
if "%C%"=="14" call "%~dp0_run.bat" tts --preview
if "%C%"=="15" call "%~dp0_run.bat" review
if "%C%"=="16" call "%~dp0_run.bat" review --import
if "%C%"=="17" call "%~dp0_run.bat" init
if "%C%"=="18" call "%~dp0_run.bat" demo
if "%C%"=="19" call "%~dp0_run.bat" videopad
if "%C%"=="20" call "%~dp0_run.bat" videopad --simple
if "%C%"=="21" call "%~dp0_run.bat" comic
if "%C%"=="22" call "%~dp0_run.bat" characters
if "%C%"=="23" call "%~dp0_run.bat" timeline
if "%C%"=="24" call "%~dp0_run.bat" remotion
if "%C%"=="25" call "%~dp0_run.bat" scenes
if "%C%"=="26" call "%~dp0_run.bat" preview
if "%C%"=="27" call "%~dp0_run.bat" scenes --demo
if "%C%"=="28" call "%~dp0_run.bat" briefs
if "%C%"=="29" call "%~dp0_run.bat" briefs --demo
if "%C%"=="0" exit /b
goto menu

@echo off
title TeamSpeak 6 MusicBot
cd /d "%~dp0bot"

if not exist "yt-dlp.exe" (
    echo [INFO] Downloading yt-dlp.exe...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe' -OutFile 'yt-dlp.exe'"
)

if not exist "ffmpeg.exe" (
    echo [INFO] ffmpeg.exe not found in bot directory.
    echo Please ensure ffmpeg is installed or download ffmpeg.exe into this folder.
)

echo Starting TeamSpeak 6 MusicBot...
TS3AudioBot.exe --non-interactive
pause

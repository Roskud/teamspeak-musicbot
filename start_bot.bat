@echo off
title TeamSpeak 6 MusicBot (Yandex.Music & Radio)
cd /d "%~dp0bot"

echo ============================================================
echo   Запуск TeamSpeak 6 MusicBot (Яндекс.Музыка и Радио)
echo ============================================================

if not exist "ffmpeg.exe" (
    echo [INFO] ffmpeg.exe не найден в папке бота.
    echo Пожалуйста, убедитесь, что ffmpeg установлен.
)

echo [1/2] Запуск шлюза Яндекс.Музыки...
start "YandexMusicBridge" python ym_bridge.py

echo [2/2] Запуск TS3AudioBot...
TS3AudioBot.exe --non-interactive
pause

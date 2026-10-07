@echo off
title Start TeamSpeak 6 Server and VibeSpeak
echo ============================================================
echo   Запуск локального TeamSpeak сервера и VibeSpeak
echo ============================================================

cd /d "%~dp0"
echo 1. Запуск сервера TeamSpeak 3/6...
start "" call start_server.bat

echo Ожидание инициализации сервера (4 сек)...
timeout /t 4 /nobreak >nul

echo 2. Запуск VibeSpeak...
start "VibeSpeak Console" call start_bot.bat

echo.
echo ============================================================
echo  Сервер запущен: localhost:9987
echo  Веб-интерфейс бота: http://localhost:58913
echo  Ключ администратора сервера сохранен в: server\credentials.txt
echo ============================================================
pause

@echo off
title TeamSpeak 3 Local Server
cd /d "%~dp0"
echo Starting TeamSpeak 3 Server...
start "" ts3server.exe
echo Server started! You can connect to localhost:9987 in TeamSpeak Client.

@echo off
:: Launch the CETUS Pexels Media Downloader GUI
cd /d "%~dp0.."
call .venv\Scripts\python.exe tools\pexels_gui.py

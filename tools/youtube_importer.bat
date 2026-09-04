@echo off
:: Launch the CETUS YouTube Media Importer GUI
cd /d "%~dp0.."
call .venv\Scripts\python.exe tools\youtube_gui.py

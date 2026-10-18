@echo off
rem Double-click to preview: renders every made-up sample day (no internet needed)
rem plus today's real Grand Rapids forecast, then opens the folder.
cd /d "%~dp0"
echo Rendering sample days...
python generator\make_dashboard.py --sample all --out preview
echo.
echo Rendering today's real forecast...
python generator\make_dashboard.py --out preview\live
start "" "preview"
echo.
pause

@echo off
rem ============================================================
rem  Halo PixelBar toolkit - Windows launcher
rem
rem  Usage:
rem    run.cmd                -> doctor (preflight check)
rem    run.cmd selftest       -> offline self test
rem    run.cmd anims cat      -> switch animation
rem    run.cmd --help         -> all commands
rem
rem  Why this launcher exists:
rem   1) Python prints UTF-8 while a Chinese Windows console defaults
rem      to GBK, so running python directly shows mojibake. We switch
rem      the console to 65001 first.
rem   2) It turns "python not found" and "dependency missing" into
rem      one clear line instead of a traceback.
rem
rem  NOTE: keep this file ASCII-only. cmd.exe parses .cmd files using
rem  the OEM codepage (GBK on Chinese Windows), so non-ASCII text in
rem  here gets misread and breaks the script. All user-facing Chinese
rem  text lives in the Python side.
rem ============================================================
setlocal
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"

set PY=
for %%P in (python.exe py.exe) do (
  if not defined PY (
    where %%P >nul 2>&1 && set PY=%%P
  )
)

if not defined PY (
  echo [FAIL] Python not found. Install Python 3.10+ and tick
  echo        "Add python.exe to PATH".  https://www.python.org/downloads/
  exit /b 1
)

%PY% -c "import hid, PIL" >nul 2>&1
if errorlevel 1 (
  echo [INFO] Installing dependencies: hidapi pillow ...
  %PY% -m pip install --user --quiet hidapi pillow
  if errorlevel 1 (
    echo [FAIL] Install failed. Run manually:
    echo        %PY% -m pip install --user hidapi pillow
    echo        Package name is hidapi, NOT the PyPI package "hid".
    exit /b 1
  )
)

if "%~1"=="" (
  %PY% pixelbar.py doctor
  exit /b %errorlevel%
)

%PY% pixelbar.py %*
exit /b %errorlevel%

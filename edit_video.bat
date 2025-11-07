@echo off
REM Simple video editor runner

echo ========================================
echo Auto Video Editor
echo ========================================
echo.

REM Check for manifest
if not exist "manifest.json" (
    echo Creating manifest from example...
    copy manifest.example.json manifest.json
    echo.
    echo Please edit manifest.json with your video path!
    echo Then run this script again.
    echo.
    pause
    exit /b 1
)

echo Running video editor...
echo.

REM Create directories
if not exist "downloads" mkdir downloads
if not exist "edited" mkdir edited
if not exist "work" mkdir work

REM Run editor (auto-detection happens inside auto_edit.py)
py auto_edit.py --manifest manifest.json --work-dir work --resume

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo SUCCESS! Video edited successfully!
    echo ========================================
    echo.
    echo Check the 'edited' folder for your video.
    echo.
) else (
    echo.
    echo ========================================
    echo FAILED! Check error messages above.
    echo ========================================
    echo.
)

pause

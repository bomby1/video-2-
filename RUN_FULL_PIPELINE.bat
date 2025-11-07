@echo off
REM Full Video Production Pipeline
REM Runs: Video Generation → Editing → YouTube Upload

echo ========================================
echo Full Video Production Pipeline
echo ========================================
echo.
echo This will run:
echo   1. Video Generation (CapCut AI)
echo   2. Video Editing (FFmpeg + AI)
echo   3. YouTube Upload
echo.
echo Press Ctrl+C to cancel, or
pause

REM Run the full pipeline (has 30-second countdown before auto-close)
py run_full_pipeline.py

@echo off
REM Upload edited video to YouTube with AI-generated metadata

echo ========================================
echo YouTube Video Uploader
echo ========================================
echo.

REM Upload the latest edited video (auto-detects video, metadata, and subtitles)
REM Default: public, with hashtags in description
py youtube_uploader.py --video AUTO --privacy public

echo.
echo ========================================
echo Upload Complete!
echo ========================================
pause

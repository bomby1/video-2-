@echo off
setlocal enabledelayedexpansion

:: Display header
echo ========================================
echo     Git Repository Force Push Script
echo     (Replaces ALL Remote Content)
echo ========================================
echo.

:: Get user inputs
set /p USERNAME="Enter your GitHub username: "
set /p EMAIL="Enter your GitHub email: "
set /p REPO_NAME="Enter repository name (e.g., my-repo): "

:: Validate inputs
if "%USERNAME%"=="" (
    echo Error: Username cannot be empty!
    pause
    exit /b 1
)
if "%EMAIL%"=="" (
    echo Error: Email cannot be empty!
    pause
    exit /b 1
)
if "%REPO_NAME%"=="" (
    echo Error: Repository name cannot be empty!
    pause
    exit /b 1
)

:: Construct repository URL
set REPO_URL=https://github.com/%USERNAME%/%REPO_NAME%.git

echo.
echo Configuration:
echo - Username: %USERNAME%
echo - Email: %EMAIL%
echo - Repository: %REPO_NAME%
echo - URL: %REPO_URL%
echo.

:: Ask for confirmation
set /p CONFIRM="WARNING: This will REPLACE ALL files in the remote repository! Continue? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo Operation cancelled.
    pause
    exit /b 0
)

echo.
echo Starting Git operations...
echo.

:: Configure Git user
echo Configuring Git user...
git config user.name "%USERNAME%"
git config user.email "%EMAIL%"

:: Check if .git exists and handle accordingly
if exist .git (
    echo Removing existing .git folder...
    rmdir /s /q .git
)

:: Initialize new Git repository
echo Initializing Git repository...
git init

:: Add ALL files including hidden files
echo.
echo Adding ALL files (including hidden files)...
:: This command adds everything, including dot files
git add . --force
git add * --force 2>nul
:: Specifically add hidden files
for /f "delims=" %%i in ('dir /b /a:h 2^>nul') do (
    git add "%%i" --force 2>nul
)

:: Show what will be committed
echo.
echo Files to be uploaded:
git status --short

:: Commit files
echo.
echo Committing all files...
set COMMIT_MSG="Force push - replacing all content - %date% %time%"
git commit -m %COMMIT_MSG%

:: Add remote origin
echo.
echo Adding remote repository...
git remote add origin %REPO_URL% 2>nul
if !ERRORLEVEL! neq 0 (
    git remote set-url origin %REPO_URL%
)

:: Try to push to main branch first
echo.
echo Force pushing to main branch (replacing all remote content)...
git branch -M main
git push -u origin main --force

:: Check if push was successful, if not try master
if %ERRORLEVEL% neq 0 (
    echo.
    echo Main branch failed, trying master branch...
    git branch -M master
    git push -u origin master --force
    
    if !ERRORLEVEL! neq 0 (
        echo.
        echo ========================================
        echo ERROR: Push failed!
        echo.
        echo Possible reasons:
        echo 1. Repository doesn't exist on GitHub
        echo 2. Authentication failed (wrong credentials)
        echo 3. No internet connection
        echo 4. Need to use Personal Access Token instead of password
        echo.
        echo To fix authentication:
        echo - Create a Personal Access Token on GitHub
        echo - Use the token as your password when prompted
        echo ========================================
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo SUCCESS! All files have been force pushed!
echo.
echo What happened:
echo - ALL previous files in remote repo were REPLACED
echo - ALL local files (including hidden) were uploaded
echo - Repository URL: %REPO_URL%
echo ========================================
echo.

:: Optional: Show what was pushed
echo Files that were pushed:
git ls-files

echo.
set /p OPEN_BROWSER="Open repository in browser? (Y/N): "
if /i "%OPEN_BROWSER%"=="Y" (
    start https://github.com/%USERNAME%/%REPO_NAME%
)

echo.
echo Operation completed!
pause
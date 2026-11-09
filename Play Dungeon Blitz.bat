@echo off
rem Dungeon Blitz launcher: installs what is missing (Node.js, the server's packages,
rem Flash Browser), starts the server (src\server) and opens the home page in Flash Browser.
setlocal EnableExtensions EnableDelayedExpansion
title Dungeon Blitz Launcher
set "ROOT=%~dp0"
set "SERVER=%ROOT%src\server"
rem Flash Browser opens only a local file named on its command line (and only one whose
rem name contains ".swf"), never a web address: launcher.swf.html forwards to the home
rem page (http://localhost:8000/home), which has the Play button
set "HOME_PAGE=%ROOT%launcher.swf.html"

echo.
echo  === Dungeon Blitz ===
echo.

rem ---------------------------------------------------------------- Node.js
where node >nul 2>nul
if errorlevel 1 (
    echo [1/4] Node.js not found: installing it ...
    where winget >nul 2>nul && winget install -e --id OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
    set "PATH=%PATH%;%ProgramFiles%\nodejs"
)
where node >nul 2>nul
if errorlevel 1 (
    echo.
    echo Could not install Node.js. Install it from https://nodejs.org/ and run this again.
    pause
    exit /b 1
)
for /f "delims=" %%V in ('node --version') do echo [1/4] Node.js: %%V

rem ---------------------------------------------------------------- server packages
if not exist "%SERVER%\node_modules" (
    echo [2/4] Installing the server's packages ^(first run only^) ...
    pushd "%SERVER%"
    call npm install --no-audit --no-fund
    popd
    if not exist "%SERVER%\node_modules" (
        echo Could not install the server's packages. Check your internet connection and run this again.
        pause
        exit /b 1
    )
)
echo [2/4] Server packages: ready

rem ---------------------------------------------------------------- Flash Browser
call :find_flash_browser
if not defined FB (
    echo [3/4] Flash Browser not found: downloading the latest release ...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$r = Invoke-RestMethod 'https://api.github.com/repos/radubirsan/FlashBrowser/releases/latest';" ^
        "$a = $r.assets | Where-Object { $_.name -like '*.exe' } | Select-Object -First 1;" ^
        "if (-not $a) { exit 1 };" ^
        "Invoke-WebRequest $a.browser_download_url -OutFile \"$env:TEMP\FlashBrowserSetup.exe\""
    if exist "%TEMP%\FlashBrowserSetup.exe" (
        echo       Installing Flash Browser ...
        "%TEMP%\FlashBrowserSetup.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
    )
    call :find_flash_browser
)
if not defined FB (
    echo.
    echo Could not install Flash Browser. Get it from https://github.com/radubirsan/FlashBrowser/releases
    echo and run this again.
    pause
    exit /b 1
)
echo [3/4] Flash Browser: !FB!

rem ---------------------------------------------------------------- Server
netstat -ano | findstr /R /C:"127\.0\.0\.1:8000 .*LISTENING" >nul
if errorlevel 1 (
    echo [4/4] Starting the server ...
    if not exist "%ROOT%logs" mkdir "%ROOT%logs"
    rem the server writes logs\server.log itself (src\server\tools\modLog.js)
    start "Dungeon Blitz Server" /D "%SERVER%" cmd /k node tools\runDevServer.js
) else (
    echo [4/4] The server is already running.
)

rem wait for the server to answer (up to 90 seconds)
set /a TRIES=0
:wait_server
curl -s -o nul http://localhost:8000/home >nul 2>nul
if not errorlevel 1 goto server_up
set /a TRIES+=1
if !TRIES! geq 90 (
    echo The server did not start. Look at the "Dungeon Blitz Server" window for the error.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_server

:server_up
echo.
echo Opening Dungeon Blitz ...
start "" "!FB!" "%HOME_PAGE%"
echo Have fun! Close the "Dungeon Blitz Server" window to stop the server.
timeout /t 5 >nul
exit /b 0

rem ================================================================ helpers
:find_flash_browser
set "FB="
for %%D in ("%ProgramFiles(x86)%\FlashBrowser" "%ProgramFiles%\FlashBrowser" "%LOCALAPPDATA%\Programs\FlashBrowser" "%LOCALAPPDATA%\Programs\flash-browser") do (
    if not defined FB if exist "%%~D\FlashBrowser.exe" set "FB=%%~D\FlashBrowser.exe"
)
exit /b 0

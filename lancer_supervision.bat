@echo off
echo Starting SupervisionBroadcast...

REM Go to project directory
cd /d "%~dp0"

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Force Qt to use correct system plugins (avoids bugs with OpenCV)
set QT_QPA_PLATFORM_PLUGIN_PATH=C:\Qt\5.15.2\msvc2019_64\plugins\platforms

REM Launch application
python main.py

pause 
@echo off
chcp 65001 > nul
echo CocoroCore Build Tool

REM Activate virtual environment
echo Activating virtual environment...
call .\.venv\Scripts\activate

REM Check Python version
python -c "import sys; print(f'Python {sys.version}')"

REM Execute build script
echo Running build script...
python build_cocoro.py

REM Deactivate virtual environment
call deactivate

echo.
echo Build process completed. Press any key to exit.

@echo off
REM Create and activate a virtual environment, then install requirements
python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo Virtual environment created and dependencies installed.

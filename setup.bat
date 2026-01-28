@echo off

REM ===== Check if .venv already exists =====
if exist ".venv\" (
    echo =====================================
    echo ERROR: Virtual environment .venv exists
    echo Please delete it first or reuse it.
    echo =====================================
    pause
    exit /b
)

echo ================================
echo Create Python Virtual Environment
echo ================================

REM Create .venv
python -m venv .venv

REM Activate .venv
call .venv\Scripts\activate

echo ================================
echo Upgrade pip
echo ================================
python -m pip install --upgrade pip

echo ================================
echo Install requirements.txt
echo ================================
pip install -r requirements.txt

echo ================================
echo Install Playwright browsers
echo ================================
playwright install

echo ================================
echo DONE ✅
echo To activate .venv later, run:
echo .venv\Scripts\activate
echo ================================

pause

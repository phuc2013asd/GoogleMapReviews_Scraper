@echo off
echo ================================
echo Create Python Virtual Environment
echo ================================

REM Tạo .venv
python -m venv .venv

REM Kích hoạt .venv
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

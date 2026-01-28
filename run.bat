call .venv\Scripts\activate
echo .venv activated!
cd code

:menu
echo.
echo Available Python scripts:
setlocal enabledelayedexpansion
set count=0
for /f "delims=" %%f in ('dir /b *.py') do (
    set /a count+=1
    echo !count!. %%f
)
echo.

set /p choice="Enter script number to run: "

setlocal enabledelayedexpansion
set count=0
for /f "delims=" %%f in ('dir /b *.py') do (
    set /a count+=1
    if !count! equ %choice% (
        python %%f
        goto menu
    )
)
echo Invalid choice.
goto menu

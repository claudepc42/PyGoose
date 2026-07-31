@echo off
echo Building PyGoose...
python -m PyInstaller PyGoose.spec --noconfirm --clean

if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Copying user assets to dist...
xcopy /e /i /y "assets\images\memes"         "dist\PyGoose\assets\images\memes"
xcopy /e /i /y "assets\text\notepad_messages" "dist\PyGoose\assets\text\notepad_messages"

echo.
echo Done. Distribution is ready at dist\PyGoose\
pause

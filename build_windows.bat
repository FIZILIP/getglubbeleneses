@echo off
echo ================================================
echo   GET CLUB - Compilador de Instalador Windows
echo ================================================
echo.

set PATH=%PATH%;%LOCALAPPDATA%\Python\pythoncore-3.14-64\Scripts

echo [1/3] A instalar dependencias...
pip install flask flask-sqlalchemy flask-login werkzeug sqlalchemy pillow matplotlib pyinstaller --quiet

echo [2/3] A compilar a aplicacao (PyInstaller)...
pyinstaller --noconfirm --onedir --windowed ^
  --name "GETCLUB" ^
  --icon "static\img\getclub-logo.ico" ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "app.py;." ^
  --add-data "models.py;." ^
  --add-data "license.py;." ^
  --hidden-import flask ^
  --hidden-import flask_sqlalchemy ^
  --hidden-import flask_login ^
  --hidden-import sqlalchemy ^
  --hidden-import sqlalchemy.dialects.sqlite ^
  --hidden-import werkzeug ^
  --hidden-import werkzeug.security ^
  --hidden-import werkzeug.utils ^
  --hidden-import jinja2 ^
  --hidden-import click ^
  --hidden-import itsdangerous ^
  --hidden-import PIL ^
  --hidden-import PIL.Image ^
  --hidden-import matplotlib ^
  --hidden-import matplotlib.backends.backend_pdf ^
  --hidden-import importlib.util ^
  --collect-all flask ^
  --collect-all flask_sqlalchemy ^
  --collect-all flask_login ^
  --collect-all sqlalchemy ^
  --collect-all werkzeug ^
  --collect-all jinja2 ^
  --exclude-module tkinter ^
  --exclude-module pyiceberg ^
  --exclude-module supabase ^
  launcher.py

if errorlevel 1 (
    echo [ERRO] Falha na compilacao com PyInstaller.
    pause
    exit /b 1
)

echo [3/3] Compilacao concluida!
echo.
echo Abre o ficheiro setup_getclub.iss no Inno Setup e clica Build Compile
echo O instalador sera gerado em: installer_output\GETCLUB_Setup_v1.0.exe
echo.
echo ================================================
pause

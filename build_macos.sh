#!/usr/bin/env bash
set -euo pipefail

APP_NAME="GETCLUB"
BUNDLE_NAME="${APP_NAME}.app"
DMG_NAME="${APP_NAME}_macOS.dmg"
PKG_NAME="${APP_NAME}_Installer_macOS.pkg"
ICON_ICNS="static/img/getclub-logo.icns"
WORK_PATH="/private/tmp/getclub-pyinstaller-work"
DIST_PATH="$(pwd)/dist"
DMG_STAGING_DIR="/private/tmp/getclub-dmg-staging"
export PYINSTALLER_CONFIG_DIR="/private/tmp/getclub-pyinstaller-config"
export MPLCONFIGDIR="/private/tmp/getclub-mplconfig"
mkdir -p "${PYINSTALLER_CONFIG_DIR}" "${MPLCONFIGDIR}" "${WORK_PATH}"

echo "==============================================="
echo " GETCLUB - Build macOS ARM64 (.app + .dmg + .pkg)"
echo "==============================================="
echo "Arquitetura: $(uname -m)"

if [[ ! -f "launcher.py" || ! -f "app.py" ]]; then
  echo "Erro: execute na raiz do projecto."
  exit 1
fi

echo "[1/5] A limpar builds anteriores..."
rm -rf "${WORK_PATH}" dist build GETCLUB.spec "GETCLUB 2.spec" "GETCLUB 3.spec"
mkdir -p "${DIST_PATH}"

echo "[2/5] A compilar com PyInstaller para arm64..."
pyinstaller --noconfirm --windowed \
  --name "${APP_NAME}" \
  --target-arch arm64 \
  --distpath "${DIST_PATH}" \
  --workpath "${WORK_PATH}" \
  --add-data "templates:templates" \
  --add-data "static:static" \
  --hidden-import app \
  --hidden-import models \
  --hidden-import license \
  --hidden-import database \
  --hidden-import flask \
  --hidden-import flask_sqlalchemy \
  --hidden-import flask_login \
  --hidden-import sqlalchemy \
  --hidden-import sqlalchemy.dialects.sqlite \
  --hidden-import werkzeug \
  --hidden-import werkzeug.security \
  --hidden-import werkzeug.utils \
  --hidden-import jinja2 \
  --hidden-import click \
  --hidden-import itsdangerous \
  --hidden-import PIL \
  --hidden-import PIL.Image \
  --hidden-import matplotlib \
  --hidden-import matplotlib.backends.backend_pdf \
  --hidden-import importlib.util \
  --hidden-import socket \
  --collect-all flask \
  --collect-all flask_sqlalchemy \
  --collect-all flask_login \
  --collect-all sqlalchemy \
  --collect-all werkzeug \
  --collect-all jinja2 \
  --exclude-module tkinter \
  --icon "${ICON_ICNS}" \
  launcher.py

APP_PATH="dist/${BUNDLE_NAME}"
if [[ ! -d "${APP_PATH}" ]]; then
  echo "Erro: app não gerado."
  exit 1
fi

xattr -cr "${APP_PATH}" || true
echo "[2/5] App compilado com sucesso."

echo "[3/5] A criar .dmg..."
rm -f "dist/${DMG_NAME}"
rm -rf "${DMG_STAGING_DIR}"
mkdir -p "${DMG_STAGING_DIR}"
cp -R "${APP_PATH}" "${DMG_STAGING_DIR}/"
ln -s /Applications "${DMG_STAGING_DIR}/Applications"
hdiutil create \
  -volname "${APP_NAME}" \
  -srcfolder "${DMG_STAGING_DIR}" \
  -ov -format UDZO \
  "dist/${DMG_NAME}" >/dev/null && echo "DMG criado." || echo "Aviso: falha no DMG."
rm -rf "${DMG_STAGING_DIR}"

echo "[4/5] A criar .pkg..."
pkgbuild \
  --install-location "/Applications" \
  --component "${APP_PATH}" \
  "dist/${PKG_NAME}" >/dev/null
echo "PKG criado."

echo "[5/5] A remover quarentena..."
xattr -cr "dist/${PKG_NAME}" 2>/dev/null || true
xattr -cr "dist/${DMG_NAME}" 2>/dev/null || true

echo ""
echo "================================================"
echo " Build concluído!"
echo " DMG: dist/${DMG_NAME}  ← envia este aos clientes"
echo " PKG: dist/${PKG_NAME}"
echo "================================================"
open dist/

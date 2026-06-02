#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DB="${ROOT_DIR}/getclub.db"
APPDATA_DIR="${HOME}/Library/Application Support/GETCLUB"
APPDATA_DB="${APPDATA_DIR}/getclub.db"

echo "==> Resetando base local do projeto..."
rm -f "${PROJECT_DB}"
rm -rf "${ROOT_DIR}/static/uploads/atletas" "${ROOT_DIR}/static/uploads/comissao" "${ROOT_DIR}/static/uploads/documentos"
mkdir -p "${ROOT_DIR}/static/uploads/atletas" "${ROOT_DIR}/static/uploads/comissao" "${ROOT_DIR}/static/uploads/documentos"

echo "==> Recriando banco limpo no projeto..."
GETCLUB_DATA_DIR="${ROOT_DIR}" python3 - <<'PY'
import os
os.environ['GETCLUB_DATA_DIR'] = os.environ['GETCLUB_DATA_DIR']
import app  # noqa: F401 - dispara create_all + create_admin
print("Banco local recriado.")
PY

echo "==> Preparando base limpa para o app instalado (Application Support)..."
if mkdir -p "${APPDATA_DIR}/uploads/atletas" "${APPDATA_DIR}/uploads/comissao" "${APPDATA_DIR}/uploads/documentos" 2>/dev/null; then
  cp "${PROJECT_DB}" "${APPDATA_DB}"
  chmod u+rw "${APPDATA_DB}"
else
  echo "Aviso: sem permissão para escrever em '${APPDATA_DIR}' neste ambiente."
  echo "No Mac de destino, execute novamente este script pelo Terminal para concluir essa etapa."
fi

echo
echo "Concluído."
echo "Banco do projeto: ${PROJECT_DB}"
echo "Banco para app instalado: ${APPDATA_DB}"
echo "Credenciais padrão: admin / getclub123"

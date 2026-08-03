#!/usr/bin/env bash
# Instala servicios systemd de SISTEMA MailArchive (API + frontend preview).
# Uso: sudo bash deploy/install-systemd.sh
# Deshabilita servicios de usuario equivalentes para evitar choque de puertos.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -d "${ROOT}/backend" || ! -d "${ROOT}/frontend" ]]; then
  echo "[error] Ejecutá desde la raíz del proyecto, no desde frontend/:" >&2
  echo "  cd /mnt/almacen/apps/produccion/m365_archivo" >&2
  echo "  sudo bash deploy/install-systemd.sh" >&2
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Ejecutá con sudo: sudo bash $0" >&2
  exit 1
fi

# Evitar choque con units de usuario del mismo nombre
if [[ -n "${SUDO_USER:-}" ]]; then
  USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
  if [[ -d "${USER_HOME}/.config/systemd/user" ]]; then
    sudo -u "$SUDO_USER" XDG_RUNTIME_DIR="/run/user/$(id -u "$SUDO_USER")" \
      systemctl --user disable --now mailarchive-api.service mailarchive-frontend.service 2>/dev/null || true
  fi
fi

if [[ ! -x "${ROOT}/backend/.venv/bin/uvicorn" ]]; then
  echo "[error] Falta venv backend. Ejecutá:" >&2
  echo "  cd ${ROOT}/backend && uv venv .venv && . .venv/bin/activate && uv pip install -r requirements.txt" >&2
  exit 1
fi

if [[ ! -f "${ROOT}/frontend/dist/index.html" ]]; then
  echo "[info] Build frontend…"
  sudo -u pablo bash -lc "cd '${ROOT}/frontend' && npm run build"
fi

install -m 0644 "${ROOT}/deploy/mailarchive-api.service" /etc/systemd/system/
install -m 0644 "${ROOT}/deploy/mailarchive-frontend.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable mailarchive-api.service mailarchive-frontend.service
systemctl restart mailarchive-api.service mailarchive-frontend.service

echo "[ok] mailarchive-api + mailarchive-frontend (preview prod) instalados"
systemctl --no-pager status mailarchive-api.service mailarchive-frontend.service || true
echo ""
echo "Logs:  sudo journalctl -u mailarchive-api -f"
echo "API:    http://127.0.0.1:18100/health"
echo "UI:     http://127.0.0.1:5175/"

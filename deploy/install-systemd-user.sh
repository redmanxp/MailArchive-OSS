#!/usr/bin/env bash
# Instala servicios systemd de USUARIO (sin sudo).
# NOTA: en producción preferí servicios de SISTEMA:
#   sudo bash deploy/install-systemd.sh
#   y deshabilitá los de usuario: systemctl --user disable --now mailarchive-api mailarchive-frontend
# No uses ambos a la vez (chocan en :18100 y :5175).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_UNIT_DIR="${HOME}/.config/systemd/user"
mkdir -p "$USER_UNIT_DIR"

if [[ ! -x "${ROOT}/backend/.venv/bin/uvicorn" ]]; then
  echo "[error] Falta venv backend en ${ROOT}/backend/.venv" >&2
  exit 1
fi

if [[ ! -f "${ROOT}/frontend/dist/index.html" ]]; then
  echo "[info] Build frontend de producción…"
  (cd "${ROOT}/frontend" && npm run build)
fi

cp "${ROOT}/deploy/mailarchive-api.service" "${USER_UNIT_DIR}/"
cp "${ROOT}/deploy/mailarchive-frontend.service" "${USER_UNIT_DIR}/"

# Servicios de usuario: corren como el usuario logueado
sed -i \
  -e '/^User=/d' \
  -e '/^Group=/d' \
  -e '/RequiresMountsFor=/d' \
  -e 's/WantedBy=multi-user.target/WantedBy=default.target/' \
  "${USER_UNIT_DIR}/mailarchive-api.service" \
  "${USER_UNIT_DIR}/mailarchive-frontend.service"

systemctl --user daemon-reload
systemctl --user enable mailarchive-api.service mailarchive-frontend.service
systemctl --user restart mailarchive-api.service mailarchive-frontend.service

sleep 2
echo "[ok] Servicios de producción (usuario) levantados"
systemctl --user --no-pager --no-legend status mailarchive-api.service mailarchive-frontend.service || true
curl -sf http://127.0.0.1:18100/health && echo || echo "[warn] API aún no responde"
curl -sf -o /dev/null -w "frontend HTTP %{http_code}\n" http://127.0.0.1:5175/ || true
echo ""
echo "Logs: journalctl --user -u mailarchive-api -f"
echo "Tras reboot: sudo loginctl enable-linger $(whoami)"

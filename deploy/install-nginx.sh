#!/usr/bin/env bash
# Nginx HTTP para archivos.newlici.com (sin SSL — igual que agente.local).
# Uso: sudo bash deploy/install-nginx.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Ejecutá con sudo: sudo bash $0" >&2
  exit 1
fi

install -m 0644 "${ROOT}/deploy/nginx-archivos.newlici.com.conf" /etc/nginx/sites-available/archivos.newlici.com
ln -sf /etc/nginx/sites-available/archivos.newlici.com /etc/nginx/sites-enabled/archivos.newlici.com
nginx -t
systemctl reload nginx
echo "[ok] nginx archivos.newlici.com (HTTP :80)"

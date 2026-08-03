#!/usr/bin/env bash
# Genera cert autofirmado + instala nginx HTTP+HTTPS para archivos.newlici.com
# Uso: sudo bash deploy/install-nginx-https.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Ejecutá con sudo: sudo bash $0" >&2
  exit 1
fi

if [[ ! -f "${ROOT}/certs/fullchain.pem" ]]; then
  echo "[info] Generando certificado autofirmado..."
  sudo -u pablo bash "${ROOT}/scripts/generate-ssl-cert.sh" 192.168.0.113 archivos.newlici.com
fi

SNIP="/etc/nginx/snippets/proxy_http_defaults.conf"
if [[ ! -f "$SNIP" ]]; then
  if [[ -f "${ROOT}/../remitos2/deploy/nginx/snippets/proxy_http_defaults.conf.example" ]]; then
    install -d -m 0755 /etc/nginx/snippets
    cp "${ROOT}/../remitos2/deploy/nginx/snippets/proxy_http_defaults.conf.example" "$SNIP"
  else
    cat >"$SNIP" <<'EOF'
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_http_version 1.1;
proxy_read_timeout 300s;
EOF
  fi
fi

install -d -m 0750 /etc/nginx/ssl/mailarchive
install -m 0644 "${ROOT}/certs/fullchain.pem" /etc/nginx/ssl/mailarchive/
install -m 0640 "${ROOT}/certs/privkey.pem" /etc/nginx/ssl/mailarchive/
chown root:www-data /etc/nginx/ssl/mailarchive/privkey.pem

install -m 0644 "${ROOT}/deploy/nginx-archivos.newlici.com.https.conf" /etc/nginx/sites-available/archivos.newlici.com
ln -sf /etc/nginx/sites-available/archivos.newlici.com /etc/nginx/sites-enabled/archivos.newlici.com

nginx -t
systemctl reload nginx

echo "[ok] HTTPS activo en https://archivos.newlici.com"
echo "     (certificado autofirmado — aceptar aviso en el navegador la primera vez)"
curl -sk https://127.0.0.1/health -H 'Host: archivos.newlici.com' || true

#!/usr/bin/env bash
# Certificado autofirmado para HTTPS en LAN (OAuth Microsoft).
# Mismo enfoque que vpn_admin/scripts/generate-ssl-cert.sh
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_DIR="${DIR}/certs"
IP="${1:-192.168.0.113}"
HOST="${2:-archivos.newlici.com}"

mkdir -p "${CERT_DIR}"

openssl req -x509 -newkey rsa:2048 \
  -keyout "${CERT_DIR}/privkey.pem" \
  -out "${CERT_DIR}/fullchain.pem" \
  -days 825 -nodes \
  -subj "/CN=${HOST}" \
  -addext "subjectAltName=IP:${IP},DNS:${HOST},DNS:localhost,IP:127.0.0.1"

chmod 600 "${CERT_DIR}/privkey.pem"
chmod 644 "${CERT_DIR}/fullchain.pem"

echo "Certificado creado en ${CERT_DIR}/"
echo "Siguiente paso (nginx con HTTPS):"
echo "  sudo cp deploy/nginx-archivos.newlici.com.https.conf /etc/nginx/sites-available/archivos.newlici.com"
echo "  sudo nginx -t && sudo systemctl reload nginx"

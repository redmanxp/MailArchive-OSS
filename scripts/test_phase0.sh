#!/usr/bin/env bash
# Prueba end-to-end Fase 0 (API)
set -euo pipefail
BASE="${1:-http://127.0.0.1:18100}"
EMAIL="admin@example.com"
PASS_TEMP="TempPass123!"
PASS_NEW="NuevaPass456!"

echo "== health =="
curl -sf "$BASE/health" | tee /tmp/ma_health.json
echo

echo "== install status =="
curl -sf "$BASE/api/v1/install/status" | tee /tmp/ma_install_status.json
echo

INSTALLED=$(python3 -c "import json; print(json.load(open('/tmp/ma_install_status.json'))['installed'])")
if [ "$INSTALLED" = "False" ]; then
  echo "== install =="
  curl -sf -X POST "$BASE/api/v1/install" \
    -H 'Content-Type: application/json' \
    -d "{\"tenant_name\":\"Acme\",\"tenant_slug\":\"acme\",\"admin_name\":\"Administrator\",\"admin_email\":\"$EMAIL\",\"admin_password\":\"$PASS_TEMP\"}" \
    | tee /tmp/ma_install.json
  echo
fi

echo "== login (must change password) =="
curl -sf -X POST "$BASE/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS_TEMP\",\"tenant_slug\":\"acme\"}" \
  | tee /tmp/ma_login.json
echo
ACCESS=$(python3 -c "import json; print(json.load(open('/tmp/ma_login.json'))['access_token'])")
REFRESH=$(python3 -c "import json; print(json.load(open('/tmp/ma_login.json'))['refresh_token'])")
MCP=$(python3 -c "import json; print(json.load(open('/tmp/ma_login.json'))['must_change_password'])")
echo "must_change_password=$MCP"

echo "== gate: admin users should be 403 while must_change_password =="
CODE=$(curl -s -o /tmp/ma_users_blocked.json -w "%{http_code}" \
  -H "Authorization: Bearer $ACCESS" "$BASE/api/v1/admin/users")
echo "HTTP $CODE"
test "$CODE" = "403"

echo "== change password =="
curl -sf -X POST "$BASE/api/v1/auth/change-password" \
  -H "Authorization: Bearer $ACCESS" \
  -H 'Content-Type: application/json' \
  -d "{\"current_password\":\"$PASS_TEMP\",\"new_password\":\"$PASS_NEW\"}" \
  | tee /tmp/ma_chg.json
echo

echo "== login with new password =="
curl -sf -X POST "$BASE/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS_NEW\",\"tenant_slug\":\"acme\"}" \
  | tee /tmp/ma_login2.json
echo
ACCESS2=$(python3 -c "import json; print(json.load(open('/tmp/ma_login2.json'))['access_token'])")
MCP2=$(python3 -c "import json; print(json.load(open('/tmp/ma_login2.json'))['must_change_password'])")
test "$MCP2" = "False"

echo "== me =="
curl -sf -H "Authorization: Bearer $ACCESS2" "$BASE/api/v1/auth/me" | tee /tmp/ma_me.json
echo

echo "== admin users =="
curl -sf -H "Authorization: Bearer $ACCESS2" "$BASE/api/v1/admin/users" | tee /tmp/ma_users.json
echo

echo "== audit logs =="
curl -sf -H "Authorization: Bearer $ACCESS2" "$BASE/api/v1/admin/audit-logs" | tee /tmp/ma_logs.json
echo

echo "== refresh =="
REFRESH2=$(python3 -c "import json; print(json.load(open('/tmp/ma_login2.json'))['refresh_token'])")
curl -sf -X POST "$BASE/api/v1/auth/refresh" \
  -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"$REFRESH2\"}" \
  | tee /tmp/ma_refresh.json
echo

echo "FASE 0 OK"

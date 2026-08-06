#!/bin/sh
set -eu
mkdir -p /data /storage
echo "[entrypoint] starting MailArchive API"
exec "$@"

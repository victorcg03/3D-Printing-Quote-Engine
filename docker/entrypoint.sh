#!/usr/bin/env sh
set -e

mkdir -p /app/data /app/logs

# Fix permisos del volumen (si es root-owned al montar)
chown -R appuser:appuser /app/data /app/logs || true

exec "$@"
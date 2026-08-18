#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
set -a; source "${WORDHINT_ENV_FILE:-$PWD/.env}"; set +a
db="${WORDHINT_DATABASE:-$PWD/wordhint.db}"
out="${1:-$PWD/backups}"
mkdir -p "$out"
[[ -f "$db" ]] || { echo "数据库不存在：$db" >&2; exit 1; }
file="$out/wordhint-$(date +%Y%m%d-%H%M%S).db"
sqlite3 "$db" ".backup '$file'"
chmod 600 "$file"
echo "备份完成：$file"

#!/usr/bin/env bash
set -Eeuo pipefail

database_path=${DATABASE_PATH:-/var/lib/easynet-web/easynet.db}
backup_directory=${BACKUP_DIRECTORY:-/var/lib/easynet-web/backups}
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
database_name=$(basename "$database_path")

mkdir -p "$backup_directory"
tmp_file=$(mktemp "${backup_directory}/${database_name}.${timestamp}.XXXXXX")
output_file="${tmp_file%.XXXXXX}.sqlite3"

cleanup() {
	rm -f "$tmp_file" "$output_file"
}
trap cleanup EXIT

python3 - "$database_path" "$tmp_file" <<'PY'
import sqlite3
import sys

source = sqlite3.connect(sys.argv[1])
destination = sqlite3.connect(sys.argv[2])
with destination:
    source.backup(destination)
destination.close()
source.close()
PY

mv "$tmp_file" "$output_file"
trap - EXIT
find "$backup_directory" -maxdepth 1 -type f -name '*.sqlite3' -mtime +14 -delete
printf '%s\n' "$output_file"


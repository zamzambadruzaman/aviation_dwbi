#!/usr/bin/env bash
# ============================================================
# Load semua file CSV mentah ke staging Postgres.
# Jalankan setelah 01_staging_ddl.sql sudah dieksekusi.
#
# Cara pakai:
#   chmod +x 02_load_staging.sh
#   ./02_load_staging.sh
#
# Sesuaikan PGDATABASE/PGUSER/PGHOST/PGPORT dan path folder
# di bawah ini dengan environment lokal Anda.
# ============================================================

set -e

DB="postgres"
USER="postgres"
HOST="localhost"
PORT="5432"

ONTIME_DIR="data/ontime"
T100_DIR="data/T100"
DB1B_DIR="data/db1b"

echo "=== 1. Load semua file On-Time ke dirgantara_db.ontime_performance ==="
for f in "$ONTIME_DIR"/*.csv; do
  if [[ "$f" == *"_2022_8.csv" ]]; then
    echo "  -> SKIP $f (file terpotong/corrupt di baris terakhir, dan di luar cakupan Jan-Jun)"
    continue
  fi
  echo "  -> $f"
  psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -c "\\copy dirgantara_db.ontime_performance FROM '$f' WITH (FORMAT csv, HEADER true, NULL '')"
done

echo "=== 2. Load file T-100 ke dirgantara_db.t100_segment ==="
for f in "$T100_DIR"/*.csv; do
  echo "  -> $f"
  psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -c "\\copy dirgantara_db.t100_segment FROM '$f' WITH (FORMAT csv, HEADER true, NULL '')"
done

echo "=== 3. Load semua file DB1B ke dirgantara_db.db1b_market ==="
for f in "$DB1B_DIR"/*.csv; do
  echo "  -> $f"
  psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -c "\\copy dirgantara_db.db1b_market FROM '$f' WITH (FORMAT csv, HEADER true, NULL '')"
done

echo "=== Selesai. Cek jumlah baris: ==="
psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -c "
SELECT 'ontime_performance' AS tabel, COUNT(*) FROM dirgantara_db.ontime_performance
UNION ALL
SELECT 't100_segment', COUNT(*) FROM dirgantara_db.t100_segment
UNION ALL
SELECT 'db1b_market', COUNT(*) FROM dirgantara_db.db1b_market;
"
"""
etl_common.py — konfigurasi & koneksi untuk pipeline dimensi & fact.
"""

import duckdb
from datetime import date

# ==========================================================
# KONFIGURASI — WAJIB disesuaikan dengan environment dimana script ini dijalankan.
# ==========================================================
PG_CONN_STRING = "postgresql://user:password@localhost:5432/transtats_db"
DUCKDB_PATH = "transtats_dw.duckdb"
SCOPE_START = date(2022, 1, 1)
SCOPE_END = date(2022, 6, 30)


def connect():
    """Buka koneksi DuckDB dan attach ke Postgres (schema transtats_db)."""
    con = duckdb.connect(DUCKDB_PATH)
    con.execute("INSTALL postgres;")
    con.execute("LOAD postgres;")
    # Idempoten: kalau attach 'pg' sudah ada dari proses sebelumnya (mis. dijalankan
    # dari sesi python yang sama), lepas dulu supaya tidak error "already attached".
    try:
        con.execute("DETACH pg;")
    except duckdb.Error:
        pass
    con.execute(f"ATTACH '{PG_CONN_STRING}' AS pg (TYPE postgres, READ_ONLY);")
    return con


def connect_duckdb_only(read_only: bool = False):
    """Buka koneksi DuckDB murni, TANPA attach Postgres.
    Dipakai oleh build_datamart.py (baca dw.*, tulis mart.*) dan
    streamlit_app.py (baca mart.* & dw.dim_* saja) — keduanya tidak
    perlu akses Postgres sama sekali.
    """
    return duckdb.connect(DUCKDB_PATH, read_only=read_only)
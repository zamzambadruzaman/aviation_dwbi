"""
run_analysis.py — Menjalankan analysis_queries.sql tanpa perlu DuckDB CLI.

Membaca analysis_queries.sql, menjalankan setiap query secara berurutan,
lalu mencetak hasilnya ke layar sekaligus menyimpannya ke analysis_output.txt.

Jalankan:
    python run_analysis.py

Butuh: duckdb dan pandas (keduanya sudah terpasang dari tahap sebelumnya).
Koneksi dibuka read-only agar tidak bentrok dengan Metabase yang berjalan.
"""

import re
import sys
import duckdb

DUCKDB_PATH = "transtats_dw.duckdb"
SQL_FILE = "analysis_queries.sql"
OUT_FILE = "analysis_output.txt"


def split_statements(sql_text):
    """Pecah berkas SQL menjadi (label, statement).

    Label diambil dari baris komentar tepat sebelum statement, sehingga
    nomor query (A1, B2, D1, dst.) ikut tercetak bersama hasilnya.
    """
    statements = []
    buffer_comments = []
    buffer_sql = []

    for line in sql_text.splitlines():
        stripped = line.strip()

        if not buffer_sql and (stripped.startswith("--") or stripped == ""):
            if stripped.startswith("--"):
                text = stripped.lstrip("-").strip()
                # Abaikan garis pemisah dan blok header
                if text and not set(text) <= {"="}:
                    buffer_comments.append(text)
            elif stripped == "":
                # Baris kosong memisahkan blok komentar yang tidak terkait
                if not buffer_sql:
                    buffer_comments = []
            continue

        buffer_sql.append(line)

        if stripped.endswith(";"):
            sql = "\n".join(buffer_sql).strip()
            label = " | ".join(buffer_comments[:2]) if buffer_comments else "(tanpa label)"
            statements.append((label, sql))
            buffer_comments = []
            buffer_sql = []

    return statements


def main():
    try:
        con = duckdb.connect(DUCKDB_PATH, read_only=True)
    except Exception as exc:
        print(f"Gagal membuka {DUCKDB_PATH}: {exc}")
        print("Pastikan Anda menjalankan script ini dari folder yang memuat berkas tersebut.")
        sys.exit(1)

    with open(SQL_FILE) as f:
        sql_text = f.read()

    statements = split_statements(sql_text)
    print(f"Ditemukan {len(statements)} query di {SQL_FILE}\n")

    lines_out = []
    for i, (label, sql) in enumerate(statements, start=1):
        header = f"\n{'=' * 78}\n[{i}/{len(statements)}] {label}\n{'=' * 78}"
        print(header)
        lines_out.append(header)
        try:
            df = con.execute(sql).df()
            body = df.to_string(index=False)
        except Exception as exc:
            body = f"GAGAL: {exc}"
        print(body)
        lines_out.append(body)

    con.close()

    with open(OUT_FILE, "w") as f:
        f.write("\n".join(lines_out))

    print(f"\n\nSeluruh hasil juga tersimpan di {OUT_FILE}")


if __name__ == "__main__":
    main()
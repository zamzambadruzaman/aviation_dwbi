"""
Data profiling script untuk dataset TranStats (On-Time, T-100, DB1B).

Cara pakai:
    python profile_data.py <folder_path>

Contoh:
    python profile_data.py data/ontime
    python profile_data.py data/t100
    python profile_data.py data/db1b

Butuh: pandas (pip install pandas)
"""

import sys
import glob
import pandas as pd


def profile_file(filepath):
    print(f"\n{'='*70}")
    print(f"FILE: {filepath}")
    print("=" * 70)

    df = pd.read_csv(filepath, low_memory=False)

    print(f"\nJumlah baris : {len(df):,}")
    print(f"Jumlah kolom : {len(df.columns)}")

    print("\n--- Daftar kolom & tipe data ---")
    print(df.dtypes)

    print("\n--- Persentase nilai kosong per kolom (top 15) ---")
    null_pct = (df.isnull().sum() / len(df) * 100).sort_values(ascending=False)
    print(null_pct.head(15).round(2))

    print("\n--- Jumlah baris duplikat penuh (semua kolom identik) ---")
    print(f"{df.duplicated().sum():,}")

    print("\n--- Contoh 3 baris pertama ---")
    print(df.head(3).to_string())

    return df


def profile_folder(folder_path):
    files = sorted(glob.glob(f"{folder_path}/*.csv"))
    if not files:
        print(f"Tidak ada file .csv ditemukan di {folder_path}")
        return

    print(f"Ditemukan {len(files)} file CSV di {folder_path}")

    summaries = []
    for f in files:
        df = profile_file(f)
        summaries.append({"file": f, "rows": len(df), "cols": len(df.columns)})

    print(f"\n{'='*70}")
    print("RINGKASAN SEMUA FILE")
    print("=" * 70)
    summary_df = pd.DataFrame(summaries)
    print(summary_df.to_string(index=False))
    print(f"\nTotal baris gabungan: {summary_df['rows'].sum():,}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python profile_data.py <folder_path>")
        sys.exit(1)
    profile_folder(sys.argv[1])
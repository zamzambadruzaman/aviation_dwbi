"""
load_dimensions.py — Load semua tabel dimensi (Dim_Date, Dim_Airport,
Dim_Carrier, Dim_Aircraft_Type) dari staging Postgres ke DuckDB.

Idempoten: setiap dijalankan, schema & sequence di-reset (DROP lalu CREATE)
sebelum diisi ulang, jadi aman dijalankan berkali-kali tanpa duplikasi.

Jalankan SEBELUM load_facts.py (fact table butuh dimensi ini sudah ada).

Jalankan : python load_dimensions.py
Butuh    : pip install duckdb polars
"""

import polars as pl
from etl_common import connect, SCOPE_START, SCOPE_END


def create_dimension_tables(con):
    con.execute("CREATE SCHEMA IF NOT EXISTS dw;")

    # --- Dim_Date ---
    con.execute("DROP TABLE IF EXISTS dw.dim_date;")
    con.execute("""
        CREATE TABLE dw.dim_date (
            date_key      INTEGER PRIMARY KEY,
            full_date     DATE,
            year          INTEGER,
            quarter       INTEGER,
            month         INTEGER,
            month_name    VARCHAR,
            day           INTEGER,
            day_of_week   INTEGER,
            day_name      VARCHAR,
            is_weekend    BOOLEAN
        );
    """)

    # --- Dim_Airport ---
    con.execute("DROP TABLE IF EXISTS dw.dim_airport;")
    con.execute("DROP SEQUENCE IF EXISTS dw.seq_airport;")
    con.execute("CREATE SEQUENCE dw.seq_airport START 1;")
    con.execute("""
        CREATE TABLE dw.dim_airport (
            airport_key   INTEGER PRIMARY KEY DEFAULT nextval('dw.seq_airport'),
            airport_code  VARCHAR UNIQUE,
            city_name     VARCHAR,
            state_code    VARCHAR,
            state_name    VARCHAR
        );
    """)

    # --- Dim_Carrier ---
    con.execute("DROP TABLE IF EXISTS dw.dim_carrier;")
    con.execute("DROP SEQUENCE IF EXISTS dw.seq_carrier;")
    con.execute("CREATE SEQUENCE dw.seq_carrier START 1;")
    con.execute("""
        CREATE TABLE dw.dim_carrier (
            carrier_key   INTEGER PRIMARY KEY DEFAULT nextval('dw.seq_carrier'),
            carrier_code  VARCHAR UNIQUE,
            carrier_name  VARCHAR
        );
    """)

    # --- Dim_Aircraft_Type ---
    con.execute("DROP TABLE IF EXISTS dw.dim_aircraft_type;")
    con.execute("DROP SEQUENCE IF EXISTS dw.seq_aircraft;")
    con.execute("CREATE SEQUENCE dw.seq_aircraft START 1;")
    con.execute("""
        CREATE TABLE dw.dim_aircraft_type (
            aircraft_type_key   INTEGER PRIMARY KEY DEFAULT nextval('dw.seq_aircraft'),
            aircraft_type_code  VARCHAR UNIQUE
        );
    """)


def load_dim_date(con):
    dates = pl.date_range(SCOPE_START, SCOPE_END, interval="1d", eager=True).alias("full_date")
    df = pl.DataFrame({"full_date": dates}).with_columns([
        pl.col("full_date").dt.strftime("%Y%m%d").cast(pl.Int64).alias("date_key"),
        pl.col("full_date").dt.year().alias("year"),
        pl.col("full_date").dt.quarter().alias("quarter"),
        pl.col("full_date").dt.month().alias("month"),
        pl.col("full_date").dt.strftime("%B").alias("month_name"),
        pl.col("full_date").dt.day().alias("day"),
        pl.col("full_date").dt.weekday().alias("day_of_week"),
        pl.col("full_date").dt.strftime("%A").alias("day_name"),
    ]).with_columns(
        (pl.col("day_of_week") >= 6).alias("is_weekend")
    )
    con.register("df_dim_date", df)
    con.execute("""
        INSERT INTO dw.dim_date
        SELECT date_key, full_date, year, quarter, month, month_name, day, day_of_week, day_name, is_weekend
        FROM df_dim_date
    """)
    con.unregister("df_dim_date")
    print(f"  dim_date: {len(df)} baris")


def load_dim_airport(con):
    con.execute("""
        INSERT INTO dw.dim_airport (airport_code, city_name, state_code, state_name)
        SELECT code, MAX(city_name), MAX(state_code), MAX(state_name)
        FROM (
            SELECT "Origin" AS code, "OriginCityName" AS city_name,
                   "OriginState" AS state_code, "OriginStateName" AS state_name
            FROM pg.transtats_db.ontime_performance
            UNION ALL
            SELECT "Dest", "DestCityName", "DestState", "DestStateName"
            FROM pg.transtats_db.ontime_performance
            UNION ALL
            SELECT "ORIGIN", "ORIGIN_CITY_NAME", NULL, NULL
            FROM pg.transtats_db.t100_segment
            UNION ALL
            SELECT "DEST", "DEST_CITY_NAME", NULL, NULL
            FROM pg.transtats_db.t100_segment
            UNION ALL
            SELECT "Origin", NULL, "OriginState", "OriginStateName"
            FROM pg.transtats_db.db1b_market
            UNION ALL
            SELECT "Dest", NULL, "DestState", "DestStateName"
            FROM pg.transtats_db.db1b_market
        ) all_airports
        WHERE code IS NOT NULL AND TRIM(code) <> ''
        GROUP BY code
    """)
    n = con.execute("SELECT COUNT(*) FROM dw.dim_airport").fetchone()[0]
    print(f"  dim_airport: {n} baris")


def load_dim_carrier(con):
    con.execute("""
        INSERT INTO dw.dim_carrier (carrier_code, carrier_name)
        SELECT code, MAX(name)
        FROM (
            SELECT "Reporting_Airline" AS code, CAST(NULL AS VARCHAR) AS name
            FROM pg.transtats_db.ontime_performance
            UNION ALL
            SELECT "UNIQUE_CARRIER", "UNIQUE_CARRIER_NAME"
            FROM pg.transtats_db.t100_segment
            UNION ALL
            SELECT "RPCarrier", CAST(NULL AS VARCHAR)
            FROM pg.transtats_db.db1b_market
            UNION ALL
            SELECT "TkCarrier", CAST(NULL AS VARCHAR)
            FROM pg.transtats_db.db1b_market
            UNION ALL
            SELECT "OpCarrier", CAST(NULL AS VARCHAR)
            FROM pg.transtats_db.db1b_market
        ) all_carriers
        WHERE code IS NOT NULL AND TRIM(code) <> ''
        GROUP BY code
    """)
    n = con.execute("SELECT COUNT(*) FROM dw.dim_carrier").fetchone()[0]
    print(f"  dim_carrier: {n} baris")


def load_dim_aircraft_type(con):
    con.execute("""
        INSERT INTO dw.dim_aircraft_type (aircraft_type_code)
        SELECT DISTINCT "AIRCRAFT_TYPE"
        FROM pg.transtats_db.t100_segment
        WHERE "AIRCRAFT_TYPE" IS NOT NULL AND TRIM("AIRCRAFT_TYPE") <> ''
    """)
    n = con.execute("SELECT COUNT(*) FROM dw.dim_aircraft_type").fetchone()[0]
    print(f"  dim_aircraft_type: {n} baris")


def main():
    print("Menghubungkan ke Postgres & DuckDB...")
    con = connect()

    print("Reset & buat ulang tabel dimensi (idempoten)...")
    create_dimension_tables(con)

    print("Loading dimensi...")
    load_dim_date(con)
    load_dim_airport(con)
    load_dim_carrier(con)
    load_dim_aircraft_type(con)

    con.close()
    print("\nSelesai. Lanjutkan dengan: python load_facts.py")


if __name__ == "__main__":
    main()
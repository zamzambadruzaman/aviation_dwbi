"""
02_load_facts.py — Load semua fact table (Fact_Flight_OnTime, Fact_Route_Traffic,
Fact_Ticket_Market) dari staging Postgres ke DuckDB.

Data cleansing yang diterapkan sebelum load:
  1. Deduplikasi berbasis business key (bukan cuma DISTINCT * ) — menangani
     kasus baris yang ke-load dobel di staging (root cause: script load
     staging sempat dijalankan ulang tanpa reset). Dedup dilakukan di level
     query, jadi pipeline ini tetap aman meski staging belum/tidak direset.
  2. Penanganan nilai kosong ("" ter-quote maupun tidak) lewat NULLIF+TRIM
     sebelum cast ke tipe numerik/tanggal (TRY_CAST supaya nilai yang tidak
     terduga jadi NULL, bukan menggagalkan seluruh batch).
  3. Filter cakupan waktu ke Jan-Jun 2022.

Idempoten: fact table di-reset (DROP+CREATE, sequence direset) setiap
dijalankan, jadi hasil akhirnya selalu konsisten berapa kali pun dijalankan.

Jalankan SETELAH 01_load_dimensions.py (fact butuh dimensi sudah terisi).

Jalankan : python 02_load_facts.py
Butuh    : pip install duckdb
"""

from etl_common import connect, SCOPE_START, SCOPE_END


def create_fact_tables(con):
    con.execute("CREATE SCHEMA IF NOT EXISTS dw;")

    con.execute("DROP TABLE IF EXISTS dw.fact_flight_ontime;")
    con.execute("DROP SEQUENCE IF EXISTS dw.seq_fact_ontime;")
    con.execute("CREATE SEQUENCE dw.seq_fact_ontime START 1;")
    con.execute("""
        CREATE TABLE dw.fact_flight_ontime (
            fact_id               BIGINT PRIMARY KEY DEFAULT nextval('dw.seq_fact_ontime'),
            date_key              INTEGER,
            origin_airport_key    INTEGER,
            dest_airport_key      INTEGER,
            carrier_key           INTEGER,
            flight_number         INTEGER,
            tail_number           VARCHAR,
            dep_delay             DOUBLE,
            arr_delay             DOUBLE,
            taxi_out              DOUBLE,
            taxi_in               DOUBLE,
            air_time              DOUBLE,
            distance              DOUBLE,
            cancelled             DOUBLE,
            diverted              DOUBLE,
            carrier_delay         DOUBLE,
            weather_delay         DOUBLE,
            nas_delay             DOUBLE,
            security_delay        DOUBLE,
            late_aircraft_delay   DOUBLE
        );
    """)

    con.execute("DROP TABLE IF EXISTS dw.fact_route_traffic;")
    con.execute("DROP SEQUENCE IF EXISTS dw.seq_fact_traffic;")
    con.execute("CREATE SEQUENCE dw.seq_fact_traffic START 1;")
    con.execute("""
        CREATE TABLE dw.fact_route_traffic (
            fact_id                BIGINT PRIMARY KEY DEFAULT nextval('dw.seq_fact_traffic'),
            date_key               INTEGER,
            origin_airport_key     INTEGER,
            dest_airport_key       INTEGER,
            carrier_key            INTEGER,
            aircraft_type_key      INTEGER,
            departures_scheduled   DOUBLE,
            departures_performed   DOUBLE,
            seats                  DOUBLE,
            passengers             DOUBLE,
            freight                DOUBLE,
            mail                   DOUBLE,
            distance               DOUBLE
        );
    """)

    con.execute("DROP TABLE IF EXISTS dw.fact_ticket_market;")
    con.execute("DROP SEQUENCE IF EXISTS dw.seq_fact_market;")
    con.execute("CREATE SEQUENCE dw.seq_fact_market START 1;")
    con.execute("""
        CREATE TABLE dw.fact_ticket_market (
            fact_id             BIGINT PRIMARY KEY DEFAULT nextval('dw.seq_fact_market'),
            date_key            INTEGER,
            origin_airport_key  INTEGER,
            dest_airport_key    INTEGER,
            carrier_key         INTEGER,
            passengers          DOUBLE,
            mkt_fare            DOUBLE,
            mkt_distance        DOUBLE,
            mkt_miles_flown     DOUBLE,
            mkt_coupons         INTEGER
        );
    """)


def print_dedup_summary(con, label, raw_sql, dedup_sql):
    raw_count = con.execute(raw_sql).fetchone()[0]
    dedup_count = con.execute(dedup_sql).fetchone()[0]
    removed = raw_count - dedup_count
    print(f"  [cleansing] {label}: {raw_count:,} baris mentah -> {dedup_count:,} setelah dedup "
          f"({removed:,} baris duplikat dibuang)")


def load_fact_flight_ontime(con):
    print_dedup_summary(
        con,
        "ontime_performance",
        'SELECT COUNT(*) FROM pg.transtats_db.ontime_performance',
        """
        SELECT COUNT(*) FROM (
            SELECT ROW_NUMBER() OVER (
                PARTITION BY "FlightDate", "Reporting_Airline",
                             "Flight_Number_Reporting_Airline", "Origin", "Dest"
                ORDER BY "FlightDate"
            ) AS rn
            FROM pg.transtats_db.ontime_performance
        ) x WHERE rn = 1
        """
    )

    con.execute(f"""
        INSERT INTO dw.fact_flight_ontime
            (date_key, origin_airport_key, dest_airport_key, carrier_key,
             flight_number, tail_number, dep_delay, arr_delay, taxi_out, taxi_in,
             air_time, distance, cancelled, diverted,
             carrier_delay, weather_delay, nas_delay, security_delay, late_aircraft_delay)
        WITH deduped AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY "FlightDate", "Reporting_Airline",
                                 "Flight_Number_Reporting_Airline", "Origin", "Dest"
                    ORDER BY "FlightDate"
                ) AS rn
            FROM pg.transtats_db.ontime_performance
        )
        SELECT
            CAST(strftime(TRY_CAST(o."FlightDate" AS DATE), '%Y%m%d') AS INTEGER),
            da_o.airport_key,
            da_d.airport_key,
            dc.carrier_key,
            TRY_CAST(NULLIF(TRIM(o."Flight_Number_Reporting_Airline"), '') AS INTEGER),
            o."Tail_Number",
            TRY_CAST(NULLIF(TRIM(o."DepDelay"), '') AS DOUBLE),
            TRY_CAST(NULLIF(TRIM(o."ArrDelay"), '') AS DOUBLE),
            TRY_CAST(NULLIF(TRIM(o."TaxiOut"), '') AS DOUBLE),
            TRY_CAST(NULLIF(TRIM(o."TaxiIn"), '') AS DOUBLE),
            TRY_CAST(NULLIF(TRIM(o."AirTime"), '') AS DOUBLE),
            TRY_CAST(NULLIF(TRIM(o."Distance"), '') AS DOUBLE),
            TRY_CAST(NULLIF(TRIM(o."Cancelled"), '') AS DOUBLE),
            TRY_CAST(NULLIF(TRIM(o."Diverted"), '') AS DOUBLE),
            TRY_CAST(NULLIF(TRIM(o."CarrierDelay"), '') AS DOUBLE),
            TRY_CAST(NULLIF(TRIM(o."WeatherDelay"), '') AS DOUBLE),
            TRY_CAST(NULLIF(TRIM(o."NASDelay"), '') AS DOUBLE),
            TRY_CAST(NULLIF(TRIM(o."SecurityDelay"), '') AS DOUBLE),
            TRY_CAST(NULLIF(TRIM(o."LateAircraftDelay"), '') AS DOUBLE)
        FROM deduped o
        JOIN dw.dim_airport da_o ON da_o.airport_code = o."Origin"
        JOIN dw.dim_airport da_d ON da_d.airport_code = o."Dest"
        JOIN dw.dim_carrier dc  ON dc.carrier_code   = o."Reporting_Airline"
        WHERE o.rn = 1
          AND TRY_CAST(o."FlightDate" AS DATE) BETWEEN DATE '{SCOPE_START}' AND DATE '{SCOPE_END}'
    """)
    n = con.execute("SELECT COUNT(*) FROM dw.fact_flight_ontime").fetchone()[0]
    print(f"  fact_flight_ontime: {n:,} baris")


def load_fact_route_traffic(con):
    # CATATAN PENTING: baris dengan Year+Month+Carrier+Origin+Dest+AircraftType yang
    # sama BUKAN duplikat — dikonfirmasi manual bahwa measure-nya berbeda (kemungkinan
    # dipisah oleh kolom CLASS/service-class yang tidak ikut terdownload di 23 kolom
    # T-100 kita). Karena itu measure di-SUM per kombinasi kunci (agregasi), bukan
    # dibuang salah satunya (row elimination) — supaya total passengers/freight/mail
    # tidak understated.
    raw = con.execute('SELECT COUNT(*) FROM pg.transtats_db.t100_segment').fetchone()[0]
    grain = con.execute("""
        SELECT COUNT(*) FROM (
            SELECT "YEAR","MONTH","UNIQUE_CARRIER","ORIGIN","DEST","AIRCRAFT_TYPE"
            FROM pg.transtats_db.t100_segment
            GROUP BY 1,2,3,4,5,6
        ) x
    """).fetchone()[0]
    print(f"  [cleansing] t100_segment: {raw:,} baris mentah -> {grain:,} kombinasi kunci unik "
          f"(measure di-SUM per kombinasi, bukan dibuang -- lihat catatan di source)")

    con.execute("""
        INSERT INTO dw.fact_route_traffic
            (date_key, origin_airport_key, dest_airport_key, carrier_key, aircraft_type_key,
             departures_scheduled, departures_performed, seats, passengers, freight, mail, distance)
        WITH aggregated AS (
            SELECT
                "YEAR", "MONTH", "UNIQUE_CARRIER", "ORIGIN", "DEST", "AIRCRAFT_TYPE",
                SUM(TRY_CAST(NULLIF(TRIM("DEPARTURES_SCHEDULED"), '') AS DOUBLE)) AS departures_scheduled,
                SUM(TRY_CAST(NULLIF(TRIM("DEPARTURES_PERFORMED"), '') AS DOUBLE)) AS departures_performed,
                SUM(TRY_CAST(NULLIF(TRIM("SEATS"), '') AS DOUBLE)) AS seats,
                SUM(TRY_CAST(NULLIF(TRIM("PASSENGERS"), '') AS DOUBLE)) AS passengers,
                SUM(TRY_CAST(NULLIF(TRIM("FREIGHT"), '') AS DOUBLE)) AS freight,
                SUM(TRY_CAST(NULLIF(TRIM("MAIL"), '') AS DOUBLE)) AS mail,
                MAX(TRY_CAST(NULLIF(TRIM("DISTANCE"), '') AS DOUBLE)) AS distance
            FROM pg.transtats_db.t100_segment
            WHERE TRY_CAST("YEAR" AS INTEGER) = 2022
              AND TRY_CAST("MONTH" AS INTEGER) BETWEEN 1 AND 6
            GROUP BY "YEAR", "MONTH", "UNIQUE_CARRIER", "ORIGIN", "DEST", "AIRCRAFT_TYPE"
        )
        SELECT
            CAST(strftime(
                make_date(TRY_CAST(a."YEAR" AS INTEGER), TRY_CAST(a."MONTH" AS INTEGER), 1),
                '%Y%m%d') AS INTEGER),
            da_o.airport_key,
            da_d.airport_key,
            dc.carrier_key,
            dat.aircraft_type_key,
            a.departures_scheduled,
            a.departures_performed,
            a.seats,
            a.passengers,
            a.freight,
            a.mail,
            a.distance
        FROM aggregated a
        JOIN dw.dim_airport da_o ON da_o.airport_code = a."ORIGIN"
        JOIN dw.dim_airport da_d ON da_d.airport_code = a."DEST"
        JOIN dw.dim_carrier dc  ON dc.carrier_code   = a."UNIQUE_CARRIER"
        LEFT JOIN dw.dim_aircraft_type dat ON dat.aircraft_type_code = a."AIRCRAFT_TYPE"
    """)
    n = con.execute("SELECT COUNT(*) FROM dw.fact_route_traffic").fetchone()[0]
    print(f"  fact_route_traffic: {n:,} baris")


def load_fact_ticket_market(con):
    print_dedup_summary(
        con,
        "db1b_market",
        'SELECT COUNT(*) FROM pg.transtats_db.db1b_market',
        """
        SELECT COUNT(*) FROM (
            SELECT ROW_NUMBER() OVER (
                PARTITION BY "ItinID", "MktID"
                ORDER BY "ItinID"
            ) AS rn
            FROM pg.transtats_db.db1b_market
        ) x WHERE rn = 1
        """
    )

    con.execute("""
        INSERT INTO dw.fact_ticket_market
            (date_key, origin_airport_key, dest_airport_key, carrier_key,
             passengers, mkt_fare, mkt_distance, mkt_miles_flown, mkt_coupons)
        WITH deduped AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY "ItinID", "MktID"
                    ORDER BY "ItinID"
                ) AS rn
            FROM pg.transtats_db.db1b_market
        )
        SELECT
            CAST(strftime(
                make_date(TRY_CAST(m."Year" AS INTEGER), (TRY_CAST(m."Quarter" AS INTEGER) - 1) * 3 + 1, 1),
                '%Y%m%d') AS INTEGER),
            da_o.airport_key,
            da_d.airport_key,
            dc.carrier_key,
            TRY_CAST(NULLIF(TRIM(m."Passengers"), '') AS DOUBLE),
            TRY_CAST(NULLIF(TRIM(m."MktFare"), '') AS DOUBLE),
            TRY_CAST(NULLIF(TRIM(m."MktDistance"), '') AS DOUBLE),
            TRY_CAST(NULLIF(TRIM(m."MktMilesFlown"), '') AS DOUBLE),
            TRY_CAST(NULLIF(TRIM(m."MktCoupons"), '') AS INTEGER)
        FROM deduped m
        JOIN dw.dim_airport da_o ON da_o.airport_code = m."Origin"
        JOIN dw.dim_airport da_d ON da_d.airport_code = m."Dest"
        JOIN dw.dim_carrier dc  ON dc.carrier_code   = m."OpCarrier"
        WHERE m.rn = 1
          AND TRY_CAST(m."Year" AS INTEGER) = 2022
          AND TRY_CAST(m."Quarter" AS INTEGER) IN (1, 2)
    """)
    n = con.execute("SELECT COUNT(*) FROM dw.fact_ticket_market").fetchone()[0]
    print(f"  fact_ticket_market: {n:,} baris")


def verify(con):
    result = con.sql("""
        SELECT 'fact_flight_ontime' AS tabel, COUNT(*) AS jumlah FROM dw.fact_flight_ontime
        UNION ALL SELECT 'fact_route_traffic', COUNT(*) FROM dw.fact_route_traffic
        UNION ALL SELECT 'fact_ticket_market', COUNT(*) FROM dw.fact_ticket_market
    """).pl()
    print("\n=== Ringkasan akhir fact table ===")
    print(result)


def main():
    print("Menghubungkan ke Postgres & DuckDB...")
    con = connect()

    print("Reset & buat ulang fact table (idempoten)...")
    create_fact_tables(con)

    print("Loading fact (dengan data cleansing: dedup + null handling)...")
    load_fact_flight_ontime(con)
    load_fact_route_traffic(con)
    load_fact_ticket_market(con)

    verify(con)
    con.close()
    print(f"\nSelesai.")


if __name__ == "__main__":
    main()
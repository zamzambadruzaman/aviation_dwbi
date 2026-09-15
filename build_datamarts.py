"""
03_build_datamart.py — Bangun datamart (tabel agregat siap-pakai) dari fact
table di schema dw, disimpan sebagai schema mart di file DuckDB yang sama.

Kenapa perlu tahap ini: fact_ticket_market sendiri 13,5 juta baris. Kalau
Streamlit menjalankan agregasi on-the-fly setiap kali filter berubah, itu
scan jutaan baris berulang kali. Tahap ini melakukan agregasi SEKALI di sini,
menyimpan hasilnya di grain (tanggal x carrier x origin x dest) -- cukup detail
untuk semua filter/chart yang dipakai dashboard, tapi jauh lebih kecil dari
fact aslinya. Streamlit tinggal baca & SUM ulang tabel kecil ini saat filter
berubah.

Idempoten: schema mart di-reset (DROP+CREATE) setiap dijalankan.

Jalankan SETELAH 02_load_facts.py.

Jalankan : python 03_build_datamart.py
Butuh    : pip install duckdb
"""

from etl_common import connect_duckdb_only


def build_ontime_summary(con):
    con.execute("DROP TABLE IF EXISTS mart.ontime_summary;")
    con.execute("""
        CREATE TABLE mart.ontime_summary AS
        SELECT
            date_key, carrier_key, origin_airport_key, dest_airport_key,
            COUNT(*)                                                        AS total_flights,
            SUM(cancelled)                                                  AS total_cancelled,
            SUM(diverted)                                                   AS total_diverted,
            SUM(CASE WHEN cancelled = 0 THEN arr_delay ELSE 0 END)          AS sum_arr_delay,
            SUM(CASE WHEN cancelled = 0 THEN 1 ELSE 0 END)                  AS count_flown,
            SUM(CASE WHEN cancelled = 0 AND arr_delay <= 15 THEN 1 ELSE 0 END) AS count_on_time,
            SUM(carrier_delay)                                              AS sum_carrier_delay,
            SUM(weather_delay)                                              AS sum_weather_delay,
            SUM(nas_delay)                                                  AS sum_nas_delay,
            SUM(security_delay)                                             AS sum_security_delay,
            SUM(late_aircraft_delay)                                        AS sum_late_aircraft_delay
        FROM dw.fact_flight_ontime
        GROUP BY date_key, carrier_key, origin_airport_key, dest_airport_key
    """)


def build_traffic_summary(con):
    con.execute("DROP TABLE IF EXISTS mart.traffic_summary;")
    con.execute("""
        CREATE TABLE mart.traffic_summary AS
        SELECT
            date_key, carrier_key, origin_airport_key, dest_airport_key,
            SUM(seats)                AS total_seats,
            SUM(passengers)           AS total_passengers,
            SUM(freight)              AS total_freight,
            SUM(mail)                 AS total_mail,
            SUM(departures_performed) AS total_departures
        FROM dw.fact_route_traffic
        GROUP BY date_key, carrier_key, origin_airport_key, dest_airport_key
    """)


def build_market_summary(con):
    con.execute("DROP TABLE IF EXISTS mart.market_summary;")
    con.execute("""
        CREATE TABLE mart.market_summary AS
        SELECT
            date_key, carrier_key, origin_airport_key, dest_airport_key,
            SUM(passengers)                AS total_passengers,
            SUM(mkt_fare * passengers)      AS fare_revenue_proxy,
            SUM(mkt_distance * passengers)  AS distance_weighted_proxy
        FROM dw.fact_ticket_market
        GROUP BY date_key, carrier_key, origin_airport_key, dest_airport_key
    """)


def main():
    con = connect_duckdb_only()
    con.execute("CREATE SCHEMA IF NOT EXISTS mart;")

    print("Membangun mart.ontime_summary...")
    build_ontime_summary(con)
    print("Membangun mart.traffic_summary...")
    build_traffic_summary(con)
    print("Membangun mart.market_summary...")
    build_market_summary(con)

    print("\n=== Ringkasan datamart ===")
    for t in ["ontime_summary", "traffic_summary", "market_summary"]:
        n = con.execute(f"SELECT COUNT(*) FROM mart.{t}").fetchone()[0]
        print(f"  mart.{t}: {n:,} baris")

    con.close()
    print("\nSelesai. Streamlit app sekarang membaca dari schema mart, bukan dw.fact_*.")


if __name__ == "__main__":
    main()
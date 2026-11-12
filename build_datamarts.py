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
            f.date_key, d.full_date, d.year, d.quarter, d.month,
            f.carrier_key, f.origin_airport_key, f.dest_airport_key,
            COUNT(*)                                                        AS total_flights,
            SUM(f.cancelled)                                                  AS total_cancelled,
            SUM(f.diverted)                                                   AS total_diverted,
            SUM(CASE WHEN f.cancelled = 0 THEN f.arr_delay ELSE 0 END)          AS sum_arr_delay,
            SUM(CASE WHEN f.cancelled = 0 THEN 1 ELSE 0 END)                  AS count_flown,
            SUM(CASE WHEN f.cancelled = 0 AND f.arr_delay <= 15 THEN 1 ELSE 0 END) AS count_on_time,
            SUM(f.carrier_delay)                                              AS sum_carrier_delay,
            SUM(f.weather_delay)                                              AS sum_weather_delay,
            SUM(f.nas_delay)                                                  AS sum_nas_delay,
            SUM(f.security_delay)                                             AS sum_security_delay,
            SUM(f.late_aircraft_delay)                                        AS sum_late_aircraft_delay
        FROM dw.fact_flight_ontime f
        JOIN dw.dim_date d ON d.date_key = f.date_key
        GROUP BY f.date_key, d.full_date, d.year, d.quarter, d.month,
                 f.carrier_key, f.origin_airport_key, f.dest_airport_key
    """)


def build_traffic_summary(con):
    con.execute("DROP TABLE IF EXISTS mart.traffic_summary;")
    con.execute("""
        CREATE TABLE mart.traffic_summary AS
        SELECT
            f.date_key, d.full_date, d.year, d.quarter, d.month,
            f.carrier_key, f.origin_airport_key, f.dest_airport_key,
            SUM(f.seats)                AS total_seats,
            SUM(f.passengers)           AS total_passengers,
            SUM(f.freight)              AS total_freight,
            SUM(f.mail)                 AS total_mail,
            SUM(f.departures_performed) AS total_departures
        FROM dw.fact_route_traffic f
        JOIN dw.dim_date d ON d.date_key = f.date_key
        GROUP BY f.date_key, d.full_date, d.year, d.quarter, d.month,
                 f.carrier_key, f.origin_airport_key, f.dest_airport_key
    """)


def build_market_summary(con):
    # CATATAN: baris dengan carrier_code '99' DIKELUARKAN di sini.
    # Pada DB1B, kolom maskapai hanya berisi kode maskapai untuk itinerary
    # yang seluruhnya diterbangkan satu maskapai (on-line itinerary); selain
    # itu nilainya 99, yang menandakan itinerary interline. Kode 99 karena itu
    # bukan maskapai, dan bila dibiarkan akan muncul sebagai batang kelima
    # terbesar pada grafik pangsa pasar seolah-olah sebuah maskapai.
    # Verifikasi yang mendasari keputusan ini (Jan-Jun 2022):
    #   - pangsa penumpang 9,61%, satu-satunya kode tanpa carrier_name
    #   - tarif rata-rata $316,21 vs $201,88 untuk maskapai tunggal
    #   - KPI Tarif Rata-rata keseluruhan turun dari $212,86 ke $201,88 (-5,4%)
    # Penyaringan sengaja dilakukan di lapisan datamart, BUKAN di tabel fakta,
    # agar dw.fact_ticket_market tetap merepresentasikan sumber secara utuh.
    con.execute("DROP TABLE IF EXISTS mart.market_summary;")
    con.execute("""
        CREATE TABLE mart.market_summary AS
        SELECT
            f.date_key, d.full_date, d.year, d.quarter, d.month,
            f.carrier_key, f.origin_airport_key, f.dest_airport_key,
            SUM(f.passengers)                AS total_passengers,
            SUM(f.mkt_fare * f.passengers)      AS fare_revenue_proxy,
            SUM(f.mkt_distance * f.passengers)  AS distance_weighted_proxy
        FROM dw.fact_ticket_market f
        JOIN dw.dim_date d ON d.date_key = f.date_key
        JOIN dw.dim_carrier c ON c.carrier_key = f.carrier_key
        WHERE c.carrier_code <> '99'
        GROUP BY f.date_key, d.full_date, d.year, d.quarter, d.month,
                 f.carrier_key, f.origin_airport_key, f.dest_airport_key
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
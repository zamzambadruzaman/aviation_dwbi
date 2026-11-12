-- ============================================================
-- analysis_queries.sql
-- Query analisis untuk Final Project (Bab 6 dan Bab 7)
--
-- Jalankan:  duckdb -readonly transtats_dw.duckdb < analysis_queries.sql
-- atau buka  duckdb -readonly transtats_dw.duckdb  lalu tempel per blok.
--
-- Mode readonly dipakai agar tidak bentrok dengan Metabase yang berjalan.
-- Setiap query diberi nomor; kirimkan hasilnya untuk dipakai menyusun
-- narasi dan insight di laporan.
--
-- CATATAN GRAIN: ontime harian, traffic bulanan (date_key = tanggal 1 bulan),
-- market kuartalan (date_key = tanggal 1 bulan pertama kuartal). Query lintas
-- proses di bagian D menyamakan grain ke tingkat bulan lebih dulu.
-- ============================================================


-- ============================================================
-- A. OPERASIONAL DAN KETEPATAN WAKTU
-- ============================================================

-- A1. Ketepatan waktu per maskapai (min. 10.000 penerbangan)
--     Untuk: Bab 6.1, 6.2, 7.1
SELECT c.carrier_name,
       SUM(m.total_flights)                                      AS flights,
       SUM(m.count_on_time) / SUM(m.count_flown)                 AS on_time_rate,
       SUM(m.sum_arr_delay) / SUM(m.count_flown)                 AS avg_arr_delay,
       SUM(m.total_cancelled) / SUM(m.total_flights)             AS cancel_rate
FROM mart.ontime_summary m
JOIN dw.dim_carrier c ON c.carrier_key = m.carrier_key
GROUP BY 1
HAVING SUM(m.total_flights) >= 10000
ORDER BY on_time_rate DESC;


-- A2. Tren bulanan ketepatan waktu dan pembatalan
--     Untuk: Bab 6.2 (narasi tren)
SELECT m.year, m.month,
       SUM(m.total_flights)                          AS flights,
       SUM(m.count_on_time) / SUM(m.count_flown)     AS on_time_rate,
       SUM(m.sum_arr_delay) / SUM(m.count_flown)     AS avg_arr_delay,
       SUM(m.total_cancelled) / SUM(m.total_flights) AS cancel_rate
FROM mart.ontime_summary m
GROUP BY 1, 2
ORDER BY 1, 2;


-- A3. Komposisi penyebab keterlambatan (total dan proporsi)
--     Untuk: Bab 6.2, 7.1
SELECT 'carrier'        AS penyebab, SUM(sum_carrier_delay)        AS menit FROM mart.ontime_summary
UNION ALL SELECT 'weather',          SUM(sum_weather_delay)        FROM mart.ontime_summary
UNION ALL SELECT 'nas',              SUM(sum_nas_delay)            FROM mart.ontime_summary
UNION ALL SELECT 'security',         SUM(sum_security_delay)       FROM mart.ontime_summary
UNION ALL SELECT 'late_aircraft',    SUM(sum_late_aircraft_delay)  FROM mart.ontime_summary
ORDER BY menit DESC;


-- A4. Komposisi penyebab keterlambatan per maskapai (proporsi)
--     Untuk: Bab 7.1 — apakah profil penyebab berbeda antar maskapai
WITH t AS (
  SELECT c.carrier_name,
         SUM(m.sum_carrier_delay)       AS carrier_d,
         SUM(m.sum_weather_delay)       AS weather_d,
         SUM(m.sum_nas_delay)           AS nas_d,
         SUM(m.sum_late_aircraft_delay) AS late_ac_d,
         SUM(m.total_flights)           AS flights
  FROM mart.ontime_summary m
  JOIN dw.dim_carrier c ON c.carrier_key = m.carrier_key
  GROUP BY 1 HAVING SUM(m.total_flights) >= 10000
)
SELECT carrier_name,
       carrier_d  / NULLIF(carrier_d + weather_d + nas_d + late_ac_d, 0) AS pct_carrier,
       weather_d  / NULLIF(carrier_d + weather_d + nas_d + late_ac_d, 0) AS pct_weather,
       nas_d      / NULLIF(carrier_d + weather_d + nas_d + late_ac_d, 0) AS pct_nas,
       late_ac_d  / NULLIF(carrier_d + weather_d + nas_d + late_ac_d, 0) AS pct_late_aircraft
FROM t ORDER BY pct_late_aircraft DESC;


-- A5. Dua puluh bandara asal dengan keterlambatan terburuk (min. 20.000 penerbangan)
--     Untuk: Bab 6.2, 7.1 — apakah masalahnya terkonsentrasi di hub tertentu
SELECT a.airport_code, a.city_name,
       SUM(m.total_flights)                      AS flights,
       SUM(m.sum_arr_delay) / SUM(m.count_flown) AS avg_arr_delay,
       SUM(m.count_on_time) / SUM(m.count_flown) AS on_time_rate
FROM mart.ontime_summary m
JOIN dw.dim_airport a ON a.airport_key = m.origin_airport_key
GROUP BY 1, 2
HAVING SUM(m.total_flights) >= 20000
ORDER BY avg_arr_delay DESC
LIMIT 20;


-- ============================================================
-- B. KAPASITAS DAN LALU LINTAS
-- ============================================================

-- B1. Load factor per maskapai
--     Untuk: Bab 6.1, 7.1
SELECT c.carrier_name,
       SUM(t.total_seats)                         AS seats,
       SUM(t.total_passengers)                    AS pax,
       SUM(t.total_passengers) / SUM(t.total_seats) AS load_factor
FROM mart.traffic_summary t
JOIN dw.dim_carrier c ON c.carrier_key = t.carrier_key
GROUP BY 1
HAVING SUM(t.total_seats) >= 100000
ORDER BY load_factor DESC;


-- B2. Tren bulanan kapasitas dan load factor
--     Untuk: Bab 6.2 — pemulihan pasca pandemi sepanjang Jan-Jun 2022
SELECT t.year, t.month,
       SUM(t.total_seats)                           AS seats,
       SUM(t.total_passengers)                      AS pax,
       SUM(t.total_passengers) / SUM(t.total_seats) AS load_factor
FROM mart.traffic_summary t
GROUP BY 1, 2 ORDER BY 1, 2;


-- B3. Rute dengan load factor terendah di antara rute bervolume besar
--     Untuk: Bab 7.1, 7.3 — kandidat rute dengan kapasitas berlebih
SELECT o.airport_code || '-' || d.airport_code AS rute,
       SUM(t.total_seats)                           AS seats,
       SUM(t.total_passengers)                      AS pax,
       SUM(t.total_passengers) / SUM(t.total_seats) AS load_factor
FROM mart.traffic_summary t
JOIN dw.dim_airport o ON o.airport_key = t.origin_airport_key
JOIN dw.dim_airport d ON d.airport_key = t.dest_airport_key
GROUP BY 1
HAVING SUM(t.total_seats) >= 50000
ORDER BY load_factor ASC
LIMIT 20;


-- B4. Rute dengan load factor tertinggi (kandidat penambahan frekuensi)
--     Untuk: Bab 7.1, 7.3
SELECT o.airport_code || '-' || d.airport_code AS rute,
       SUM(t.total_seats)                           AS seats,
       SUM(t.total_passengers)                      AS pax,
       SUM(t.total_passengers) / SUM(t.total_seats) AS load_factor
FROM mart.traffic_summary t
JOIN dw.dim_airport o ON o.airport_key = t.origin_airport_key
JOIN dw.dim_airport d ON d.airport_key = t.dest_airport_key
GROUP BY 1
HAVING SUM(t.total_seats) >= 50000
ORDER BY load_factor DESC
LIMIT 20;


-- ============================================================
-- C. TARIF DAN PANGSA PASAR
-- ============================================================

-- C1. Pangsa pasar dan tarif per maskapai, termasuk tarif per mil
--     Untuk: Bab 6.1, 7.1
SELECT c.carrier_name,
       SUM(k.total_passengers)                                      AS pax,
       SUM(k.total_passengers) / SUM(SUM(k.total_passengers)) OVER () AS market_share,
       SUM(k.fare_revenue_proxy) / SUM(k.total_passengers)          AS avg_fare,
       SUM(k.distance_weighted_proxy) / SUM(k.total_passengers)     AS avg_distance,
       SUM(k.fare_revenue_proxy) / SUM(k.distance_weighted_proxy)   AS fare_per_mile
FROM mart.market_summary k
JOIN dw.dim_carrier c ON c.carrier_key = k.carrier_key
GROUP BY 1
HAVING SUM(k.total_passengers) >= 100000
ORDER BY market_share DESC;


-- C2. Konsentrasi pasar: pangsa kumulatif empat dan delapan maskapai terbesar
--     Untuk: Bab 7.1 — seberapa terkonsentrasi pasar domestik AS
WITH s AS (
  SELECT c.carrier_name,
         SUM(k.total_passengers) / SUM(SUM(k.total_passengers)) OVER () AS share
  FROM mart.market_summary k
  JOIN dw.dim_carrier c ON c.carrier_key = k.carrier_key
  GROUP BY 1
), r AS (
  SELECT carrier_name, share, ROW_NUMBER() OVER (ORDER BY share DESC) AS rn FROM s
)
SELECT SUM(CASE WHEN rn <= 4 THEN share END) AS cr4,
       SUM(CASE WHEN rn <= 8 THEN share END) AS cr8
FROM r;


-- C3. Jumlah maskapai yang bersaing per rute dan kaitannya dengan tarif
--     Untuk: Bab 7.1 — apakah rute dengan sedikit pesaing bertarif lebih tinggi
WITH rute AS (
  SELECT o.airport_code || '-' || d.airport_code AS rute,
         COUNT(DISTINCT k.carrier_key)                              AS n_maskapai,
         SUM(k.total_passengers)                                    AS pax,
         SUM(k.fare_revenue_proxy) / SUM(k.distance_weighted_proxy) AS fare_per_mile
  FROM mart.market_summary k
  JOIN dw.dim_airport o ON o.airport_key = k.origin_airport_key
  JOIN dw.dim_airport d ON d.airport_key = k.dest_airport_key
  GROUP BY 1
  HAVING SUM(k.total_passengers) >= 5000
)
SELECT CASE WHEN n_maskapai = 1 THEN '1 maskapai'
            WHEN n_maskapai = 2 THEN '2 maskapai'
            WHEN n_maskapai = 3 THEN '3 maskapai'
            ELSE '4 maskapai atau lebih' END AS tingkat_persaingan,
       COUNT(*)              AS jumlah_rute,
       SUM(pax)              AS total_pax,
       AVG(fare_per_mile)    AS rata2_fare_per_mile
FROM rute
GROUP BY 1
ORDER BY 1;


-- ============================================================
-- D. LINTAS PROSES BISNIS  (inti Bab 6.3)
--    Grain disamakan ke bulan x maskapai x rute
-- ============================================================

-- D1. Apakah rute dengan load factor tinggi juga rute dengan delay lebih buruk?
--     Untuk: Bab 6.3, 7.1 — pertanyaan utama laporan ini
WITH ot AS (
  SELECT m.year, m.month, m.carrier_key, m.origin_airport_key, m.dest_airport_key,
         SUM(m.total_flights)                      AS flights,
         SUM(m.sum_arr_delay) / SUM(m.count_flown) AS avg_delay,
         SUM(m.count_on_time) / SUM(m.count_flown) AS on_time_rate
  FROM mart.ontime_summary m
  GROUP BY 1,2,3,4,5
),
tr AS (
  SELECT t.year, t.month, t.carrier_key, t.origin_airport_key, t.dest_airport_key,
         SUM(t.total_seats)      AS seats,
         SUM(t.total_passengers) AS pax
  FROM mart.traffic_summary t
  GROUP BY 1,2,3,4,5
),
j AS (
  SELECT ot.*, tr.seats, tr.pax, tr.pax / NULLIF(tr.seats, 0) AS load_factor
  FROM ot JOIN tr
    ON  ot.year = tr.year AND ot.month = tr.month
    AND ot.carrier_key = tr.carrier_key
    AND ot.origin_airport_key = tr.origin_airport_key
    AND ot.dest_airport_key   = tr.dest_airport_key
  WHERE tr.seats >= 1000 AND ot.flights >= 20
)
SELECT CASE WHEN load_factor < 0.60 THEN 'a. di bawah 60%'
            WHEN load_factor < 0.70 THEN 'b. 60-70%'
            WHEN load_factor < 0.80 THEN 'c. 70-80%'
            WHEN load_factor < 0.90 THEN 'd. 80-90%'
            ELSE                         'e. 90% ke atas' END AS kelompok_load_factor,
       COUNT(*)           AS jumlah_rute_bulan,
       SUM(flights)       AS total_flights,
       AVG(avg_delay)     AS rata2_delay_menit,
       AVG(on_time_rate)  AS rata2_on_time_rate
FROM j
GROUP BY 1 ORDER BY 1;


-- D2. Korelasi numerik load factor dengan keterlambatan
--     Untuk: Bab 6.3 — angka pendamping D1
WITH ot AS (
  SELECT m.year, m.month, m.carrier_key, m.origin_airport_key, m.dest_airport_key,
         SUM(m.total_flights)                      AS flights,
         SUM(m.sum_arr_delay) / SUM(m.count_flown) AS avg_delay
  FROM mart.ontime_summary m GROUP BY 1,2,3,4,5
),
tr AS (
  SELECT t.year, t.month, t.carrier_key, t.origin_airport_key, t.dest_airport_key,
         SUM(t.total_seats) AS seats, SUM(t.total_passengers) AS pax
  FROM mart.traffic_summary t GROUP BY 1,2,3,4,5
)
SELECT COUNT(*)                                                   AS n,
       CORR(tr.pax / NULLIF(tr.seats,0), ot.avg_delay)            AS corr_lf_delay,
       CORR(ot.flights, ot.avg_delay)                             AS corr_volume_delay
FROM ot JOIN tr
  ON  ot.year = tr.year AND ot.month = tr.month
  AND ot.carrier_key = tr.carrier_key
  AND ot.origin_airport_key = tr.origin_airport_key
  AND ot.dest_airport_key   = tr.dest_airport_key
WHERE tr.seats >= 1000 AND ot.flights >= 20;


-- D3. Profil gabungan per maskapai: operasional, kapasitas, komersial
--     Untuk: Bab 6.3, 7.1, 8 — tabel utama yang menghubungkan ketiga proses
WITH o AS (
  SELECT m.carrier_key,
         SUM(m.total_flights)                      AS flights,
         SUM(m.count_on_time) / SUM(m.count_flown) AS on_time_rate,
         SUM(m.sum_arr_delay) / SUM(m.count_flown) AS avg_delay
  FROM mart.ontime_summary m GROUP BY 1
),
t AS (
  SELECT carrier_key,
         SUM(total_passengers) / SUM(total_seats) AS load_factor,
         SUM(total_passengers)                    AS pax_t100
  FROM mart.traffic_summary GROUP BY 1
),
k AS (
  SELECT carrier_key,
         SUM(fare_revenue_proxy) / SUM(total_passengers)    AS avg_fare,
         SUM(fare_revenue_proxy) / SUM(distance_weighted_proxy) AS fare_per_mile,
         SUM(total_passengers)                              AS pax_db1b
  FROM mart.market_summary GROUP BY 1
)
SELECT c.carrier_name, o.flights, o.on_time_rate, o.avg_delay,
       t.load_factor, k.avg_fare, k.fare_per_mile
FROM o
JOIN dw.dim_carrier c ON c.carrier_key = o.carrier_key
LEFT JOIN t ON t.carrier_key = o.carrier_key
LEFT JOIN k ON k.carrier_key = o.carrier_key
WHERE o.flights >= 10000
ORDER BY o.on_time_rate DESC;


-- D4. Rute yang muncul di dua daftar sekaligus: traffic tinggi dan delay buruk
--     Untuk: Bab 6.3, 7.3 — kandidat prioritas perbaikan
WITH top_traffic AS (
  SELECT t.origin_airport_key, t.dest_airport_key, SUM(t.total_passengers) AS pax
  FROM mart.traffic_summary t GROUP BY 1,2 ORDER BY pax DESC LIMIT 50
),
worst_delay AS (
  SELECT m.origin_airport_key, m.dest_airport_key,
         SUM(m.total_flights)                      AS flights,
         SUM(m.sum_arr_delay) / SUM(m.count_flown) AS avg_delay
  FROM mart.ontime_summary m GROUP BY 1,2
  HAVING SUM(m.total_flights) >= 500
)
SELECT o.airport_code || '-' || d.airport_code AS rute,
       tt.pax, wd.flights, wd.avg_delay
FROM top_traffic tt
JOIN worst_delay wd
  ON wd.origin_airport_key = tt.origin_airport_key
 AND wd.dest_airport_key   = tt.dest_airport_key
JOIN dw.dim_airport o ON o.airport_key = tt.origin_airport_key
JOIN dw.dim_airport d ON d.airport_key = tt.dest_airport_key
ORDER BY wd.avg_delay DESC
LIMIT 20;
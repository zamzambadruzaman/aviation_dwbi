# Metabase + DuckDB driver (MotherDuck community driver)
#
# Versi SENGAJA di-pin (bukan :latest) supaya setup ini reproducible dan
# bisa dikutip persis di laporan Bab 3.4 / Bab 4.
#   - Metabase        : v0.58.33.x
#   - DuckDB driver   : 1.5.5.0  (Metabase 63 + DuckDB 1.5.5)
#
# PENTING: pakai base image berbasis Debian/Ubuntu (bukan Alpine) —
# driver DuckDB butuh glibc dan akan gagal di Alpine (musl).

FROM eclipse-temurin:21-jre

ENV MB_PLUGINS_DIR=/plugins
RUN mkdir -p ${MB_PLUGINS_DIR} /app /data

# --- Metabase ---
# Ganti vX.Y.Z dengan versi Metabase yang Anda pilih, contoh: v0.56.8
ADD https://downloads.metabase.com/v0.58.33.x/metabase.jar /app/metabase.jar

# --- DuckDB driver ---
ADD https://github.com/MotherDuck-Open-Source/metabase_duckdb_driver/releases/download/1.5.5.0/duckdb.metabase-driver.jar ${MB_PLUGINS_DIR}/

EXPOSE 3000
CMD ["java", "-jar", "/app/metabase.jar"]
mkdir -p data/ontime && cd data/ontime

for y in 2022 2023 2024; do
  for m in $(seq 1 12); do
    FILE="On_Time_Reporting_Carrier_On_Time_Performance_1987_present_${y}_${m}.zip"
    echo "Downloading $FILE ..."
    wget -q "https://transtats.bts.gov/PREZIP/${FILE}"
    unzip -o -q "${FILE}"
    rm "${FILE}"
  done
done

echo "Selesai. Total file CSV:"
ls *.csv | wc -l
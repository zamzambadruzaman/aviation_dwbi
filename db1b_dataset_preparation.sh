mkdir -p data/db1b && cd data/db1b

for y in 2022 2023 2024; do
  for q in 1 2 3 4; do
    FILE="Origin_and_Destination_Survey_DB1BMarket_${y}_${q}.zip"
    echo "Downloading $FILE ..."
    wget -q "https://transtats.bts.gov/PREZIP/${FILE}"
    unzip -o -q "${FILE}"
    rm "${FILE}"
  done
done

echo "Selesai. Total file CSV:"
ls *.csv | wc -l
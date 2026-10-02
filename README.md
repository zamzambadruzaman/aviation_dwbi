# Aviation Datawarehouse Project

An aviation data warehouse and BI project built from U.S. Bureau of Transportation Statistics (BTS) TranStats data. It loads flight operations, route traffic, and ticket-market data into a DuckDB warehouse and provides an interactive Streamlit dashboard.

The ETL scope is **January 1–June 30, 2022**. The download scripts currently fetch data for 2022–2024; the ETL filters to the configured date range.

## What’s included

- **ETL:** PostgreSQL staging tables are loaded into DuckDB dimension and fact tables, then summarized into dashboard-ready data marts.
- **Dashboard:** Streamlit dashboard with executive KPIs and views for on-time operations, route traffic/capacity, and ticket fares/market share. It supports date and carrier filters and light/dark themes.
- **Optional Metabase:** Docker setup with a DuckDB driver, exposing the local warehouse read-only on port `3000`.
- **Data profiling:** A script for inspecting CSV files, including row counts, columns, missing values, duplicates, and sample rows.

## Requirements

- Python **3.12 or newer**
- [`uv`](https://docs.astral.sh/uv/) for the locked Python environment (or another tool that can install the dependencies in `pyproject.toml`)
- PostgreSQL and `psql` for staging and ETL
- Docker Compose for the optional local PostgreSQL and Metabase services
- `wget` and `unzip` to use the supplied BTS download scripts

## Install Python dependencies

From the repository root:

```sh
uv sync
```

This installs the dependencies declared in `pyproject.toml` using `uv.lock`.

## Data inputs

The scripts expect CSV files in these directories:

| Dataset | Expected directory | Preparation |
| --- | --- | --- |
| BTS On-Time Reporting | `data/ontime/` | `bash ontime_dataset_preparation.sh` |
| BTS DB1B Market | `data/db1b/` | `bash db1b_dataset_preparation.sh` |
| BTS T-100 Segment | `data/T100/` | Place the downloaded/extracted CSV files here; this repository does not currently include a T-100 download script. |

The supplied On-Time and DB1B scripts download all months/quarters for 2022–2024. The ETL scope is controlled by `SCOPE_START` and `SCOPE_END` in `etl_common.py`.

To inspect a dataset folder, for example:

```sh
uv run python profile_data.py data/ontime
```

## PostgreSQL staging and ETL

An optional local PostgreSQL instance can be started from the repository root:

```sh
docker compose -f postgres_local/docker-compose.yaml up -d
```

The Compose file configures user `postgres`, password `postgres`, and database `mydb`. The staging loader currently connects to database `postgres` on `localhost:5432` and expects the staging tables to exist before loading data. **The SQL that creates those staging tables is not included in this repository.**

> **Before running the ETL, reconcile the PostgreSQL setup:** `load_to_postgres.sh` loads into schema `dirgantara_db`, while `load_dimensions.py` and `load_facts.py` read from schema `transtats_db`. Create/configure the staging schema and tables consistently, or update the loader/ETL queries so they use the same schema. Also update the connection string in `etl_common.py` to match your PostgreSQL host, port, credentials, and database.

Once the staging tables and connection are configured, run the pipeline from the repository root in this order:

```sh
bash load_to_postgres.sh
uv run python load_dimensions.py
uv run python load_facts.py
uv run python build_datamarts.py
```

The stages create:

1. `dw.dim_date`, `dw.dim_airport`, `dw.dim_carrier`, and `dw.dim_aircraft_type`
2. `dw.fact_flight_ontime`, `dw.fact_route_traffic`, and `dw.fact_ticket_market`
3. `mart.ontime_summary`, `mart.traffic_summary`, and `mart.market_summary`

The dimension and fact loaders rebuild their destination tables when run. Run the dimension stage before facts, and the fact stage before building the marts.

## Run the Streamlit dashboard

After the DuckDB warehouse and marts have been built:

```sh
uv run streamlit run streamlit_app.py
```

The dashboard reads `transtats_dw.duckdb` in read-only mode. It includes:

- Executive summary KPIs for flights, on-time performance, delays, cancellations, passengers, load factor, and fares
- Operational/on-time performance analysis
- Route traffic and capacity analysis
- Ticket fares and market-share analysis

Use the sidebar to filter the date range and carriers. The DuckDB file is a generated local artifact and is ignored by Git; the dashboard will not have data until the ETL has populated it.

## Optional: run Metabase

With Docker available and `transtats_dw.duckdb` present in the repository root:

```sh
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000). The Compose configuration mounts the DuckDB file read-only and persists Metabase’s own metadata in a Docker volume.

## Repository layout

```text
.
├── data/                           # Local BTS CSV inputs (not committed)
├── postgres_local/                 # Optional PostgreSQL Compose configuration
├── etl_common.py                   # Shared connection and date-scope configuration
├── load_to_postgres.sh             # Load CSV inputs into PostgreSQL staging
├── load_dimensions.py              # Build/load warehouse dimensions
├── load_facts.py                   # Build/load warehouse facts
├── build_datamarts.py              # Build dashboard summary tables
├── streamlit_app.py                # Interactive Streamlit dashboard
├── profile_data.py                 # CSV profiling utility
├── Dockerfile                      # Metabase image with DuckDB driver
└── docker-compose.yml              # Optional Metabase service
```

Large source datasets and DuckDB database files should remain local or be stored in a data-storage service; they are not suitable for ordinary GitHub commits.

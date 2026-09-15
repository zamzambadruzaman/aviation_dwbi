"""
streamlit_app.py — Dashboard TranStats
Proses bisnis: Operasional & Ketepatan Waktu | Kapasitas & Traffic Rute | Tarif & Pangsa Pasar

PENTING: app ini HANYA membaca (read-only) dari:
  - schema mart.*   -> tabel agregat siap-pakai, hasil 03_build_datamart.py
  - schema dw.dim_* -> tabel dimensi kecil, untuk menampilkan nama/kode
Tidak ada agregasi berat dijalankan di sini; semua sudah disiapkan lebih dulu.

Urutan pipeline lengkap:
  1. python 01_load_dimensions.py
  2. python 02_load_facts.py
  3. python 03_build_datamart.py
  4. streamlit run streamlit_app.py   <-- file ini

Butuh: pip install streamlit duckdb pandas plotly
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.io as pio
from datetime import date

from etl_common import connect_duckdb_only, DUCKDB_PATH, SCOPE_START, SCOPE_END

# ==========================================================
# KONFIGURASI HALAMAN & STYLING
# ==========================================================
st.set_page_config(page_title="TranStats Airline Dashboard", page_icon="✈️", layout="wide")

BRAND_COLORS = ["#1656D9", "#00B2A9", "#F2994A", "#EB5757", "#9B51E0", "#2D9CDB", "#27AE60", "#828282"]
pio.templates["brand"] = pio.templates["plotly_white"]
pio.templates["brand"].layout.colorway = BRAND_COLORS
pio.templates["brand"].layout.font = dict(family="sans serif", size=13, color="#1A2233")
pio.templates["brand"].layout.title.font = dict(size=16, color="#14203D")
pio.templates["brand"].layout.margin = dict(l=10, r=10, t=50, b=10)
pio.templates.default = "brand"

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; }

    .block-container {
        padding-top: 1.3rem;
        padding-bottom: 1.5rem;
        padding-left: 2.2rem;
        padding-right: 2.2rem;
    }

    div[data-testid="stMetric"] {
        background-color: #EEF3FB;
        border: none;
        border-radius: 10px;
        padding: 10px 16px 8px 16px;
    }
    div[data-testid="stMetricLabel"] {
        font-weight: 600; color: #5B6472; font-size: 0.74rem;
        text-transform: uppercase; letter-spacing: 0.03em;
    }
    div[data-testid="stMetricValue"] { font-size: 1.45rem; font-weight: 700; color: #0F172A; }

    h1 { font-size: 1.55rem; font-weight: 800; color: #0F172A; padding-bottom: 0; margin-bottom: 0.1rem; }
    .app-subtitle { color: #6B7280; font-size: 0.86rem; margin-top: 0; margin-bottom: 0.6rem; }
    .section-label {
        font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.04em; color: #2563EB; margin: 0.2rem 0 0.15rem 2px;
    }
    .app-footer { color: #9CA3AF; font-size: 0.72rem; text-align: center; margin-top: 1rem; }

    button[data-baseweb="tab"] { font-weight: 600; padding: 4px 14px; font-size: 0.9rem; }

    div[data-testid="stVerticalBlock"] { gap: 0.6rem; }
</style>
""", unsafe_allow_html=True)


# ==========================================================
# FORMATTER AMAN-NaN — dipakai tiap kali menampilkan angka KPI.
# Perlu karena SUM() atas hasil filter yang kosong (mis. maskapai
# terpilih tidak muncul sama sekali di salah satu fact pada rentang
# tanggal terpilih) menghasilkan NULL/NaN, dan int(NaN) akan error.
# ==========================================================
def fmt_int(val):
    return "N/A" if pd.isna(val) else f"{int(val):,}"


def fmt_pct(val, decimals=1):
    return "N/A" if pd.isna(val) else f"{val * 100:.{decimals}f}%"


def fmt_money(val, decimals=2):
    return "N/A" if pd.isna(val) else f"${val:,.{decimals}f}"


def fmt_num(val, decimals=1, suffix=""):
    return "N/A" if pd.isna(val) else f"{val:.{decimals}f}{suffix}"


@st.cache_resource
def get_connection():
    return connect_duckdb_only(read_only=True)


@st.cache_data
def run_query(sql):
    return get_connection().execute(sql).df()


@st.cache_data
def load_carrier_list():
    return run_query("""
        SELECT carrier_code, COALESCE(carrier_name, carrier_code) AS display_name
        FROM dw.dim_carrier
        ORDER BY display_name
    """)


def styled_chart(fig, height=300):
    fig.update_layout(
        height=height,
        title_x=0.02,
        margin=dict(l=10, r=10, t=40, b=5),
        plot_bgcolor="white",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="#EEF1F6", zeroline=False),
    )
    st.plotly_chart(fig, use_container_width=True)


def chart_or_empty(df, render_fn, empty_msg="Tidak ada data untuk kombinasi filter ini."):
    """Render chart lewat render_fn(df) kalau df ada isinya, kalau tidak tampilkan pesan info."""
    if df is None or df.empty:
        st.info(empty_msg)
    else:
        render_fn(df)


def section_label(text):
    st.markdown(f'<p class="section-label">{text}</p>', unsafe_allow_html=True)


def kpi_row(items):
    """items: list of (label, value_str) tuples, dirender sebagai kartu metric flat."""
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        with col:
            st.metric(label, value)


# ==========================================================
# HEADER
# ==========================================================
st.title("✈️  TranStats Airline Dashboard")
st.markdown(
    '<p class="app-subtitle">Analisis Operasional, Kapasitas, dan Pangsa Pasar Penerbangan AS · Jan–Jun 2022</p>',
    unsafe_allow_html=True,
)

# ==========================================================
# SIDEBAR — filter global
# ==========================================================
with st.sidebar:
    st.header("🔎 Filter")

    date_range = st.date_input(
        "Rentang tanggal",
        value=(SCOPE_START, SCOPE_END),
        min_value=SCOPE_START,
        max_value=SCOPE_END,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        filter_start, filter_end = date_range
    else:
        filter_start, filter_end = SCOPE_START, SCOPE_END

    carrier_df = load_carrier_list()
    selected_carriers = st.multiselect(
        "Maskapai (kosongkan = semua)", options=carrier_df["display_name"].tolist(), default=[]
    )
    st.divider()
    st.caption(f"📁 Sumber: `{DUCKDB_PATH}`  ·  schema `mart`")

selected_codes = None
if selected_carriers:
    selected_codes = carrier_df[carrier_df["display_name"].isin(selected_carriers)]["carrier_code"].tolist()

date_key_start = int(filter_start.strftime("%Y%m%d"))
date_key_end = int(filter_end.strftime("%Y%m%d"))


def carrier_clause(alias="dc"):
    if selected_codes:
        codes = ",".join(f"'{c}'" for c in selected_codes)
        return f"AND {alias}.carrier_code IN ({codes})"
    return ""


# ==========================================================
# TABS — navigasi utama
# ==========================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📊  Ringkasan Eksekutif",
    "🛫  Operasional & Ketepatan Waktu",
    "📦  Kapasitas & Traffic Rute",
    "💰  Tarif & Pangsa Pasar",
])

# ----------------------------------------------------------
# TAB 1 — RINGKASAN EKSEKUTIF
# ----------------------------------------------------------
with tab1:
    clause = carrier_clause("dc")

    ontime_kpi = run_query(f"""
        SELECT
            SUM(total_flights) AS total_flights,
            SUM(total_cancelled) AS total_cancelled,
            SUM(sum_arr_delay) / NULLIF(SUM(count_flown), 0) AS avg_arr_delay,
            SUM(count_on_time)::DOUBLE / NULLIF(SUM(count_flown), 0) AS on_time_rate
        FROM mart.ontime_summary m
        JOIN dw.dim_carrier dc ON dc.carrier_key = m.carrier_key
        WHERE m.date_key BETWEEN {date_key_start} AND {date_key_end} {clause}
    """)
    traffic_kpi = run_query(f"""
        SELECT
            SUM(total_passengers) AS total_passengers,
            SUM(total_seats) AS total_seats,
            SUM(total_passengers) / NULLIF(SUM(total_seats), 0) AS load_factor
        FROM mart.traffic_summary m
        JOIN dw.dim_carrier dc ON dc.carrier_key = m.carrier_key
        WHERE m.date_key BETWEEN {date_key_start} AND {date_key_end} {clause}
    """)
    market_kpi = run_query(f"""
        SELECT
            SUM(total_passengers) AS total_market_passengers,
            SUM(fare_revenue_proxy) / NULLIF(SUM(total_passengers), 0) AS avg_fare_weighted
        FROM mart.market_summary m
        JOIN dw.dim_carrier dc ON dc.carrier_key = m.carrier_key
        WHERE m.date_key BETWEEN {date_key_start} AND {date_key_end} {clause}
    """)

    total_flights = ontime_kpi["total_flights"][0]
    total_cancelled = ontime_kpi["total_cancelled"][0]
    cancel_rate = (total_cancelled / total_flights) if pd.notna(total_flights) and total_flights else None

    section_label("Operasional")
    kpi_row([
        ("Total Penerbangan", fmt_int(total_flights)),
        ("On-Time Rate", fmt_pct(ontime_kpi["on_time_rate"][0])),
        ("Rata-rata Delay", fmt_num(ontime_kpi["avg_arr_delay"][0], suffix=" mnt")),
        ("Tingkat Pembatalan", fmt_pct(cancel_rate, decimals=2)),
    ])

    section_label("Kapasitas & Pasar")
    kpi_row([
        ("Total Penumpang (T-100)", fmt_int(traffic_kpi["total_passengers"][0])),
        ("Load Factor", fmt_pct(traffic_kpi["load_factor"][0])),
        ("Rata-rata Tarif", fmt_money(market_kpi["avg_fare_weighted"][0])),
    ])

    st.caption("KPI di atas adalah draf awal — sesuaikan definisi & pilihannya dengan narasi Bab 4.1 Anda.")
    st.write("")

    trend = run_query(f"""
        SELECT d.full_date,
               SUM(m.count_on_time)::DOUBLE / NULLIF(SUM(m.count_flown), 0) AS on_time_rate
        FROM mart.ontime_summary m
        JOIN dw.dim_date d ON d.date_key = m.date_key
        JOIN dw.dim_carrier dc ON dc.carrier_key = m.carrier_key
        WHERE m.date_key BETWEEN {date_key_start} AND {date_key_end} {clause}
        GROUP BY d.full_date ORDER BY d.full_date
    """)

    def render_trend(df):
        fig = px.area(df, x="full_date", y="on_time_rate", title="Tren On-Time Rate Harian")
        fig.update_traces(line=dict(width=2.5))
        fig.update_yaxes(tickformat=".0%", title="On-Time Rate")
        fig.update_xaxes(title="")
        styled_chart(fig)

    chart_or_empty(trend.dropna(subset=["on_time_rate"]), render_trend)

# ----------------------------------------------------------
# TAB 2 — OPERASIONAL & KETEPATAN WAKTU
# ----------------------------------------------------------
with tab2:
    clause = carrier_clause("dc")
    col_a, col_b = st.columns(2)

    by_carrier = run_query(f"""
        SELECT dc.carrier_code, COALESCE(dc.carrier_name, dc.carrier_code) AS carrier_name,
               SUM(m.total_flights) AS total_flights,
               SUM(m.sum_arr_delay) / NULLIF(SUM(m.count_flown), 0) AS avg_delay
        FROM mart.ontime_summary m
        JOIN dw.dim_carrier dc ON dc.carrier_key = m.carrier_key
        WHERE m.date_key BETWEEN {date_key_start} AND {date_key_end} {clause}
        GROUP BY dc.carrier_code, dc.carrier_name
        HAVING SUM(m.total_flights) > 100
        ORDER BY avg_delay DESC LIMIT 15
    """).dropna(subset=["avg_delay"])

    def render_delay_bar(df):
        fig = px.bar(df, x="avg_delay", y="carrier_name", orientation="h", text_auto=".1f",
                      title="Rata-rata Keterlambatan Kedatangan per Maskapai (menit)")
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        styled_chart(fig)

    with col_a:
        chart_or_empty(by_carrier, render_delay_bar)

    delay_cause = run_query(f"""
        SELECT SUM(sum_carrier_delay) AS carrier_delay, SUM(sum_weather_delay) AS weather_delay,
               SUM(sum_nas_delay) AS nas_delay, SUM(sum_security_delay) AS security_delay,
               SUM(sum_late_aircraft_delay) AS late_aircraft_delay
        FROM mart.ontime_summary m
        JOIN dw.dim_carrier dc ON dc.carrier_key = m.carrier_key
        WHERE m.date_key BETWEEN {date_key_start} AND {date_key_end} {clause}
    """)
    cause_long = delay_cause.melt(var_name="penyebab", value_name="total_menit").dropna(subset=["total_menit"])
    cause_long = cause_long[cause_long["total_menit"] > 0]

    def render_cause_pie(df):
        fig = px.pie(df, names="penyebab", values="total_menit", hole=0.5,
                      title="Distribusi Total Menit Delay Berdasarkan Penyebab")
        fig.update_traces(textinfo="percent", textposition="inside", insidetextorientation="horizontal")
        fig.update_layout(uniformtext=dict(minsize=10, mode="hide"),
                           legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02))
        styled_chart(fig)

    with col_b:
        chart_or_empty(cause_long, render_cause_pie)

    top_routes = run_query(f"""
        SELECT o.airport_code || ' → ' || d.airport_code AS route,
               SUM(m.total_flights) AS total_flights,
               SUM(m.sum_arr_delay) / NULLIF(SUM(m.count_flown), 0) AS avg_delay
        FROM mart.ontime_summary m
        JOIN dw.dim_airport o ON o.airport_key = m.origin_airport_key
        JOIN dw.dim_airport d ON d.airport_key = m.dest_airport_key
        JOIN dw.dim_carrier dc ON dc.carrier_key = m.carrier_key
        WHERE m.date_key BETWEEN {date_key_start} AND {date_key_end} {clause}
        GROUP BY route HAVING SUM(m.total_flights) > 50
        ORDER BY avg_delay DESC LIMIT 15
    """).dropna(subset=["avg_delay"])
    section_label("Rute dengan Rata-rata Delay Tertinggi")
    chart_or_empty(top_routes, lambda df: st.dataframe(df, use_container_width=True, hide_index=True))

# ----------------------------------------------------------
# TAB 3 — KAPASITAS & TRAFFIC RUTE
# ----------------------------------------------------------
with tab3:
    clause = carrier_clause("dc")

    monthly = run_query(f"""
        SELECT d.year, d.month, SUM(m.total_seats) AS total_seats, SUM(m.total_passengers) AS total_passengers
        FROM mart.traffic_summary m
        JOIN dw.dim_date d ON d.date_key = m.date_key
        JOIN dw.dim_carrier dc ON dc.carrier_key = m.carrier_key
        WHERE m.date_key BETWEEN {date_key_start} AND {date_key_end} {clause}
        GROUP BY d.year, d.month ORDER BY d.year, d.month
    """)

    def render_monthly(df):
        df = df.copy()
        df["periode"] = df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2)
        fig = px.line(df, x="periode", y=["total_seats", "total_passengers"],
                       title="Tren Kapasitas vs Penumpang per Bulan", markers=True)
        fig.update_traces(line=dict(width=2.5), marker=dict(size=7))
        fig.update_xaxes(title="")
        fig.update_yaxes(title="Jumlah")
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1, title=None))
        styled_chart(fig)

    chart_or_empty(monthly.dropna(subset=["total_seats", "total_passengers"], how="all"), render_monthly)

    col_a, col_b = st.columns(2)
    by_carrier = run_query(f"""
        SELECT dc.carrier_code, COALESCE(dc.carrier_name, dc.carrier_code) AS carrier_name,
               SUM(m.total_passengers) / NULLIF(SUM(m.total_seats), 0) AS load_factor
        FROM mart.traffic_summary m
        JOIN dw.dim_carrier dc ON dc.carrier_key = m.carrier_key
        WHERE m.date_key BETWEEN {date_key_start} AND {date_key_end} {clause}
        GROUP BY dc.carrier_code, dc.carrier_name
        HAVING SUM(m.total_seats) > 1000
        ORDER BY load_factor DESC LIMIT 15
    """).dropna(subset=["load_factor"])

    def render_lf(df):
        fig = px.bar(df, x="load_factor", y="carrier_name", orientation="h", text_auto=".0%",
                      title="Load Factor per Maskapai (Top 15)")
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_xaxes(tickformat=".0%", title="")
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        styled_chart(fig)

    with col_a:
        chart_or_empty(by_carrier, render_lf)

    top_routes = run_query(f"""
        SELECT o.airport_code || ' → ' || d.airport_code AS route,
               SUM(m.total_passengers) AS total_passengers
        FROM mart.traffic_summary m
        JOIN dw.dim_airport o ON o.airport_key = m.origin_airport_key
        JOIN dw.dim_airport d ON d.airport_key = m.dest_airport_key
        JOIN dw.dim_carrier dc ON dc.carrier_key = m.carrier_key
        WHERE m.date_key BETWEEN {date_key_start} AND {date_key_end} {clause}
        GROUP BY route ORDER BY total_passengers DESC LIMIT 15
    """).dropna(subset=["total_passengers"])

    def render_top_routes_traffic(df):
        fig = px.bar(df, x="total_passengers", y="route", orientation="h", text_auto=".2s",
                      title="Rute dengan Traffic Penumpang Tertinggi")
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        styled_chart(fig)

    with col_b:
        chart_or_empty(top_routes, render_top_routes_traffic)

# ----------------------------------------------------------
# TAB 4 — TARIF & PANGSA PASAR
# ----------------------------------------------------------
with tab4:
    clause = carrier_clause("dc")

    by_carrier = run_query(f"""
        SELECT dc.carrier_code, COALESCE(dc.carrier_name, dc.carrier_code) AS carrier_name,
               SUM(m.total_passengers) AS total_passengers,
               SUM(m.fare_revenue_proxy) / NULLIF(SUM(m.total_passengers), 0) AS avg_fare
        FROM mart.market_summary m
        JOIN dw.dim_carrier dc ON dc.carrier_key = m.carrier_key
        WHERE m.date_key BETWEEN {date_key_start} AND {date_key_end} {clause}
        GROUP BY dc.carrier_code, dc.carrier_name
        HAVING SUM(m.total_passengers) > 1000
        ORDER BY total_passengers DESC LIMIT 15
    """).dropna(subset=["total_passengers"])

    col_a, col_b = st.columns(2)

    def render_share_pie(df):
        fig = px.pie(df, names="carrier_name", values="total_passengers", hole=0.5,
                      title="Pangsa Pasar Berdasarkan Jumlah Penumpang (Top 15)")
        fig.update_traces(textinfo="percent", textposition="inside", insidetextorientation="horizontal")
        fig.update_layout(uniformtext=dict(minsize=10, mode="hide"),
                           legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02))
        styled_chart(fig)

    with col_a:
        chart_or_empty(by_carrier, render_share_pie)

    def render_fare_bar(df):
        fig = px.bar(df.sort_values("avg_fare"), x="avg_fare", y="carrier_name", orientation="h",
                      text_auto=",.0f", title="Rata-rata Tarif per Maskapai (tertimbang penumpang)")
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        styled_chart(fig)

    with col_b:
        chart_or_empty(by_carrier.dropna(subset=["avg_fare"]), render_fare_bar)

    route_fare = run_query(f"""
        SELECT o.airport_code || ' → ' || d.airport_code AS route,
               SUM(m.distance_weighted_proxy) / NULLIF(SUM(m.total_passengers), 0) AS avg_distance,
               SUM(m.fare_revenue_proxy) / NULLIF(SUM(m.total_passengers), 0) AS avg_fare,
               SUM(m.total_passengers) AS total_passengers
        FROM mart.market_summary m
        JOIN dw.dim_airport o ON o.airport_key = m.origin_airport_key
        JOIN dw.dim_airport d ON d.airport_key = m.dest_airport_key
        JOIN dw.dim_carrier dc ON dc.carrier_key = m.carrier_key
        WHERE m.date_key BETWEEN {date_key_start} AND {date_key_end} {clause}
        GROUP BY route HAVING SUM(m.total_passengers) > 500
    """).dropna(subset=["avg_distance", "avg_fare"], how="any")

    def render_scatter(df):
        fig = px.scatter(df, x="avg_distance", y="avg_fare", size="total_passengers",
                          hover_name="route", title="Tarif vs Jarak per Rute (ukuran bubble = jumlah penumpang)",
                          color_discrete_sequence=[BRAND_COLORS[0]])
        fig.update_traces(marker=dict(opacity=0.75, line=dict(width=0.5, color="white")))
        fig.update_xaxes(title="Jarak rata-rata (mil)")
        fig.update_yaxes(title="Tarif rata-rata ($)")
        styled_chart(fig, height=320)

    chart_or_empty(route_fare, render_scatter)

# ==========================================================
# FOOTER
# ==========================================================
st.markdown(
    '<p class="app-footer">TranStats Airline Dashboard · Sumber data: US DOT Bureau of Transportation '
    'Statistics · Dibangun dengan DuckDB + Streamlit</p>',
    unsafe_allow_html=True,
)
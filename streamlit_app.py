"""
streamlit_app.py — Dashboard TranStats
Proses bisnis: Operasional & Ketepatan Waktu | Kapasitas & Traffic Rute | Tarif & Pangsa Pasar

PENTING: app ini HANYA membaca (read-only) dari:
  - schema mart.*   -> tabel agregat siap-pakai, hasil build_datamart.py
  - schema dw.dim_* -> tabel dimensi kecil, untuk menampilkan nama/kode
Tidak ada agregasi berat dijalankan di sini; semua sudah disiapkan lebih dulu.

Urutan pipeline lengkap:
  1. python load_dimensions.py
  2. python load_facts.py
  3. python build_datamart.py
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

# Material Design color palette (Material Blue as primary, Material accents for series)
BRAND_COLORS = ["#1976D2", "#009688", "#FF9800", "#E53935", "#7B1FA2",
                "#039BE5", "#43A047", "#FBC02D", "#5E35B1", "#00897B",
                "#F4511E", "#3949AB", "#7CB342", "#8D6E63", "#546E7A"]

# Material 3 surface / on-surface tokens
LIGHT = dict(
    bg="#FFFFFF", surface="#F5F7FA", sidebar_bg="#F8F9FC",
    text_primary="#1C1B1F", text_secondary="#49454F",
    primary="#1565C0", outline="#E3E5EA",
    chart_font="#49454F", chart_title_font="#1C1B1F", chart_gridline="#ECEFF3",
)
DARK = dict(
    bg="#121212", surface="#1E1E1E", sidebar_bg="#181818",
    text_primary="#E6E1E5", text_secondary="#CAC4D0",
    primary="#90CAF9", outline="#2E2E2E",
    chart_font="#CAC4D0", chart_title_font="#E6E1E5", chart_gridline="#2A2A2A",
)


def configure_plotly_theme(dark: bool):
    t = DARK if dark else LIGHT
    base = "plotly_dark" if dark else "plotly_white"
    pio.templates["brand"] = pio.templates[base]
    pio.templates["brand"].layout.colorway = BRAND_COLORS
    pio.templates["brand"].layout.font = dict(family="Roboto, sans-serif", size=13, color=t["chart_font"])
    pio.templates["brand"].layout.title.font = dict(family="Roboto, sans-serif", size=16, color=t["chart_title_font"])
    pio.templates["brand"].layout.margin = dict(l=10, r=10, t=50, b=10)
    pio.templates["brand"].layout.paper_bgcolor = "rgba(0,0,0,0)"
    pio.templates["brand"].layout.plot_bgcolor = "rgba(0,0,0,0)"
    pio.templates.default = "brand"


def render_theme_css(dark: bool):
    t = DARK if dark else LIGHT
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');

        html, body, .stApp, .stApp * {{
            font-family: 'Roboto', -apple-system, 'Segoe UI', sans-serif;
        }}

        .stApp {{ background-color: {t['bg']}; }}
        section[data-testid="stSidebar"] {{
            background-color: {t['sidebar_bg']};
            border-right: 1px solid {t['outline']};
        }}

        .block-container {{
            padding: 1.25rem 2rem 1.5rem 2rem;
            max-width: 100%;
        }}

        .stApp, .stApp p, .stApp span, .stApp label, .stApp li {{ color: {t['text_primary']}; }}

        /* Material type scale — headline small / title medium */
        h1 {{
            font-size: 1.5rem !important; font-weight: 500 !important; letter-spacing: 0;
            color: {t['text_primary']} !important; padding: 0 !important; margin-bottom: 0.1rem !important;
        }}
        h2, h3 {{ font-weight: 500 !important; color: {t['text_primary']} !important; }}

        /* Material filled card — flat, no elevation shadow */
        div[data-testid="stMetric"] {{
            background-color: {t['surface']};
            border: 1px solid {t['outline']};
            border-radius: 12px;
            padding: 12px 16px 10px 16px;
        }}
        div[data-testid="stMetricLabel"] {{
            font-weight: 500; color: {t['text_secondary']} !important;
            font-size: 0.75rem; letter-spacing: 0.05em; text-transform: uppercase;
        }}
        div[data-testid="stMetricValue"] {{
            font-size: 1.5rem; font-weight: 500; color: {t['text_primary']} !important;
        }}

        .app-subtitle {{
            color: {t['text_secondary']} !important; font-size: 0.875rem;
            letter-spacing: 0.02em; margin: 0 0 0.75rem 0;
        }}
        .section-label {{
            font-size: 0.6875rem; font-weight: 500; text-transform: uppercase;
            letter-spacing: 0.08em; color: {t['primary']} !important; margin: 0.35rem 0 0.2rem 2px;
        }}
        .app-footer {{
            color: {t['text_secondary']} !important; font-size: 0.75rem;
            text-align: center; margin-top: 1.25rem; letter-spacing: 0.02em;
        }}

        /* Material tabs — indicator underline, medium weight */
        button[data-baseweb="tab"] {{
            font-weight: 500 !important; font-size: 0.875rem !important;
            letter-spacing: 0.02em; padding: 6px 18px !important;
        }}
        div[data-baseweb="tab-highlight"] {{ background-color: {t['primary']} !important; height: 2px; }}

        /* Material shape — rounded inputs & controls */
        div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {{
            border-radius: 8px !important; border-color: {t['outline']} !important;
        }}
        div[data-testid="stDataFrame"] {{
            background-color: {t['surface']}; border-radius: 12px; border: 1px solid {t['outline']};
        }}
        hr {{ border-color: {t['outline']}; }}
        div[data-testid="stVerticalBlock"] {{ gap: 0.65rem; }}
    </style>
    """, unsafe_allow_html=True)


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
    grid = DARK["chart_gridline"] if CURRENT_DARK else LIGHT["chart_gridline"]
    fig.update_layout(
        height=height,
        title_x=0.02,
        margin=dict(l=10, r=10, t=40, b=5),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor=grid, zeroline=False),
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
# DARK MODE — dibaca lebih dulu supaya tema (CSS & chart) konsisten
# di seluruh halaman, termasuk yang dirender sebelum sidebar penuh muncul
# ==========================================================
dark_mode = st.sidebar.toggle(":material/dark_mode: Mode Gelap", value=False)
CURRENT_DARK = dark_mode
configure_plotly_theme(dark_mode)
render_theme_css(dark_mode)

# ==========================================================
# HEADER
# ==========================================================
st.title(":material/flight_takeoff: TranStats Airline Dashboard")
st.markdown(
    '<p class="app-subtitle">Analisis Operasional, Kapasitas, dan Pangsa Pasar Penerbangan AS · Jan–Jun 2022</p>',
    unsafe_allow_html=True,
)

# ==========================================================
# SIDEBAR — filter global
# ==========================================================
with st.sidebar:
    st.divider()
    st.header(":material/tune: Filter")

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
    st.caption(f":material/database: Sumber: `{DUCKDB_PATH}`  ·  schema `mart`")

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
    ":material/dashboard: Ringkasan Eksekutif",
    ":material/schedule: Operasional & Ketepatan Waktu",
    ":material/airline_seat_recline_normal: Kapasitas & Traffic Rute",
    ":material/payments: Tarif & Pangsa Pasar",
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
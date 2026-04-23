import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import json
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

# ── GOOGLE SHEETS (via Service Account) ───────────────────────────────────────
# IDs de los spreadsheets — en st.secrets (NO en el código)
# Secrets requeridos en Streamlit Cloud:
#   GCP_SERVICE_ACCOUNT  = '{ ... json del key de la SA ... }'
#   MAIN_SHEET_ID        = '1abc...'   (el sheet con ventas/deuda/stock/gastos/etc)
#   DOLAR_SHEET_ID       = '1xyz...'   (el sheet de tipo de cambio)
#   PRODUCT_KEY_SHEET_ID = '1def...'   (el Product Key)

# GIDs de cada tab dentro del MAIN_SHEET
GID_FECHA_EXP  = 1343545783
GID_VENTAS     = 1735040693
GID_DEUDA      = 700818473
GID_STOCK      = 1454621843
GID_PENDIENTES = 514545578
GID_GASTOS     = 954051275
GID_CLIENTES   = 197301160

# GID del dólar dentro de DOLAR_SHEET
GID_DOLAR      = 1836470632

# GID del Product Key dentro de PRODUCT_KEY_SHEET (primera hoja)
GID_PRODUCT_KEY = 0


@st.cache_resource
def _gspread_client():
    """Crea el cliente gspread autenticado con Service Account (cacheado en memoria)."""
    sa_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
    creds = Credentials.from_service_account_info(
        sa_info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )
    return gspread.authorize(creds)


@st.cache_data(ttl=60)
def _ws_to_df(sheet_id: str, gid: int) -> pd.DataFrame:
    """Lee una worksheet por spreadsheet_id + gid y devuelve un DataFrame."""
    gc = _gspread_client()
    sh = gc.open_by_key(sheet_id)
    ws = next((w for w in sh.worksheets() if w.id == gid), None)
    if ws is None:
        raise ValueError(f"No se encontró worksheet con gid={gid} en sheet {sheet_id}")
    rows = ws.get_all_values()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows[1:], columns=rows[0])


st.set_page_config(
    page_title="Dashboard Stromberg",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    /* ── Claude Design × Gularo ────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

    html, body, [data-testid="stAppViewContainer"] * {
        font-family: 'Inter', -apple-system, sans-serif !important;
    }

    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"] {
        background: radial-gradient(ellipse at top, #0F0840 0%, #070320 70%) !important;
    }
    .block-container { padding-top: 4rem; padding-bottom: 3rem; }
    header[data-testid="stHeader"] { background: transparent; }

    /* ── KPI cards ─────────────────────────────────────────────────── */
    div[data-testid="metric-container"] {
        background: #FFFFFF;
        border-radius: 14px;
        padding: 18px 22px;
        border: none;
        box-shadow:
            0 10px 40px -10px rgba(0,0,0,0.5),
            0 2px 6px rgba(15,191,239,0.15);
        transition: transform .15s ease, box-shadow .2s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow:
            0 14px 50px -10px rgba(0,0,0,0.55),
            0 2px 12px rgba(15,191,239,0.35);
    }
    div[data-testid="metric-container"] label {
        color: #6B7AA5 !important;
        font-size: 0.72rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 1.2px;
    }
    div[data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #160B7C !important;
        font-size: 2rem !important;
        font-weight: 800 !important;
        line-height: 1.1 !important;
        letter-spacing: -0.02em;
    }
    div[data-testid="metric-container"] [data-testid="stMetricDelta"] {
        color: #0FBFEF !important;
        font-weight: 600;
    }

    /* ── Tabs ──────────────────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background: rgba(255,255,255,0.04);
        padding: 4px;
        border-radius: 12px;
        border: 1px solid rgba(15,191,239,0.12);
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 9px;
        padding: 10px 22px;
        color: #9BA8D4;
        border: none;
        font-weight: 600;
        font-size: 0.88rem;
        transition: all .15s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #F5F7FF;
        background: rgba(255,255,255,0.05);
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #0FBFEF 0%, #06A6D8 100%) !important;
        color: #070320 !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 16px rgba(15,191,239,0.4);
    }

    /* ── Dataframes ────────────────────────────────────────────────── */
    .stDataFrame, [data-testid="stDataFrame"] {
        background: #FFFFFF !important;
    }
    .stDataFrame [role="gridcell"],
    [data-testid="stDataFrame"] [role="gridcell"],
    .stDataFrame [role="rowheader"],
    [data-testid="stDataFrame"] [role="rowheader"] {
        background: #FFFFFF !important;
        color: #1A1D3A !important;
    }
    .stDataFrame [role="columnheader"],
    [data-testid="stDataFrame"] [role="columnheader"] {
        background: #160B7C !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    /* ── Typography ────────────────────────────────────────────────── */
    h1 { color: #0FBFEF !important; font-weight: 800 !important; letter-spacing: -0.02em !important; }
    h2 { color: #F5F7FF !important; font-weight: 700 !important; letter-spacing: -0.01em !important; }
    h3 { color: #E0E8FF !important; font-weight: 600 !important; }
    p, span, div, label { color: #E0E8FF; }

    /* ── Form controls ─────────────────────────────────────────────── */
    .stMultiSelect [data-baseweb="select"] > div,
    .stDateInput   [data-baseweb="input"]  > div {
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid rgba(15,191,239,0.2) !important;
        border-radius: 9px !important;
    }
    .stMultiSelect [data-baseweb="select"] > div:hover,
    .stDateInput   [data-baseweb="input"]  > div:hover {
        border-color: rgba(15,191,239,0.5) !important;
    }

    /* ── Misc ──────────────────────────────────────────────────────── */
    hr {
        border: none !important; height: 1px !important;
        background: linear-gradient(90deg, transparent 0%, rgba(15,191,239,0.3) 50%, transparent 100%) !important;
        margin: 1.2rem 0 !important;
    }
    [data-testid="stSidebar"] {
        background: #0A0530 !important;
        border-right: 1px solid rgba(15,191,239,0.15);
    }
    .stAlert {
        background: rgba(15,191,239,0.08) !important;
        border: 1px solid rgba(15,191,239,0.3) !important;
        border-radius: 10px !important;
    }
    .stAlert * { color: #E0E8FF !important; }
    .stButton > button {
        background: #0FBFEF !important; color: #070320 !important;
        border: none !important; border-radius: 9px !important;
        font-weight: 700 !important; padding: 8px 20px !important;
        transition: all .15s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(15,191,239,0.4);
    }
</style>
""", unsafe_allow_html=True)

PLOTLY_THEME = {
    "paper_bgcolor": "#FFFFFF",
    "plot_bgcolor":  "#FAFBFF",
    "font":  {"color": "#1A1D3A", "family": "Inter, sans-serif"},
    "xaxis": {"gridcolor": "rgba(22,11,124,0.08)", "linecolor": "rgba(22,11,124,0.2)",
              "tickfont": {"color": "#6B7AA5"}},
    "yaxis": {"gridcolor": "rgba(22,11,124,0.08)", "linecolor": "rgba(22,11,124,0.2)",
              "tickfont": {"color": "#6B7AA5"}},
    "margin": {"t": 50, "b": 40, "l": 40, "r": 20},
    "title":  {"font": {"color": "#160B7C", "size": 15, "family": "Inter, sans-serif"}},
}


# ── CARGA DE DATOS ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_dolar():
    df = _ws_to_df(st.secrets["DOLAR_SHEET_ID"], GID_DOLAR)
    df = df.dropna(subset=["Fecha", "Round"])
    df["close_num"] = (
        df["Round"]
        .str.replace("$", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
    )
    df["fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce").dt.normalize()
    df = df.dropna(subset=["fecha", "close_num"])
    serie = df.groupby("fecha")["close_num"].mean()
    idx_completo = pd.date_range(serie.index.min(), serie.index.max(), freq="D")
    serie = serie.reindex(idx_completo).ffill()
    return serie


def cruzar_con_dolar(ventas: pd.DataFrame, dolar_serie: pd.Series) -> pd.DataFrame:
    v = ventas.copy()
    v["fecha_join"] = v["Fecha"].dt.normalize()
    v["dolar_dia"]  = v["fecha_join"].map(dolar_serie)
    v["dolar_dia"]  = v["dolar_dia"].fillna(dolar_serie.mean())
    v["Total_USD"]  = (v["Total"] / v["dolar_dia"]).round(2)
    return v


@st.cache_data(ttl=3600)
def load_product_key():
    # El Product Key tiene 2 filas de header: fila 0 = fila extra, fila 1 = headers reales
    # (equivalente al header=1 del pd.read_csv anterior)
    gc = _gspread_client()
    sh = gc.open_by_key(st.secrets["PRODUCT_KEY_SHEET_ID"])
    ws = next((w for w in sh.worksheets() if w.id == GID_PRODUCT_KEY), None)
    if ws is None:
        return pd.DataFrame()
    rows = ws.get_all_values()
    if len(rows) < 2:
        return pd.DataFrame()
    df = pd.DataFrame(rows[2:], columns=[c.strip() for c in rows[1]])
    keep = ["SKU Limpio", "SubCategoria", "Marca", "MODEL"]
    df = df[[c for c in keep if c in df.columns]].copy()
    df["SKU Limpio"]   = df["SKU Limpio"].astype(str).str.strip()
    df["SubCategoria"] = df["SubCategoria"].astype(str).str.strip()
    df["Marca"]        = df["Marca"].astype(str).str.strip()
    df = df[df["SKU Limpio"].str.len() > 3]
    return df.drop_duplicates("SKU Limpio")


@st.cache_data(ttl=60)
def load_all():
    MAIN = st.secrets["MAIN_SHEET_ID"]
    try:
        ventas     = _ws_to_df(MAIN, GID_VENTAS)
        deuda      = _ws_to_df(MAIN, GID_DEUDA)
        stock      = _ws_to_df(MAIN, GID_STOCK)
        gastos     = _ws_to_df(MAIN, GID_GASTOS)
        pendientes = _ws_to_df(MAIN, GID_PENDIENTES)
        fecha_df   = _ws_to_df(MAIN, GID_FECHA_EXP)
        fecha_exp  = str(fecha_df.iloc[1, 0]).strip() if len(fecha_df) > 1 else "N/D"
    except Exception as e:
        st.error(f"❌ Error cargando datos desde Google Sheets: {e}")
        st.stop()

    # ── Ventas
    ventas["Fecha"]    = pd.to_datetime(ventas["Fecha"], errors="coerce")

    def parse_ars(col):
        return (col.astype(str)
                   .str.replace(r"[$ ]", "", regex=True)
                   .str.replace(".", "", regex=False)
                   .str.replace(",", ".", regex=False)
                   .pipe(pd.to_numeric, errors="coerce")
                   .fillna(0))

    ventas["Precio"]   = parse_ars(ventas["Precio"])
    ventas["Cantidad"] = pd.to_numeric(ventas["Cantidad"], errors="coerce").fillna(0)

    # ── Lógica Q / Facturación (replica fórmulas del Looker)
    _mod   = ventas["Modelo"].astype(str).str.strip()
    _codfo = ventas["FCRMVH_CODFOR"].astype(str).str.strip().str.upper()
    modelo_empty = _mod.isin(["", "nan", "NaN", "None", "☐"])
    is_credit    = _codfo.str.contains(r"CA0004|CB0004|CE0005|CEA007", na=False, regex=True)
    is_CA0004    = _codfo.eq("CA0004")
    is_DI_or_CI  = _codfo.isin(["DI", "CI"])

    ventas["Q_looker"] = np.where(modelo_empty, 0,
                          np.where(is_credit, -ventas["Cantidad"].abs(),
                                              ventas["Cantidad"]))
    ventas["Facturacion"] = np.where(is_DI_or_CI, 0,
                            np.where(modelo_empty & is_CA0004, -ventas["Precio"].abs(),
                            np.where(modelo_empty, 0,
                                     ventas["Precio"] * ventas["Q_looker"])))
    ventas["Cantidad"] = ventas["Q_looker"]
    ventas["Total"]    = ventas["Facturacion"]

    # ── Deuda (formato argentino)
    for c in ["SAL30","SAL60","SALMAY60","SALMAY90","TOTCTA","VALVEN","LIMCRED"]:
        deuda[c] = parse_ars(deuda[c])

    # ── Stock
    for c in ["DISPONIBLE","NV","OC","ST"]:
        stock[c] = pd.to_numeric(stock[c], errors="coerce").fillna(0)
    stock["CODIGO_DEPOSITO"] = pd.to_numeric(stock["CODIGO_DEPOSITO"], errors="coerce").fillna(0).astype(int)
    stock = stock[stock["CODIGO_DEPOSITO"].isin([1, 12, 15])]

    # ── Gastos
    gastos["W_FCHMOV"] = pd.to_datetime(gastos["W_FCHMOV"], errors="coerce")
    gastos["SALDO"]    = pd.to_numeric(gastos["SALDO"], errors="coerce").fillna(0)

    # ── Pendientes
    pendientes["CANTID"]        = pd.to_numeric(pendientes["CANTID"], errors="coerce").fillna(0)
    pendientes["Import"]        = pd.to_numeric(pendientes["Import"], errors="coerce").fillna(0)
    pendientes["nCntEstimada"]  = pd.to_numeric(pendientes["nCntEstimada"], errors="coerce").fillna(0)
    pendientes["FCRMVI_FCHENT"] = pd.to_datetime(pendientes["FCRMVI_FCHENT"], errors="coerce")

    return ventas, deuda, stock, gastos, pendientes, fecha_exp


# ── DASHBOARD ─────────────────────────────────────────────────────────────────
@st.fragment(run_every=120)
def dashboard():
    ventas, deuda, stock, gastos, pendientes, fecha_exp = load_all()
    dolar_serie = load_dolar()

    ventas = cruzar_con_dolar(ventas, dolar_serie)

    pk  = load_product_key()
    _pk = pk[["SKU Limpio", "SubCategoria", "Marca"]].drop_duplicates("SKU Limpio")
    ventas = ventas.merge(_pk, left_on="FCRMVI_ARTCOD", right_on="SKU Limpio", how="left"
                         ).drop(columns=["SKU Limpio"], errors="ignore")
    stock  = stock.merge(_pk,  left_on="STMPDH_ARTCOD",  right_on="SKU Limpio", how="left"
                        ).drop(columns=["SKU Limpio"], errors="ignore")

    ventas_pos = ventas.copy()

    # ── Canal: RETAIL / HOGAR / ECOMM
    _vend_u = ventas_pos["Vendedor"].astype(str).str.upper().str.strip()
    _cli_u  = ventas_pos["Cliente"].astype(str).str.upper().str.strip()
    retail_mask = _vend_u.str.contains("GER", na=False, regex=True)
    ecomm_mask  = (
        _cli_u.str.contains("CLIENTE CONTADO", na=False, regex=True) |
        _cli_u.str.contains("CLIENTE PARA",    na=False, regex=True)
    )
    ventas_pos["Canal"] = "HOGAR"
    ventas_pos.loc[retail_mask, "Canal"] = "RETAIL"
    ventas_pos.loc[ecomm_mask,  "Canal"] = "ECOMM"

    pendientes_pos = pendientes[pendientes["CANTID"] > 0]
    dolar_hoy = dolar_serie.iloc[-1]

    def get_sel(ev, key="y"):
        try:
            p = ev.selection.points[0]
            return p.get(key) or p.get("label") or p.get("x")
        except Exception:
            return None

    tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Resumen", "📈 Ventas", "💰 Deuda", "📦 Stock", "⏳ Pendientes", "💸 Gastos"
    ])

    # ────────────────────────────── TAB 0: RESUMEN
    with tab0:
        import datetime as _dt
        hoy     = _dt.date.today()
        mes_ini = hoy.replace(day=1)
        u12m_ini = (pd.Timestamp(mes_ini) - pd.DateOffset(months=12)).date()
        u12m_fin = mes_ini - _dt.timedelta(days=1)

        v_hoy  = ventas_pos[ventas_pos["Fecha"].dt.date == hoy]
        v_mes  = ventas_pos[ventas_pos["Fecha"].dt.date >= mes_ini]
        v_u12m = ventas_pos[(ventas_pos["Fecha"].dt.date >= u12m_ini) &
                            (ventas_pos["Fecha"].dt.date <= u12m_fin)]

        def _canal_metrics(df, canal):
            sub = df[df["Canal"] == canal]
            return sub["Total"].sum(), sub["Total_USD"].sum(), sub["Cantidad"].sum()

        st.markdown("""
        <style>
        .lkr-card { background:#FFFFFF; color:#1A1A1A; border-radius:12px; padding:14px 18px;
                    box-shadow:0 2px 8px rgba(0,0,0,.15); border:1px solid rgba(15,191,239,.3); }
        .lkr-head { text-align:center; font-weight:700; font-size:0.85rem; padding:10px 14px;
                    border-radius:10px 10px 0 0; color:white; letter-spacing:1px; }
        .lkr-head-hoy  { background:#4B57C9; }
        .lkr-head-mes  { background:#3E4BCC; }
        .lkr-head-u12m { background:#2E8555; }
        .lkr-head-sldc { background:#2E8AD6; }
        .lkr-head-stk  { background:#2E8AD6; }
        .lkr-head-pnd  { background:#D04444; }
        .lkr-head-ing  { background:#8D8717; }
        .lkr-head-pf   { background:#C93B3B; }
        .lkr-head-pv   { background:#C93B3B; }
        .lkr-row-label { background:#3E4BCC; color:white; padding:10px 14px; font-weight:700;
                         border-radius:10px 0 0 10px; display:flex; align-items:center; justify-content:center; }
        .lkr-value       { font-size:1.55rem; font-weight:700; color:#2E4A9C; }
        .lkr-value-q     { color:#8B00CC; }
        .lkr-value-usd   { color:#2E8555; }
        .lkr-value-small { font-size:1.2rem; }
        .lkr-value-red   { color:#D04444; }
        .lkr-value-gold  { color:#8D8717; }
        </style>
        """, unsafe_allow_html=True)

        def _fmt_ars(v): return f"{v:,.0f}" if pd.notna(v) else "—"
        def _fmt_usd(v): return f"{v:,.0f}" if pd.notna(v) else "—"
        def _fmt_q(v):   return f"{v:,.0f}" if pd.notna(v) else "—"

        col_main, col_side = st.columns([3, 1])

        with col_main:
            h1, h2, h3, h4 = st.columns([1, 2, 2, 2])
            h1.markdown("&nbsp;", unsafe_allow_html=True)
            h2.markdown('<div class="lkr-head lkr-head-hoy">HOY</div>',  unsafe_allow_html=True)
            h3.markdown('<div class="lkr-head lkr-head-mes">MES</div>',  unsafe_allow_html=True)
            h4.markdown('<div class="lkr-head lkr-head-u12m">U12M U$D</div>', unsafe_allow_html=True)

            r1, r2, r3, r4 = st.columns([1, 2, 2, 2])
            r1.markdown('<div class="lkr-row-label">$</div>', unsafe_allow_html=True)
            r2.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value">{_fmt_ars(v_hoy["Total"].sum())}</div></div>', unsafe_allow_html=True)
            r3.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value">{_fmt_ars(v_mes["Total"].sum())}</div></div>', unsafe_allow_html=True)
            r4.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-usd">{_fmt_usd(v_u12m["Total_USD"].sum())}</div></div>', unsafe_allow_html=True)

            q1, q2, q3, q4 = st.columns([1, 2, 2, 2])
            q1.markdown('<div class="lkr-row-label" style="background:#6B2DCC">Q</div>', unsafe_allow_html=True)
            q2.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-q">{_fmt_q(v_hoy["Cantidad"].sum())}</div></div>', unsafe_allow_html=True)
            q3.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-q">{_fmt_q(v_mes["Cantidad"].sum())}</div></div>', unsafe_allow_html=True)
            q4.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-q">{_fmt_q(v_u12m["Cantidad"].sum())}</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            for canal, color in [("RETAIL","#3E4BCC"), ("HOGAR","#3E4BCC"), ("ECOMM","#3E4BCC")]:
                ars_h, usd_h, _ = _canal_metrics(v_hoy,  canal)
                ars_m, usd_m, _ = _canal_metrics(v_mes,  canal)
                _, usd_u, _     = _canal_metrics(v_u12m, canal)
                c1, c2, c3, c4 = st.columns([1, 2, 2, 2])
                c1.markdown(f'<div class="lkr-row-label" style="background:{color}">{canal}</div>', unsafe_allow_html=True)
                ars_h_cls = "lkr-value-red" if ars_h < 0 else ""
                c2.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-small {ars_h_cls}">{_fmt_ars(ars_h)}</div></div>', unsafe_allow_html=True)
                c3.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-small">{_fmt_ars(ars_m)}</div></div>', unsafe_allow_html=True)
                c4.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-small lkr-value-usd">{_fmt_usd(usd_u)}</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            p1, p2, p3 = st.columns([1, 2, 2])
            pend_fact_usd = pendientes_pos["Import"].sum() / dolar_hoy if dolar_hoy else 0
            preventa_usd  = 0
            if "nCntEstimada" in pendientes_pos.columns:
                preventa_usd = (pendientes_pos["nCntEstimada"] * pendientes_pos["Import"] /
                                pendientes_pos["CANTID"].replace(0, 1)).sum() / dolar_hoy if dolar_hoy else 0
            p2.markdown('<div class="lkr-head lkr-head-pf">PEND FACTURAR U$D</div>', unsafe_allow_html=True)
            p2.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-usd">$ {pend_fact_usd/1000:.2f}K</div></div>', unsafe_allow_html=True)
            p3.markdown('<div class="lkr-head lkr-head-pv">PREVENTA U$D</div>', unsafe_allow_html=True)
            p3.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-usd">$ {preventa_usd/1000:.2f}K</div></div>', unsafe_allow_html=True)

        with col_side:
            st.markdown('<div class="lkr-head lkr-head-sldc">🟡 SALDOS COMERCIALES</div>', unsafe_allow_html=True)
            saldo = deuda["TOTCTA"].sum()
            st.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value">$ {saldo/1e6:.2f}M</div></div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            stk = stock["DISPONIBLE"].sum()
            pnd = pendientes_pos["CANTID"].sum()
            ing = stock["OC"].sum()

            s1, s2 = st.columns([1, 3])
            s1.markdown('<div class="lkr-head lkr-head-stk" style="padding:14px 8px;margin:0">STK</div>', unsafe_allow_html=True)
            s2.markdown(f'<div class="lkr-card" style="text-align:center;padding:10px"><div class="lkr-value lkr-value-small">{_fmt_q(stk)}</div></div>', unsafe_allow_html=True)

            p1_, p2_ = st.columns([1, 3])
            p1_.markdown('<div class="lkr-head lkr-head-pnd" style="padding:14px 8px;margin:0">PND</div>', unsafe_allow_html=True)
            p2_.markdown(f'<div class="lkr-card" style="text-align:center;padding:10px"><div class="lkr-value lkr-value-small lkr-value-red">{_fmt_q(pnd)}</div></div>', unsafe_allow_html=True)

            i1, i2 = st.columns([1, 3])
            i1.markdown('<div class="lkr-head lkr-head-ing" style="padding:14px 8px;margin:0">ING</div>', unsafe_allow_html=True)
            i2.markdown(f'<div class="lkr-card" style="text-align:center;padding:10px"><div class="lkr-value lkr-value-small lkr-value-gold">{_fmt_q(ing)}</div></div>', unsafe_allow_html=True)

            st.markdown("<br><br>", unsafe_allow_html=True)
            st.markdown(f'<div class="lkr-card" style="text-align:center;font-size:0.85rem;color:#555">{datetime.now().strftime("%b %d, %Y, %I:%M:%S %p")}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="lkr-card" style="text-align:center;font-weight:700;color:#2E4A9C">{dolar_hoy:,.2f}</div>', unsafe_allow_html=True)

        st.caption("💡 Clasificación RETAIL/HOGAR/ECOMM: Vendedor contiene 'GER' → RETAIL, Cliente contiene 'CLIENTE CONTADO/PARA' → ECOMM, resto → HOGAR.")

    # ────────────────────────────── TAB 1: VENTAS
    with tab1:
        cf1, cf2, cf3, cf4 = st.columns([2, 2, 2, 2])
        with cf1:
            marcas_disp = sorted(ventas_pos["Marca"].dropna().unique().tolist())
            marca_sel = st.multiselect("🏷️ Marca", marcas_disp, placeholder="Todas las marcas", key="f_marca")
        with cf2:
            cats_disp = sorted(ventas_pos["SubCategoria"].dropna().unique().tolist())
            cat_sel = st.multiselect("📂 Categoría", cats_disp, placeholder="Todas las categorías", key="f_cat")
        with cf3:
            vend_disp = sorted(ventas_pos["Vendedor"].dropna().unique().tolist())
            vend_sel = st.multiselect("👤 Vendedor", vend_disp, placeholder="Todos", key="f_vend")
        with cf4:
            u12m_start = (pd.Timestamp.today() - pd.DateOffset(months=12)).date()
            f_min = ventas_pos["Fecha"].min().date()
            f_max = ventas_pos["Fecha"].max().date()
            rango_v = st.date_input("📅 Período (default: U12M)",
                                    value=(max(u12m_start, f_min), f_max),
                                    min_value=f_min, max_value=f_max, key="f_fecha")

        vf = ventas_pos.copy()
        if marca_sel: vf = vf[vf["Marca"].isin(marca_sel)]
        if cat_sel:   vf = vf[vf["SubCategoria"].isin(cat_sel)]
        if vend_sel:  vf = vf[vf["Vendedor"].isin(vend_sel)]
        if isinstance(rango_v, (tuple, list)) and len(rango_v) == 2:
            vf = vf[(vf["Fecha"].dt.date >= rango_v[0]) & (vf["Fecha"].dt.date <= rango_v[1])]

        st.divider()

        if vf["Fecha"].notna().any():
            vm = vf.groupby(vf["Fecha"].dt.to_period("M")).agg(
                Total=("Total","sum"), Total_USD=("Total_USD","sum"),
                dolar_prom=("dolar_dia","mean")
            ).reset_index()
            vm["Mes"] = vm["Fecha"].astype(str)
            fig_dual = go.Figure()
            fig_dual.add_trace(go.Bar(name="Ventas ARS", x=vm["Mes"], y=vm["Total"],
                                      marker_color="#0FBFEF", yaxis="y1", opacity=0.7))
            fig_dual.add_trace(go.Scatter(name="Ventas USD", x=vm["Mes"], y=vm["Total_USD"],
                                          mode="lines+markers", marker_color="#f7c948",
                                          yaxis="y2", line=dict(width=3)))
            fig_dual.add_trace(go.Scatter(name="Dólar promedio", x=vm["Mes"], y=vm["dolar_prom"],
                                          mode="lines", line=dict(color="#e05c5c", dash="dot", width=2),
                                          yaxis="y3"))
            fig_dual.update_layout(
                paper_bgcolor="#FFFFFF", plot_bgcolor="#FAFBFF",
                font=dict(color="#1A1D3A", family="Inter, sans-serif"),
                margin=dict(t=50, b=60, l=40, r=80),
                title=dict(text="Ventas mensuales: ARS vs USD vs Tipo de cambio",
                           font=dict(color="#160B7C", size=15)),
                xaxis=dict(gridcolor="rgba(22,11,124,0.08)", tickfont=dict(color="#6B7AA5")),
                yaxis =dict(title=dict(text="ARS", font=dict(color="#0FBFEF", size=12)),
                            gridcolor="rgba(22,11,124,0.08)", tickfont=dict(color="#6B7AA5")),
                yaxis2=dict(title=dict(text="USD", font=dict(color="#E8A800", size=12)),
                            overlaying="y", side="right", gridcolor="rgba(0,0,0,0)",
                            tickfont=dict(color="#6B7AA5")),
                yaxis3=dict(title=dict(text="$/USD", font=dict(color="#D04462", size=12)),
                            overlaying="y", side="right", anchor="free",
                            position=0.97, gridcolor="rgba(0,0,0,0)",
                            tickfont=dict(color="#6B7AA5")),
                legend=dict(orientation="h", y=-0.2, font=dict(color="#1A1D3A")),
                hovermode="x unified",
            )
            st.plotly_chart(fig_dual, use_container_width=True)

        top_usd = (vf.groupby("Modelo")["Total_USD"]
                   .sum().sort_values(ascending=False).head(12).reset_index())
        fig_um = px.bar(top_usd, x="Total_USD", y="Modelo", orientation="h",
                        title="🖱️ Clic en modelo para ver detalle mensual",
                        color="Total_USD", color_continuous_scale="YlOrBr")
        fig_um.update_layout(**PLOTLY_THEME, showlegend=False, coloraxis_showscale=False)
        sel_mod = st.plotly_chart(fig_um, use_container_width=True,
                                  on_select="rerun", key="sel_mod")

        mod_sel = get_sel(sel_mod)
        if mod_sel:
            st.divider()
            st.subheader(f"📦 Detalle mensual — {mod_sel}")
            df_m = vf[vf["Modelo"] == mod_sel].copy()
            df_m["Mes"] = df_m["Fecha"].dt.to_period("M").astype(str)
            dm = df_m.groupby("Mes").agg(Unidades=("Cantidad","sum"),
                                          Total_USD=("Total_USD","sum")).reset_index()
            fc1, fc2 = st.columns(2)
            with fc1:
                fig_dd = px.bar(dm, x="Mes", y="Total_USD", text="Unidades",
                                title=f"{mod_sel} — USD por mes",
                                color="Total_USD", color_continuous_scale="YlOrBr")
                fig_dd.update_traces(texttemplate="%{text:.0f} u.", textposition="outside")
                fig_dd.update_layout(**PLOTLY_THEME, coloraxis_showscale=False)
                fig_dd.update_xaxes(tickangle=-40)
                st.plotly_chart(fig_dd, use_container_width=True)
            with fc2:
                fig_dd2 = px.bar(dm, x="Mes", y="Unidades",
                                 title=f"{mod_sel} — Unidades por mes",
                                 color="Unidades", color_continuous_scale="Blues")
                fig_dd2.update_layout(**PLOTLY_THEME, coloraxis_showscale=False)
                fig_dd2.update_xaxes(tickangle=-40)
                st.plotly_chart(fig_dd2, use_container_width=True)
            dm_fmt = dm.copy()
            dm_fmt["Total_USD"] = dm_fmt["Total_USD"].map("U$D {:,.0f}".format)
            dm_fmt["Unidades"]  = dm_fmt["Unidades"].map("{:,.0f}".format)
            st.dataframe(dm_fmt, use_container_width=True, hide_index=True)
            st.divider()

        bm1, bm2 = st.columns(2)
        with bm1:
            marca_agg = (vf.groupby("Marca")["Total_USD"].sum()
                         .sort_values(ascending=False).reset_index())
            fig_marca = px.pie(marca_agg, values="Total_USD", names="Marca",
                               title="Ventas USD por Marca", hole=0.4,
                               color_discrete_sequence=px.colors.sequential.Teal)
            fig_marca.update_layout(**PLOTLY_THEME)
            st.plotly_chart(fig_marca, use_container_width=True)
        with bm2:
            cat_agg = (vf.groupby("SubCategoria")["Total_USD"].sum()
                       .sort_values(ascending=False).reset_index())
            fig_cat_v = px.bar(cat_agg, x="Total_USD", y="SubCategoria", orientation="h",
                               title="Ventas USD por Categoría",
                               color="Total_USD", color_continuous_scale="Blues")
            fig_cat_v.update_layout(**PLOTLY_THEME, coloraxis_showscale=False)
            st.plotly_chart(fig_cat_v, use_container_width=True)

        st.subheader("Top 15 Clientes — USD")
        cli_usd = (vf.groupby("Cliente")
                   .agg(Total_USD=("Total_USD","sum"), TC_Prom=("dolar_dia","mean"))
                   .sort_values("Total_USD", ascending=False).head(15).reset_index())
        cli_usd["Total_USD"] = cli_usd["Total_USD"].map("U$D {:,.0f}".format)
        cli_usd["TC_Prom"]   = cli_usd["TC_Prom"].map("${:,.0f}".format)
        cli_usd.columns      = ["Cliente","Ventas USD","TC Promedio"]
        st.dataframe(cli_usd, use_container_width=True, hide_index=True)

    # ────────────────────────────── TAB 2: DEUDA
    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            aging = pd.DataFrame({
                "Período": ["0-30 días","31-60 días","61-90 días","+90 días"],
                "Monto":   [deuda["SAL30"].sum(), deuda["SAL60"].sum(),
                            deuda["SALMAY60"].sum(), deuda["SALMAY90"].sum()],
            })
            fig_ag = px.bar(aging, x="Período", y="Monto",
                            title="Pirámide de Antigüedad de Deuda",
                            color="Período",
                            color_discrete_sequence=["#4CAF50","#FFC107","#FF9800","#F44336"])
            fig_ag.update_layout(**PLOTLY_THEME, showlegend=False)
            st.plotly_chart(fig_ag, use_container_width=True)

        with c2:
            top_d = deuda.nlargest(10, "TOTCTA").copy()
            top_d["nc"] = top_d["VTMCLH_NOMBRE"].str[:22]
            fig_dd = go.Figure()
            fig_dd.add_trace(go.Bar(name="Deuda total", x=top_d["nc"], y=top_d["TOTCTA"],
                                    marker_color="#FF5E7E", customdata=top_d["VTMCLH_NOMBRE"],
                                    hovertemplate="%{customdata}<br>$%{y:,.0f}<extra></extra>"))
            fig_dd.add_trace(go.Bar(name="Límite crédito", x=top_d["nc"], y=top_d["LIMCRED"],
                                    marker_color="#0FBFEF"))
            fig_dd.update_layout(**PLOTLY_THEME, title="🖱️ Clic en cliente para ver antigüedad",
                                 barmode="group")
            fig_dd.update_xaxes(tickangle=-40)
            sel_deu = st.plotly_chart(fig_dd, use_container_width=True,
                                      on_select="rerun", key="sel_deu")

        cli_deu_sel = get_sel(sel_deu, "x")
        if cli_deu_sel:
            match = deuda[deuda["VTMCLH_NOMBRE"].str[:22] == cli_deu_sel]
            if match.empty:
                match = deuda[deuda["VTMCLH_NOMBRE"].str.contains(cli_deu_sel, na=False)]
            if not match.empty:
                row = match.iloc[0]
                st.divider()
                st.subheader(f"📋 Antigüedad — {row['VTMCLH_NOMBRE']}")
                fc1, fc2 = st.columns(2)
                with fc1:
                    ag_cli = pd.DataFrame({
                        "Período": ["0-30d","31-60d","61-90d","+90d"],
                        "Monto":   [row["SAL30"], row["SAL60"], row["SALMAY60"], row["SALMAY90"]],
                    })
                    fig_ag2 = px.bar(ag_cli, x="Período", y="Monto", color="Período",
                                     color_discrete_sequence=["#4CAF50","#FFC107","#FF9800","#F44336"],
                                     title="Deuda por antigüedad")
                    fig_ag2.update_layout(**PLOTLY_THEME, showlegend=False)
                    st.plotly_chart(fig_ag2, use_container_width=True)
                with fc2:
                    uso_pct = (row["TOTCTA"] / row["LIMCRED"] * 100) if row["LIMCRED"] > 0 else 0
                    fig_g = go.Figure(go.Indicator(
                        mode="gauge+number", value=uso_pct,
                        title={"text":"Uso de límite de crédito (%)",
                               "font":{"color":"#160B7C","size":14}},
                        gauge={"axis":{"range":[0,100],"tickcolor":"#6B7AA5"},
                               "bar":{"color":"#160B7C"},"bgcolor":"#F0F3FA",
                               "borderwidth":2,"bordercolor":"#E2E6F0",
                               "steps":[{"range":[0,60],"color":"#D4F5E9"},
                                        {"range":[60,80],"color":"#FFE9C7"},
                                        {"range":[80,100],"color":"#FFD3DC"}],
                               "threshold":{"line":{"color":"#D04462","width":3},"value":80}},
                        number={"suffix":"%","valueformat":".1f","font":{"color":"#160B7C","size":34}}
                    ))
                    fig_g.update_layout(paper_bgcolor="#FFFFFF",
                                        font=dict(color="#1A1D3A",family="Inter, sans-serif"),
                                        height=300, margin=dict(t=60,b=20,l=20,r=20))
                    st.plotly_chart(fig_g, use_container_width=True)
                st.divider()

        st.subheader("Detalle completo de deuda")
        dd = deuda[["VTMCLH_NOMBRE","SAL30","SAL60","SALMAY60","SALMAY90","TOTCTA","LIMCRED"]].copy()
        dd.columns = ["Cliente","0-30d","31-60d","61-90d","+90d","Total","Límite"]
        dd = dd.sort_values("Total", ascending=False)
        fmt = {c: "${:,.0f}" for c in ["0-30d","31-60d","61-90d","+90d","Total","Límite"]}
        st.dataframe(dd.style.format(fmt), use_container_width=True, hide_index=True)

    # ────────────────────────────── TAB 3: STOCK
    with tab3:
        stock_pos = stock[stock["DISPONIBLE"] > 0].copy()

        sf1c, sf2c, sf3c = st.columns([2, 2, 2])
        with sf1c:
            dep_opts = sorted(stock_pos["CODIGO_DEPOSITO"].unique().tolist())
            dep_labels = {d: f"Depósito {d}" for d in dep_opts}
            if "NOMBRE_DEPOSITO" in stock_pos.columns:
                for d in dep_opts:
                    sub = stock_pos[stock_pos["CODIGO_DEPOSITO"]==d]
                    if not sub.empty:
                        name = sub["NOMBRE_DEPOSITO"].iloc[0]
                        if name and str(name).strip():
                            dep_labels[d] = f"{d} — {str(name).strip()}"
            dep_sel = st.multiselect("🏭 Depósito", dep_opts, default=dep_opts,
                                     format_func=lambda d: dep_labels.get(d, str(d)), key="st_dep")
        with sf2c:
            s_marcas = sorted(stock_pos["Marca"].dropna().unique().tolist())
            s_marca_sel = st.multiselect("🏷️ Marca", s_marcas, placeholder="Todas las marcas", key="st_marca")
        with sf3c:
            s_cats = sorted(stock_pos["SubCategoria"].dropna().unique().tolist())
            s_cat_sel = st.multiselect("📂 Categoría", s_cats, placeholder="Todas las categorías", key="st_cat")

        sf = stock_pos.copy()
        if dep_sel:     sf = sf[sf["CODIGO_DEPOSITO"].isin(dep_sel)]
        if s_marca_sel: sf = sf[sf["Marca"].isin(s_marca_sel)]
        if s_cat_sel:   sf = sf[sf["SubCategoria"].isin(s_cat_sel)]
        st.divider()

        c1, c2 = st.columns(2)
        with c1:
            top_st = sf.nlargest(15, "DISPONIBLE").copy()
            top_st["Desc"] = top_st["STMPDH_DESCRP"].str[:38]
            fig_st = px.bar(top_st, x="DISPONIBLE", y="Desc", orientation="h",
                            title="🖱️ Clic en producto para ver disponible / NV / OC",
                            color="DISPONIBLE", color_continuous_scale="Greens")
            fig_st.update_layout(**PLOTLY_THEME, showlegend=False, coloraxis_showscale=False)
            sel_st = st.plotly_chart(fig_st, use_container_width=True,
                                     on_select="rerun", key="sel_st")
        with c2:
            por_cat = sf.groupby("STTTPH_DESCRP")["DISPONIBLE"].sum().reset_index()
            por_cat.columns = ["Categoría","Stock"]
            fig_cat = px.pie(por_cat, values="Stock", names="Categoría",
                             title="Stock por Categoría", hole=0.45)
            fig_cat.update_layout(**PLOTLY_THEME)
            st.plotly_chart(fig_cat, use_container_width=True)

        prod_sel = get_sel(sel_st)
        if prod_sel:
            match_st = stock[stock["STMPDH_DESCRP"].str[:38] == prod_sel]
            if not match_st.empty:
                row_st = match_st.iloc[0]
                st.divider()
                st.subheader(f"📦 {row_st['STMPDH_DESCRP']}")
                fc1, fc2 = st.columns(2)
                with fc1:
                    st_detail = pd.DataFrame({
                        "Estado":   ["Disponible","Nota de Venta","Orden de Compra","En Stock"],
                        "Unidades": [row_st["DISPONIBLE"], row_st["NV"], row_st["OC"], row_st["ST"]],
                        "Color":    ["#4CAF50","#FFC107","#42A5F5","#AB47BC"]
                    })
                    fig_std = px.bar(st_detail, x="Estado", y="Unidades", color="Estado",
                                     color_discrete_sequence=st_detail["Color"].tolist(),
                                     title="Breakdown de stock")
                    fig_std.update_layout(**PLOTLY_THEME, showlegend=False)
                    st.plotly_chart(fig_std, use_container_width=True)
                with fc2:
                    st.markdown("#### Ficha del producto")
                    st.metric("Código",        row_st["STMPDH_ARTCOD"])
                    st.metric("Disponible",    f"{row_st['DISPONIBLE']:,.0f} u.")
                    st.metric("Nota de Venta", f"{row_st['NV']:,.0f} u.")
                    st.metric("Orden Compra",  f"{row_st['OC']:,.0f} u.")
                st.divider()

        bajo = sf[sf["DISPONIBLE"] < 50].sort_values("DISPONIBLE")
        if not bajo.empty:
            st.warning(f"⚠️ {len(bajo)} productos con stock bajo (< 50 unidades)")
            bb = bajo[["STMPDH_ARTCOD","STMPDH_DESCRP","DISPONIBLE"]].copy()
            bb.columns = ["Código","Descripción","Stock disponible"]
            st.dataframe(bb, use_container_width=True, hide_index=True)

    # ────────────────────────────── TAB 4: PENDIENTES
    with tab4:
        c1, c2 = st.columns(2)
        with c1:
            top_pend = (pendientes_pos.groupby("VTMCLH_NOMBRE")["Import"]
                        .sum().sort_values(ascending=False).head(12).reset_index())
            top_pend["nc"] = top_pend["VTMCLH_NOMBRE"].str[:28]
            fig_pc = px.bar(top_pend, x="Import", y="nc", orientation="h",
                            title="🖱️ Clic en cliente para ver sus pendientes",
                            color="Import", color_continuous_scale="Oranges")
            fig_pc.update_layout(**PLOTLY_THEME, showlegend=False, coloraxis_showscale=False)
            sel_pc = st.plotly_chart(fig_pc, use_container_width=True,
                                     on_select="rerun", key="sel_pc")
        with c2:
            top_art = (pendientes_pos.groupby("STMPDH_DESCRP")["CANTID"]
                       .sum().sort_values(ascending=False).head(12).reset_index())
            top_art["Desc"] = top_art["STMPDH_DESCRP"].str[:35]
            fig_pa = px.bar(top_art, x="CANTID", y="Desc", orientation="h",
                            title="🖱️ Clic en artículo para ver clientes pendientes",
                            color="CANTID", color_continuous_scale="Purples")
            fig_pa.update_layout(**PLOTLY_THEME, showlegend=False, coloraxis_showscale=False)
            sel_pa = st.plotly_chart(fig_pa, use_container_width=True,
                                     on_select="rerun", key="sel_pa")

        cli_pend_sel = get_sel(sel_pc)
        if cli_pend_sel:
            st.divider()
            st.subheader(f"⏳ Pendientes de — {cli_pend_sel}")
            df_cp = pendientes_pos[pendientes_pos["VTMCLH_NOMBRE"].str[:28] == cli_pend_sel]
            if df_cp.empty:
                df_cp = pendientes_pos[pendientes_pos["VTMCLH_NOMBRE"].str.contains(cli_pend_sel, na=False)]
            pp = df_cp[["STMPDH_DESCRP","CANTID","Import","FCRMVI_FCHENT"]].copy()
            pp.columns = ["Artículo","Cantidad","Importe","Fecha entrega"]
            pp = pp.sort_values("Importe", ascending=False)
            pp["Importe"] = pp["Importe"].map("${:,.0f}".format)
            fig_cp = px.bar(df_cp.assign(Desc=df_cp["STMPDH_DESCRP"].str[:30]),
                            x="Import", y="Desc", orientation="h",
                            title="Importe pendiente por artículo",
                            color="Import", color_continuous_scale="Oranges")
            fig_cp.update_layout(**PLOTLY_THEME, showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig_cp, use_container_width=True)
            st.dataframe(pp, use_container_width=True, hide_index=True)
            st.divider()

        art_pend_sel = get_sel(sel_pa)
        if art_pend_sel:
            st.divider()
            st.subheader(f"📋 Clientes pendientes — {art_pend_sel}")
            df_ap = pendientes_pos[pendientes_pos["STMPDH_DESCRP"].str[:35] == art_pend_sel]
            if df_ap.empty:
                df_ap = pendientes_pos[pendientes_pos["STMPDH_DESCRP"].str.contains(art_pend_sel, na=False)]
            ap = df_ap[["VTMCLH_NOMBRE","CANTID","Import","FCRMVI_FCHENT"]].copy()
            ap.columns = ["Cliente","Cantidad","Importe","Fecha entrega"]
            ap = ap.sort_values("Importe", ascending=False)
            ap["Importe"] = ap["Importe"].map("${:,.0f}".format)
            st.dataframe(ap, use_container_width=True, hide_index=True)
            st.divider()

    # ────────────────────────────── TAB 5: GASTOS
    with tab5:
        gastos_pos = gastos[gastos["SALDO"] > 0].copy()
        c1, c2 = st.columns(2)
        with c1:
            gm = (gastos_pos.groupby(gastos_pos["W_FCHMOV"].dt.to_period("M"))["SALDO"]
                  .sum().reset_index())
            gm["W_FCHMOV"] = gm["W_FCHMOV"].astype(str)
            fig_gm = px.bar(gm, x="W_FCHMOV", y="SALDO", title="Gastos Mensuales",
                            color="SALDO", color_continuous_scale="Reds")
            fig_gm.update_layout(**PLOTLY_THEME, coloraxis_showscale=False)
            fig_gm.update_xaxes(tickangle=-40)
            st.plotly_chart(fig_gm, use_container_width=True)

        with c2:
            top_prov = (gastos_pos.groupby("PVMPRH_NOMBRE")["SALDO"]
                        .sum().sort_values(ascending=False).head(10).reset_index())
            top_prov["Proveedor"] = top_prov["PVMPRH_NOMBRE"].str[:25]
            fig_prov = px.bar(top_prov, x="SALDO", y="Proveedor", orientation="h",
                              title="🖱️ Clic en proveedor para ver evolución mensual",
                              color="SALDO", color_continuous_scale="Oranges")
            fig_prov.update_layout(**PLOTLY_THEME, showlegend=False, coloraxis_showscale=False)
            sel_prov = st.plotly_chart(fig_prov, use_container_width=True,
                                       on_select="rerun", key="sel_prov")

        prov_sel = get_sel(sel_prov)
        if prov_sel:
            prov_full = prov_sel
            match_prov = gastos_pos[gastos_pos["PVMPRH_NOMBRE"].str[:25] == prov_sel]
            if not match_prov.empty:
                prov_full = match_prov["PVMPRH_NOMBRE"].iloc[0]
            st.divider()
            st.subheader(f"💸 Evolución mensual — {prov_full}")
            df_pv = gastos_pos[gastos_pos["PVMPRH_NOMBRE"] == prov_full].copy()
            df_pv["Mes"] = df_pv["W_FCHMOV"].dt.to_period("M").astype(str)
            gp = df_pv.groupby("Mes")["SALDO"].sum().reset_index()
            fig_pv = px.area(gp, x="Mes", y="SALDO",
                             title=f"{prov_full} — gasto mensual",
                             color_discrete_sequence=["#0FBFEF"])
            fig_pv.update_layout(**PLOTLY_THEME)
            fig_pv.update_xaxes(tickangle=-40)
            st.plotly_chart(fig_pv, use_container_width=True)
            st.divider()

        por_concepto = (gastos_pos.groupby("CGMPCH_DESCRP")["SALDO"]
                        .sum().sort_values(ascending=False).reset_index())
        por_concepto.columns = ["Concepto","Total"]
        fig_conc = px.pie(por_concepto, values="Total", names="Concepto",
                          title="Gastos por Concepto", hole=0.45)
        fig_conc.update_layout(**PLOTLY_THEME)
        st.plotly_chart(fig_conc, use_container_width=True)


dashboard()

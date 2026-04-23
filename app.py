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
    /* ── Claude Design × Gularo — Light Fintech Theme ──────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
      --bg: oklch(99% 0.003 85);
      --surface: #ffffff;
      --subtle: oklch(97.5% 0.003 85);
      --hairline: oklch(92% 0.005 260);
      --hairline-soft: oklch(94.5% 0.004 260);
      --ink: oklch(22% 0.01 260);
      --ink-sub: oklch(46% 0.01 260);
      --ink-muted: oklch(62% 0.01 260);
      --accent: oklch(55% 0.17 265);
      --accent-soft: oklch(96% 0.03 265);
      --accent-ink: oklch(42% 0.17 265);
      --accent-mid: oklch(32% 0.09 265);
      --pos: oklch(52% 0.14 150);
      --pos-soft: oklch(96% 0.04 150);
      --neg: oklch(55% 0.18 25);
      --neg-soft: oklch(96% 0.04 25);
      --sans: 'Inter', -apple-system, sans-serif;
      --mono: 'JetBrains Mono', ui-monospace, monospace;
    }

    html, body, [data-testid="stAppViewContainer"] * {
        font-family: var(--sans) !important;
    }

    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"] {
        background: var(--bg) !important;
    }
    .block-container { padding-top: 4rem; padding-bottom: 3rem; }
    header[data-testid="stHeader"] { background: transparent; }

    /* ── KPI cards ─────────────────────────────────────────────────── */
    div[data-testid="metric-container"] {
        background: var(--surface);
        border-radius: 12px;
        padding: 18px 22px;
        border: 1px solid var(--hairline);
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        transition: transform .15s ease, box-shadow .2s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.09);
    }
    div[data-testid="metric-container"] label {
        color: var(--ink-muted) !important;
        font-size: 0.72rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 1.2px;
    }
    div[data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: var(--ink) !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
        line-height: 1.1 !important;
        letter-spacing: -0.02em;
    }
    div[data-testid="metric-container"] [data-testid="stMetricDelta"] {
        color: var(--pos) !important;
        font-weight: 600;
    }

    /* ── Tabs — subtle pill style, indigo active ──────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: var(--subtle);
        padding: 4px;
        border-radius: 12px;
        border: 1px solid var(--hairline);
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 9px;
        padding: 10px 22px;
        color: var(--ink-sub);
        border: none;
        font-weight: 600;
        font-size: 0.88rem;
        transition: all .15s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: var(--ink);
        background: var(--surface);
    }
    .stTabs [aria-selected="true"] {
        background: var(--accent) !important;
        color: #fff !important;
        font-weight: 700 !important;
        box-shadow: 0 2px 8px oklch(55% 0.17 265 / 0.3);
    }

    /* ── Dataframes ────────────────────────────────────────────────── */
    .stDataFrame, [data-testid="stDataFrame"] {
        background: var(--surface) !important;
        border: 1px solid var(--hairline);
        border-radius: 10px;
    }
    .stDataFrame [role="gridcell"],
    [data-testid="stDataFrame"] [role="gridcell"],
    .stDataFrame [role="rowheader"],
    [data-testid="stDataFrame"] [role="rowheader"] {
        background: var(--surface) !important;
        color: var(--ink) !important;
    }
    .stDataFrame [role="columnheader"],
    [data-testid="stDataFrame"] [role="columnheader"] {
        background: var(--subtle) !important;
        color: var(--ink-sub) !important;
        font-weight: 600 !important;
    }

    /* ── Typography ────────────────────────────────────────────────── */
    h1 { color: var(--accent) !important; font-weight: 800 !important; letter-spacing: -0.02em !important; }
    h2 { color: var(--ink) !important; font-weight: 700 !important; letter-spacing: -0.01em !important; }
    h3 { color: var(--ink-sub) !important; font-weight: 600 !important; }
    p, span, div, label { color: var(--ink); }

    /* ── Form controls ─────────────────────────────────────────────── */
    .stMultiSelect [data-baseweb="select"] > div,
    .stDateInput   [data-baseweb="input"]  > div {
        background: var(--surface) !important;
        border: 1px solid var(--hairline) !important;
        border-radius: 9px !important;
        color: var(--ink) !important;
    }
    .stMultiSelect [data-baseweb="select"] > div:hover,
    .stDateInput   [data-baseweb="input"]  > div:hover {
        border-color: var(--accent) !important;
    }

    /* ── Misc ──────────────────────────────────────────────────────── */
    hr {
        border: none !important; height: 1px !important;
        background: var(--hairline) !important;
        margin: 1.2rem 0 !important;
    }
    [data-testid="stSidebar"] {
        background: var(--surface) !important;
        border-right: 1px solid var(--hairline);
    }
    .stAlert {
        background: var(--accent-soft) !important;
        border: 1px solid var(--hairline) !important;
        border-radius: 10px !important;
    }
    .stAlert * { color: var(--ink) !important; }
    .stButton > button {
        background: var(--accent) !important; color: #fff !important;
        border: none !important; border-radius: 9px !important;
        font-weight: 700 !important; padding: 8px 20px !important;
        transition: all .15s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 14px oklch(55% 0.17 265 / 0.35);
    }
</style>
""", unsafe_allow_html=True)

PLOTLY_THEME = {
    "paper_bgcolor": "#FFFFFF",
    "plot_bgcolor":  "oklch(97.5% 0.003 85)",
    "font":  {"color": "oklch(22% 0.01 260)", "family": "Inter, sans-serif"},
    "xaxis": {"gridcolor": "oklch(92% 0.005 260)", "linecolor": "oklch(92% 0.005 260)",
              "tickfont": {"color": "oklch(62% 0.01 260)"}},
    "yaxis": {"gridcolor": "oklch(92% 0.005 260)", "linecolor": "oklch(92% 0.005 260)",
              "tickfont": {"color": "oklch(62% 0.01 260)"}},
    "margin": {"t": 40, "b": 30, "l": 40, "r": 20},
    "title":  {"font": {"color": "oklch(42% 0.17 265)", "size": 13, "family": "Inter, sans-serif"}},
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


# ── VISUAL HELPERS ─────────────────────────────────────────────────────────────

def sparkline_svg(values, width=100, height=28, color="oklch(55% 0.17 265)"):
    if not values or len(values) < 2:
        return f'<svg width="{width}" height="{height}"></svg>'
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1
    pts = []
    for i, v in enumerate(values):
        x = i / (len(values)-1) * width
        y = height - ((v - mn) / rng) * (height - 4) - 2
        pts.append(f"{x:.1f},{y:.1f}")
    path = " ".join(pts)
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'style="display:block">'
            f'<polyline points="{path}" fill="none" stroke="{color}" '
            f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/></svg>')


def delta_html(v):
    if v is None or (isinstance(v, float) and (v != v)):
        return ""
    color = "oklch(52% 0.14 150)" if v >= 0 else "oklch(55% 0.18 25)"
    arrow = "↑" if v >= 0 else "↓"
    sign  = "+" if v >= 0 else ""
    return (f'<span style="color:{color};font-size:11px;font-weight:600;'
            f'font-family:var(--mono)">{arrow} {sign}{v:.1f}%</span>')


def num_html(v, size=22, color="oklch(22% 0.01 260)", weight=600):
    if isinstance(v, str):
        formatted = v
    else:
        neg = v < 0
        formatted = f"{abs(v):,.0f}".replace(",", "·TEMP·").replace(".", ",").replace("·TEMP·", ".")
        if neg:
            formatted = f"−{formatted}"
        color = "oklch(55% 0.18 25)" if neg and color == "oklch(22% 0.01 260)" else color
    return (f'<span style="font-family:var(--mono);font-size:{size}px;'
            f'font-weight:{weight};color:{color};font-variant-numeric:tabular-nums">'
            f'{formatted}</span>')


def rank_table_html(title, rows, value_col, label_col, accent, accent_soft, numbered=True, prefix="U$D", compact=False):
    """Renders a heatmap-shaded ranking table as HTML."""
    if rows.empty:
        return f'<div style="padding:12px;color:var(--ink-muted);font-size:12px">Sin datos</div>'
    max_val = rows[value_col].max()
    pad = "7px 14px" if compact else "9px 14px"
    rows_html = ""
    for i, (_, row) in enumerate(rows.iterrows()):
        pct = float(row[value_col]) / max_val if max_val > 0 else 0
        intensity = int(pct * 35)
        text_color = "#fff" if pct > 0.55 else accent
        val = row[value_col]
        if val >= 1e6:
            val_str = f"{val/1e6:.1f}M".replace(".", ",")
        elif val >= 1e3:
            val_str = f"{val/1e3:.0f}K"
        else:
            val_str = f"{int(val):,}".replace(",", ".")
        num_cell = (f'<span style="text-align:right;padding:4px 10px;border-radius:5px;'
                    f'background:color-mix(in oklch,{accent} {intensity}%,#fff);'
                    f'color:{text_color};font-family:var(--mono);font-weight:600;font-size:12px">'
                    f'{val_str}</span>')
        idx_cell = (f'<span style="color:var(--ink-muted);font-family:var(--mono);font-size:11px;min-width:20px">'
                    f'{i+1}.</span> ') if numbered else ""
        label = str(row[label_col])[:28]
        rows_html += (f'<div style="display:flex;align-items:center;justify-content:space-between;'
                      f'padding:{pad};border-bottom:1px solid var(--hairline-soft);gap:8px">'
                      f'<div style="display:flex;align-items:center;gap:4px;overflow:hidden;flex:1">'
                      f'{idx_cell}'
                      f'<span style="font-size:12.5px;color:var(--ink);font-weight:500;'
                      f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{label}</span></div>'
                      f'{num_cell}</div>')
    return (f'<div style="background:#fff;border:1px solid var(--hairline);border-radius:12px;'
            f'display:flex;flex-direction:column;overflow:hidden;height:100%">'
            f'<div style="padding:10px 14px;border-bottom:1px solid var(--hairline-soft);'
            f'font-size:11px;font-weight:600;color:{accent};letter-spacing:-0.1px">'
            f'{title} &nbsp;<span style="font-size:10px;color:var(--ink-muted);font-weight:400">'
            f'{prefix}</span></div>'
            f'{rows_html}</div>')


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

    # Pendientes de facturar y preventa (needed in tab0 sidebar)
    pend_fact_usd = pendientes_pos["Import"].sum() / dolar_hoy if dolar_hoy else 0
    preventa_usd  = 0
    if "nCntEstimada" in pendientes_pos.columns:
        preventa_usd = (pendientes_pos["nCntEstimada"] * pendientes_pos["Import"] /
                        pendientes_pos["CANTID"].replace(0, 1)).sum() / dolar_hoy if dolar_hoy else 0

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
        hoy = _dt.date.today()
        mes_ini = hoy.replace(day=1)
        mes_ant_fin = mes_ini - _dt.timedelta(days=1)
        mes_ant_ini = mes_ant_fin.replace(day=1)
        u12m_ini = (pd.Timestamp(mes_ini) - pd.DateOffset(months=12)).date()
        u12m_fin = mes_ini - _dt.timedelta(days=1)

        v_hoy    = ventas_pos[ventas_pos["Fecha"].dt.date == hoy]
        v_mes    = ventas_pos[ventas_pos["Fecha"].dt.date >= mes_ini]
        v_mes_ant = ventas_pos[(ventas_pos["Fecha"].dt.date >= mes_ant_ini) &
                               (ventas_pos["Fecha"].dt.date <= mes_ant_fin)]
        v_u12m   = ventas_pos[(ventas_pos["Fecha"].dt.date >= u12m_ini) &
                               (ventas_pos["Fecha"].dt.date <= u12m_fin)]

        def safe_delta(new, old):
            if old and old != 0:
                return (new / old - 1) * 100
            return None

        # Monthly sparkline series (last 12 complete months)
        monthly = (ventas_pos[ventas_pos["Fecha"].dt.date <= u12m_fin]
                   .groupby(ventas_pos["Fecha"].dt.to_period("M"))
                   .agg(Total=("Total","sum"), Q=("Cantidad","sum"))
                   .tail(12))
        def canal_monthly(canal):
            sub = ventas_pos[(ventas_pos["Canal"] == canal) &
                             (ventas_pos["Fecha"].dt.date <= u12m_fin)]
            return (sub.groupby(sub["Fecha"].dt.to_period("M"))["Total"].sum().tail(12).tolist())

        sparks = {
            "dollar": monthly["Total"].tolist(),
            "qty":    monthly["Q"].tolist(),
            "retail": canal_monthly("RETAIL"),
            "hogar":  canal_monthly("HOGAR"),
            "ecomm":  canal_monthly("ECOMM"),
        }

        # Values
        hoy_ars  = v_hoy["Total"].sum()
        mes_ars  = v_mes["Total"].sum()
        u12m_usd = v_u12m["Total_USD"].sum()
        hoy_q    = v_hoy["Cantidad"].sum()
        mes_q    = v_mes["Cantidad"].sum()
        u12m_q   = v_u12m["Cantidad"].sum()

        def canal_vals(canal):
            return {
                "hoy":  ventas_pos[(ventas_pos["Canal"]==canal) & (ventas_pos["Fecha"].dt.date==hoy)]["Total"].sum(),
                "mes":  ventas_pos[(ventas_pos["Canal"]==canal) & (ventas_pos["Fecha"].dt.date>=mes_ini)]["Total"].sum(),
                "u12m": ventas_pos[(ventas_pos["Canal"]==canal) & (ventas_pos["Fecha"].dt.date>=u12m_ini) &
                                   (ventas_pos["Fecha"].dt.date<=u12m_fin)]["Total_USD"].sum(),
            }
        rv = canal_vals("RETAIL")
        hv = canal_vals("HOGAR")
        ev = canal_vals("ECOMM")

        delta_hoy_d = safe_delta(hoy_ars, v_mes_ant[v_mes_ant["Fecha"].dt.date == mes_ant_fin]["Total"].sum())
        delta_mes_d = safe_delta(mes_ars, v_mes_ant["Total"].sum())
        delta_u12m_d = None  # no prior U12M computed

        # Build matrix HTML
        col_head_base = "font-size:10.5px;font-weight:600;text-transform:uppercase;letter-spacing:0.8px;padding:0 4px 10px;text-align:right;font-family:var(--sans)"
        cell_style = "padding:14px 16px;border-top:1px solid var(--hairline-soft);text-align:right;vertical-align:middle"
        row_label_style = ("padding:14px 12px 14px 0;font-size:11px;font-weight:600;"
                           "text-transform:uppercase;letter-spacing:0.6px;color:var(--ink-sub);"
                           "white-space:nowrap;font-family:var(--sans);vertical-align:middle")

        def matrix_row(label_html, hoy_v, mes_v, u12m_v, spark_vals,
                       hoy_size=22, canal_size=19, hoy_delta=None, mes_delta=None, u12m_delta=None):
            spark = sparkline_svg(spark_vals)
            hoy_col  = "oklch(22% 0.01 260)"
            mes_col  = "oklch(32% 0.09 265)"
            u12m_col = "oklch(42% 0.17 265)"
            sz = hoy_size
            hoy_cell = f'<div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">{num_html(hoy_v,sz,hoy_col)}{delta_html(hoy_delta) if hoy_delta is not None else ""}</div>'
            mes_cell = f'<div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">{num_html(mes_v,sz,mes_col)}{delta_html(mes_delta) if mes_delta is not None else ""}</div>'
            u12m_cell = f'<div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">{num_html(u12m_v,sz,u12m_col)}{delta_html(u12m_delta) if u12m_delta is not None else ""}</div>'
            return (f'<tr>'
                    f'<td style="{row_label_style}">{label_html}</td>'
                    f'<td style="{cell_style}">{hoy_cell}</td>'
                    f'<td style="{cell_style}">{mes_cell}</td>'
                    f'<td style="{cell_style}">{u12m_cell}</td>'
                    f'<td style="{cell_style};padding:14px 0 14px 16px">{spark}</td>'
                    f'</tr>')

        matrix_html = f"""
        <div class="mx-wrap">
          <div class="mx-card">
            <div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:8px">
              <div>
                <div style="font-size:15px;font-weight:600;color:var(--ink);letter-spacing:-0.2px">Ventas por período</div>
                <div style="font-size:12px;color:var(--ink-muted);margin-top:2px">Monto y cantidades · todas las marcas</div>
              </div>
            </div>
            <table class="mx-table">
              <thead>
                <tr>
                  <th style="width:110px"></th>
                  <th style="{col_head_base};color:var(--ink)">HOY</th>
                  <th style="{col_head_base};color:var(--accent-mid)">MES</th>
                  <th style="{col_head_base};color:var(--accent-ink)">U12M · U$D</th>
                  <th style="{col_head_base};width:110px;text-align:left;padding-left:16px">TENDENCIA</th>
                </tr>
              </thead>
              <tbody>
                {matrix_row(
                  '<span style="font-family:var(--mono);color:var(--accent);font-size:13px;font-weight:600">$</span> &nbsp;MONTO',
                  hoy_ars, mes_ars, u12m_usd, sparks["dollar"],
                  hoy_delta=delta_hoy_d, mes_delta=delta_mes_d
                )}
                {matrix_row(
                  '<span style="font-family:var(--mono);color:var(--accent);font-size:13px;font-weight:600">Q</span> &nbsp;UNIDADES',
                  hoy_q, mes_q, u12m_q, sparks["qty"]
                )}
                <tr>
                  <td colspan="5" style="padding:22px 0 6px;border-top:1px solid var(--hairline)">
                    <div style="font-size:10.5px;font-weight:600;color:var(--ink-muted);text-transform:uppercase;letter-spacing:0.8px">Por unidad de negocio</div>
                  </td>
                </tr>
                {matrix_row("RETAIL",    rv["hoy"], rv["mes"], rv["u12m"], sparks["retail"], canal_size=19)}
                {matrix_row("HOGAR",     hv["hoy"], hv["mes"], hv["u12m"], sparks["hogar"],  canal_size=19)}
                {matrix_row("E-COMMERCE",ev["hoy"], ev["mes"], ev["u12m"], sparks["ecomm"],  canal_size=19)}
              </tbody>
            </table>
          </div>

          <div style="display:flex;flex-direction:column">
            <!-- Saldos -->
            <div class="side-card">
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
                <div style="font-size:11px;font-weight:600;color:var(--ink-muted);text-transform:uppercase;letter-spacing:0.7px">Saldos comerciales</div>
                <span style="font-size:11px;color:var(--ink-muted);font-family:var(--mono)">U$D</span>
              </div>
              <div style="display:flex;align-items:baseline;gap:6px">
                <span style="font-family:var(--mono);font-size:13px;color:var(--ink-muted)">$</span>
                <span style="font-family:var(--mono);font-size:32px;font-weight:600;color:var(--ink)">{deuda["TOTCTA"].sum()/1e6:,.2f}</span>
                <span style="font-family:var(--mono);font-size:15px;color:var(--ink-sub);font-weight:500">M</span>
              </div>
            </div>

            <!-- STK / PND / ING -->
            <div class="side-card" style="padding:6px 20px">
              {"".join([
                f'<div style="display:flex;align-items:center;justify-content:space-between;padding:14px 0;border-top:{"none" if i==0 else "1px solid var(--hairline-soft)"}">'
                f'<div><div style="font-size:10.5px;font-weight:600;color:var(--ink-muted);letter-spacing:0.6px;font-family:var(--mono)">{r["label"]}</div>'
                f'<div style="font-size:12px;color:var(--ink-sub);margin-top:1px">{r["full"]}</div></div>'
                f'{num_html(r["val"],20,r["color"])}</div>'
                for i, r in enumerate([
                  {"label":"STK","full":"Stock",      "val":stock["DISPONIBLE"].sum(), "color":"oklch(22% 0.01 260)"},
                  {"label":"PND","full":"Pendientes", "val":pendientes_pos["CANTID"].sum(), "color":"oklch(55% 0.18 25)"},
                  {"label":"ING","full":"Ingresos",   "val":stock["OC"].sum(), "color":"oklch(22% 0.01 260)"},
                ])
              ])}
            </div>

            <!-- Pend Facturar / Preventa -->
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px">
              {"".join([
                f'<div class="side-card" style="margin:0;padding:14px 16px">'
                f'<div style="font-size:10.5px;font-weight:600;color:var(--ink-muted);text-transform:uppercase;letter-spacing:0.6px">{r["label"]}</div>'
                f'<div style="display:flex;align-items:baseline;gap:4px;margin-top:8px">'
                f'<span style="font-family:var(--mono);font-size:11px;color:var(--ink-muted);font-weight:500">U$D</span>'
                f'<span style="font-family:var(--mono);font-size:22px;font-weight:600;color:var(--pos)">{r["val"]}</span></div></div>'
                for r in [
                  {"label":"PEND. FACTURAR","val": f'{pend_fact_usd/1000:.1f}K'},
                  {"label":"PREVENTA",      "val": f'{preventa_usd/1000:.1f}K'},
                ]
              ])}
            </div>

            <!-- TC -->
            <div class="side-card" style="display:flex;align-items:center;justify-content:space-between">
              <div>
                <div style="font-size:10.5px;font-weight:600;color:var(--ink-muted);text-transform:uppercase;letter-spacing:0.6px">Tipo de cambio</div>
                <div style="font-size:11px;color:var(--ink-muted);margin-top:3px;font-family:var(--mono)">{datetime.now().strftime("%d %b %Y · %H:%M")}</div>
              </div>
              {num_html(dolar_hoy, 22, "oklch(22% 0.01 260)", 600)}
            </div>
          </div>
        </div>
        """

        # Inject CSS + render
        st.markdown("""
        <style>
        .mx-wrap { display:grid; grid-template-columns:1fr 320px; gap:18px; font-family:var(--sans); color:var(--ink); }
        .mx-card { background:#fff; border:1px solid var(--hairline); border-radius:12px; padding:20px 24px 24px; }
        .mx-table { width:100%; border-collapse:collapse; margin-top:14px; }
        .mx-table td, .mx-table th { font-family:var(--sans); }
        .side-card { background:#fff; border:1px solid var(--hairline); border-radius:12px; padding:18px 20px; margin-bottom:14px; }
        </style>
        """, unsafe_allow_html=True)
        st.markdown(matrix_html, unsafe_allow_html=True)

        st.caption("Clasificación RETAIL/HOGAR/ECOMM: Vendedor contiene 'GER' → RETAIL, Cliente contiene 'CLIENTE CONTADO/PARA' → ECOMM, resto → HOGAR.")

    # ────────────────────────────── TAB 1: VENTAS
    with tab1:
        cf1, cf2, cf3, cf4 = st.columns([2, 2, 2, 2])
        with cf1:
            marcas_disp = sorted(ventas_pos["Marca"].dropna().unique().tolist())
            marca_sel = st.multiselect("Marca", marcas_disp, placeholder="Todas las marcas", key="f_marca")
        with cf2:
            cats_disp = sorted(ventas_pos["SubCategoria"].dropna().unique().tolist())
            cat_sel = st.multiselect("Categoría", cats_disp, placeholder="Todas las categorías", key="f_cat")
        with cf3:
            vend_disp = sorted(ventas_pos["Vendedor"].dropna().unique().tolist())
            vend_sel = st.multiselect("Vendedor", vend_disp, placeholder="Todos", key="f_vend")
        with cf4:
            u12m_start = (pd.Timestamp.today() - pd.DateOffset(months=12)).date()
            f_min = ventas_pos["Fecha"].min().date()
            f_max = ventas_pos["Fecha"].max().date()
            rango_v = st.date_input("Período (default: U12M)",
                                    value=(max(u12m_start, f_min), f_max),
                                    min_value=f_min, max_value=f_max, key="f_fecha")

        vf = ventas_pos.copy()
        if marca_sel: vf = vf[vf["Marca"].isin(marca_sel)]
        if cat_sel:   vf = vf[vf["SubCategoria"].isin(cat_sel)]
        if vend_sel:  vf = vf[vf["Vendedor"].isin(vend_sel)]
        if isinstance(rango_v, (tuple, list)) and len(rango_v) == 2:
            vf = vf[(vf["Fecha"].dt.date >= rango_v[0]) & (vf["Fecha"].dt.date <= rango_v[1])]

        # KPI strip
        kpi1, kpi2 = st.columns(2)
        total_usd = vf["Total_USD"].sum()
        total_q   = vf["Cantidad"].sum()
        with kpi1:
            st.markdown(
                f'<div style="background:#fff;border:1px solid var(--hairline);border-radius:12px;'
                f'padding:16px 20px;margin-bottom:8px">'
                f'<div style="font-size:10.5px;font-weight:600;color:var(--pos);text-transform:uppercase;'
                f'letter-spacing:0.7px;margin-bottom:6px">Facturación U$D</div>'
                f'{num_html(total_usd, 28, "oklch(52% 0.14 150)")}'
                f'</div>',
                unsafe_allow_html=True
            )
        with kpi2:
            st.markdown(
                f'<div style="background:#fff;border:1px solid var(--hairline);border-radius:12px;'
                f'padding:16px 20px;margin-bottom:8px">'
                f'<div style="font-size:10.5px;font-weight:600;color:var(--accent);text-transform:uppercase;'
                f'letter-spacing:0.7px;margin-bottom:6px">Cantidad vendida</div>'
                f'{num_html(total_q, 28, "oklch(55% 0.17 265)")}'
                f'</div>',
                unsafe_allow_html=True
            )

        st.divider()

        # Ranking data
        top_vend = (vf.groupby("Vendedor")["Total_USD"].sum()
                    .sort_values(ascending=False).head(8).reset_index())
        top_cli  = (vf.groupby("Cliente")["Total_USD"].sum()
                    .sort_values(ascending=False).head(8).reset_index())
        top_mod  = (vf.groupby("Modelo")["Total_USD"].sum()
                    .sort_values(ascending=False).head(8).reset_index())
        top_cat  = (vf.groupby("SubCategoria").agg(Q=("Cantidad","sum"),
                    Total_USD=("Total_USD","sum")).sort_values("Q",ascending=False).head(8).reset_index())
        top_marca = (vf.groupby("Marca")["Total_USD"].sum()
                     .sort_values(ascending=False).reset_index())

        # 3-column layout
        col_left, col_mid, col_right = st.columns([1.4, 1, 1])

        with col_left:
            # Bar chart: monthly USD totals
            if vf["Fecha"].notna().any():
                vm = vf.groupby(vf["Fecha"].dt.to_period("M")).agg(
                    Total_USD=("Total_USD","sum")
                ).reset_index()
                vm["Mes"] = vm["Fecha"].astype(str)
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(
                    name="Ventas USD", x=vm["Mes"], y=vm["Total_USD"],
                    marker_color="oklch(55% 0.17 265)",
                    hovertemplate="<b>%{x}</b><br>U$D %{y:,.0f}<extra></extra>"
                ))
                fig_bar.update_layout(
                    **PLOTLY_THEME,
                    title=dict(text="Ventas mensuales U$D"),
                    showlegend=False,
                    xaxis_tickangle=-40,
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            # Brand donut
            if not top_marca.empty:
                fig_donut = px.pie(
                    top_marca, values="Total_USD", names="Marca",
                    title="Mix por Marca", hole=0.45,
                    color_discrete_sequence=[
                        "oklch(55% 0.17 265)", "oklch(42% 0.17 265)",
                        "oklch(32% 0.09 265)", "oklch(62% 0.12 265)",
                        "oklch(70% 0.10 265)"
                    ]
                )
                fig_donut.update_layout(**PLOTLY_THEME)
                st.plotly_chart(fig_donut, use_container_width=True)

        with col_mid:
            # Vendedor table
            st.markdown(
                rank_table_html(
                    "Top Vendedores", top_vend, "Total_USD", "Vendedor",
                    "oklch(55% 0.17 265)", "oklch(96% 0.03 265)"
                ),
                unsafe_allow_html=True
            )
            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
            # Cliente table
            st.markdown(
                rank_table_html(
                    "Top Clientes", top_cli, "Total_USD", "Cliente",
                    "oklch(42% 0.17 265)", "oklch(96% 0.03 265)"
                ),
                unsafe_allow_html=True
            )

        with col_right:
            # Modelo table
            st.markdown(
                rank_table_html(
                    "Top Modelos", top_mod, "Total_USD", "Modelo",
                    "oklch(55% 0.17 265)", "oklch(96% 0.03 265)"
                ),
                unsafe_allow_html=True
            )
            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
            # SubCat table with Q column
            if not top_cat.empty:
                max_q = top_cat["Q"].max()
                rows_sc = ""
                for i, (_, row) in enumerate(top_cat.iterrows()):
                    pct = float(row["Q"]) / max_q if max_q > 0 else 0
                    intensity = int(pct * 35)
                    accent_c = "oklch(32% 0.09 265)"
                    text_color = "#fff" if pct > 0.55 else accent_c
                    q_val = int(row["Q"])
                    q_str = f"{q_val:,}".replace(",", ".")
                    usd_val = row["Total_USD"]
                    if usd_val >= 1e3:
                        usd_str = f"{usd_val/1e3:.0f}K"
                    else:
                        usd_str = f"{int(usd_val):,}".replace(",", ".")
                    label = str(row["SubCategoria"])[:22]
                    rows_sc += (
                        f'<div style="display:flex;align-items:center;justify-content:space-between;'
                        f'padding:8px 14px;border-bottom:1px solid var(--hairline-soft);gap:6px">'
                        f'<span style="font-size:11px;color:var(--ink-muted);font-family:var(--mono);min-width:18px">{i+1}.</span>'
                        f'<span style="font-size:12px;color:var(--ink);font-weight:500;flex:1;'
                        f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{label}</span>'
                        f'<span style="font-family:var(--mono);font-size:11px;color:var(--ink-muted);margin-right:6px">{usd_str}</span>'
                        f'<span style="padding:3px 8px;border-radius:4px;font-family:var(--mono);font-weight:600;font-size:12px;'
                        f'background:color-mix(in oklch,{accent_c} {intensity}%,#fff);color:{text_color}">{q_str}</span>'
                        f'</div>'
                    )
                st.markdown(
                    f'<div style="background:#fff;border:1px solid var(--hairline);border-radius:12px;'
                    f'display:flex;flex-direction:column;overflow:hidden">'
                    f'<div style="padding:10px 14px;border-bottom:1px solid var(--hairline-soft);'
                    f'font-size:11px;font-weight:600;color:oklch(32% 0.09 265);letter-spacing:-0.1px">'
                    f'Top Categorías &nbsp;<span style="font-size:10px;color:var(--ink-muted);font-weight:400">Q · U$D</span></div>'
                    f'{rows_sc}</div>',
                    unsafe_allow_html=True
                )

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
                                    marker_color="oklch(55% 0.17 265)"))
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
                               "font":{"color":"oklch(42% 0.17 265)","size":14}},
                        gauge={"axis":{"range":[0,100],"tickcolor":"oklch(62% 0.01 260)"},
                               "bar":{"color":"oklch(55% 0.17 265)"},"bgcolor":"#F8F8F8",
                               "borderwidth":2,"bordercolor":"oklch(92% 0.005 260)",
                               "steps":[{"range":[0,60],"color":"oklch(96% 0.04 150)"},
                                        {"range":[60,80],"color":"oklch(97% 0.05 85)"},
                                        {"range":[80,100],"color":"oklch(96% 0.04 25)"}],
                               "threshold":{"line":{"color":"oklch(55% 0.18 25)","width":3},"value":80}},
                        number={"suffix":"%","valueformat":".1f","font":{"color":"oklch(22% 0.01 260)","size":34}}
                    ))
                    fig_g.update_layout(paper_bgcolor="#FFFFFF",
                                        font=dict(color="oklch(22% 0.01 260)",family="Inter, sans-serif"),
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
            dep_sel = st.multiselect("Depósito", dep_opts, default=dep_opts,
                                     format_func=lambda d: dep_labels.get(d, str(d)), key="st_dep")
        with sf2c:
            s_marcas = sorted(stock_pos["Marca"].dropna().unique().tolist())
            s_marca_sel = st.multiselect("Marca", s_marcas, placeholder="Todas las marcas", key="st_marca")
        with sf3c:
            s_cats = sorted(stock_pos["SubCategoria"].dropna().unique().tolist())
            s_cat_sel = st.multiselect("Categoría", s_cats, placeholder="Todas las categorías", key="st_cat")

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
                             color_discrete_sequence=["oklch(55% 0.17 265)"])
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

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
_BASE = ("https://docs.google.com/spreadsheets/d/e/"
         "2PACX-1vTlq0-rgGCiZbHZoSVLNCOy-r7LSRasPGQLxK248rDK4tbksfv1Xc8jHVDcNoflsOx8qk3p-GJS9Hc_"
         "/pub?output=csv&gid=")

SHEETS = {
    "fecha_exp":  _BASE + "1343545783",
    "ventas":     _BASE + "1735040693",
    "deuda":      _BASE + "700818473",
    "stock":      _BASE + "1454621843",
    "pendientes": _BASE + "514545578",
    "gastos":     _BASE + "954051275",
    "clientes":   _BASE + "197301160",
}

DOLAR_URL = ("https://docs.google.com/spreadsheets/d/e/"
             "2PACX-1vQPneYHu78dHhzlUssSOE6zo9My4yQDwAJCg-f9k0wJbqug_otI0D4SnISsVViWgIGRjKSTeAjC26rE"
             "/pub?gid=1836470632&single=true&output=csv")

PRODUCT_KEY_URL = ("https://docs.google.com/spreadsheets/d/e/"
                   "2PACX-1vQsCFlbhmjGK3ovcxr3lP5RNAoCz0zkTGpgu1SEvCaQxeMxGibnIL_HIwzL0nifpTuP9JCArpglIhD-"
                   "/pub?gid=0&single=true&output=csv")

st.set_page_config(
    page_title="Dashboard Stromberg",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    /* ── Gularo brand palette ──────────────────────────────── */
    /* Primary:   #160B7C  (deep violet)                        */
    /* Accent:    #0FBFEF  (cyan)                               */
    /* ──────────────────────────────────────────────────────── */
    [data-testid="stAppViewContainer"] { background-color: #0D0852; }
    [data-testid="stHeader"]           { background-color: #0D0852; }
    .block-container { padding-top: 1.5rem; }

    /* KPI cards */
    div[data-testid="metric-container"] {
        background: #160B7C;
        border-radius: 12px;
        padding: 16px 20px;
        border: 1px solid rgba(15,191,239,0.35);
        box-shadow: 0 0 12px rgba(15,191,239,0.12);
    }
    div[data-testid="metric-container"] label {
        color: #9BB8D4;
        font-size: 0.85rem;
    }
    div[data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #ffffff;
        font-size: 1.6rem;
        font-weight: 700;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background: #160B7C;
        border-radius: 8px;
        padding: 8px 20px;
        color: #9BB8D4;
        border: 1px solid rgba(15,191,239,0.2);
    }
    .stTabs [aria-selected="true"] {
        background: #0FBFEF !important;
        color: #0D0852 !important;
        font-weight: 700 !important;
    }

    /* Dataframes */
    .stDataFrame { background: #160B7C; }

    /* Dividers */
    hr { border-color: rgba(15,191,239,0.2); }

    /* Sidebar (if used) */
    [data-testid="stSidebar"] { background-color: #160B7C; }

    /* Title accent */
    h1 { color: #0FBFEF !important; }
    h2, h3 { color: #E0E8FF !important; }
</style>
""", unsafe_allow_html=True)

PLOTLY_THEME = {
    "paper_bgcolor": "#160B7C",
    "plot_bgcolor":  "#1A0E96",
    "font":  {"color": "#E0E8FF"},
    "xaxis": {"gridcolor": "rgba(255,255,255,0.08)", "linecolor": "rgba(255,255,255,0.15)"},
    "yaxis": {"gridcolor": "rgba(255,255,255,0.08)", "linecolor": "rgba(255,255,255,0.15)"},
    "margin": {"t": 50, "b": 40, "l": 40, "r": 20},
}

# ── CARGA DE DATOS ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)          # refresca cada 5 min (el sheet no cambia tan seguido)
def load_dolar():
    """Lee el sheet de dólar y devuelve una Serie indexada por fecha."""
    df = pd.read_csv(DOLAR_URL).dropna(subset=["Fecha", "Close"])
    # Formato: $1.000,08  →  punto=miles, coma=decimal
    df["close_num"] = (
        df["Close"]
        .str.replace("$", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
    )
    df["fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce").dt.normalize()
    df = df.dropna(subset=["fecha", "close_num"])
    # Una sola fila por fecha (promedio si hay duplicados)
    serie = df.groupby("fecha")["close_num"].mean()
    # Expandir al rango completo y forward-fill fines de semana / feriados
    idx_completo = pd.date_range(serie.index.min(), serie.index.max(), freq="D")
    serie = serie.reindex(idx_completo).ffill()
    return serie


def cruzar_con_dolar(ventas: pd.DataFrame, dolar_serie: pd.Series) -> pd.DataFrame:
    """
    Agrega columnas 'dolar_dia' y 'Total_USD' a ventas.
    Para fechas sin cotización (finde/feriado) usa el último precio conocido.
    """
    v = ventas.copy()
    v["fecha_join"] = v["Fecha"].dt.normalize()
    v["dolar_dia"]  = v["fecha_join"].map(dolar_serie)
    # Si todavía quedan NaN (fecha fuera del rango del sheet) usa la media
    fallback = dolar_serie.mean()
    v["dolar_dia"]  = v["dolar_dia"].fillna(fallback)
    v["Total_USD"]  = (v["Total"] / v["dolar_dia"]).round(2)
    return v


@st.cache_data(ttl=3600)
def load_product_key():
    """Lee el Product Key y devuelve DataFrame con SKU Limpio → Marca + SubCategoria."""
    df = pd.read_csv(PRODUCT_KEY_URL, header=1)   # fila 0 = nombres, fila 1 = headers reales
    df.columns = df.columns.str.strip()
    keep = ["SKU Limpio", "SubCategoria", "Marca", "MODEL"]
    df = df[[c for c in keep if c in df.columns]].copy()
    df["SKU Limpio"] = df["SKU Limpio"].astype(str).str.strip()
    df["SubCategoria"] = df["SubCategoria"].astype(str).str.strip()
    df["Marca"]        = df["Marca"].astype(str).str.strip()
    # eliminar filas sin SKU real
    df = df[df["SKU Limpio"].str.len() > 3]
    return df.drop_duplicates("SKU Limpio")


@st.cache_data(ttl=60)
def load_all():
    try:
        ventas     = pd.read_csv(SHEETS["ventas"])
        deuda      = pd.read_csv(SHEETS["deuda"])
        stock      = pd.read_csv(SHEETS["stock"])
        gastos     = pd.read_csv(SHEETS["gastos"])
        pendientes = pd.read_csv(SHEETS["pendientes"])
        fecha_df   = pd.read_csv(SHEETS["fecha_exp"], header=None)
        fecha_exp  = str(fecha_df.iloc[1, 0]).strip() if len(fecha_df) > 1 else "N/D"
    except Exception as e:
        st.error(f"❌ Error cargando datos desde Google Sheets: {e}")
        st.stop()

    # Ventas
    ventas["Fecha"]    = pd.to_datetime(ventas["Fecha"], errors="coerce")

    # Precio usa formato argentino: punto=miles, coma=decimal  →  "92.923,60" o "92923,6"
    def parse_ars(col):
        return (col.astype(str)
                   .str.replace(r"[$ ]", "", regex=True)   # quitar $ y espacios
                   .str.replace(".", "", regex=False)        # quitar separador de miles
                   .str.replace(",", ".", regex=False)       # coma decimal → punto
                   .pipe(pd.to_numeric, errors="coerce")
                   .fillna(0))

    ventas["Precio"]   = parse_ars(ventas["Precio"])
    ventas["Cantidad"] = pd.to_numeric(ventas["Cantidad"], errors="coerce").fillna(0)
    ventas["Total"]    = ventas["Precio"] * ventas["Cantidad"]

    # Deuda
    for c in ["SAL30","SAL60","SALMAY60","SALMAY90","TOTCTA","VALVEN","LIMCRED"]:
        deuda[c] = pd.to_numeric(deuda[c], errors="coerce").fillna(0)

    # Stock
    for c in ["DISPONIBLE","NV","OC","ST"]:
        stock[c] = pd.to_numeric(stock[c], errors="coerce").fillna(0)
    stock["CODIGO_DEPOSITO"] = pd.to_numeric(stock["CODIGO_DEPOSITO"], errors="coerce").fillna(0).astype(int)
    # Filtro global: solo depósitos relevantes (1=General, 12, 15)
    stock = stock[stock["CODIGO_DEPOSITO"].isin([1, 12, 15])]

    # Gastos
    gastos["W_FCHMOV"] = pd.to_datetime(gastos["W_FCHMOV"], errors="coerce")
    gastos["SALDO"]    = pd.to_numeric(gastos["SALDO"], errors="coerce").fillna(0)

    # Pendientes
    pendientes["CANTID"]           = pd.to_numeric(pendientes["CANTID"], errors="coerce").fillna(0)
    pendientes["Import"]           = pd.to_numeric(pendientes["Import"], errors="coerce").fillna(0)
    pendientes["nCntEstimada"]     = pd.to_numeric(pendientes["nCntEstimada"], errors="coerce").fillna(0)
    pendientes["FCRMVI_FCHENT"]    = pd.to_datetime(pendientes["FCRMVI_FCHENT"], errors="coerce")

    return ventas, deuda, stock, gastos, pendientes, fecha_exp


# ── DASHBOARD ─────────────────────────────────────────────────────────────────
@st.fragment(run_every=120)   # se refresca cada 2 minutos
def dashboard():
    ventas, deuda, stock, gastos, pendientes, fecha_exp = load_all()
    dolar_serie = load_dolar()

    # Cruce pesos → dólares
    ventas = cruzar_con_dolar(ventas, dolar_serie)

    # Cruce con Product Key → Marca + SubCategoría
    pk = load_product_key()
    _pk = pk[["SKU Limpio", "SubCategoria", "Marca"]].drop_duplicates("SKU Limpio")
    ventas = ventas.merge(_pk, left_on="FCRMVI_ARTCOD", right_on="SKU Limpio", how="left"
                         ).drop(columns=["SKU Limpio"], errors="ignore")
    stock  = stock.merge(_pk,  left_on="STMPDH_ARTCOD",  right_on="SKU Limpio", how="left"
                        ).drop(columns=["SKU Limpio"], errors="ignore")

    # Excluir devoluciones (Cantidad<=0) y notas de crédito/débito (Tipo_Pago==60)
    # → coincide con la columna "Q" del sheet Ventas Crudo que usa el Looker
    _tp = ventas["Tipo_Pago"].astype(str).str.strip()
    ventas_pos = ventas[(ventas["Cantidad"] > 0) & (_tp != "60")]

    # ── Clasificación de canal (RETAIL / HOGAR / ECOMM) ────────────────
    # Heurística vectorizada — ajustable:
    #   ECOMM  = CLIENTE CONTADO / MercadoLibre / Amazon / Shopify (directo al consumidor)
    #   HOGAR  = productos Marca "Stromberg Life" (línea hogar / pequeños electro)
    #   RETAIL = resto (cadenas, distribuidores B2B)
    ventas_pos = ventas_pos.copy()
    _cli_u = ventas_pos["Cliente"].astype(str).str.upper().str.strip()
    _mrc_u = ventas_pos["Marca"].astype(str).str.upper().str.strip()

    ecomm_mask = (
        _cli_u.str.contains("CONTADO",        na=False) |
        _cli_u.str.contains("MERCADOLIBRE",   na=False) |
        _cli_u.str.contains("MERCADO LIBRE",  na=False) |
        _cli_u.str.contains(r"\bML\b",        na=False, regex=True) |
        _cli_u.str.contains("AMAZON",         na=False) |
        _cli_u.str.contains("TIENDA NUBE",    na=False) |
        _cli_u.str.contains("SHOPIFY",        na=False) |
        _cli_u.str.contains("E[- ]?COMMERCE", na=False, regex=True) |
        _cli_u.str.contains("ECOMM",          na=False)
    )
    hogar_mask = _mrc_u.str.contains("STROMBERG LIFE", na=False)

    ventas_pos["Canal"] = "RETAIL"
    ventas_pos.loc[hogar_mask, "Canal"] = "HOGAR"
    ventas_pos.loc[ecomm_mask, "Canal"] = "ECOMM"   # ECOMM pisa a HOGAR si el cliente es ecomm
    pendientes_pos = pendientes[pendientes["CANTID"] > 0]

    # ── Header
    c1, c2, c3 = st.columns([4, 2, 2])
    with c1:
        st.title("📊 Dashboard Stromberg")
    with c2:
        try:
            fe = pd.to_datetime(fecha_exp).strftime("%d/%m/%Y %H:%M")
        except Exception:
            fe = fecha_exp
        st.metric("🕐 Última exportación Arrow", fe)
    with c3:
        st.metric("🔄 Actualización dashboard", datetime.now().strftime("%H:%M:%S"))

    st.divider()

    # ── FILTROS GLOBALES (arriba del todo, afectan KPIs y gráficos) ───────────
    cf1, cf2, cf3, cf4 = st.columns([2, 2, 2, 2])
    with cf1:
        marcas_disp = sorted(ventas_pos["Marca"].dropna().unique().tolist())
        marca_sel = st.multiselect("🏷️ Marca", marcas_disp,
                                   placeholder="Todas las marcas", key="f_marca")
    with cf2:
        cats_disp = sorted(ventas_pos["SubCategoria"].dropna().unique().tolist())
        cat_sel = st.multiselect("📂 Categoría", cats_disp,
                                 placeholder="Todas las categorías", key="f_cat")
    with cf3:
        vend_disp = sorted(ventas_pos["Vendedor"].dropna().unique().tolist())
        vend_sel = st.multiselect("👤 Vendedor", vend_disp,
                                  placeholder="Todos", key="f_vend")
    with cf4:
        u12m_start = (pd.Timestamp.today() - pd.DateOffset(months=12)).date()
        f_min = ventas_pos["Fecha"].min().date()
        f_max = ventas_pos["Fecha"].max().date()
        rango_v = st.date_input("📅 Período (default: U12M)",
                                value=(max(u12m_start, f_min), f_max),
                                min_value=f_min, max_value=f_max,
                                key="f_fecha")

    # Aplicar filtros de dropdown
    vf = ventas_pos.copy()
    if marca_sel:
        vf = vf[vf["Marca"].isin(marca_sel)]
    if cat_sel:
        vf = vf[vf["SubCategoria"].isin(cat_sel)]
    if vend_sel:
        vf = vf[vf["Vendedor"].isin(vend_sel)]
    if isinstance(rango_v, (tuple, list)) and len(rango_v) == 2:
        vf = vf[(vf["Fecha"].dt.date >= rango_v[0]) & (vf["Fecha"].dt.date <= rango_v[1])]

    # ── Leer selección activa del gráfico de modelos (persiste entre reruns)
    def _read_chart_sel(key, field="y"):
        try:
            pts = st.session_state[key].selection.points
            if pts:
                v = pts[0].get(field) or pts[0].get("label") or pts[0].get("x")
                return v if v else None
        except Exception:
            return None

    active_model = _read_chart_sel("sel_mod")

    # Aplicar selección de gráfico a los KPIs
    vf_kpi = vf[vf["Modelo"] == active_model] if active_model else vf

    # ── KPIs (filtrados por dropdown + clic en gráfico) ───────────────────────
    dolar_hoy = dolar_serie.iloc[-1]
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("💵 Ventas USD",       f"U$D {vf_kpi['Total_USD'].sum():,.0f}")
    k2.metric("📦 Unidades",         f"{vf_kpi['Cantidad'].sum():,.0f}")
    k3.metric("🛍️ Transacciones",    f"{len(vf_kpi):,}")
    k4.metric("📋 Deuda total",      f"${deuda['TOTCTA'].sum():,.0f}")
    k5.metric("📦 Stock disponible", f"{stock['DISPONIBLE'].sum():,.0f} u.")
    k6.metric("💱 Dólar hoy",        f"${dolar_hoy:,.2f}")

    if active_model:
        st.info(f"🔍 Modelo activo: **{active_model}** — clic en el mismo modelo o en área vacía del gráfico para limpiar")

    st.divider()

    # ── helper
    def get_sel(ev, key="y"):
        try:
            p = ev.selection.points[0]
            return p.get(key) or p.get("label") or p.get("x")
        except Exception:
            return None

    # ── Tabs
    tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Resumen", "📈 Ventas", "💰 Deuda", "📦 Stock", "⏳ Pendientes", "💸 Gastos"
    ])

    # ────────────────────────────── TAB 0: RESUMEN (estilo Looker)
    with tab0:
        import datetime as _dt
        hoy = _dt.date.today()
        mes_ini = hoy.replace(day=1)
        u12m_ini = (pd.Timestamp.today() - pd.DateOffset(months=12)).date()

        v_hoy  = ventas_pos[ventas_pos["Fecha"].dt.date == hoy]
        v_mes  = ventas_pos[ventas_pos["Fecha"].dt.date >= mes_ini]
        v_u12m = ventas_pos[ventas_pos["Fecha"].dt.date >= u12m_ini]

        def _canal_metrics(df, canal):
            sub = df[df["Canal"] == canal]
            return sub["Total"].sum(), sub["Total_USD"].sum(), sub["Cantidad"].sum()

        # CSS custom para las cards estilo Looker
        st.markdown("""
        <style>
        .lkr-card {
            background: #FFFFFF; color: #1A1A1A; border-radius: 12px;
            padding: 14px 18px; box-shadow: 0 2px 8px rgba(0,0,0,.15);
            border: 1px solid rgba(15,191,239,.3);
        }
        .lkr-head {
            text-align: center; font-weight: 700; font-size: 0.85rem;
            padding: 10px 14px; border-radius: 10px 10px 0 0; color: white;
            letter-spacing: 1px;
        }
        .lkr-head-hoy   { background: #4B57C9; }
        .lkr-head-mes   { background: #3E4BCC; }
        .lkr-head-u12m  { background: #2E8555; }
        .lkr-head-sldc  { background: #2E8AD6; }
        .lkr-head-stk   { background: #2E8AD6; color: #fff; }
        .lkr-head-pnd   { background: #D04444; }
        .lkr-head-ing   { background: #8D8717; }
        .lkr-head-pf    { background: #C93B3B; }
        .lkr-head-pv    { background: #C93B3B; }
        .lkr-row-label  {
            background: #3E4BCC; color: white; padding: 10px 14px;
            font-weight: 700; border-radius: 10px 0 0 10px;
            display: flex; align-items: center; justify-content: center;
        }
        .lkr-value      { font-size: 1.55rem; font-weight: 700; color: #2E4A9C; }
        .lkr-value-q    { color: #8B00CC; }
        .lkr-value-usd  { color: #2E8555; }
        .lkr-value-small{ font-size: 1.2rem; }
        .lkr-value-red  { color: #D04444; }
        .lkr-value-gold { color: #8D8717; }
        .lkr-small      { font-size: 0.75rem; color: #888; text-align: center; }
        </style>
        """, unsafe_allow_html=True)

        def _fmt_ars(v): return f"{v:,.0f}" if pd.notna(v) else "—"
        def _fmt_usd(v): return f"{v:,.0f}" if pd.notna(v) else "—"
        def _fmt_q(v):   return f"{v:,.0f}" if pd.notna(v) else "—"

        # ── Layout principal: matriz izq + sidebar der
        col_main, col_side = st.columns([3, 1])

        with col_main:
            # Header HOY / MES / U12M U$D
            h1, h2, h3, h4 = st.columns([1, 2, 2, 2])
            h1.markdown("&nbsp;", unsafe_allow_html=True)
            h2.markdown('<div class="lkr-head lkr-head-hoy">HOY</div>', unsafe_allow_html=True)
            h3.markdown('<div class="lkr-head lkr-head-mes">MES</div>', unsafe_allow_html=True)
            h4.markdown('<div class="lkr-head lkr-head-u12m">U12M U$D</div>', unsafe_allow_html=True)

            # Fila $ (ARS para HOY/MES, USD para U12M)
            r1, r2, r3, r4 = st.columns([1, 2, 2, 2])
            r1.markdown('<div class="lkr-row-label">$</div>', unsafe_allow_html=True)
            r2.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value">{_fmt_ars(v_hoy["Total"].sum())}</div></div>', unsafe_allow_html=True)
            r3.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value">{_fmt_ars(v_mes["Total"].sum())}</div></div>', unsafe_allow_html=True)
            r4.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-usd">{_fmt_usd(v_u12m["Total_USD"].sum())}</div></div>', unsafe_allow_html=True)

            # Fila Q
            q1, q2, q3, q4 = st.columns([1, 2, 2, 2])
            q1.markdown('<div class="lkr-row-label" style="background:#6B2DCC">Q</div>', unsafe_allow_html=True)
            q2.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-q">{_fmt_q(v_hoy["Cantidad"].sum())}</div></div>', unsafe_allow_html=True)
            q3.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-q">{_fmt_q(v_mes["Cantidad"].sum())}</div></div>', unsafe_allow_html=True)
            q4.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-q">{_fmt_q(v_u12m["Cantidad"].sum())}</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Filas por canal
            for canal, color in [("RETAIL", "#3E4BCC"), ("HOGAR", "#3E4BCC"), ("ECOMM", "#3E4BCC")]:
                ars_h, usd_h, _ = _canal_metrics(v_hoy, canal)
                ars_m, usd_m, _ = _canal_metrics(v_mes, canal)
                _, usd_u, _     = _canal_metrics(v_u12m, canal)
                c1, c2, c3, c4 = st.columns([1, 2, 2, 2])
                c1.markdown(f'<div class="lkr-row-label" style="background:{color}">{canal}</div>', unsafe_allow_html=True)
                ars_h_class = "lkr-value-red" if ars_h < 0 else ""
                c2.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-small {ars_h_class}">{_fmt_ars(ars_h)}</div></div>', unsafe_allow_html=True)
                c3.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-small">{_fmt_ars(ars_m)}</div></div>', unsafe_allow_html=True)
                c4.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-small lkr-value-usd">{_fmt_usd(usd_u)}</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Pend Facturar / Preventa (fila inferior)
            p1, p2, p3 = st.columns([1, 2, 2])
            pend_fact_usd = pendientes_pos["Import"].sum() / dolar_hoy if dolar_hoy else 0
            preventa_usd = 0  # placeholder — requiere identificar preventa en pendientes
            if "nCntEstimada" in pendientes_pos.columns:
                preventa_usd = (pendientes_pos["nCntEstimada"] * pendientes_pos["Import"] / pendientes_pos["CANTID"].replace(0, 1)).sum() / dolar_hoy if dolar_hoy else 0
            p2.markdown('<div class="lkr-head lkr-head-pf">PEND FACTURAR U$D</div>', unsafe_allow_html=True)
            p2.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-usd">$ {pend_fact_usd/1000:.2f}K</div></div>', unsafe_allow_html=True)
            p3.markdown('<div class="lkr-head lkr-head-pv">PREVENTA U$D</div>', unsafe_allow_html=True)
            p3.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value lkr-value-usd">$ {preventa_usd/1000:.2f}K</div></div>', unsafe_allow_html=True)

        with col_side:
            # Saldos Comerciales
            st.markdown('<div class="lkr-head lkr-head-sldc">🟡 SALDOS COMERCIALES</div>', unsafe_allow_html=True)
            saldo = deuda["TOTCTA"].sum()
            st.markdown(f'<div class="lkr-card" style="text-align:center"><div class="lkr-value">$ {saldo/1e6:.2f}M</div></div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            # STK / PND / ING mini-cards
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

            # Fecha + TC del día
            st.markdown(f'<div class="lkr-card" style="text-align:center;font-size:0.85rem;color:#555">{datetime.now().strftime("%b %d, %Y, %I:%M:%S %p")}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="lkr-card" style="text-align:center;font-weight:700;color:#2E4A9C">{dolar_hoy:,.2f}</div>', unsafe_allow_html=True)

        st.caption("💡 Clasificación RETAIL/HOGAR/ECOMM es heurística (Marca=Stromberg Life → HOGAR, Cliente con CONTADO/ML → ECOMM, resto → RETAIL). Ajustable en `_canal()`.")

    # ────────────────────────────── TAB 1: VENTAS (USD)
    with tab1:

        # Gráfico dual ARS / USD / TC
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
                paper_bgcolor="#160B7C", plot_bgcolor="#1A0E96",
                font=dict(color="#E0E8FF"), margin=dict(t=50, b=60, l=40, r=80),
                title="Ventas mensuales: ARS vs USD vs Tipo de cambio",
                xaxis=dict(gridcolor="rgba(255,255,255,0.08)", linecolor="rgba(255,255,255,0.15)"),
                yaxis =dict(title=dict(text="ARS", font=dict(color="#0FBFEF")),
                            gridcolor="rgba(255,255,255,0.08)"),
                yaxis2=dict(title=dict(text="USD", font=dict(color="#f7c948")),
                            overlaying="y", side="right", gridcolor="rgba(0,0,0,0)"),
                yaxis3=dict(title=dict(text="$/USD", font=dict(color="#FF7BA0")),
                            overlaying="y", side="right", anchor="free",
                            position=0.97, gridcolor="rgba(0,0,0,0)"),
                legend=dict(orientation="h", y=-0.2), hovermode="x unified",
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

        # Drill-down modelo
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
                fig_dd.update_layout(**PLOTLY_THEME, coloraxis_showscale=False, xaxis_tickangle=-40)
                st.plotly_chart(fig_dd, use_container_width=True)
            with fc2:
                fig_dd2 = px.bar(dm, x="Mes", y="Unidades",
                                 title=f"{mod_sel} — Unidades por mes",
                                 color="Unidades", color_continuous_scale="Blues")
                fig_dd2.update_layout(**PLOTLY_THEME, coloraxis_showscale=False, xaxis_tickangle=-40)
                st.plotly_chart(fig_dd2, use_container_width=True)
            dm_fmt = dm.copy()
            dm_fmt["Total_USD"] = dm_fmt["Total_USD"].map("U$D {:,.0f}".format)
            dm_fmt["Unidades"]  = dm_fmt["Unidades"].map("{:,.0f}".format)
            st.dataframe(dm_fmt, use_container_width=True, hide_index=True)
            st.divider()

        # Desglose por Marca y SubCategoría
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
                                 barmode="group", xaxis_tickangle=-40)
            sel_deu = st.plotly_chart(fig_dd, use_container_width=True,
                                      on_select="rerun", key="sel_deu")

        # Drill-down cliente deuda
        cli_deu_sel = get_sel(sel_deu, "x")
        if cli_deu_sel:
            # Buscar nombre completo (puede estar truncado)
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
                    fig_ag2 = px.bar(ag_cli, x="Período", y="Monto",
                                     color="Período",
                                     color_discrete_sequence=["#4CAF50","#FFC107","#FF9800","#F44336"],
                                     title="Deuda por antigüedad")
                    fig_ag2.update_layout(**PLOTLY_THEME, showlegend=False)
                    st.plotly_chart(fig_ag2, use_container_width=True)
                with fc2:
                    uso_pct = (row["TOTCTA"] / row["LIMCRED"] * 100) if row["LIMCRED"] > 0 else 0
                    fig_g = go.Figure(go.Indicator(
                        mode="gauge+number", value=uso_pct,
                        title={"text": "Uso de límite de crédito (%)"},
                        gauge={"axis":{"range":[0,100]},
                               "bar":{"color":"#FF5E7E"},
                               "steps":[{"range":[0,60],"color":"#1A0E96"},
                                        {"range":[60,80],"color":"#3D1A5C"},
                                        {"range":[80,100],"color":"#5A0F3A"}],
                               "threshold":{"line":{"color":"#0FBFEF","width":2},"value":80}},
                        number={"suffix":"%","valueformat":".1f"}
                    ))
                    fig_g.update_layout(paper_bgcolor="#160B7C", font=dict(color="#E0E8FF"),
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

        # ── Filtros stock ──────────────────────────────────────────────────────
        sf1c, sf2c, sf3c = st.columns([2, 2, 2])
        with sf1c:
            dep_opts = sorted(stock_pos["CODIGO_DEPOSITO"].unique().tolist())
            dep_labels = {d: f"Depósito {d}" for d in dep_opts}
            if "NOMBRE_DEPOSITO" in stock_pos.columns:
                for d in dep_opts:
                    name = stock_pos[stock_pos["CODIGO_DEPOSITO"]==d]["NOMBRE_DEPOSITO"].iloc[0] \
                           if not stock_pos[stock_pos["CODIGO_DEPOSITO"]==d].empty else ""
                    if name and str(name).strip():
                        dep_labels[d] = f"{d} — {str(name).strip()}"
            dep_sel = st.multiselect("🏭 Depósito", dep_opts,
                                     default=dep_opts,
                                     format_func=lambda d: dep_labels.get(d, str(d)),
                                     key="st_dep")
        with sf2c:
            s_marcas = sorted(stock_pos["Marca"].dropna().unique().tolist())
            s_marca_sel = st.multiselect("🏷️ Marca", s_marcas,
                                         placeholder="Todas las marcas", key="st_marca")
        with sf3c:
            s_cats = sorted(stock_pos["SubCategoria"].dropna().unique().tolist())
            s_cat_sel = st.multiselect("📂 Categoría", s_cats,
                                       placeholder="Todas las categorías", key="st_cat")
        sf = stock_pos.copy()
        if dep_sel:
            sf = sf[sf["CODIGO_DEPOSITO"].isin(dep_sel)]
        if s_marca_sel:
            sf = sf[sf["Marca"].isin(s_marca_sel)]
        if s_cat_sel:
            sf = sf[sf["SubCategoria"].isin(s_cat_sel)]
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

        # Drill-down producto stock
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
                        "Estado": ["Disponible","Nota de Venta","Orden de Compra","En Stock"],
                        "Unidades": [row_st["DISPONIBLE"], row_st["NV"],
                                     row_st["OC"], row_st["ST"]],
                        "Color": ["#4CAF50","#FFC107","#42A5F5","#AB47BC"]
                    })
                    fig_std = px.bar(st_detail, x="Estado", y="Unidades",
                                     color="Estado",
                                     color_discrete_sequence=st_detail["Color"].tolist(),
                                     title="Breakdown de stock")
                    fig_std.update_layout(**PLOTLY_THEME, showlegend=False)
                    st.plotly_chart(fig_std, use_container_width=True)
                with fc2:
                    st.markdown("#### Ficha del producto")
                    st.metric("Código",       row_st["STMPDH_ARTCOD"])
                    st.metric("Disponible",   f"{row_st['DISPONIBLE']:,.0f} u.")
                    st.metric("Nota de Venta",f"{row_st['NV']:,.0f} u.")
                    st.metric("Orden Compra", f"{row_st['OC']:,.0f} u.")
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

        # Drill-down cliente pendiente
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

        # Drill-down artículo pendiente
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
            fig_gm.update_layout(**PLOTLY_THEME, coloraxis_showscale=False, xaxis_tickangle=-40)
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

        # Drill-down proveedor
        prov_sel = get_sel(sel_prov)
        if prov_sel:
            prov_full = gastos_pos[gastos_pos["PVMPRH_NOMBRE"].str[:25] == prov_sel]["PVMPRH_NOMBRE"].iloc[0] \
                        if not gastos_pos[gastos_pos["PVMPRH_NOMBRE"].str[:25] == prov_sel].empty else prov_sel
            st.divider()
            st.subheader(f"💸 Evolución mensual — {prov_full}")
            df_pv = gastos_pos[gastos_pos["PVMPRH_NOMBRE"] == prov_full].copy()
            df_pv["Mes"] = df_pv["W_FCHMOV"].dt.to_period("M").astype(str)
            gp = df_pv.groupby("Mes")["SALDO"].sum().reset_index()
            fig_pv = px.area(gp, x="Mes", y="SALDO",
                             title=f"{prov_full} — gasto mensual",
                             color_discrete_sequence=["#0FBFEF"])
            fig_pv.update_layout(**PLOTLY_THEME, xaxis_tickangle=-40)
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

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

st.set_page_config(
    page_title="Dashboard Stromberg",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background-color: #0f1117; }
    [data-testid="stHeader"] { background-color: #0f1117; }
    .block-container { padding-top: 1.5rem; }
    div[data-testid="metric-container"] {
        background: #1e1e2e;
        border-radius: 12px;
        padding: 16px 20px;
        border: 1px solid #2a2a3e;
    }
    div[data-testid="metric-container"] label { color: #aaa; font-size: 0.85rem; }
    div[data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #fff;
        font-size: 1.6rem;
        font-weight: 700;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background: #1e1e2e;
        border-radius: 8px;
        padding: 8px 20px;
        color: #aaa;
    }
    .stTabs [aria-selected="true"] {
        background: #4f8ef7 !important;
        color: white !important;
    }
    .stDataFrame { background: #1e1e2e; }
</style>
""", unsafe_allow_html=True)

PLOTLY_THEME = {
    "paper_bgcolor": "#1e1e2e",
    "plot_bgcolor": "#1e1e2e",
    "font": {"color": "#e0e0e0"},
    "xaxis": {"gridcolor": "#2a2a3e", "linecolor": "#2a2a3e"},
    "yaxis": {"gridcolor": "#2a2a3e", "linecolor": "#2a2a3e"},
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
    ventas["Precio"]   = pd.to_numeric(ventas["Precio"], errors="coerce").fillna(0)
    ventas["Cantidad"] = pd.to_numeric(ventas["Cantidad"], errors="coerce").fillna(0)
    ventas["Total"]    = ventas["Precio"] * ventas["Cantidad"]

    # Deuda
    for c in ["SAL30","SAL60","SALMAY60","SALMAY90","TOTCTA","VALVEN","LIMCRED"]:
        deuda[c] = pd.to_numeric(deuda[c], errors="coerce").fillna(0)

    # Stock
    for c in ["DISPONIBLE","NV","OC","ST"]:
        stock[c] = pd.to_numeric(stock[c], errors="coerce").fillna(0)

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
    ventas      = cruzar_con_dolar(ventas, dolar_serie)
    ventas_pos  = ventas[ventas["Cantidad"] > 0]
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

    # ── KPIs
    k1, k2, k3, k4, k5 = st.columns(5)
    dolar_hoy = dolar_serie.iloc[-1]
    k1.metric("💰 Ventas ARS",        f"${ventas_pos['Total'].sum():,.0f}")
    k2.metric("💵 Ventas USD",        f"U$D {ventas_pos['Total_USD'].sum():,.0f}")
    k3.metric("📋 Deuda total",       f"${deuda['TOTCTA'].sum():,.0f}")
    k4.metric("📦 Stock disponible",  f"{stock['DISPONIBLE'].sum():,.0f} u.")
    k5.metric("💱 Dólar hoy",         f"${dolar_hoy:,.2f}")

    st.divider()

    # ── Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📈 Ventas", "💵 Ventas en USD", "💰 Deuda", "📦 Stock", "⏳ Pendientes", "💸 Gastos"
    ])

    # ────────────────────────────── TAB 1: VENTAS
    with tab1:
        c1, c2 = st.columns(2)

        with c1:
            top_mod = (ventas_pos.groupby("Modelo")["Total"]
                       .sum().sort_values(ascending=False).head(12).reset_index())
            fig = px.bar(top_mod, x="Total", y="Modelo", orientation="h",
                         title="Top 12 Modelos por $ vendido",
                         color="Total", color_continuous_scale="Blues")
            fig.update_layout(**PLOTLY_THEME, showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            vend = (ventas_pos.groupby("Vendedor")["Total"]
                    .sum().sort_values(ascending=False).head(10).reset_index())
            fig2 = px.pie(vend, values="Total", names="Vendedor",
                          title="Ventas por Vendedor", hole=0.45)
            fig2.update_layout(**PLOTLY_THEME)
            st.plotly_chart(fig2, use_container_width=True)

        # Evolución mensual
        if ventas_pos["Fecha"].notna().any():
            vt = (ventas_pos.groupby(ventas_pos["Fecha"].dt.to_period("M"))["Total"]
                  .sum().reset_index())
            vt["Fecha"] = vt["Fecha"].astype(str)
            fig3 = px.area(vt, x="Fecha", y="Total",
                           title="Evolución Mensual de Ventas",
                           color_discrete_sequence=["#4f8ef7"])
            fig3.update_layout(**PLOTLY_THEME)
            st.plotly_chart(fig3, use_container_width=True)

        st.subheader("Top 15 Clientes")
        top_cli = (ventas_pos.groupby("Cliente")["Total"]
                   .sum().sort_values(ascending=False).head(15).reset_index())
        top_cli["Total"] = top_cli["Total"].map("${:,.0f}".format)
        st.dataframe(top_cli, use_container_width=True, hide_index=True)

    # ────────────────────────────── TAB 2: VENTAS EN USD
    with tab2:
        if ventas_pos["Fecha"].notna().any():
            # Evolución mensual ARS vs USD en eje dual
            vm = ventas_pos.groupby(ventas_pos["Fecha"].dt.to_period("M")).agg(
                Total=("Total","sum"), Total_USD=("Total_USD","sum"),
                dolar_prom=("dolar_dia","mean")
            ).reset_index()
            vm["Mes"] = vm["Fecha"].astype(str)

            fig_dual = go.Figure()
            fig_dual.add_trace(go.Bar(
                name="Ventas ARS", x=vm["Mes"], y=vm["Total"],
                marker_color="#4f8ef7", yaxis="y1", opacity=0.7
            ))
            fig_dual.add_trace(go.Scatter(
                name="Ventas USD", x=vm["Mes"], y=vm["Total_USD"],
                mode="lines+markers", marker_color="#f7c948",
                yaxis="y2", line=dict(width=3)
            ))
            fig_dual.add_trace(go.Scatter(
                name="Dólar promedio", x=vm["Mes"], y=vm["dolar_prom"],
                mode="lines", line=dict(color="#e05c5c", dash="dot", width=2),
                yaxis="y3"
            ))
            fig_dual.update_layout(
                paper_bgcolor="#1e1e2e", plot_bgcolor="#1e1e2e",
                font=dict(color="#e0e0e0"),
                margin=dict(t=50, b=60, l=40, r=80),
                title="Ventas mensuales: ARS vs USD vs Tipo de cambio",
                xaxis  =dict(gridcolor="#2a2a3e", linecolor="#2a2a3e"),
                yaxis  =dict(title=dict(text="ARS",  font=dict(color="#4f8ef7")), gridcolor="#2a2a3e"),
                yaxis2 =dict(title=dict(text="USD",  font=dict(color="#f7c948")),
                             overlaying="y", side="right", gridcolor="rgba(0,0,0,0)"),
                yaxis3 =dict(title=dict(text="$/USD", font=dict(color="#e05c5c")),
                             overlaying="y", side="right", anchor="free",
                             position=0.97, gridcolor="rgba(0,0,0,0)"),
                legend=dict(orientation="h", y=-0.2),
                hovermode="x unified",
            )
            st.plotly_chart(fig_dual, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            # Top modelos en USD
            top_usd = (ventas_pos.groupby("Modelo")["Total_USD"]
                       .sum().sort_values(ascending=False).head(12).reset_index())
            fig_um = px.bar(top_usd, x="Total_USD", y="Modelo", orientation="h",
                            title="Top 12 Modelos por USD vendido",
                            color="Total_USD", color_continuous_scale="YlOrBr")
            fig_um.update_layout(**PLOTLY_THEME, showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig_um, use_container_width=True)

        with c2:
            # Evolución del tipo de cambio
            dolar_df = dolar_serie.reset_index()
            dolar_df.columns = ["Fecha", "Dólar"]
            dolar_df = dolar_df[dolar_df["Fecha"] >= pd.Timestamp("2024-01-01")]
            fig_tc = px.area(dolar_df, x="Fecha", y="Dólar",
                             title="Evolución del tipo de cambio (desde 2024)",
                             color_discrete_sequence=["#e05c5c"])
            fig_tc.update_layout(**PLOTLY_THEME)
            st.plotly_chart(fig_tc, use_container_width=True)

        # Tabla: ventas por cliente en ARS y USD
        st.subheader("Top 15 Clientes — ARS y USD")
        cli_usd = (ventas_pos.groupby("Cliente")
                   .agg(Total_ARS=("Total","sum"), Total_USD=("Total_USD","sum"),
                        Dolar_Prom=("dolar_dia","mean"))
                   .sort_values("Total_USD", ascending=False).head(15).reset_index())
        cli_usd["Total_ARS"]   = cli_usd["Total_ARS"].map("${:,.0f}".format)
        cli_usd["Total_USD"]   = cli_usd["Total_USD"].map("U$D {:,.0f}".format)
        cli_usd["Dolar_Prom"]  = cli_usd["Dolar_Prom"].map("${:,.0f}".format)
        cli_usd.columns        = ["Cliente","Ventas ARS","Ventas USD","TC Promedio"]
        st.dataframe(cli_usd, use_container_width=True, hide_index=True)

    # ────────────────────────────── TAB 3: DEUDA
    with tab3:
        c1, c2 = st.columns(2)

        with c1:
            aging = pd.DataFrame({
                "Período": ["0-30 días", "31-60 días", "61-90 días", "+90 días"],
                "Monto":   [deuda["SAL30"].sum(), deuda["SAL60"].sum(),
                            deuda["SALMAY60"].sum(), deuda["SALMAY90"].sum()],
                "Color":   ["#4CAF50","#FFC107","#FF9800","#F44336"],
            })
            fig4 = px.bar(aging, x="Período", y="Monto",
                          title="Pirámide de Antigüedad de Deuda",
                          color="Período",
                          color_discrete_sequence=aging["Color"].tolist())
            fig4.update_layout(**PLOTLY_THEME, showlegend=False)
            st.plotly_chart(fig4, use_container_width=True)

        with c2:
            top_d = deuda.nlargest(10, "TOTCTA").copy()
            top_d["nombre_corto"] = top_d["VTMCLH_NOMBRE"].str[:22]
            fig5 = go.Figure()
            fig5.add_trace(go.Bar(name="Deuda total",
                                  x=top_d["nombre_corto"], y=top_d["TOTCTA"],
                                  marker_color="#EF5350"))
            fig5.add_trace(go.Bar(name="Límite de crédito",
                                  x=top_d["nombre_corto"], y=top_d["LIMCRED"],
                                  marker_color="#42A5F5"))
            fig5.update_layout(**PLOTLY_THEME,
                               title="Top 10 Deudores vs Límite",
                               barmode="group", xaxis_tickangle=-40)
            st.plotly_chart(fig5, use_container_width=True)

        st.subheader("Detalle completo de deuda")
        dd = deuda[["VTMCLH_NOMBRE","SAL30","SAL60","SALMAY60","SALMAY90","TOTCTA","LIMCRED"]].copy()
        dd.columns = ["Cliente","0-30d","31-60d","61-90d","+90d","Total","Límite"]
        dd = dd.sort_values("Total", ascending=False)
        fmt = {c: "${:,.0f}" for c in ["0-30d","31-60d","61-90d","+90d","Total","Límite"]}
        st.dataframe(dd.style.format(fmt), use_container_width=True, hide_index=True)

    # ────────────────────────────── TAB 4: STOCK
    with tab4:
        stock_pos = stock[stock["DISPONIBLE"] > 0].copy()
        c1, c2 = st.columns(2)

        with c1:
            top_st = stock_pos.nlargest(15, "DISPONIBLE").copy()
            top_st["Desc"] = top_st["STMPDH_DESCRP"].str[:38]
            fig6 = px.bar(top_st, x="DISPONIBLE", y="Desc", orientation="h",
                          title="Top 15 Productos con Mayor Stock",
                          color="DISPONIBLE", color_continuous_scale="Greens")
            fig6.update_layout(**PLOTLY_THEME, showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig6, use_container_width=True)

        with c2:
            por_cat = stock_pos.groupby("STTTPH_DESCRP")["DISPONIBLE"].sum().reset_index()
            por_cat.columns = ["Categoría","Stock"]
            fig7 = px.pie(por_cat, values="Stock", names="Categoría",
                          title="Stock por Categoría", hole=0.45)
            fig7.update_layout(**PLOTLY_THEME)
            st.plotly_chart(fig7, use_container_width=True)

        bajo = stock_pos[stock_pos["DISPONIBLE"] < 50].sort_values("DISPONIBLE")
        if not bajo.empty:
            st.warning(f"⚠️ {len(bajo)} productos con stock bajo (< 50 unidades)")
            bb = bajo[["STMPDH_ARTCOD","STMPDH_DESCRP","DISPONIBLE"]].copy()
            bb.columns = ["Código","Descripción","Stock disponible"]
            st.dataframe(bb, use_container_width=True, hide_index=True)
        else:
            st.success("✅ Todos los productos tienen stock suficiente (≥ 50 u.)")

    # ────────────────────────────── TAB 5: PENDIENTES
    with tab5:
        c1, c2 = st.columns(2)

        with c1:
            top_pend = (pendientes_pos.groupby("VTMCLH_NOMBRE")["Import"]
                        .sum().sort_values(ascending=False).head(12).reset_index())
            top_pend["nombre_corto"] = top_pend["VTMCLH_NOMBRE"].str[:28]
            fig8 = px.bar(top_pend, x="Import", y="nombre_corto", orientation="h",
                          title="Top 12 Clientes con Mayor Pendiente ($)",
                          color="Import", color_continuous_scale="Oranges")
            fig8.update_layout(**PLOTLY_THEME, showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig8, use_container_width=True)

        with c2:
            top_art = (pendientes_pos.groupby("STMPDH_DESCRP")["CANTID"]
                       .sum().sort_values(ascending=False).head(12).reset_index())
            top_art["Desc"] = top_art["STMPDH_DESCRP"].str[:35]
            fig9 = px.bar(top_art, x="CANTID", y="Desc", orientation="h",
                          title="Top 12 Artículos Pendientes (u.)",
                          color="CANTID", color_continuous_scale="Purples")
            fig9.update_layout(**PLOTLY_THEME, showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig9, use_container_width=True)

        st.subheader("Detalle de pendientes")
        pp = pendientes_pos[["VTMCLH_NOMBRE","STMPDH_DESCRP","CANTID",
                              "Import","FCRMVI_FCHENT"]].copy()
        pp.columns = ["Cliente","Artículo","Cantidad","Importe","Fecha entrega"]
        pp = pp.sort_values("Importe", ascending=False)
        pp["Importe"] = pp["Importe"].map("${:,.0f}".format)
        st.dataframe(pp, use_container_width=True, hide_index=True)

    # ────────────────────────────── TAB 6: GASTOS
    with tab6:
        gastos_pos = gastos[gastos["SALDO"] > 0].copy()
        c1, c2 = st.columns(2)

        with c1:
            gm = (gastos_pos.groupby(gastos_pos["W_FCHMOV"].dt.to_period("M"))["SALDO"]
                  .sum().reset_index())
            gm["W_FCHMOV"] = gm["W_FCHMOV"].astype(str)
            fig10 = px.bar(gm, x="W_FCHMOV", y="SALDO",
                           title="Gastos Mensuales",
                           color="SALDO", color_continuous_scale="Reds")
            fig10.update_layout(**PLOTLY_THEME, coloraxis_showscale=False,
                                xaxis_tickangle=-40)
            st.plotly_chart(fig10, use_container_width=True)

        with c2:
            top_prov = (gastos_pos.groupby("PVMPRH_NOMBRE")["SALDO"]
                        .sum().sort_values(ascending=False).head(10).reset_index())
            top_prov.columns = ["Proveedor","Total"]
            top_prov["Proveedor"] = top_prov["Proveedor"].str[:25]
            fig11 = px.bar(top_prov, x="Total", y="Proveedor", orientation="h",
                           title="Top 10 Proveedores por Gasto",
                           color="Total", color_continuous_scale="Oranges")
            fig11.update_layout(**PLOTLY_THEME, showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig11, use_container_width=True)

        # Por concepto
        por_concepto = (gastos_pos.groupby("CGMPCH_DESCRP")["SALDO"]
                        .sum().sort_values(ascending=False).reset_index())
        por_concepto.columns = ["Concepto","Total"]
        fig12 = px.pie(por_concepto, values="Total", names="Concepto",
                       title="Gastos por Concepto", hole=0.45)
        fig12.update_layout(**PLOTLY_THEME)
        st.plotly_chart(fig12, use_container_width=True)


dashboard()

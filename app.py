"""
app.py — Interfaz corporativa del Agente ARIA.

Diseño enterprise: sin emojis, tipografia Inter, paleta azul corporativa oscura.
Ejecutar: streamlit run app.py
"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Debe ser el primer comando Streamlit del modulo
st.set_page_config(
    page_title="ARIA — Inventory Intelligence System",
    page_icon="A",
    layout="wide",
    initial_sidebar_state="expanded"
)

from config import BD_PATH, PDF_DIR, MODELO_LLM
from agent_core import crear_agente, ejecutar_react


# ─── CSS CORPORATIVO ──────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Ocultar menu y pie de pagina unicamente ── */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* ── BASE: 15px minimo, alto contraste ── */
html, body { font-size: 15px; }
.stApp {
    background-color: #0d0d14;
    color: #f0f0f5;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
/* Garantizar minimo 15px en todos los textos nativos de Streamlit */
p, li { font-size: 15px !important; color: #e5e7eb; line-height: 1.7; }
span  { color: inherit; }
label { font-size: 14px !important; color: #d1d5db !important; }

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
    background-color: #111118;
    border-right: 1px solid #2d2d3a;
}
[data-testid="stSidebar"] > div:first-child { padding: 28px 20px 20px; }
/* Todos los textos del sidebar con buen contraste */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div { color: #d1d5db; }

/* ── MÉTRICAS KPI ── */
[data-testid="stMetric"] {
    background: #1a1a26;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 16px 18px;
    transition: border-color 0.2s;
}
[data-testid="stMetric"]:hover { border-color: #3b82f6; }
[data-testid="stMetricLabel"] p {
    font-size: 11px !important;
    font-weight: 600 !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
    color: #9ca3af !important;
}
[data-testid="stMetricValue"] {
    font-size: 30px !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
    color: #ffffff !important;
}

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent;
    border-bottom: 1px solid #2d2d3a;
    gap: 0; padding: 0;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    color: #9ca3af;
    font-size: 15px;
    font-weight: 500;
    padding: 12px 24px 11px;
    transition: color 0.15s, border-color 0.15s;
}
.stTabs [aria-selected="true"] {
    color: #ffffff !important;
    border-bottom: 2px solid #3b82f6 !important;
    font-weight: 600 !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #e5e7eb !important;
    background: rgba(59,130,246,0.06) !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 24px; }

/* ── BOTONES ── */
.stButton > button {
    background: #1e293b;
    border: 1px solid #374151;
    border-radius: 6px;
    color: #e5e7eb;
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    font-weight: 500;
    height: 36px;
    padding: 0 18px;
    transition: all 0.15s;
}
.stButton > button:hover {
    background: #334155;
    border-color: #6b7280;
    color: #ffffff;
}

/* ── CHAT INPUT ── */
[data-testid="stChatInput"] {
    background: #111118;
    border: 1px solid #374151;
    border-radius: 8px;
}
[data-testid="stChatInput"] textarea {
    color: #f0f0f5 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 15px !important;
    background: transparent !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important;
}

/* ── MENSAJES DE CHAT ── */
[data-testid="stChatMessage"] {
    background: #161b22;
    border: 1px solid #2d2d3a;
    border-radius: 8px;
    margin-bottom: 10px;
}
[data-testid="stChatMessageContent"] p {
    font-size: 15px !important;
    line-height: 1.7 !important;
    color: #e5e7eb !important;
}
[data-testid="chatAvatarIcon-user"],
[data-testid="chatAvatarIcon-assistant"] { display: none; }

/* ── EXPANDERS ── */
[data-testid="stExpander"] {
    background: #0f0f1a;
    border: 1px solid #2d2d3a !important;
    border-radius: 6px;
}
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary {
    font-size: 13px !important;
    color: #9ca3af !important;
    font-weight: 500;
}
[data-testid="stExpander"] summary:hover p { color: #e5e7eb !important; }

/* ── DATAFRAME (dark via config.toml, aqui solo el wrapper) ── */
[data-testid="stDataFrame"] {
    border: 1px solid #2d2d3a;
    border-radius: 8px;
    overflow: hidden;
}

/* ── DIVIDER ── */
hr { border: none; border-top: 1px solid #2d2d3a; margin: 16px 0; }

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0d0d14; }
::-webkit-scrollbar-thumb { background: #374151; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #6b7280; }

/* ── CLASES REUTILIZABLES ── */
.brand-name {
    font-size: 22px; font-weight: 800;
    letter-spacing: -0.04em; color: #ffffff; line-height: 1;
}
.brand-sub {
    font-size: 12px; color: #6b7280;
    margin-top: 4px; letter-spacing: 0.02em;
}
.sect-label {
    font-size: 11px; font-weight: 700;
    letter-spacing: 0.1em; text-transform: uppercase;
    color: #6b7280; margin-bottom: 10px;
    padding-bottom: 6px; border-bottom: 1px solid #2d2d3a;
}
.page-title {
    font-size: 18px; font-weight: 600;
    color: #ffffff; letter-spacing: -0.01em;
}
.page-sub {
    font-size: 14px; color: #9ca3af; margin-top: 2px;
}
.status-dot {
    display: inline-block; width: 8px; height: 8px;
    border-radius: 50%; margin-right: 7px;
    vertical-align: middle; position: relative; top: -1px;
}
.dot-online  { background: #22c55e; box-shadow: 0 0 5px rgba(34,197,94,0.6); }
.dot-offline { background: #ef4444; }

/* Trace de herramienta */
.tool-trace {
    background: #0d0d14;
    border: 1px solid #2d2d3a;
    border-left: 3px solid #3b82f6;
    border-radius: 4px;
    padding: 9px 13px; margin: 4px 0;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 13px;
    display: flex; justify-content: space-between; align-items: center;
}
.tool-trace .tn  { color: #60a5fa; font-weight: 500; }
.tool-trace .arg { color: #9ca3af; font-size: 12px; margin-left: 8px; }
.tool-trace .lat { color: #4ade80; font-size: 12px; }
.tool-trace .lat.slow { color: #f87171; }

/* Info box */
.info-box {
    background: rgba(59,130,246,0.07);
    border: 1px solid rgba(59,130,246,0.25);
    border-radius: 6px; padding: 12px 15px;
    font-size: 14px; color: #d1d5db; line-height: 1.65;
}
.info-box code {
    background: rgba(59,130,246,0.12); border-radius: 3px;
    padding: 1px 6px; color: #93c5fd;
    font-family: 'JetBrains Mono', monospace; font-size: 12px;
}

/* Download button */
.stDownloadButton > button {
    background: #1e293b; border: 1px solid #374151;
    border-radius: 6px; color: #e5e7eb;
    font-size: 14px; font-weight: 500;
    height: 36px; padding: 0 18px; width: 100%;
}
.stDownloadButton > button:hover {
    background: #2563eb; border-color: #2563eb; color: #fff;
}

/* Alertas */
[data-testid="stAlert"] { border-radius: 6px; }
[data-testid="stAlert"] p { font-size: 14px !important; }

/* ── BARRA DE IDENTIDAD DEL SISTEMA ── */
.sys-bar {
    background: #0d0d14;
    border: 1px solid #2d2d3a;
    border-radius: 6px;
    padding: 8px 12px;
    margin-bottom: 14px;
}
.sys-bar-row {
    display: flex; align-items: center;
    justify-content: space-between;
    font-size: 11px; color: #6b7280;
    margin-bottom: 4px;
}
.sys-bar-row:last-child { margin-bottom: 0; }
.sys-bar-val {
    color: #9ca3af; font-weight: 500;
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
}
.badge-env {
    display: inline-block;
    background: rgba(59,130,246,0.15);
    border: 1px solid rgba(59,130,246,0.3);
    color: #60a5fa;
    border-radius: 4px;
    padding: 1px 7px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
}
</style>
""", unsafe_allow_html=True)


# ─── AUTENTICACIÓN PIN (RA03) ─────────────────────────────────────────────────

PIN_ACCESO = "1234"   # PIN de demostración — cámbialo en producción

if not st.session_state.get("autenticado", False):
    _c1, _cmid, _c3 = st.columns([1, 1.4, 1])
    with _cmid:
        st.markdown(
            '<div style="padding:52px 0 20px;text-align:center;">'
            '<div style="font-size:36px;font-weight:800;letter-spacing:-0.05em;color:#fff;">ARIA</div>'
            '<div style="font-size:11px;color:#6b7280;margin-top:6px;letter-spacing:0.1em;'
            'text-transform:uppercase;">Inventory Intelligence System</div>'
            '</div>',
            unsafe_allow_html=True
        )
        st.markdown(
            '<div style="background:#1a1a26;border:1px solid #374151;'
            'border-radius:10px;padding:32px 28px;">'
            '<p style="font-size:13px;color:#9ca3af;margin:0 0 8px;font-weight:500;">'
            'PIN de acceso</p>',
            unsafe_allow_html=True
        )
        _pin_entrada = st.text_input(
            "PIN",
            type="password",
            placeholder="\u2022 \u2022 \u2022 \u2022",
            max_chars=4,
            key="pin_field",
            label_visibility="collapsed"
        )
        if st.button("Ingresar al sistema", use_container_width=True, key="btn_acceder"):
            if _pin_entrada == PIN_ACCESO:
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("PIN incorrecto. Inténtalo de nuevo.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown(
            '<div style="text-align:center;font-size:11px;color:#4b5563;margin-top:14px;">'
            'Acceso restringido \u00b7 Información comercial protegida</div>',
            unsafe_allow_html=True
        )
    st.stop()


# ─── INICIALIZACIÓN DE ESTADO ─────────────────────────────────────────────────

def _init():
    if "agente_ok" not in st.session_state:
        try:
            st.session_state.chat      = crear_agente()
            st.session_state.agente_ok = True
        except Exception as e:
            st.session_state.agente_ok  = False
            st.session_state.err_agente = str(e)
    if "mensajes" not in st.session_state:
        st.session_state.mensajes = []

_init()


# ─── CONSULTAS A SQLITE ────────────────────────────────────────────────────────

@st.cache_data(ttl=4)
def _inventario() -> pd.DataFrame:
    try:
        con = sqlite3.connect(str(BD_PATH))
        df  = pd.read_sql_query(
            "SELECT * FROM productos ORDER BY cantidad_actual ASC", con
        )
        con.close()
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=4)
def _historial() -> pd.DataFrame:
    try:
        con = sqlite3.connect(str(BD_PATH))
        df  = pd.read_sql_query(
            """SELECT timestamp, herramienta, latencia_ms, resultado
               FROM historial_acciones ORDER BY id DESC LIMIT 60""",
            con
        )
        con.close()
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=4)
def _ordenes() -> pd.DataFrame:
    try:
        con = sqlite3.connect(str(BD_PATH))
        df  = pd.read_sql_query(
            "SELECT * FROM ordenes_compra ORDER BY id DESC", con
        )
        con.close()
        return df
    except Exception:
        return pd.DataFrame()


def _kpi() -> dict:
    df = _inventario()
    if df.empty:
        return {"total": 0, "criticos": 0, "bajo_min": 0, "ok": 0}
    return {
        "total":    len(df),
        "criticos": int((df["estado"] == "Crítico").sum()),
        "bajo_min": int((df["cantidad_actual"] <= df["cantidad_minima"]).sum()),
        "ok":       int((df["estado"] == "Disponible").sum()),
    }


def _limpiar_cache():
    _inventario.clear()
    _historial.clear()
    _ordenes.clear()


def _cargar_archivo(archivo) -> dict:
    """
    Procesa un archivo Excel o CSV y carga los productos en inventario.db.
    Mapeo de columnas flexible: acepta nombres en español e inglés.
    Reemplaza todos los productos existentes por los del archivo subido.
    """
    try:
        if archivo.name.lower().endswith(".csv"):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo, engine="openpyxl")

        def _norm_col(s: str) -> str:
            for src, dst in [("-","_"),(" ","_"),("\u00e1","a"),("\u00e9","e"),("\u00ed","i"),
                             ("\u00f3","o"),("\u00fa","u"),("\u00f1","n")]:
                s = s.replace(src, dst)
            return s.strip().lower()

        df.columns = [_norm_col(c) for c in df.columns]

        CAMPO_COLS = {
            "nombre":           ["nombre","producto","name","item","descripcion","articulo"],
            "categoria":        ["categoria","category","rubro","tipo","seccion","departamento"],
            "cantidad_actual":  ["cantidad_actual","stock","cantidad","existencia",
                                 "stock_actual","disponible"],
            "cantidad_minima":  ["cantidad_minima","stock_minimo","minimo","min",
                                 "min_stock","stock_min"],
            "precio_unitario":  ["precio_unitario","precio","price","costo","valor",
                                 "pu","precio_unit"],
            "ventas_semanales": ["ventas_semanales","ventas","rotacion","sales",
                                 "v_sem","ventas_sem"],
        }
        col_map = {}
        for campo, opciones in CAMPO_COLS.items():
            for op in opciones:
                if op in df.columns:
                    col_map[campo] = op
                    break

        if "nombre" not in col_map:
            return {"ok": False, "error":
                    "No se encontró columna 'nombre' o 'producto' en el archivo. "
                    "Revisa los encabezados e inténtalo de nuevo."}

        def _safe_str(row, campo, default="General"):
            k = col_map.get(campo)
            v = str(row[k]).strip() if k else ""
            return v if v.lower() not in ("nan","none","") else default

        def _safe_int(row, campo, default=0):
            k = col_map.get(campo)
            try: return int(float(row[k])) if k else default
            except: return default

        def _safe_float(row, campo, default=0.0):
            k = col_map.get(campo)
            try: return float(row[k]) if k else default
            except: return default

        productos = []
        for _, row in df.iterrows():
            nombre = str(row[col_map["nombre"]]).strip()
            if not nombre or nombre.lower() in ("nan","none",""):
                continue
            productos.append((
                nombre,
                _safe_str(row, "categoria"),
                _safe_int(row, "cantidad_actual"),
                _safe_int(row, "cantidad_minima", 10),
                _safe_float(row, "precio_unitario"),
                _safe_float(row, "ventas_semanales"),
                "Disponible"
            ))

        if not productos:
            return {"ok": False, "error": "El archivo no contiene filas de productos válidas."}

        con = sqlite3.connect(str(BD_PATH))
        cur = con.cursor()
        # Reemplazar inventario con los datos del archivo
        cur.execute("DELETE FROM productos")
        cur.executemany(
            """INSERT INTO productos
               (nombre, categoria, cantidad_actual, cantidad_minima,
                precio_unitario, ventas_semanales, estado)
               VALUES (?,?,?,?,?,?,?)""",
            productos
        )
        # Limpiar historial y órdenes de la sesión anterior (demo u otro negocio)
        cur.execute("DELETE FROM historial_acciones")
        cur.execute("DELETE FROM ordenes_compra")
        con.commit()
        con.close()

        # Eliminar PDFs generados en sesiones anteriores
        for _pdf in PDF_DIR.glob("*.pdf"):
            _pdf.unlink(missing_ok=True)

        return {"ok": True, "productos": len(productos),
                "columnas_mapeadas": list(col_map.keys())}

    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── SIDEBAR ──────────────────────────────────────────────────────────────────

with st.sidebar:

    st.markdown(
        '<div class="brand-name">ARIA</div>'
        '<div class="brand-sub">Inventory Intelligence System · v1.0</div>',
        unsafe_allow_html=True
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # Barra de identidad del sistema
    ultima_act = datetime.now().strftime("%H:%M:%S")
    st.markdown(
        f'<div class="sys-bar">'
        f'<div class="sys-bar-row">'
        f'  <span>Modelo LLM</span>'
        f'  <span class="sys-bar-val">{MODELO_LLM}</span>'
        f'</div>'
        f'<div class="sys-bar-row">'
        f'  <span>Entorno</span>'
        f'  <span class="badge-env">DEMO</span>'
        f'</div>'
        f'<div class="sys-bar-row">'
        f'  <span>Actualizado</span>'
        f'  <span class="sys-bar-val">{ultima_act}</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    # Estado del agente
    st.markdown('<div class="sect-label">Estado del Sistema</div>', unsafe_allow_html=True)
    if st.session_state.get("agente_ok"):
        st.markdown(
            '<div style="font-size:14px;font-weight:500;color:#22c55e;">'
            '<span class="status-dot dot-online"></span>Agente operativo</div>',
            unsafe_allow_html=True
        )
    else:
        err = st.session_state.get("err_agente", "Error de configuración")
        st.markdown(
            f'<div style="font-size:14px;font-weight:500;color:#ef4444;">'
            f'<span class="status-dot dot-offline"></span>Sin conexión</div>'
            f'<div style="font-size:12px;color:#9ca3af;margin-top:6px;">{err}</div>',
            unsafe_allow_html=True
        )
        st.markdown(
            '<div class="info-box" style="margin-top:10px;">'
            'Crea el archivo <code>.env</code> con tu clave:<br>'
            '<code>GEMINI_API_KEY=...</code></div>',
            unsafe_allow_html=True
        )

    st.markdown("<hr>", unsafe_allow_html=True)

    # KPIs
    st.markdown('<div class="sect-label">Inventario</div>', unsafe_allow_html=True)
    kpi = _kpi()
    c1, c2 = st.columns(2)
    c1.metric("Activos",    kpi["total"])
    c2.metric("Críticos",   kpi["criticos"])
    c1.metric("Bajo Mín.",  kpi["bajo_min"])
    c2.metric("Operativos", kpi["ok"])

    st.markdown("<hr>", unsafe_allow_html=True)

    # Acciones
    st.markdown('<div class="sect-label">Acciones</div>', unsafe_allow_html=True)
    if st.button("Nueva sesión de chat", use_container_width=True):
        st.session_state.mensajes = []
        if st.session_state.get("agente_ok"):
            st.session_state.chat = crear_agente()
        st.rerun()
    if st.button("Actualizar datos", use_container_width=True):
        _limpiar_cache()
        st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    # ─ Carga de datos del negocio (RNF04 / ingesta Excel) ─────────────────
    st.markdown('<div class="sect-label">Datos del Negocio</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="info-box" style="margin-bottom:10px;font-size:12px;">'
        'Sube tu inventario en <code>.xlsx</code> o <code>.csv</code>.<br>'
        'Columnas reconocidas: <code>nombre</code>, <code>categoria</code>, '
        '<code>stock</code>, <code>precio</code>, <code>ventas</code>.'
        '</div>',
        unsafe_allow_html=True
    )
    _archivo = st.file_uploader(
        "Cargar inventario",
        type=["xlsx", "csv"],
        key="fu_inventario",
        label_visibility="collapsed"
    )
    if _archivo is not None:
        if st.session_state.get("_archivo_cargado") != _archivo.name:
            with st.spinner("Importando datos..."):
                _res = _cargar_archivo(_archivo)
            if _res["ok"]:
                st.session_state["_archivo_cargado"] = _archivo.name
                st.session_state["_import_msg"] = (
                    f"{_res['productos']} productos importados — "
                    f"{len(_res.get('columnas_mapeadas', []))} columnas mapeadas."
                )
                # Reset completo de la sesión anterior
                _limpiar_cache()
                st.session_state.mensajes = []          # limpiar chat
                if st.session_state.get("agente_ok"):   # reiniciar agente
                    st.session_state.chat = crear_agente()
                st.rerun()
            else:
                st.error(_res["error"])
    if st.session_state.get("_import_msg"):
        st.success(st.session_state["_import_msg"])

    st.markdown("<hr>", unsafe_allow_html=True)

    with st.expander("Guía de pruebas"):
        st.markdown(
            '<div class="info-box">'
            '<b>Prueba 1 — Análisis</b><br>'
            'Genera un reporte de lo que se va a agotar pronto y emite la orden al proveedor más rápido.<br><br>'
            '<b>Prueba 2 — Self-Healing</b><br>'
            'Audita la base de datos antes de comprar.<br><br>'
            '<b>Prueba 3 — Presupuesto</b><br>'
            'Reabastece los productos faltantes, presupuesto máximo: $100.'
            '</div>',
            unsafe_allow_html=True
        )


# ─── TABS PRINCIPALES ─────────────────────────────────────────────────────────

tab_consola, tab_visor, tab_auditoria, tab_ordenes, tab_arq = st.tabs([
    "Consola de Operaciones",
    "Visor Transaccional",
    "Auditoría del Sistema",
    "Gestión de Órdenes",
    "Arquitectura del Sistema",
])


# ══════════════════════════════════════════════════════════════
# TAB 1 — CONSOLA DE OPERACIONES
# ══════════════════════════════════════════════════════════════
with tab_consola:
    col_h, col_i = st.columns([4, 1])
    col_h.markdown(
        '<div class="page-title">Consola de Operaciones</div>'
        '<div class="page-sub">Interacción directa con el agente ARIA vía lenguaje natural</div>',
        unsafe_allow_html=True
    )
    if col_i.button("Limpiar", key="clr_chat"):
        st.session_state.mensajes = []
        if st.session_state.get("agente_ok"):
            st.session_state.chat = crear_agente()
        st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    # Contenedor con scroll para el historial de mensajes
    chat_container = st.container(height=550)
    
    with chat_container:
        if not st.session_state.mensajes:
            st.markdown(
                '<div class="info-box" style="text-align:center;padding:28px 24px;">'
                '<div style="font-size:15px;font-weight:600;color:#d1d5db;margin-bottom:6px;">'
                'Sistema listo</div>'
                '<div style="font-size:14px;color:#9ca3af;">'
                'Escribe una instrucción en el campo inferior para iniciar una sesión con ARIA.'
                '</div></div>',
                unsafe_allow_html=True
            )

        for msg in st.session_state.mensajes:
            rol_st = "user" if msg["rol"] == "usuario" else "assistant"
            with st.chat_message(rol_st):
                remitente = "OPERADOR" if rol_st == "user" else "ARIA"
                color_rem = "#9ca3af"  if rol_st == "user" else "#3b82f6"
                st.markdown(
                    f'<div style="font-size:11px;font-weight:700;letter-spacing:0.08em;'
                    f'text-transform:uppercase;color:{color_rem};margin-bottom:5px;">'
                    f'{remitente}</div>',
                    unsafe_allow_html=True
                )
                st.markdown(msg["contenido"])

                pasos = msg.get("pasos", [])
                if pasos:
                    with st.expander(f"Traza de ejecución — {len(pasos)} herramienta(s) invocada(s)"):
                        for paso in pasos:
                            lat     = paso["latencia_ms"]
                            cls     = "slow" if lat > 1500 else ""
                            args    = paso.get("args", {})
                            args_s  = ", ".join(f"{k}={v}" for k, v in args.items()) if args else "—"
                            st.markdown(
                                f'<div class="tool-trace">'
                                f'<span><span class="tn">{paso["herramienta"]}</span>'
                                f'<span class="arg">({args_s})</span></span>'
                                f'<span class="lat {cls}">{lat:.0f} ms</span>'
                                f'</div>',
                                unsafe_allow_html=True
                            )

    # Campo de entrada fijo al fondo del tab
    if prompt := st.chat_input("Instrucción para ARIA..."):
        if not st.session_state.get("agente_ok"):
            st.error("El agente no está disponible. Configura la API Key en el archivo .env")
        else:
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(
                        '<div style="font-size:11px;font-weight:700;letter-spacing:0.08em;'
                        'text-transform:uppercase;color:#9ca3af;margin-bottom:5px;">OPERADOR</div>',
                        unsafe_allow_html=True
                    )
                    st.markdown(prompt)
                st.session_state.mensajes.append({"rol": "usuario", "contenido": prompt})

                with st.chat_message("assistant"):
                    st.markdown(
                        '<div style="font-size:11px;font-weight:700;letter-spacing:0.08em;'
                        'text-transform:uppercase;color:#3b82f6;margin-bottom:5px;">ARIA</div>',
                        unsafe_allow_html=True
                    )
                    with st.status("Procesando instrucción...", expanded=True) as estado_ui:
                        def _cb(paso: dict):
                            estado_ui.update(label=f"Ejecutando {paso['herramienta']}...")

                        respuesta, pasos, nuevo_chat = ejecutar_react(
                            st.session_state.chat, prompt, callback=_cb
                        )
                        # Si hubo fallback de modelo, actualizar la sesión
                        if nuevo_chat is not None:
                            st.session_state.chat = nuevo_chat
                        estado_ui.update(label="Ejecución completada", state="complete")

                    st.markdown(respuesta)

                    if pasos:
                        with st.expander(f"Traza de ejecución — {len(pasos)} herramienta(s) invocada(s)"):
                            for paso in pasos:
                                lat    = paso["latencia_ms"]
                                cls    = "slow" if lat > 1500 else ""
                                args   = paso.get("args", {})
                                args_s = ", ".join(f"{k}={v}" for k, v in args.items()) if args else "—"
                                st.markdown(
                                    f'<div class="tool-trace">'
                                    f'<span><span class="tn">{paso["herramienta"]}</span>'
                                    f'<span class="arg">({args_s})</span></span>'
                                    f'<span class="lat {cls}">{lat:.0f} ms</span>'
                                    f'</div>',
                                    unsafe_allow_html=True
                                )

                st.session_state.mensajes.append({
                    "rol":       "agente",
                    "contenido": respuesta,
                    "pasos":     pasos
                })
            _limpiar_cache()


def _render_graficos_inventario(df: pd.DataFrame):
    """
    Genera gráficos analíticos detallados, interactivos y de alta precisión para cualquier tabla de inventario.
    Incorpora Plotly con paleta corporativa oscura, etiquetas con valores exactos, tooltips completos y
    dimensionamiento dinámico para evitar truncamiento de nombres.
    """
    if df.empty:
        return

    st.markdown('<div class="sect-label">Diagnóstico Visual de Inventario</div>', unsafe_allow_html=True)

    # Sub-pestañas analíticas
    sub_tab1, sub_tab2, sub_tab3 = st.tabs([
        "📊 Balance de Stock vs. Mínimo (Detalle por Producto)",
        "⏳ Proyección de Cobertura y Agotamiento",
        "🥧 Distribución por Categorías y Capital"
    ])

    # Preparar datos base sanitizados
    df_plot = df.copy()
    df_plot["categoria"] = df_plot["categoria"].fillna("Sin Categoría")
    df_plot["cantidad_actual"] = pd.to_numeric(df_plot["cantidad_actual"], errors="coerce").fillna(0)
    df_plot["cantidad_minima"] = pd.to_numeric(df_plot["cantidad_minima"], errors="coerce").fillna(0)
    df_plot["precio_unitario"] = pd.to_numeric(df_plot["precio_unitario"], errors="coerce").fillna(0.0)
    df_plot["ventas_semanales"] = pd.to_numeric(df_plot["ventas_semanales"], errors="coerce").fillna(0.0)
    df_plot["deficit"] = df_plot["cantidad_minima"] - df_plot["cantidad_actual"]
    df_plot["valor_stock"] = df_plot["cantidad_actual"].apply(lambda x: max(0, x)) * df_plot["precio_unitario"]

    # ─────────────────────────────────────────────────────────────
    # SUBTAB 1: BALANCE DE STOCK VS MÍNIMO
    # ─────────────────────────────────────────────────────────────
    with sub_tab1:
        col_ctrl1, col_ctrl2 = st.columns([3, 2])
        criterio_orden = col_ctrl1.selectbox(
            "Criterio de ordenamiento:",
            [
                "Mayor déficit primero (Urgencia de reabastecimiento)",
                "Menor stock actual primero",
                "Alfabético por nombre de producto",
                "Orden original de la tabla"
            ],
            key="orden_chart_stock"
        )
        orientacion = col_ctrl2.radio(
            "Orientación de barras:",
            ["Horizontal (Recomendado)", "Vertical"],
            horizontal=True,
            key="orientacion_chart_stock"
        )

        df_sorted = df_plot.copy()
        if "Mayor déficit" in criterio_orden:
            df_sorted = df_sorted.sort_values(by="deficit", ascending=False)
        elif "Menor stock" in criterio_orden:
            df_sorted = df_sorted.sort_values(by="cantidad_actual", ascending=True)
        elif "Alfabético" in criterio_orden:
            df_sorted = df_sorted.sort_values(by="nombre", ascending=True)

        is_horiz = "Horizontal" in orientacion
        if is_horiz:
            # En Plotly horizontal, invertimos el dataframe para que el primer ítem se pinte arriba
            df_display = df_sorted.iloc[::-1]
        else:
            df_display = df_sorted

        # Colores por estado para Stock Actual
        colores_actual = []
        for _, row in df_display.iterrows():
            act = row["cantidad_actual"]
            mini = row["cantidad_minima"]
            if act <= 0:
                colores_actual.append("#ef4444")  # Rojo: Agotado / Anomalía negativa
            elif act < mini:
                colores_actual.append("#f59e0b")  # Ámbar: Déficit respecto al mínimo
            else:
                colores_actual.append("#10b981")  # Verde: Stock óptimo

        customdata_actual = []
        for idx, row in df_display.iterrows():
            diff = row["cantidad_actual"] - row["cantidad_minima"]
            diff_txt = f"+{diff:.0f} (Superávit)" if diff >= 0 else f"{diff:.0f} (Déficit)"
            customdata_actual.append([
                row["nombre"],
                row["id"],
                row["categoria"],
                row["cantidad_minima"],
                diff_txt,
                row["ventas_semanales"],
                row["precio_unitario"],
                row["valor_stock"],
                row["estado"]
            ])

        fig_balance = go.Figure()

        if is_horiz:
            # Trace Stock Actual (Horizontal)
            fig_balance.add_trace(go.Bar(
                y=df_display["nombre"],
                x=df_display["cantidad_actual"],
                name="Stock Actual",
                orientation="h",
                marker=dict(color=colores_actual),
                text=df_display["cantidad_actual"].apply(lambda v: f"{v:.0f}"),
                textposition="auto",
                textfont=dict(color="#ffffff", size=12, family="Inter, sans-serif"),
                customdata=customdata_actual,
                hovertemplate=(
                    "<b>%{customdata[0]}</b> (ID: %{customdata[1]})<br>"
                    "Categoría: %{customdata[2]}<br>"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━<br>"
                    "<b>Stock Actual:</b> %{x:.0f} un.<br>"
                    "<b>Stock Mínimo:</b> %{customdata[3]:.0f} un.<br>"
                    "<b>Balance:</b> %{customdata[4]}<br>"
                    "Ventas Semanales: %{customdata[5]:.1f} un./sem<br>"
                    "Precio Unitario: $%{customdata[6]:,.2f}<br>"
                    "Valor en Stock: $%{customdata[7]:,.2f}<br>"
                    "Estado: %{customdata[8]}"
                    "<extra></extra>"
                )
            ))
            # Trace Stock Mínimo (Horizontal)
            fig_balance.add_trace(go.Bar(
                y=df_display["nombre"],
                x=df_display["cantidad_minima"],
                name="Stock Mínimo Requerido",
                orientation="h",
                marker=dict(
                    color="rgba(148, 163, 184, 0.28)",
                    line=dict(color="#94a3b8", width=1.5)
                ),
                text=df_display["cantidad_minima"].apply(lambda v: f"{v:.0f}"),
                textposition="auto",
                textfont=dict(color="#cbd5e1", size=11, family="Inter, sans-serif"),
                hovertemplate="<b>%{y}</b><br>Stock Mínimo Requerido: %{x:.0f} un.<extra></extra>"
            ))
        else:
            # Trace Stock Actual (Vertical)
            fig_balance.add_trace(go.Bar(
                x=df_display["nombre"],
                y=df_display["cantidad_actual"],
                name="Stock Actual",
                marker=dict(color=colores_actual),
                text=df_display["cantidad_actual"].apply(lambda v: f"{v:.0f}"),
                textposition="auto",
                textfont=dict(color="#ffffff", size=12, family="Inter, sans-serif"),
                customdata=customdata_actual,
                hovertemplate=(
                    "<b>%{customdata[0]}</b> (ID: %{customdata[1]})<br>"
                    "Categoría: %{customdata[2]}<br>"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━<br>"
                    "<b>Stock Actual:</b> %{y:.0f} un.<br>"
                    "<b>Stock Mínimo:</b> %{customdata[3]:.0f} un.<br>"
                    "<b>Balance:</b> %{customdata[4]}<br>"
                    "Ventas Semanales: %{customdata[5]:.1f} un./sem<br>"
                    "Precio Unitario: $%{customdata[6]:,.2f}<br>"
                    "Valor en Stock: $%{customdata[7]:,.2f}<br>"
                    "Estado: %{customdata[8]}"
                    "<extra></extra>"
                )
            ))
            # Trace Stock Mínimo (Vertical)
            fig_balance.add_trace(go.Bar(
                x=df_display["nombre"],
                y=df_display["cantidad_minima"],
                name="Stock Mínimo Requerido",
                marker=dict(
                    color="rgba(148, 163, 184, 0.28)",
                    line=dict(color="#94a3b8", width=1.5)
                ),
                text=df_display["cantidad_minima"].apply(lambda v: f"{v:.0f}"),
                textposition="auto",
                textfont=dict(color="#cbd5e1", size=11, family="Inter, sans-serif"),
                hovertemplate="<b>%{x}</b><br>Stock Mínimo Requerido: %{y:.0f} un.<extra></extra>"
            ))

        num_items = len(df_display)
        calc_height = max(420, num_items * 38) if is_horiz else 460

        fig_balance.update_layout(
            barmode="group",
            height=calc_height,
            margin=dict(l=20, r=20, t=40, b=40),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(17, 17, 24, 0.6)",
            font=dict(family="Inter, -apple-system, sans-serif", color="#e5e7eb", size=12),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=12, color="#d1d5db"),
                bgcolor="rgba(17, 17, 24, 0.8)",
                bordercolor="#2d2d3a",
                borderwidth=1
            ),
            xaxis=dict(
                gridcolor="#27273a",
                zeroline=True,
                zerolinecolor="#6b7280",
                zerolinewidth=1.5,
                tickfont=dict(color="#9ca3af"),
                title="Unidades de Producto" if is_horiz else None
            ),
            yaxis=dict(
                gridcolor="#27273a",
                zeroline=True,
                zerolinecolor="#6b7280",
                zerolinewidth=1.5,
                tickfont=dict(color="#d1d5db"),
                tickangle=-30 if not is_horiz else 0,
                title="Unidades de Producto" if not is_horiz else None
            )
        )
        st.plotly_chart(fig_balance, use_container_width=True, config={"displayModeBar": True, "displaylogo": False})

        # Leyenda de interpretación de colores
        st.markdown(
            '<div style="display:flex;gap:20px;flex-wrap:wrap;padding:10px 14px;background:#14141e;'
            'border:1px solid #27273a;border-radius:8px;font-size:12px;color:#9ca3af;margin-top:-6px;">'
            '<span><span style="color:#ef4444;font-weight:700;">■</span> Rojo: Agotado o Stock Negativo</span>'
            '<span><span style="color:#f59e0b;font-weight:700;">■</span> Ámbar: Stock menor al mínimo requerido</span>'
            '<span><span style="color:#10b981;font-weight:700;">■</span> Verde: Stock suficiente o superior al mínimo</span>'
            '<span><span style="color:#94a3b8;font-weight:700;">□</span> Barra Gris: Umbral de Stock Mínimo</span>'
            '</div>',
            unsafe_allow_html=True
        )

    # ─────────────────────────────────────────────────────────────
    # SUBTAB 2: PROYECCIÓN DE COBERTURA Y DÍAS DE AGOTAMIENTO
    # ─────────────────────────────────────────────────────────────
    with sub_tab2:
        st.markdown(
            '<div style="font-size:13px;color:#9ca3af;margin-bottom:12px;">'
            'Estimación matemática exacta de los días de inventario restantes antes de ruptura de stock '
            '<code>(Stock Actual / Ventas Diarias)</code>. Umbrales ARIA: Crítico ≤ 6 días, Alerta ≤ 14 días.'
            '</div>',
            unsafe_allow_html=True
        )

        df_cob = df_plot.copy()
        dias_list = []
        colores_cob = []
        estados_cob = []

        for _, r in df_cob.iterrows():
            act = r["cantidad_actual"]
            vsem = r["ventas_semanales"]
            vdia = vsem / 7.0 if vsem > 0 else 0.0

            if act <= 0:
                dias = 0.0
                estado = "Agotado (0 días)"
                color = "#ef4444"
            elif vdia <= 0:
                dias = 999.0
                estado = "Sin rotación semanal"
                color = "#10b981"
            else:
                dias = round(act / vdia, 1)
                if dias <= 6.0:
                    estado = f"Crítico ({dias:.1f} días)"
                    color = "#ef4444"
                elif dias <= 14.0:
                    estado = f"Alerta ({dias:.1f} días)"
                    color = "#f59e0b"
                else:
                    estado = f"Seguro ({dias:.1f} días)"
                    color = "#10b981"

            dias_list.append(dias)
            colores_cob.append(color)
            estados_cob.append(estado)

        df_cob["dias_restantes"] = dias_list
        df_cob["color_cob"] = colores_cob
        df_cob["estado_cob"] = estados_cob

        # Ordenar de menor a mayor días (más urgente primero)
        df_cob_sorted = df_cob.sort_values(by="dias_restantes", ascending=True)
        # Invertir para que el más crítico aparezca arriba en la barra horizontal
        df_cob_display = df_cob_sorted.iloc[::-1]

        fig_cob = go.Figure()
        fig_cob.add_trace(go.Bar(
            y=df_cob_display["nombre"],
            x=df_cob_display["dias_restantes"].apply(lambda d: min(d, 35.0)),
            orientation="h",
            marker=dict(color=df_cob_display["color_cob"].tolist()),
            text=df_cob_display["dias_restantes"].apply(lambda d: f"{d:.1f} días" if d < 900 else "Sin ventas"),
            textposition="outside",
            textfont=dict(color="#f3f4f6", size=12, family="Inter, sans-serif"),
            customdata=df_cob_display[["id", "categoria", "cantidad_actual", "ventas_semanales", "estado_cob"]].values,
            hovertemplate=(
                "<b>%{y}</b> (ID: %{customdata[0]})<br>"
                "Categoría: %{customdata[1]}<br>"
                "━━━━━━━━━━━━━━━━━━━━━━━━━<br>"
                "<b>Stock Actual:</b> %{customdata[2]:.0f} un.<br>"
                "Ventas Semanales: %{customdata[3]:.1f} un./sem<br>"
                "<b>Tiempo de Cobertura:</b> %{customdata[4]}"
                "<extra></extra>"
            )
        ))

        # Líneas de referencia para 7 días y 14 días
        fig_cob.add_vline(x=7, line_width=1.5, line_dash="dash", line_color="#f59e0b",
                          annotation_text="Límite 7 días (Crítico)", annotation_font_color="#f59e0b",
                          annotation_position="top right")
        fig_cob.add_vline(x=14, line_width=1.5, line_dash="dash", line_color="#3b82f6",
                          annotation_text="Horizonte ARIA 14 días", annotation_font_color="#60a5fa",
                          annotation_position="top right")

        calc_height_cob = max(400, len(df_cob_display) * 36)
        fig_cob.update_layout(
            height=calc_height_cob,
            margin=dict(l=20, r=40, t=30, b=40),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(17, 17, 24, 0.6)",
            font=dict(family="Inter, -apple-system, sans-serif", color="#e5e7eb", size=12),
            xaxis=dict(
                title="Días Estimados de Cobertura",
                gridcolor="#27273a",
                zeroline=True,
                zerolinecolor="#6b7280"
            ),
            yaxis=dict(
                gridcolor="#27273a",
                tickfont=dict(color="#d1d5db")
            ),
            showlegend=False
        )
        st.plotly_chart(fig_cob, use_container_width=True, config={"displayModeBar": True, "displaylogo": False})

    # ─────────────────────────────────────────────────────────────
    # SUBTAB 3: DISTRIBUCIÓN POR CATEGORÍAS Y CAPITAL INMOVILIZADO
    # ─────────────────────────────────────────────────────────────
    with sub_tab3:
        cat_group = df_plot.groupby("categoria").agg(
            total_stock=("cantidad_actual", lambda x: max(0, x.sum())),
            valor_inventario=("valor_stock", "sum"),
            cant_productos=("id", "count")
        ).reset_index()

        col_cat1, col_cat2 = st.columns(2)

        PALETA_CATEGORIAS = [
            "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6",
            "#ec4899", "#06b6d4", "#f97316", "#14b8a6"
        ]

        with col_cat1:
            st.markdown('<div class="sect-label">Unidades Físicas por Categoría</div>', unsafe_allow_html=True)
            fig_pie = go.Figure(data=[go.Pie(
                labels=cat_group["categoria"],
                values=cat_group["total_stock"],
                hole=0.48,
                marker=dict(colors=PALETA_CATEGORIAS[:len(cat_group)]),
                textinfo="label+percent",
                textfont=dict(color="#ffffff", size=12, family="Inter, sans-serif"),
                hovertemplate="<b>%{label}</b><br>Stock Total: %{value:,.0f} unidades (%{percent})<extra></extra>"
            )])
            fig_pie.update_layout(
                height=360,
                margin=dict(l=20, r=20, t=20, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, sans-serif", color="#e5e7eb"),
                legend=dict(orientation="h", y=-0.1, font=dict(color="#d1d5db"))
            )
            st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})

        with col_cat2:
            st.markdown('<div class="sect-label">Capital Inmovilizado por Categoría ($ USD)</div>', unsafe_allow_html=True)
            fig_val = go.Figure(data=[go.Bar(
                x=cat_group["categoria"],
                y=cat_group["valor_inventario"],
                marker=dict(color=PALETA_CATEGORIAS[:len(cat_group)]),
                text=cat_group["valor_inventario"].apply(lambda v: f"${v:,.2f}"),
                textposition="outside",
                textfont=dict(color="#f3f4f6", size=12, family="Inter, sans-serif"),
                hovertemplate="<b>%{x}</b><br>Capital en Stock: $%{y:,.2f}<br>Productos: %{customdata} SKU<extra></extra>",
                customdata=cat_group["cant_productos"]
            )])
            fig_val.update_layout(
                height=360,
                margin=dict(l=20, r=20, t=20, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(17, 17, 24, 0.6)",
                font=dict(family="Inter, sans-serif", color="#e5e7eb"),
                xaxis=dict(gridcolor="#27273a", tickfont=dict(color="#d1d5db")),
                yaxis=dict(gridcolor="#27273a", tickfont=dict(color="#9ca3af"), title="Monto Total ($ USD)")
            )
            st.plotly_chart(fig_val, use_container_width=True, config={"displayModeBar": False})


# ══════════════════════════════════════════════════════════════
# TAB 2 — VISOR TRANSACCIONAL
# ══════════════════════════════════════════════════════════════
with tab_visor:
    col_h, col_r = st.columns([5, 1])
    col_h.markdown(
        '<div class="page-title">Visor Transaccional</div>'
        '<div class="page-sub">Estado en tiempo real de todos los activos de inventario</div>',
        unsafe_allow_html=True
    )
    if col_r.button("Actualizar", key="ref_visor"):
        _limpiar_cache()
        st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    df = _inventario()

    if df.empty:
        st.markdown(
            '<div style="display:flex;flex-direction:column;align-items:center;'
            'justify-content:center;padding:64px 24px;text-align:center;">'
            '<div style="font-size:48px;margin-bottom:16px;">&#128230;</div>'
            '<div style="font-size:18px;font-weight:700;color:#d1d5db;margin-bottom:8px;">'
            'Sin inventario cargado</div>'
            '<div style="font-size:14px;color:#6b7280;max-width:380px;line-height:1.6;">'
            'Sube tu archivo <code>.xlsx</code> o <code>.csv</code> desde la '
            'barra lateral para ver tu inventario aquí.'
            '</div></div>',
            unsafe_allow_html=True
        )
    else:
        kpi = _kpi()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total de Activos",  kpi["total"])
        c2.metric("Estado Crítico",    kpi["criticos"])
        c3.metric("Por Debajo Mínimo", kpi["bajo_min"])
        c4.metric("Operativos",         kpi["ok"])

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="sect-label">Registro de Inventario</div>', unsafe_allow_html=True)

        # ── Badge / pill por estado ──
        BADGE_ESTADO = {
            "Critico":             ("color: #f87171; font-weight: 600;"
                                    " background-color: rgba(248,113,113,0.12);"
                                    " border-radius: 999px; padding: 2px 10px;"
                                    " font-size: 12px; text-transform: uppercase;"),
            "Crítico":             ("color: #f87171; font-weight: 600;"
                                    " background-color: rgba(248,113,113,0.12);"
                                    " border-radius: 999px; padding: 2px 10px;"
                                    " font-size: 12px; text-transform: uppercase;"),
            "Revisión":            ("color: #c084fc; font-weight: 600;"
                                    " background-color: rgba(192,132,252,0.12);"
                                    " border-radius: 999px; padding: 2px 10px;"
                                    " font-size: 12px; text-transform: uppercase;"),
            "En Reabastecimiento": ("color: #60a5fa; font-weight: 600;"
                                    " background-color: rgba(96,165,250,0.12);"
                                    " border-radius: 999px; padding: 2px 10px;"
                                    " font-size: 12px; text-transform: uppercase;"),
            "Disponible":          ("color: #4ade80; font-weight: 600;"
                                    " background-color: rgba(74,222,128,0.12);"
                                    " border-radius: 999px; padding: 2px 10px;"
                                    " font-size: 12px; text-transform: uppercase;"),
        }

        def _badge_estado(val: str) -> str:
            return BADGE_ESTADO.get(val, "")

        cols_sel = ["id", "nombre", "categoria", "cantidad_actual",
                    "cantidad_minima", "precio_unitario", "ventas_semanales", "estado"]
        df_vis = df[cols_sel].copy()
        df_vis.columns = ["ID", "Producto", "Categoría",
                          "Stock Actual", "Stock Mínimo",
                          "Precio Unit.", "Ventas / Sem.", "Estado"]

        fmt = {
            "Stock Actual":  "{:.0f}",
            "Stock Mínimo":  "{:.0f}",
            "Precio Unit.":  "${:,.2f}",
            "Ventas / Sem.": "{:.1f}",
        }
        styled = (
            df_vis.style
            .format(fmt)
            .map(_badge_estado, subset=["Estado"])
            .set_properties(**{"font-size": "14px", "font-family": "Inter, sans-serif"})
            .set_properties(
                subset=["Stock Actual", "Stock Mínimo", "Precio Unit.", "Ventas / Sem.", "ID"],
                **{"text-align": "right"}
            )
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Exportar CSV del inventario
        csv_inv = df_vis.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="Exportar CSV",
            data=csv_inv,
            file_name="inventario.csv",
            mime="text/csv",
            key="dl_inv_csv"
        )

        st.markdown("<br>", unsafe_allow_html=True)
        _render_graficos_inventario(df)


# ══════════════════════════════════════════════════════════════
# TAB 3 — AUDITORIA DEL SISTEMA
# ══════════════════════════════════════════════════════════════
with tab_auditoria:
    col_h, col_r = st.columns([5, 1])
    col_h.markdown(
        '<div class="page-title">Auditoría del Sistema</div>'
        '<div class="page-sub">Registro completo de invocaciones con trazabilidad y métricas de latencia</div>',
        unsafe_allow_html=True
    )
    if col_r.button("Actualizar", key="ref_aud"):
        _limpiar_cache()
        st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    df_h = _historial()

    if df_h.empty:
        st.markdown(
            '<div style="display:flex;flex-direction:column;align-items:center;'
            'justify-content:center;padding:64px 24px;text-align:center;">'
            '<div style="font-size:48px;margin-bottom:16px;">&#128203;</div>'
            '<div style="font-size:18px;font-weight:700;color:#d1d5db;margin-bottom:8px;">'
            'Sin registros de actividad</div>'
            '<div style="font-size:14px;color:#6b7280;max-width:420px;line-height:1.6;">'
            'El historial de auditoría se llena automáticamente cada vez que ARIA '
            'invoca una herramienta. Inicia una conversación en la '
            '<b>Consola de Operaciones</b> para ver registros aquí.'
            '</div></div>',
            unsafe_allow_html=True
        )
    else:
        prom  = df_h["latencia_ms"].mean()
        maxi  = df_h["latencia_ms"].max()
        sobre = int((df_h["latencia_ms"] > 3500).sum())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Invocaciones Totales", len(df_h))
        c2.metric("Latencia Promedio ms", f"{prom:.0f}")
        c3.metric("Latencia Máxima ms",   f"{maxi:.0f}")
        c4.metric("Sobre Límite 3500ms",  sobre)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="sect-label">Log de Ejecuciones</div>', unsafe_allow_html=True)

        def _color_latencia(val):
            if isinstance(val, (int, float)):
                if val > 3500: return "color: #f87171; font-weight: 600;"
                if val > 1500: return "color: #fbbf24;"
                return "color: #4ade80;"
            return ""

        styled_h = (
            df_h.style
            .format({"latencia_ms": "{:.1f}"})
            .map(_color_latencia, subset=["latencia_ms"])
            .set_properties(**{"font-size": "14px", "font-family": "Inter, sans-serif"})
        )
        st.dataframe(
            styled_h,
            use_container_width=True,
            hide_index=True,
            column_config={
                "timestamp":   st.column_config.TextColumn("Marca de Tiempo", width="medium"),
                "herramienta": st.column_config.TextColumn("Herramienta", width="medium"),
                "latencia_ms": st.column_config.NumberColumn("Latencia (ms)", format="%.1f ms"),
                "resultado":   st.column_config.TextColumn("Resultado", width="large"),
            }
        )

        # Exportar CSV de la auditoría
        csv_audit = df_h.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="Exportar CSV",
            data=csv_audit,
            file_name="auditoria.csv",
            mime="text/csv",
            key="dl_audit_csv"
        )


# ══════════════════════════════════════════════════════════════
# TAB 4 — GESTIÓN DE ÓRDENES
# ══════════════════════════════════════════════════════════════
with tab_ordenes:
    col_h, col_r = st.columns([5, 1])
    col_h.markdown(
        '<div class="page-title">Gestión de Órdenes</div>'
        '<div class="page-sub">Órdenes de compra generadas y disponibles para descarga</div>',
        unsafe_allow_html=True
    )
    if col_r.button("Actualizar", key="ref_ord"):
        _limpiar_cache()
        st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    df_o = _ordenes()

    if df_o.empty:
        st.markdown(
            '<div style="display:flex;flex-direction:column;align-items:center;'
            'justify-content:center;padding:64px 24px;text-align:center;">'
            '<div style="font-size:48px;margin-bottom:16px;">&#128196;</div>'
            '<div style="font-size:18px;font-weight:700;color:#d1d5db;margin-bottom:8px;">'
            'Sin órdenes generadas</div>'
            '<div style="font-size:14px;color:#6b7280;max-width:420px;line-height:1.6;">'
            'Las órdenes de compra aparecen aquí una vez que ARIA las emite. '
            'Prueba con: <br><code>Genera la orden de compra para los productos críticos.</code>'
            '</div></div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div style="font-size:14px;color:#9ca3af;margin-bottom:16px;">'
            f'{len(df_o)} orden(es) registrada(s) en el sistema.</div>',
            unsafe_allow_html=True
        )
        st.markdown('<div class="sect-label">Detalle de Órdenes</div>', unsafe_allow_html=True)

        for _, orden in df_o.iterrows():
            encabezado = (
                f"ORD-{str(orden['id']).zfill(4)}  |  "
                f"{orden['proveedor']}  |  "
                f"${orden['total']:,.2f}  |  "
                f"{orden['timestamp']}"
            )
            with st.expander(encabezado, expanded=False):
                col_info, col_btn = st.columns([3, 1])
                col_info.markdown(
                    f'<div style="font-size:14px;color:#9ca3af;line-height:2.2;">'
                    f'<b style="color:#e5e7eb;">Proveedor</b>&nbsp;&nbsp;{orden["proveedor"]}<br>'
                    f'<b style="color:#e5e7eb;">Total</b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
                    f'<span style="color:#4ade80;font-weight:700;">${orden["total"]:,.2f}</span><br>'
                    f'<b style="color:#e5e7eb;">Emitida</b>&nbsp;&nbsp;&nbsp;{orden["timestamp"]}'
                    f'</div>',
                    unsafe_allow_html=True
                )
                pdf_path = orden.get("archivo_pdf", "")
                if pdf_path and os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f_pdf:
                        col_btn.download_button(
                            label="Descargar PDF",
                            data=f_pdf.read(),
                            file_name=Path(pdf_path).name,
                            mime="application/pdf",
                            key=f"dl_{orden['id']}"
                        )
                else:
                    col_btn.markdown(
                        '<div style="font-size:13px;color:#6b7280;margin-top:8px;">'
                        'Archivo no disponible</div>',
                        unsafe_allow_html=True
                    )


# ══════════════════════════════════════════════════════════════
# TAB 5 — ARQUITECTURA DEL SISTEMA
# ══════════════════════════════════════════════════════════════
with tab_arq:
    st.markdown(
        '<div class="page-title">Arquitectura del Sistema</div>'
        '<div class="page-sub">Componentes internos del agente ARIA y sus archivos correspondientes</div>',
        unsafe_allow_html=True
    )
    st.markdown("<hr>", unsafe_allow_html=True)

    st.markdown('<div class="sect-label">Componentes del Agente</div>', unsafe_allow_html=True)

    _componentes = [
        (
            "Cerebro (LLM)",
            "agent_core.py",
            f"Google {MODELO_LLM} vía SDK google-genai. Recibe el contexto completo y decide "
            "qué herramienta invocar en cada paso del ciclo."
        ),
        (
            "Bucle ReAct",
            "agent_core.py",
            "Ciclo Razonar \u2192 Actuar \u2192 Observar. Máximo 10 iteraciones por consulta. "
            "Mide latencia por herramienta y registra advertencias si supera 3\u202f500\u202fms."
        ),
        (
            "Herramientas (\u00d7 6)",
            "tools.py",
            "analizar_agotamiento \u00b7 evaluar_proveedores \u00b7 auditar_bd \u00b7 "
            "ajustar_presupuesto \u00b7 generar_pdf \u00b7 actualizar_inventario"
        ),
        (
            "Memoria",
            "session_state + SQLite",
            "Historial de chat en st.session_state (volátil por sesión). "
            "Inventario, proveedores, órdenes y trazas de auditoría en inventario.db (persistente)."
        ),
        (
            "Interfaz UI",
            "app.py",
            "Streamlit con 5 pestañas: Consola de Operaciones \u00b7 Visor Transaccional \u00b7 "
            "Auditoría del Sistema \u00b7 Gestión de Órdenes \u00b7 Arquitectura del Sistema."
        ),
        (
            "Calidad",
            "test_calidad.py  +  logs/",
            "31 pruebas pytest que cubren exactitud matemática, self-healing, restricción de "
            "presupuesto, generación de PDF, latencia y determinismo. "
            "Logs persistentes con Loguru (rotación 5\u202fMB, retención 10 días)."
        ),
        (
            "Infraestructura",
            ".env  +  requirements.txt",
            "Variables de entorno gestionadas con python-dotenv. "
            "Dependencias: google-genai \u00b7 streamlit \u00b7 reportlab \u00b7 pandas \u00b7 loguru \u00b7 pytest."
        ),
    ]

    for nombre, archivo, desc in _componentes:
        st.markdown(
            f'<div class="info-box" style="margin-bottom:8px;">'
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:baseline;margin-bottom:5px;">'
            f'<span style="font-weight:700;color:#e5e7eb;font-size:14px;">{nombre}</span>'
            f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:11px;'
            f'color:#60a5fa;background:rgba(59,130,246,0.12);'
            f'padding:1px 8px;border-radius:3px;">{archivo}</span>'
            f'</div>'
            f'<span style="color:#9ca3af;font-size:13px;line-height:1.6;">{desc}</span>'
            f'</div>',
            unsafe_allow_html=True
        )

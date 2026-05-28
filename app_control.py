"""
BeisSeven — Streamlit + Neon (PostgreSQL)
pip install streamlit pandas openpyxl reportlab psycopg2-binary
streamlit run beisseven_app.py
"""

import streamlit as st
import psycopg2
import hashlib
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
import logging

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    PDF_OK = True
except ImportError:
    PDF_OK = False

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("beisseven.log"), logging.StreamHandler()])

DATABASE_URL = (
    "postgresql://neondb_owner:npg_aM1DT8ekNIyi"
    "@ep-soft-waterfall-aqc33eta.c-8.us-east-1.aws.neon.tech"
    "/neondb?sslmode=require&channel_binding=require"
)

C_ACCENT  = "#00AAFF"
C_SUCCESS = "#00FF77"
C_DANGER  = "#FF2244"
C_WARN    = "#FFB800"

st.set_page_config(page_title="BeisSeven", page_icon="⚾",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=Barlow:wght@300;400;500;600&display=swap');
*, *::before, *::after { box-sizing: border-box; }
html, body, [data-testid="stAppViewContainer"] {
    background: #030810 !important; color: #E8EFF8 !important;
    font-family: 'Barlow', sans-serif !important; }
[data-testid="stSidebar"] { background: #030810 !important; border-right: 1px solid #0D2040 !important; }
[data-testid="stSidebar"] * { color: #CBD5E0 !important; }
.stButton > button {
    background: linear-gradient(135deg, #00AAFF, #0077CC) !important;
    color: white !important; font-family: 'Rajdhani', sans-serif !important;
    font-weight: 700 !important; font-size: 0.9rem !important;
    letter-spacing: 0.08em !important; border: none !important;
    border-radius: 8px !important; transition: all 0.2s ease !important; }
.stButton > button:hover { transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(0,170,255,0.4) !important; }
.stTextInput > div > div > input, .stNumberInput > div > div > input,
.stSelectbox > div > div, .stTextArea textarea {
    background: #0A1628 !important; border: 1px solid #0D2040 !important;
    border-radius: 8px !important; color: #E8EFF8 !important; }
[data-testid="stDataFrame"] { background: #0A1628 !important; border-radius: 12px !important; }
.stTabs [data-baseweb="tab-list"] { background: #0A1628 !important; border-radius: 10px !important; padding: 4px !important; }
.stTabs [data-baseweb="tab"] { background: transparent !important; color: #7A90A8 !important;
    font-family: 'Rajdhani', sans-serif !important; font-weight: 600 !important;
    border-radius: 7px !important; border: none !important; }
.stTabs [aria-selected="true"] { background: #00AAFF !important; color: white !important; }
[data-testid="stMetric"] { background: #0A1628 !important; border: 1px solid #0D2040 !important;
    border-radius: 14px !important; padding: 1.2rem 1.5rem !important; }
[data-testid="stMetricLabel"] { font-family: 'Rajdhani', sans-serif !important;
    font-size: 0.78rem !important; letter-spacing: 0.12em !important;
    color: #7A90A8 !important; font-weight: 600 !important; }
[data-testid="stMetricValue"] { font-family: 'Rajdhani', sans-serif !important;
    font-size: 2.4rem !important; font-weight: 700 !important; color: #00AAFF !important; }
.streamlit-expanderHeader { background: #0A1628 !important; border-radius: 10px !important;
    font-family: 'Rajdhani', sans-serif !important; font-weight: 600 !important; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #030810; }
::-webkit-scrollbar-thumb { background: #0D2040; border-radius: 3px; }
#MainMenu, footer, [data-testid="stDecoration"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# COMPONENTES
# ─────────────────────────────────────────────
def card_metric(titulo, valor, color=C_ACCENT, subtitulo=""):
    sub = f"<p style='margin:2px 0 0;font-size:0.72rem;color:#7A90A8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>{subtitulo}</p>" if subtitulo else ""
    st.markdown(f"""
    <div style="background:#0A1628;border:1px solid #0D2040;border-radius:14px;
                padding:1rem 0.8rem;text-align:center;border-top:3px solid {color};
                min-height:110px;display:flex;flex-direction:column;justify-content:center;">
        <p style="margin:0 0 4px;font-family:'Rajdhani',sans-serif;font-size:0.68rem;
                  font-weight:600;letter-spacing:0.12em;color:#7A90A8;
                  text-transform:uppercase;white-space:nowrap;overflow:hidden;
                  text-overflow:ellipsis;">{titulo}</p>
        <p style="margin:0;font-family:'Rajdhani',sans-serif;
                  font-size:clamp(1.2rem,2.5vw,2rem);
                  font-weight:700;color:{color};line-height:1.1;
                  word-break:break-word;overflow-wrap:anywhere;">{valor}</p>
        {sub}
    </div>""", unsafe_allow_html=True)

def titulo_seccion(texto, icono=""):
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:1.2rem;">
        <span style="font-size:1.5rem;">{icono}</span>
        <h2 style="margin:0;font-family:'Rajdhani',sans-serif;font-size:1.7rem;
                   font-weight:700;color:#E8EFF8;letter-spacing:0.04em;">{texto}</h2>
    </div>""", unsafe_allow_html=True)

def badge(texto, color=C_ACCENT):
    return (f"<span style='background:{color}22;color:{color};border:1px solid {color}55;"
            f"border-radius:5px;padding:2px 10px;font-size:0.78rem;"
            f"font-family:Rajdhani,sans-serif;font-weight:600;"
            f"letter-spacing:0.06em;'>{texto}</span>")

def divider():
    st.markdown("<hr style='border:none;border-top:1px solid #0D2040;margin:1.2rem 0;'>",
                unsafe_allow_html=True)

# ─────────────────────────────────────────────
# BASE DE DATOS
# ─────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_conn():
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
    return conn

def db_conn():
    conn = get_conn()
    try:
        conn.cursor().execute("SELECT 1")
    except Exception:
        st.cache_resource.clear()
        conn = get_conn()
    return conn

def db_exec(query: str, params: tuple = (), fetch: str = "none"):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if fetch == "one":
                return cur.fetchone()
            if fetch == "all":
                return cur.fetchall()
            conn.commit()
            return None
    except Exception as e:
        conn.rollback()
        logging.error(f"DB error: {e} | Query: {query}")
        raise e

@st.cache_resource(show_spinner="Conectando a Neon... ☁️")
def inicializar_db():
    """
    Crea las tablas en Neon.
    Si ya existen con esquema incorrecto, las recrea.
    """
    # ── Reiniciar tablas si tienen columnas incorrectas ──
    conn = db_conn()
    with conn.cursor() as cur:
        # Verificar si la tabla usuarios tiene la columna 'nombre'
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='usuarios' AND column_name='nombre'
        """)
        tiene_nombre = cur.fetchone()

        if not tiene_nombre:
            # Tabla existe con otro esquema — borrar y recrear todo
            logging.warning("Esquema incorrecto detectado. Recreando tablas...")
            cur.execute("DROP TABLE IF EXISTS picheos CASCADE")
            cur.execute("DROP TABLE IF EXISTS usuarios CASCADE")
            cur.execute("DROP TABLE IF EXISTS config CASCADE")
            conn.commit()

    # ── Crear tablas correctas ──
    db_exec("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id     SERIAL PRIMARY KEY,
            nombre TEXT UNIQUE NOT NULL,
            pass   TEXT NOT NULL,
            rol    TEXT NOT NULL DEFAULT 'operador'
        )
    """)
    db_exec("""
        CREATE TABLE IF NOT EXISTS picheos (
            id         SERIAL PRIMARY KEY,
            fecha      TEXT NOT NULL,
            id_control TEXT NOT NULL,
            cantidad   INTEGER NOT NULL,
            operador   TEXT NOT NULL
        )
    """)
    db_exec("""
        CREATE TABLE IF NOT EXISTS config (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
    """)
    db_exec("INSERT INTO config (clave,valor) VALUES ('precio','0.024') ON CONFLICT DO NOTHING")

    # ── Crear admin por defecto ──
    admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
    db_exec("""
        INSERT INTO usuarios (nombre, pass, rol)
        VALUES ('admin', %s, 'admin')
        ON CONFLICT (nombre) DO NOTHING
    """, (admin_hash,))

# ─────────────────────────────────────────────
# EXPORTACIONES
# ─────────────────────────────────────────────
def exportar_excel() -> BytesIO:
    conn = db_conn()
    df = pd.read_sql(
        "SELECT id,fecha,id_control,cantidad,operador FROM picheos ORDER BY fecha DESC", conn)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Registros")
    buf.seek(0)
    return buf

def exportar_pdf() -> BytesIO:
    if not PDF_OK:
        return None
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    estilos = getSampleStyleSheet()
    t_style = ParagraphStyle("t", parent=estilos["Title"], fontName="Helvetica-Bold",
                              fontSize=18, textColor=colors.HexColor("#00AAFF"), spaceAfter=6)
    s_style = ParagraphStyle("s", parent=estilos["Normal"], fontName="Helvetica",
                              fontSize=9, textColor=colors.grey, spaceAfter=16)
    elems = [Paragraph("REPORTE — BEISSEVEN", t_style),
             Paragraph(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", s_style),
             Spacer(1, 0.4*cm)]
    datos = db_exec(
        "SELECT fecha,id_control,cantidad,operador FROM picheos ORDER BY fecha DESC LIMIT 500",
        fetch="all")
    if datos:
        td = [["FECHA","CONTROL","CANTIDAD","OPERADOR"]] + [list(r) for r in datos]
        t = Table(td, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#00AAFF")),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),9),
            ("ALIGN",(0,0),(-1,-1),"CENTER"),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#F7F9FC"),colors.HexColor("#EDF2F7")]),
            ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#CBD5E0")),
            ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ]))
        elems.append(t)
    doc.build(elems)
    buf.seek(0)
    return buf

# ─────────────────────────────────────────────
# SESSION
# ─────────────────────────────────────────────
def init_session():
    for k, v in {"logged_in": False, "user": None, "nav": "Dashboard"}.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────
def pantalla_login():
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("""
        <div style="text-align:center;padding:3rem 0 1.5rem;">
            <div style="font-size:4rem;">⚾</div>
            <h1 style="margin:0;font-family:'Rajdhani',sans-serif;font-size:3.4rem;font-weight:700;
                background:linear-gradient(135deg,#00AAFF,#00FF77);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;">BeisSeven</h1>
            <p style="margin:0.3rem 0 2.5rem;color:#7A90A8;font-size:0.95rem;
                letter-spacing:0.12em;text-transform:uppercase;">
                Sistema de Gestión · Neon Cloud</p>
        </div>""", unsafe_allow_html=True)

        with st.container():
            st.markdown("""<div style="background:#0A1628;border:1px solid #0D2040;
                border-radius:18px;padding:2.5rem 2rem;
                box-shadow:0 20px 60px rgba(0,0,0,0.6);">""", unsafe_allow_html=True)

            usuario  = st.text_input("👤  Usuario",    placeholder="Ingrese su usuario")
            password = st.text_input("🔒  Contraseña", placeholder="Ingrese su contraseña",
                                     type="password")
            st.markdown("<br>", unsafe_allow_html=True)

            if st.button("INGRESAR AL SISTEMA", use_container_width=True):
                if not usuario or not password:
                    st.error("Por favor ingrese usuario y contraseña.")
                else:
                    ph = hashlib.sha256(password.encode()).hexdigest()
                    try:
                        user = db_exec(
                            "SELECT * FROM usuarios WHERE nombre=%s AND pass=%s",
                            (usuario, ph), fetch="one")
                        if user:
                            st.session_state.logged_in = True
                            st.session_state.user = user
                            logging.info(f"Login: {usuario}")
                            st.rerun()
                        else:
                            st.error("Credenciales incorrectas.")
                    except Exception as e:
                        st.error(f"Error de conexión: {e}")

            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("""<p style="text-align:center;margin-top:2rem;color:#3A5070;font-size:0.8rem;">
            Usuario: <b style='color:#00AAFF'>admin</b> /
            Contraseña: <b style='color:#00AAFF'>admin123</b></p>""",
            unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
def sidebar_nav():
    user = st.session_state.user
    rol  = user[3]
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center;padding:1.5rem 0 1rem;">
            <div style="font-size:2.8rem;">⚾</div>
            <h2 style="margin:0.2rem 0 0.1rem;font-family:'Rajdhani',sans-serif;font-size:2rem;
                font-weight:700;background:linear-gradient(135deg,#00AAFF,#00FF77);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;">BeisSeven</h2>
            <p style="margin:0;color:#3A5070;font-size:0.65rem;letter-spacing:0.1em;
                text-transform:uppercase;">☁️ Neon Cloud</p>
        </div>""", unsafe_allow_html=True)

        st.markdown(f"""
        <div style="background:#0A1628;border:1px solid #0D2040;border-radius:10px;
            padding:0.8rem 1rem;margin:0.5rem 0 1.5rem;text-align:center;">
            <p style="margin:0;font-size:0.72rem;color:#7A90A8;letter-spacing:0.1em;
                text-transform:uppercase;">Sesión activa</p>
            <p style="margin:2px 0 0;font-family:'Rajdhani',sans-serif;
                font-size:1.1rem;font-weight:700;color:#E8EFF8;">{user[1].upper()}</p>
            <p style="margin:2px 0 0;">{badge(rol.upper(), C_ACCENT if rol=='admin' else C_SUCCESS)}</p>
        </div>""", unsafe_allow_html=True)

        opciones = [("📊","Dashboard"), ("📝","Registros")]
        if rol == "admin":
            opciones += [("👥","Usuarios"), ("⚙️","Configuración")]

        for icono, nombre in opciones:
            activo = st.session_state.nav == nombre
            bg = "#00AAFF22" if activo else "transparent"
            bord = "#00AAFF" if activo else "transparent"
            col_t = "#00AAFF" if activo else "#CBD5E0"
            st.markdown(f"""
            <div style="background:{bg};border-left:3px solid {bord};border-radius:0 8px 8px 0;
                padding:0.55rem 1rem;margin:2px 0;">
                <span>{icono}</span>
                <span style="font-family:'Rajdhani',sans-serif;font-weight:600;font-size:0.95rem;
                    color:{col_t};margin-left:8px;letter-spacing:0.06em;">{nombre.upper()}</span>
            </div>""", unsafe_allow_html=True)
            if st.button(nombre, key=f"nav_{nombre}", use_container_width=True):
                st.session_state.nav = nombre
                st.rerun()

        st.markdown("<br>" * 3, unsafe_allow_html=True)
        if st.button("🚪  CERRAR SESIÓN", use_container_width=True, key="logout"):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.nav  = "Dashboard"
            st.rerun()

        st.markdown("""<p style="text-align:center;color:#1A2840;font-size:0.68rem;
            margin-top:1rem;">BeisSeven v2.0 — Neon PostgreSQL</p>""",
            unsafe_allow_html=True)

# ─────────────────────────────────────────────
# VISTAS
# ─────────────────────────────────────────────
def vista_dashboard():
    titulo_seccion("Resumen de Operaciones", "📊")
    c1, c2 = st.columns(2)
    with c1:
        fecha_desde = st.date_input("📅 Desde",
            value=datetime.now().date() - timedelta(days=30), key="d_desde")
    with c2:
        fecha_hasta = st.date_input("📅 Hasta",
            value=datetime.now().date(), key="d_hasta")
    divider()

    if fecha_desde > fecha_hasta:
        st.warning("⚠️ La fecha 'Desde' no puede ser mayor que 'Hasta'.")
        return

    try:
        total = db_exec(
            "SELECT COALESCE(SUM(cantidad),0) FROM picheos WHERE fecha BETWEEN %s AND %s",
            (str(fecha_desde), str(fecha_hasta)), fetch="one")[0]
        total = int(total)

        p_row = db_exec("SELECT valor FROM config WHERE clave='precio'", fetch="one")
        precio = float(p_row[0]) if p_row else 0.024

        top_row = db_exec(
            """SELECT operador, SUM(cantidad) AS s FROM picheos
               WHERE fecha BETWEEN %s AND %s
               GROUP BY operador ORDER BY s DESC LIMIT 1""",
            (str(fecha_desde), str(fecha_hasta)), fetch="one")

        dias = db_exec(
            "SELECT COUNT(DISTINCT fecha) FROM picheos WHERE fecha BETWEEN %s AND %s",
            (str(fecha_desde), str(fecha_hasta)), fetch="one")[0]

    except Exception as e:
        st.error(f"Error al cargar métricas: {e}")
        return

    m1, m2, m3, m4 = st.columns(4)
    with m1: card_metric("TOTAL PICHEOS", f"{total:,}", C_ACCENT, f"{fecha_desde} → {fecha_hasta}")
    with m2: card_metric("USD ESTIMADO", f"${total*precio:,.2f}", C_SUCCESS, f"@ ${precio}/unidad")
    with m3: card_metric("DÍAS ACTIVOS", str(dias), C_WARN, "En el rango")
    with m4: card_metric("TOP OPERADOR",
                         top_row[0] if top_row else "—", "#BF8FFF",
                         f"{int(top_row[1]):,} picheos" if top_row else "0 picheos")
    divider()

    try:
        conn = db_conn()
        df_c = pd.read_sql(
            """SELECT fecha, SUM(cantidad) as total FROM picheos
               WHERE fecha BETWEEN %s AND %s GROUP BY fecha ORDER BY fecha""",
            conn, params=(str(fecha_desde), str(fecha_hasta)))
        if not df_c.empty:
            st.markdown("""<p style="font-family:'Rajdhani',sans-serif;font-weight:600;
                color:#7A90A8;font-size:0.8rem;letter-spacing:0.1em;text-transform:uppercase;">
                📈  Evolución Diaria</p>""", unsafe_allow_html=True)
            df_c["fecha"] = pd.to_datetime(df_c["fecha"])
            st.area_chart(df_c.set_index("fecha")["total"], color=C_ACCENT)
        else:
            st.info("Sin datos para graficar en este rango.")
    except Exception as e:
        logging.error(f"Error gráfica: {e}")

    divider()
    st.markdown("""<p style="font-family:'Rajdhani',sans-serif;font-weight:600;color:#7A90A8;
        font-size:0.8rem;letter-spacing:0.1em;text-transform:uppercase;">
        🕐  Últimos 10 Registros</p>""", unsafe_allow_html=True)
    try:
        rows = db_exec(
            "SELECT fecha,id_control,cantidad,operador FROM picheos ORDER BY id DESC LIMIT 10",
            fetch="all")
        if rows:
            st.dataframe(pd.DataFrame(rows, columns=["Fecha","Control","Cantidad","Operador"]),
                         use_container_width=True, hide_index=True)
        else:
            st.info("Sin registros todavía.")
    except Exception as e:
        st.error(f"Error: {e}")


def vista_registros():
    user = st.session_state.user
    titulo_seccion("Gestión de Registros", "📝")

    with st.expander("➕  NUEVO REGISTRO", expanded=True):
        c1, c2, c3, c4 = st.columns([1.5, 2, 1.5, 1.2])
        with c1: reg_fecha = st.date_input("Fecha", value=datetime.now().date(), key="rf")
        with c2: reg_id    = st.text_input("ID Control", placeholder="Ej: BC-20250601", key="rid")
        with c3: reg_cant  = st.number_input("Cantidad", min_value=1, step=1, key="rc")
        with c4:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾  GUARDAR", use_container_width=True):
                if not reg_id.strip():
                    st.error("El ID de control es obligatorio.")
                else:
                    try:
                        db_exec(
                            "INSERT INTO picheos (fecha,id_control,cantidad,operador) VALUES (%s,%s,%s,%s)",
                            (str(reg_fecha), reg_id.strip(), int(reg_cant), user[1]))
                        st.success("✅ Registro guardado en Neon.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    divider()
    with st.expander("🔍  FILTROS"):
        fc1, fc2, fc3 = st.columns(3)
        with fc1: f_d = st.date_input("Desde", value=datetime.now().date()-timedelta(days=90), key="fd")
        with fc2: f_h = st.date_input("Hasta", value=datetime.now().date(), key="fh")
        with fc3: f_c = st.text_input("ID Control (contiene)", key="fc")

    try:
        q = "SELECT id,fecha,id_control,cantidad,operador FROM picheos WHERE fecha BETWEEN %s AND %s"
        p = [str(f_d), str(f_h)]
        if f_c.strip():
            q += " AND id_control ILIKE %s"
            p.append(f"%{f_c.strip()}%")
        q += " ORDER BY id DESC LIMIT 500"
        rows = db_exec(q, tuple(p), fetch="all")
    except Exception as e:
        st.error(f"Error: {e}")
        return

    df = pd.DataFrame(rows, columns=["ID","Fecha","Control","Cantidad","Operador"]) \
         if rows else pd.DataFrame(columns=["ID","Fecha","Control","Cantidad","Operador"])

    if not df.empty:
        tot = df["Cantidad"].sum()
        p_row = db_exec("SELECT valor FROM config WHERE clave='precio'", fetch="one")
        precio = float(p_row[0]) if p_row else 0.024
        ca, cb, _ = st.columns([1,1,3])
        with ca: card_metric("REGISTROS", str(len(df)), C_ACCENT)
        with cb: card_metric("TOTAL PICHEOS", f"{tot:,}", C_SUCCESS, f"≈ ${tot*precio:,.2f} USD")
        st.markdown("<br>", unsafe_allow_html=True)

    st.dataframe(df, use_container_width=True, hide_index=True)

    if user[3] == "admin" and not df.empty:
        divider()
        st.markdown("**🗑️  Eliminar registro por ID** *(solo admin)*")
        ec1, ec2 = st.columns([2,4])
        with ec1: del_id = st.number_input("ID a eliminar", min_value=1, step=1, key="del_id")
        with ec2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("ELIMINAR REGISTRO", key="btn_del"):
                ex = db_exec("SELECT id FROM picheos WHERE id=%s", (int(del_id),), fetch="one")
                if not ex:
                    st.error("No existe ese ID.")
                else:
                    db_exec("DELETE FROM picheos WHERE id=%s", (int(del_id),))
                    st.success(f"Registro #{del_id} eliminado.")
                    st.rerun()

    divider()
    st.markdown("""<p style="font-family:'Rajdhani',sans-serif;font-weight:600;color:#7A90A8;
        font-size:0.8rem;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:0.5rem;">
        📤  Exportar Datos</p>""", unsafe_allow_html=True)
    e1, e2, _ = st.columns([1,1,4])
    with e1:
        try:
            st.download_button("📊  EXCEL", data=exportar_excel(),
                file_name=f"BeisSeven_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True)
        except Exception as e:
            st.error(f"Error Excel: {e}")
    with e2:
        if PDF_OK:
            try:
                buf = exportar_pdf()
                if buf:
                    st.download_button("📄  PDF", data=buf,
                        file_name=f"BeisSeven_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf", use_container_width=True)
            except Exception as e:
                st.error(f"Error PDF: {e}")


def vista_usuarios():
    user = st.session_state.user
    if user[3] != "admin":
        st.error("🔒 Acceso restringido — solo administradores.")
        return
    titulo_seccion("Gestión de Personal", "👥")

    with st.expander("➕  CREAR NUEVO USUARIO", expanded=True):
        u1,u2,u3,u4 = st.columns([2,2,1.5,1.2])
        with u1: u_nom  = st.text_input("Nombre de usuario", key="u_nom")
        with u2: u_pass = st.text_input("Contraseña", type="password", key="u_pass")
        with u3: u_rol  = st.selectbox("Rol", ["operador","admin"], key="u_rol")
        with u4:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("CREAR USUARIO", use_container_width=True):
                if not u_nom.strip() or not u_pass.strip():
                    st.error("Nombre y contraseña son obligatorios.")
                else:
                    ph = hashlib.sha256(u_pass.encode()).hexdigest()
                    try:
                        db_exec("INSERT INTO usuarios (nombre,pass,rol) VALUES (%s,%s,%s)",
                                (u_nom.strip(), ph, u_rol))
                        st.success(f"✅ Usuario '{u_nom}' creado.")
                        st.rerun()
                    except Exception as e:
                        if "unique" in str(e).lower():
                            st.error("El nombre de usuario ya existe.")
                        else:
                            st.error(f"Error: {e}")

    divider()
    try:
        rows = db_exec("SELECT id,nombre,rol FROM usuarios ORDER BY id", fetch="all")
        df_u = pd.DataFrame(rows, columns=["ID","Usuario","Rol"]) if rows else \
               pd.DataFrame(columns=["ID","Usuario","Rol"])
        st.dataframe(df_u, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Error: {e}")
        return

    divider()
    st.markdown("**🗑️  Eliminar usuario**")
    nombres = [r[1] for r in rows if r[1] != user[1]]
    if nombres:
        del_usr = st.selectbox("Seleccione usuario", nombres, key="del_usr")
        if st.button("ELIMINAR USUARIO SELECCIONADO"):
            if del_usr == "admin":
                st.error("No se puede eliminar al administrador principal.")
            else:
                db_exec("DELETE FROM usuarios WHERE nombre=%s", (del_usr,))
                st.success(f"Usuario '{del_usr}' eliminado.")
                st.rerun()
    else:
        st.info("No hay otros usuarios para eliminar.")


def vista_config():
    user = st.session_state.user
    if user[3] != "admin":
        st.error("🔒 Acceso restringido — solo administradores.")
        return
    titulo_seccion("Configuración del Sistema", "⚙️")

    col_c, _ = st.columns([1.5, 2.5])
    with col_c:
        st.markdown("""<div style="background:#0A1628;border:1px solid #0D2040;
            border-radius:14px;padding:2rem;">""", unsafe_allow_html=True)
        try:
            p_row = db_exec("SELECT valor FROM config WHERE clave='precio'", fetch="one")
            precio_actual = float(p_row[0]) if p_row else 0.024
        except Exception:
            precio_actual = 0.024

        nuevo_precio = st.number_input("💵  Precio por Unidad (USD)",
            min_value=0.0, value=precio_actual, step=0.001, format="%.4f")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾  GUARDAR CONFIGURACIÓN", use_container_width=True):
            try:
                db_exec("UPDATE config SET valor=%s WHERE clave='precio'", (str(nuevo_precio),))
                st.success(f"✅ Precio actualizado a ${nuevo_precio:.4f} USD")
            except Exception as e:
                st.error(f"Error: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

    divider()
    try:
        total_reg = db_exec("SELECT COUNT(*) FROM picheos",  fetch="one")[0]
        total_usr = db_exec("SELECT COUNT(*) FROM usuarios", fetch="one")[0]
        si1, si2, si3 = st.columns(3)
        with si1: card_metric("TOTAL REGISTROS",  f"{total_reg:,}", C_ACCENT)
        with si2: card_metric("USUARIOS ACTIVOS", str(total_usr),   C_SUCCESS)
        with si3: card_metric("BASE DE DATOS",    "☁️ Neon",        C_WARN)
    except Exception as e:
        st.error(f"Error: {e}")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    init_session()
    try:
        inicializar_db()   # cacheado — solo corre la primera vez
    except Exception as e:
        st.error(f"❌ No se pudo conectar a Neon: {e}")
        st.info("Verifica tu conexión a internet y que el servidor Neon esté activo.")
        st.cache_resource.clear()   # limpia caché para reintentar
        st.stop()

    if not st.session_state.logged_in:
        pantalla_login()
        return

    sidebar_nav()

    nav = st.session_state.nav
    if   nav == "Dashboard":     vista_dashboard()
    elif nav == "Registros":     vista_registros()
    elif nav == "Usuarios":      vista_usuarios()
    elif nav == "Configuración": vista_config()

if __name__ == "__main__":
    main()

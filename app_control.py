import streamlit as st
import hashlib
from datetime import datetime
from sqlalchemy import create_engine, text

# Configuración de página
st.set_page_config(page_title="Apex Pitch", layout="wide")

# Conexión maestra: Lee ÚNICAMENTE del Secret
@st.cache_resource
def get_engine():
    # Si esta línea falla, es que el nombre de la variable en Secrets no es 'db_url'
    url = st.secrets["db_url"]
    return create_engine(url, pool_pre_ping=True)

# Inicializar motor
try:
    engine = get_engine()
except Exception as e:
    st.error(f"Error de configuración en Secrets: {e}")
    st.stop()

# Lógica de Base de Datos
def inicializar_sistema():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nombre_usuario TEXT UNIQUE, contrasena_hash TEXT, rol_acceso TEXT);
            CREATE TABLE IF NOT EXISTS registros_picheo (id SERIAL PRIMARY KEY, fecha_registro TEXT, id_control TEXT, cantidad_picheos INTEGER, operador_responsable TEXT);
        """))

inicializar_sistema()

# Interfaz
if "login" not in st.session_state: st.session_state.login = False

if not st.session_state.login:
    st.title("⚾ APEX PITCH")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("ACCEDER"):
        with engine.connect() as conn:
            res = conn.execute(text("SELECT contrasena_hash, rol_acceso FROM usuarios WHERE nombre_usuario = :u"), {"u": u}).fetchone()
            if res and res[0] == hashlib.sha256(p.encode()).hexdigest():
                st.session_state.update({"login": True, "user": u, "rol": res[1]})
                st.rerun()
            else: st.error("Acceso denegado")
else:
    st.sidebar.title(f"Usuario: {st.session_state.user.upper()}")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.login = False
        st.rerun()
    st.header("Dashboard de Picheo")
    with engine.connect() as conn:
        total = conn.execute(text("SELECT SUM(cantidad_picheos) FROM registros_picheo")).scalar() or 0
    st.metric("Total Picheos", f"{total:,}")

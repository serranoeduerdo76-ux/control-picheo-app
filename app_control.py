import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime
from sqlalchemy import create_engine, text
import io

# Configuración de página
st.set_page_config(page_title="Apex Pitch", layout="wide")

# Conexión ultra-robusta a Neon
@st.cache_resource
def get_engine():
    # Obtenemos la URL desde Secrets
    url = st.secrets.get("db_url")
    if not url:
        st.error("🚨 Variable 'db_url' no encontrada en Secrets.")
        st.stop()
    
    # Limpieza automática: elimina parámetros que causan errores de 'channel_binding'
    if "?" in url:
        base_url = url.split("?")[0]
        url = f"{base_url}?sslmode=require"
        
    return create_engine(url, pool_size=5, max_overflow=10, pool_pre_ping=True)

try:
    engine = get_engine()
except Exception as e:
    st.error(f"Error fatal de conexión: {e}")
    st.stop()

# --- Estructura de base de datos ---
def inicializar_sistema():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nombre_usuario TEXT UNIQUE, contrasena_hash TEXT, rol_acceso TEXT);
            CREATE TABLE IF NOT EXISTS registros_picheo (id SERIAL PRIMARY KEY, fecha_registro TEXT, id_control TEXT, cantidad_picheos INTEGER, operador_responsable TEXT);
            CREATE TABLE IF NOT EXISTS configuracion_global (clave_parametro TEXT PRIMARY KEY, valor_parametro TEXT);
        """))
        # Crear usuario admin por defecto
        if conn.execute(text("SELECT COUNT(*) FROM usuarios WHERE nombre_usuario = 'admin'")).scalar() == 0:
            h = hashlib.sha256("admin123".encode()).hexdigest()
            conn.execute(text("INSERT INTO usuarios (nombre_usuario, contrasena_hash, rol_acceso) VALUES ('admin', :h, 'admin')"), {"h": h})
            conn.execute(text("INSERT INTO configuracion_global (clave_parametro, valor_parametro) VALUES ('tarifa_unidad', '0.024') ON CONFLICT DO NOTHING"))

inicializar_sistema()

# --- Interfaz de Login ---
if "login" not in st.session_state: st.session_state.login = False

if not st.session_state.login:
    st.title("⚾ APEX PITCH - INICIO")
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
    # --- Interfaz Principal ---
    st.sidebar.title(f"Usuario: {st.session_state.user.upper()}")
    menu = st.sidebar.radio("MENÚ", ["📊 Resumen", "📝 Registro"])
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.login = False
        st.rerun()

    if menu == "📊 Resumen":
        st.subheader("Métricas de Sistema")
        with engine.connect() as conn:
            data = conn.execute(text("SELECT SUM(cantidad_picheos) FROM registros_picheo")).scalar() or 0
        st.metric("Total Picheos", f"{data:,}")

    elif menu == "📝 Registro":
        with st.form("manual"):
            c = st.number_input("Cantidad", min_value=1)
            id_c = st.text_input("Código Control")
            if st.form_submit_button("Guardar"):
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO registros_picheo (fecha_registro, id_control, cantidad_picheos, operador_responsable) VALUES (:f, :id, :c, :o)"),
                                 {"f": str(datetime.now().date()), "id": id_c, "c": c, "o": st.session_state.user})
                st.success("Guardado")

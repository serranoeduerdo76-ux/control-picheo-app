import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime
from sqlalchemy import create_engine, text

# Configuración de página
st.set_page_config(page_title="Apex Pitch", layout="wide")

# Función de conexión simplificada al máximo
@st.cache_resource
def get_engine():
    try:
        url = st.secrets["db_url"]
        # Creamos el motor sin parámetros extraños que causan conflictos
        return create_engine(url, pool_pre_ping=True)
    except Exception as e:
        st.error(f"Error en configuración de conexión: {e}")
        st.stop()

# Intento de conexión con captura de error detallada
try:
    engine = get_engine()
    # Probamos la conexión inmediatamente
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
except Exception as e:
    st.error("--- ERROR DE CONEXIÓN A NEON ---")
    st.error(f"El sistema no pudo conectar con la base de datos.")
    st.error(f"Detalle técnico: {e}")
    st.stop()

# --- Lógica de Base de Datos ---
def inicializar_sistema():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY, 
                nombre_usuario TEXT UNIQUE, 
                contrasena_hash TEXT, 
                rol_acceso TEXT
            );
            CREATE TABLE IF NOT EXISTS registros_picheo (
                id SERIAL PRIMARY KEY, 
                fecha_registro TEXT, 
                id_control TEXT, 
                cantidad_picheos INTEGER, 
                operador_responsable TEXT
            );
        """))
        if conn.execute(text("SELECT COUNT(*) FROM usuarios")).scalar() == 0:
            h = hashlib.sha256("admin123".encode()).hexdigest()
            conn.execute(text("INSERT INTO usuarios (nombre_usuario, contrasena_hash, rol_acceso) VALUES ('admin', :h, 'admin')"), {"h": h})

inicializar_sistema()

# --- Interfaz Principal ---
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
    st.metric("Total Picheos en Servidor", f"{total:,}")

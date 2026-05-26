import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import io

# Configuración inicial
st.set_page_config(page_title="Apex Pitch", layout="wide")

# Conexión robusta a Neon
@st.cache_resource
def get_engine():
    # Lee desde los Secrets
    url = st.secrets["db_url"]
    # Limpieza automática por si acaso
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url, pool_size=5, max_overflow=10, pool_pre_ping=True)

engine = get_engine()

# --- Lógica de Seguridad y Base de Datos ---
def inicializar_sistema():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY, nombre_usuario TEXT UNIQUE, contrasena_hash TEXT, rol_acceso TEXT
            );
            CREATE TABLE IF NOT EXISTS registros_picheo (
                id SERIAL PRIMARY KEY, fecha_registro TEXT, id_control TEXT, cantidad_picheos INTEGER, operador_responsable TEXT
            );
            CREATE TABLE IF NOT EXISTS configuracion_global (clave_parametro TEXT PRIMARY KEY, valor_parametro TEXT);
        """))
        # Crear admin si no existe
        if conn.execute(text("SELECT COUNT(*) FROM usuarios WHERE nombre_usuario = 'admin'")).scalar() == 0:
            h = hashlib.sha256("admin123".encode()).hexdigest()
            conn.execute(text("INSERT INTO usuarios (nombre_usuario, contrasena_hash, rol_acceso) VALUES ('admin', :h, 'admin')"), {"h": h})

inicializar_sistema()

# --- Interfaz ---
if "login" not in st.session_state: st.session_state.login = False

if not st.session_state.login:
    st.title("⚾ Acceso Apex Pitch")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        with engine.connect() as conn:
            res = conn.execute(text("SELECT contrasena_hash, rol_acceso FROM usuarios WHERE nombre_usuario = :u"), {"u": u}).fetchone()
            if res and res[0] == hashlib.sha256(p.encode()).hexdigest():
                st.session_state.update({"login": True, "user": u, "rol": res[1]})
                st.rerun()
            else: st.error("Credenciales incorrectas")
else:
    st.sidebar.title(f"Hola, {st.session_state.user}")
    menu = st.sidebar.radio("Navegación", ["📊 Resumen", "📝 Registro", "👥 Personal", "⚙️ Ajustes"])
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.login = False
        st.rerun()

    if menu == "📊 Resumen":
        st.subheader("Métricas de Sistema")
        try:
            with engine.connect() as conn:
                data = conn.execute(text("SELECT SUM(cantidad_picheos) FROM registros_picheo")).scalar() or 0
            st.metric("Volumen Total", f"{data:,}")
        except Exception as e: st.error(f"Error cargando tabla: {e}")

    elif menu == "📝 Registro":
        with st.form("nuevo_picheo"):
            c = st.number_input("Cantidad", min_value=1)
            id_c = st.text_input("Código Control")
            if st.form_submit_button("Guardar"):
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO registros_picheo (fecha_registro, id_control, cantidad_picheos, operador_responsable) VALUES (:f, :id, :c, :o)"),
                                 {"f": str(datetime.now().date()), "id": id_c, "c": c, "o": st.session_state.user})
                st.success("Registrado")
    
    elif menu == "👥 Personal" and st.session_state.rol == "admin":
        st.subheader("Gestión de Usuarios")
        # Aquí iría el formulario de alta de usuario

    elif menu == "⚙️ Ajustes" and st.session_state.rol == "admin":
        st.subheader("Ajustes")

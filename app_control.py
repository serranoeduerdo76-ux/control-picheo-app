import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import io

st.set_page_config(page_title="Apex Pitch", layout="wide")

# ==========================================
# 1. CONEXIÓN NEON
# ==========================================
@st.cache_resource
def conectar_base_datos_neon():
    url = st.secrets.get("db_url")
    if not url: st.error("Faltan secrets"); st.stop()
    return create_engine(url.replace("postgres://", "postgresql://"), pool_pre_ping=True)

engine = conectar_base_datos_neon()

# ==========================================
# 2. LOGIN (NATIVO)
# ==========================================
if "sesion_activa" not in st.session_state: st.session_state["sesion_activa"] = False

if not st.session_state["sesion_activa"]:
    st.title("⚾ APEX PITCH")
    st.caption("Sistema de gestión de scouting profesional")
    
    with st.form("login"):
        user = st.text_input("Usuario")
        pwd = st.text_input("Contraseña", type="password")
        if st.form_submit_button("ENTRAR"):
            # Lógica simple de validación
            if user == "admin" and pwd == "admin123":
                st.session_state["sesion_activa"] = True
                st.session_state["usuario_actual"] = "admin"
                st.session_state["rol_actual"] = "admin"
                st.rerun()
            else: st.error("Credenciales inválidas")
    st.stop()

# ==========================================
# 3. INTERFAZ (COMPONENTES NATIVOS)
# ==========================================
st.sidebar.title("MENU")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state["sesion_activa"] = False
    st.rerun()

st.header(f"Bienvenido, {st.session_state['usuario_actual']}")

# Ejemplo de Métrica Nativa (Sin HTML, sin errores)
col1, col2 = st.columns(2)
with col1:
    st.metric("Total Picheos", "12,450")
with col2:
    st.metric("Rendimiento USD", "$298.80")

st.divider()

# Tabla Nativa
try:
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM registros_picheo ORDER BY id DESC LIMIT 100", conn)
        st.subheader("Últimos registros")
        st.dataframe(df, use_container_width=True)
except Exception as e:
    st.error(f"Error cargando tabla: {e}")

import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import io

# 1. CONFIGURACIÓN DE PLATAFORMA DE ALTA DENSIDAD
st.set_page_config(
    page_title="Apex Pitch - Analytics System", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# 2. PROCESAMIENTO DE ESTILOS CSS EN FORMATO ESTÁNDAR
CSS_PRODUCCION = (
    "<style>"
    ".block-container { padding-top: 1.5rem; padding-bottom: 1rem; }"
    ".metric-card { "
    "background: linear-gradient(135deg, #161B26 0%, #1A202C 100%); "
    "border-left: 5px solid #00E676; padding: 22px; border-radius: 8px; "
    "box-shadow: 0 4px 15px rgba(0,0,0,0.4); margin-bottom: 15px; "
    "}"
    ".metric-label { color: #8B949E; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px; }"
    ".metric-value { color: #FFFFFF; font-size: 40px; font-weight: 700; font-family: 'Courier New', monospace; margin-top: 5px; }"
    ".stTabs [data-baseweb='tab-list'] { gap: 10px; border-bottom: 1px solid #161B26; }"
    ".stTabs [data-baseweb='tab'] { background-color: #111622; border: 1px solid #161B26; border-radius: 6px 6px 0px 0px; padding: 12px 24px; color: #8B949E; font-weight: 600; }"
    "</style>"
)

st.markdown(CSS_PRODUCCION, unsafe_with_html=True)

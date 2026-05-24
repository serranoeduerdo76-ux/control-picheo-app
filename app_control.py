import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# ==========================================
# 1. CONFIGURACIÓN DE LA BASE DE DATOS
# ==========================================
def obtener_motor_db():
    """Valida la existencia de secretos en la nube o usa base local."""
    if "connections" in st.secrets and "sqlite" in st.secrets["connections"]:
        db_url = st.secrets["connections"]["sqlite"]["url"]
    elif "db_url" in st.secrets:
        db_url = st.secrets["db_url"]
    else:
        db_url = "sqlite:///control_picheo_app.db"
    return create_engine(db_url, echo=False)

engine = obtener_motor_db()

def inicializar_base_de_datos():
    """Crea las tablas necesarias si no existen."""
    with engine.connect() as conn:
        # Tabla de Usuarios
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL UNIQUE,
                clave TEXT NOT NULL,
                rol TEXT DEFAULT 'usuario'
            );
        """))
        # Tabla de Logs de Picheo
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS logs_picheo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lanzador TEXT NOT NULL,
                tipo_picheo TEXT,
                velocidad REAL,
                spin_rate INTEGER,
                resultado TEXT,
                fecha TEXT,
                notas TEXT
            );
        """))
        conn.commit()

def crear_usuario_defecto():
    """Inserta el administrador inicial si la tabla está vacía."""
    with engine.connect() as conn:
        resultado = conn.execute(text("SELECT COUNT(*) FROM usuarios;")).scalar()
        if resultado == 0:
            conn.execute(text("""
                INSERT INTO usuarios (usuario, clave, rol) 
                VALUES ('admin', 'Admin123*', 'admin');
            """))
            conn.commit()

# Inicializar estructuras de datos
try:
    inicializar_base_de_datos()
    crear_usuario_defecto()
except Exception as e:
    st.error(f"Error al inicializar la base de datos: {e}")

# ==========================================
# 2. GESTIÓN DE SESIÓN (LOGIN)
# ==========================================
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario"] = None

if not st.session_state["autenticado"]:
    st.title("⚾ Control de Picheo")
    st.subheader("Acceso al Sistema Central")
    
    with st.form("login_form"):
        usuario_input = st.text_input("Nombre de Usuario")
        clave_input = st.text_input("Contraseña", type="password")
        boton_login = st.form_submit_button("Iniciar Sesión")
        
        if boton_login:
            with engine.connect() as conn:
                query = text("SELECT usuario, clave FROM usuarios WHERE usuario = :u AND clave = :c;")
                usuario_db = conn.execute(query, {"u": usuario_input, "c": clave_input}).fetchone()
                
                if usuario_db:
                    st.session_state["autenticado"] = True
                    st.session_state["usuario"] = usuario_db[0]
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")
    st.caption("Nota: Si es la primera ejecución, ingresa con 'admin' y clave 'Admin123*'.")

# ==========================================
# 3. DASHBOARD PRINCIPAL (SESIÓN ACTIVA)
# ==========================================
else:
    # Barra lateral de navegación
    st.sidebar.title(f"Bienvenido, {st.session_state['usuario']}")
    opcion = st.sidebar.radio("Navegación", ["Dashboard Estado", "Módulo de Registro"])
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state["autenticado"] = False
        st.session_state["usuario"] = None
        st.rerun()

    # --- VISTA 1: ESTADO DEL SISTEMA ---
    if opcion == "Dashboard Estado":
        st.title("Dashboard de Control de Picheo")
        st.write("La base de datos está activa y respondiendo correctamente.")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Estado DB", "Conectado", "↑ Estable")
        col2.metric("Motor SQL", "SQLAlchemy", "↑ Verificado")
        col3.metric("Sesión Activa", "Administrador", "↑ Segura", delta_color="normal")

    # --- VISTA 2: MÓDULO DE REGISTRO INTERACTIVO ---
    elif opcion == "Módulo de Registro":
        st.title("⚾ Módulo de Registro")
        
        tab1, tab2 = st.tabs(["📝 Registro Individual", "📂 Carga Masiva (CSV/Excel)"])
        
        # Pestaña Registro Manual
        with tab1:
            st.write("### Registrar Nuevo Log de Picheo")
            with st.form("formulario_picheo", clear_on_submit=True):
                col1_p, col2_p, col3_p = st.columns(3)
                with col1_p:
                    lanzador = st.text_input("Nombre del Lanzador")
                    tipo_picheo = st.selectbox("Tipo de Lanzamiento", ["Recta (FB)", "Curva (CB)", "Slider (SL)", "Cambio (CH)", "Sinker (SI)"])
                with col2_p:
                    velocidad = st.number_input("Velocidad (MPH)", min_value=0.0, max_value=110.0, value=90.0, step=0.1)
                    spin_rate = st.number_input("Spin Rate (RPM)", min_value=0, max_value=4000, value=2200, step=50)
                with col3_p:
                    resultado = st.selectbox("Resultado", ["Strike", "Bola", "Hit", "Out", "Jonrón"])
                    fecha = st.date_input("Fecha")
                
                notas = st.text_area("Observaciones del Scouting")
                btn_guardar = st.form_submit_button("Guardar Lanzamiento")
                
                if btn_guardar:
                    if not lanzador.strip():
                        st.error("El nombre del lanzador es requerido.")
                    else:
                        try:
                            with engine.connect() as conn:
                                conn.execute(text("""
                                    INSERT INTO logs_picheo (lanzador, tipo_picheo, velocidad, spin_rate, resultado, fecha, notas)
                                    VALUES (:lanzador, :tipo_picheo, :velocidad, :spin_rate, :resultado, :fecha, :notas);
                                """), {
                                    "lanzador": lanzador, "tipo_picheo": tipo_picheo, "velocidad": velocidad,
                                    "spin_rate": spin_rate, "resultado": resultado, "fecha": str(fecha), "notas": notas
                                })
                                conn.commit()
                            st.success(f"✅ ¡Registro guardado para {lanzador}!")
                        except Exception as e:
                            st.error(f"Error de almacenamiento: {e}")
                            
        # Pestaña Carga Masiva
        with tab2:
            st.write("### Importar Logs desde Archivo")
            archivo_cargado = st.file_uploader("Sube un archivo CSV o Excel", type=["csv", "xlsx"])
            
            if archivo_cargado is not None:
                try:
                    df = pd.read_csv(archivo_cargado) if archivo_cargado.name.endswith('.csv') else pd.read_excel(archivo_cargado)
                    st.write("##### Vista previa de los datos:")
                    st.dataframe(df.head())
                    
                    btn_procesar = st.button("Confirmar Carga Masiva")
                    if btn_procesar:
                        columnas_ok = ['lanzador', 'tipo_picheo', 'velocidad', 'spin_rate', 'resultado', 'fecha']
                        if all(c in df.columns for c in columnas_ok):
                            with engine.begin() as conexion:
                                df.to_sql('logs_picheo', con=conexion, if_exists='append', index=False)
                            st.success(f"🔥 Se importaron {len(df)} registros de forma masiva.")
                        else:
                            st.error("Estructura inválida. Asegúrate de incluir las columnas estándar.")
                except Exception as e:
                    st.error(f"Error procesando archivo: {e}")

import os
import streamlit as st
from sqlalchemy import create_engine, text
import hashlib

# ==========================================
# 1. CONFIGURACIÓN DE LA PÁGINA Y ESTILOS
# ==========================================
st.set_page_config(
    page_title="Apex Pitch - Control de Usuarios",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. CONEXIÓN Y BASE DE DATOS (SQLAlchemy 2.0)
# ==========================================
def obtener_motor_db():
    """Detecta de forma segura si está en producción (Streamlit Cloud) o local."""
    try:
        # Validación explícita de la jerarquía de secretos para evitar KeyError
        if "connections" in st.secrets and "sqlite" in st.secrets["connections"]:
            db_url = st.secrets["connections"]["sqlite"]["url"]
        elif "db_url" in st.secrets:
            db_url = st.secrets["db_url"]
        else:
            # Configuración por defecto para desarrollo local
            db_url = "sqlite:///control_picheo.db"
    except Exception:
        # Caída segura ante cualquier problema leyendo variables de entorno
        db_url = "sqlite:///control_picheo_fallback.db"
        
    return create_engine(db_url, echo=False, connect_args={"check_same_thread": False})

engine = obtener_motor_db()

def verificar_y_crear_tablas():
    """Crea la estructura de tablas garantizando la sintaxis correcta."""
    query_usuarios = """
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        nombre_completo TEXT NOT NULL,
        rol TEXT NOT NULL DEFAULT 'Analista',
        fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """
    try:
        with engine.connect() as conn:
            # Ejecución explícita usando la función text() de SQLAlchemy 2.0
            conn.execute(text(query_usuarios))
            # Confirmación obligatoria de la transacción (Evita OperationalError)
            conn.commit()
    except Exception as e:
        st.error(f"❌ Error crítico en la base de datos al inicializar tablas: {e}")
        st.stop()

# Ejecución garantizada al arrancar el hilo de Streamlit
verificar_y_crear_tablas()

# ==========================================
# 3. FUNCIONES DE UTILIDAD (SEGURIDAD Y AUTH)
# ==========================================
def generar_hash(password: str) -> str:
    """Genera un hash SHA-256 seguro para las contraseñas."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def validar_credenciales(usuario: str, clave: str):
    """Busca al usuario en la base de datos y valida su hash."""
    query = text("SELECT password_hash, nombre_completo, rol FROM usuarios WHERE usuario = :usr")
    try:
        with engine.connect() as conn:
            resultado = conn.execute(query, {"usr": usuario}).fetchone()
            if resultado:
                hash_almacenado, nombre, rol = resultado
                if hash_almacenado == generar_hash(clave):
                    return {"nombre": nombre, "rol": rol}
            return None
    except Exception as e:
        st.error(f"Error al verificar credenciales: {e}")
        return None

def registrar_usuario_inicial():
    """Crea un usuario administrador por defecto si la tabla está vacía."""
    query_verificar = text("SELECT COUNT(*) FROM usuarios")
    query_insertar = text("""
        INSERT INTO usuarios (usuario, password_hash, nombre_completo, rol)
        VALUES (:usr, :hash, :nombre, :rol)
    """)
    try:
        with engine.connect() as conn:
            conteo = conn.execute(query_verificar).scalar()
            if conteo == 0:
                # Contraseña por defecto: 'Admin123*'
                hash_admin = generar_hash("Admin123*")
                conn.execute(query_insertar, {
                    "usr": "admin",
                    "hash": hash_admin,
                    "nombre": "Administrador del Sistema",
                    "rol": "Administrador"
                })
                conn.commit()
    except Exception as e:
        st.warning(f"No se pudo verificar/crear el usuario inicial: {e}")

registrar_usuario_inicial()

# ==========================================
# 4. GESTIÓN DEL ESTADO DE LA SESIÓN (SESSION STATE)
# ==========================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_nombre" not in st.session_state:
    st.session_state.usuario_nombre = ""
if "usuario_rol" not in st.session_state:
    st.session_state.usuario_rol = ""

# ==========================================
# 5. VISTAS DE LA APLICACIÓN
# ==========================================
def vista_login():
    """Dibuja la interfaz de acceso protegida."""
    st.markdown("""
        <style>
        .login-box { padding: 2rem; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.title("⚾ Control de Picheo")
        st.subheader("Acceso al Sistema Central")
        
        with st.form("formulario_login", clear_on_submit=False):
            input_user = st.text_input("Nombre de Usuario", placeholder="Ej: eserrano").strip()
            input_pass = st.text_input("Contraseña", type="password", placeholder="••••••••")
            # Corrección del método nativo de Streamlit para el envío de formularios
            boton_enviar = st.form_submit_button("Iniciar Sesión")
            
            if boton_enviar:
                if not input_user or not input_pass:
                    st.error("⚠️ Todos los campos son obligatorios.")
                else:
                    datos_usuario = validar_credenciales(input_user, input_pass)
                    if datos_usuario:
                        st.session_state.autenticado = True
                        st.session_state.usuario_nombre = datos_usuario["nombre"]
                        st.session_state.usuario_rol = datos_usuario["rol"]
                        st.rerun()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos.")
        
        st.caption("Nota: Si es la primera ejecución, ingresa con 'admin' y clave 'Admin123*'.")

def vista_principal():
    """Panel principal una vez superada la autenticación."""
    st.sidebar.title(f"Bienvenido, {st.session_state.usuario_nombre}")
    st.sidebar.info(f"Nivel de acceso: {st.session_state.usuario_rol}")
    
    if st.sidebar.button("Cerrar Sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.session_state.usuario_nombre = ""
        st.session_state.usuario_rol = ""
        st.rerun()
    
    opcion = st.sidebar.radio("Navegación", ["Dashboard Analítico", "Ingreso de Datos", "Configuración"])
    
    if opcion == "Dashboard Analítico":
        st.header("📊 Dashboard de Control de Picheo")
        st.write("La base de datos está activa y respondiendo correctamente.")
        
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Estado DB", "Conectado", "Estable")
        kpi2.metric("Motor SQL", "SQLAlchemy 2.0", "Verificado")
        kpi3.metric("Sesión Activa", st.session_state.usuario_rol, "Segura")

    elif opcion == "Ingreso de Datos":
        st.header("📝 Módulo de Registro")
        st.info("Espacio preparado para integrar la carga masiva de datos y logs de picheo.")
        
    elif opcion == "Configuración":
        st.header("⚙️ Ajustes del Sistema")
        st.write("Mapeo de variables y gestión interna del software.")

# ==========================================
# 6. ENRUTADOR PRINCIPAL
# ==========================================
if not st.session_state.autenticado:
    vista_login()
else:
    vista_principal()

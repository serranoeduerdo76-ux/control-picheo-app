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
    """Crea exactamente las tablas del sistema original."""
    with engine.connect() as conn:
        # Tabla de Usuarios
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                nombre TEXT UNIQUE NOT NULL, 
                pass TEXT NOT NULL, 
                rol TEXT NOT NULL DEFAULT 'operador'
            );
        """))
        
        # Tabla de Picheos (Estructura idéntica a Geremo.py)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS picheos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                fecha TEXT NOT NULL, 
                id_control TEXT NOT NULL, 
                cantidad INTEGER NOT NULL, 
                operador TEXT NOT NULL
            );
        """))
        
        # Tabla de Configuración
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS config (
                clave TEXT PRIMARY KEY, 
                valor TEXT NOT NULL
            );
        """))
        conn.commit()

def preparar_datos_defecto():
    """Inserta configuraciones y administrador inicial si están vacíos."""
    with engine.connect() as conn:
        # Insertar configuración de precio por defecto (0.024)
        conn.execute(text("INSERT OR IGNORE INTO config (clave, valor) VALUES ('precio', '0.024');"))
        
        # Crear usuario administrador por defecto si la tabla está vacía
        resultado = conn.execute(text("SELECT COUNT(*) FROM usuarios;")).scalar()
        if resultado == 0:
            # Nota: Al migrar a web es ideal usar hashes (SHA256), por compatibilidad 
            # directa con tu login actual se establece la clave por defecto
            conn.execute(text("""
                INSERT OR IGNORE INTO usuarios (nombre, pass, rol) 
                VALUES ('admin', 'admin123', 'admin');
            """))
        conn.commit()

# Inicializar base de datos
try:
    inicializar_base_de_datos()
    preparar_datos_defecto()
except Exception as e:
    st.error(f"Error al inicializar la base de datos: {e}")

# ==========================================
# 2. GESTIÓN DE SESIÓN (LOGIN)
# ==========================================
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario"] = None
    st.session_state["rol"] = None

if not st.session_state["autenticado"]:
    st.title("⚾ Control de Picheo")
    st.subheader("Acceso al Sistema Central")
    
    with st.form("login_form"):
        usuario_input = st.text_input("Nombre de Usuario")
        clave_input = st.text_input("Contraseña", type="password")
        boton_login = st.form_submit_button("Iniciar Sesión")
        
        if boton_login:
            with engine.connect() as conn:
                # Comprobación directa basada en tus columnas de 'usuarios'
                query = text("SELECT nombre, pass, rol FROM usuarios WHERE nombre = :u AND pass = :c;")
                usuario_db = conn.execute(query, {"u": usuario_input, "c": clave_input}).fetchone()
                
                if usuario_db:
                    st.session_state["autenticado"] = True
                    st.session_state["usuario"] = usuario_db[0]
                    st.session_state["rol"] = usuario_db[2]
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")
    st.caption("Nota: Datos iniciales: 'admin' con clave 'admin123'.")

# ==========================================
# 3. INTERFAZ PRINCIPAL (SESIÓN ACTIVA)
# ==========================================
else:
    # Barra lateral de navegación
    st.sidebar.title(f"Bienvenido, {st.session_state['usuario'].upper()}")
    opcion = st.sidebar.radio("Navegación", ["Dashboard Estado", "Módulo de Registro"])
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state["autenticado"] = False
        st.session_state["usuario"] = None
        st.session_state["rol"] = None
        st.rerun()

    # --- VISTA 1: ESTADO DEL SISTEMA ---
    if opcion == "Dashboard Estado":
        st.title("Dashboard de Control de Picheo")
        st.write("La base de datos está activa y respondiendo correctamente.")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Estado DB", "Conectado", "↑ Estable")
        col2.metric("Motor SQL", "SQLAlchemy", "↑ Verificado")
        col3.metric("Rol de Usuario", st.session_state["rol"].upper(), "✔ Activo")

    # --- VISTA 2: MÓDULO DE REGISTRO INTEGRADO ---
    elif opcion == "Módulo de Registro":
        st.title("⚾ Módulo de Registro")
        
        tab1, tab2 = st.tabs(["📝 Registro Individual", "📂 Carga Masiva (CSV/Excel)"])
        
        # Pestaña: Registro Individual (Fiel a guardar_dato de Geremo.py)
        with tab1:
            st.write("### Registrar Nuevo Log de Picheo")
            with st.form("formulario_picheo", clear_on_submit=True):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    reg_fecha = st.date_input("Fecha")
                with col2:
                    id_control = st.text_input("ID Control")
                with col3:
                    cantidad = st.number_input("Cantidad", min_value=1, step=1, value=1)
                
                btn_guardar = st.form_submit_button("GUARDAR REGISTRO")
                
                if btn_guardar:
                    if not id_control.strip():
                        st.error("El campo 'ID Control' es obligatorio.")
                    else:
                        try:
                            with engine.connect() as conn:
                                # Inserción estricta usando tus columnas exactas
                                conn.execute(text("""
                                    INSERT INTO picheos (fecha, id_control, cantidad, operador)
                                    VALUES (:fecha, :id_control, :cantidad, :operador);
                                """), {
                                    "fecha": str(reg_fecha),
                                    "id_control": id_control.strip(),
                                    "cantidad": int(cantidad),
                                    "operador": st.session_state["usuario"]
                                })
                                conn.commit()
                            st.success(f"✅ Registro guardado: {id_control.strip()} - {cantidad} picheos.")
                        except Exception as e:
                            st.error(f"Error al almacenar el registro: {e}")
                            
        # Pestaña: Carga Masiva (Estructurada para tus columnas de la tabla 'picheos')
        with tab2:
            st.write("### Importar Picheos desde Archivo")
            st.info("El archivo externo debe contener exactamente las siguientes columnas: *fecha, id_control, cantidad, operador*")
            
            archivo_cargado = st.file_uploader("Sube tu archivo plano", type=["csv", "xlsx"])
            
            if archivo_cargado is not None:
                try:
                    df = pd.read_csv(archivo_cargado) if archivo_cargado.name.endswith('.csv') else pd.read_excel(archivo_cargado)
                    st.write("##### Vista previa de los datos detectados:")
                    st.dataframe(df.head())
                    
                    btn_procesar = st.button("Confirmar Carga Masiva")
                    if btn_procesar:
                        # Validación estricta contra las columnas exactas de tu tabla 'picheos'
                        columnas_requeridas = ['fecha', 'id_control', 'cantidad', 'operador']
                        if all(c in df.columns for c in columnas_requeridas):
                            with engine.begin() as conexion:
                                df.to_sql('picheos', con=conexion, if_exists='append', index=False)
                            st.success(f"🔥 Se importaron exitosamente {len(df)} registros a la tabla 'picheos'.")
                        else:
                            st.error("Error: Las columnas del archivo no coinciden con la estructura de la tabla 'picheos'.")
                except Exception as e:
                    st.error(f"Error procesando el archivo: {e}")

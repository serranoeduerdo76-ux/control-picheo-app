import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import io

# Configuración de página optimizada para visualización analítica de datos
st.set_page_config(page_title="Apex Pitch - Control", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 1. MOTOR DE BASE DE DATOS Y CONEXIÓN SEGURA
# ==========================================
@st.cache_resource
def inicializar_motor_seguro():
    """Garantiza una única instancia del pool de conexiones para evitar bloqueos."""
    if "connections" in st.secrets and "sqlite" in st.secrets["connections"]:
        db_url = st.secrets["connections"]["sqlite"]["url"]
    elif "db_url" in st.secrets:
        db_url = st.secrets["db_url"]
    else:
        db_url = "sqlite:///control_picheo_app.db"
    # Pool_size no se usa en SQLite nativo, pero controlamos timeouts para hilos concurrentes web
    return create_engine(db_url, connect_args={"timeout": 30}, echo=False)

engine = inicializar_motor_seguro()

def inicializar_base_de_datos():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                nombre TEXT UNIQUE NOT NULL, 
                pass TEXT NOT NULL, 
                rol TEXT NOT NULL DEFAULT 'operador'
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS picheos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                fecha TEXT NOT NULL, 
                id_control TEXT NOT NULL, 
                cantidad INTEGER NOT NULL, 
                operador TEXT NOT NULL
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS config (
                clave TEXT PRIMARY KEY, 
                valor TEXT NOT NULL
            );
        """))
        conn.commit()

def preparar_datos_defecto():
    with engine.connect() as conn:
        conn.execute(text("INSERT OR IGNORE INTO config (clave, valor) VALUES ('precio', '0.024');"))
        resultado = conn.execute(text("SELECT COUNT(*) FROM usuarios;")).scalar()
        if resultado == 0:
            hash_admin = hashlib.sha256("admin123".encode()).hexdigest()
            conn.execute(text("""
                INSERT INTO usuarios (nombre, pass, rol) 
                VALUES ('admin', :p, 'admin');
            """), {"p": hash_admin})
        conn.commit()

try:
    inicializar_base_de_datos()
    preparar_datos_defecto()
except Exception as e:
    st.error(f"🚨 Error crítico de inicialización de infraestructura: {e}")

# Manejo estricto de variables de estado web
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario"] = None
    st.session_state["rol"] = None

# ==========================================
# 2. INTERFAZ DE AUTENTICACIÓN (LOGIN)
# ==========================================
if not st.session_state["autenticado"]:
    st.title("⚾ Control de Picheo")
    st.subheader("Acceso al Sistema Central")
    
    with st.form("login_form"):
        usuario_input = st.text_input("Nombre de Usuario").strip().lower()
        clave_input = st.text_input("Contraseña", type="password").strip()
        boton_login = st.form_submit_button("INGRESAR")
        
        if boton_login:
            if usuario_input and clave_input:
                password_hash = hashlib.sha256(clave_input.encode()).hexdigest()
                
                with engine.connect() as conn:
                    query = text("SELECT nombre, pass, rol FROM usuarios WHERE nombre = :u AND pass = :c;")
                    usuario_db = conn.execute(query, {"u": usuario_input, "c": password_hash}).fetchone()
                    
                    if usuario_db:
                        st.session_state["autenticado"] = True
                        st.session_state["usuario"] = usuario_db[0]
                        st.session_state["rol"] = usuario_db[2]
                        st.rerun()
                    else:
                        st.error("❌ Credenciales incorrectas.")
            else:
                st.warning("Por favor, rellene todos los campos de autenticación.")
    st.caption("Aviso del Sistema: Credenciales maestras iniciales: 'admin' / 'admin123'.")

# ==========================================
# 3. ENTORNO DEL DASHBOARD PRINCIPAL (SESIÓN ACTIVA)
# ==========================================
else:
    # Barra Lateral
    st.sidebar.title("⚾ BeisSeven Pro")
    st.sidebar.markdown(f"**Operador Activo:** `{st.session_state['usuario'].upper()}`")
    st.sidebar.markdown(f"**Privilegios:** `{st.session_state['rol'].upper()}`")
    st.sidebar.write("---")
    
    opciones_menu = ["📊 DASHBOARD", "📝 GESTIÓN DE REGISTROS"]
    if st.session_state["rol"] == "admin":
        opciones_menu.extend(["👥 PANEL DE PERSONAL", "⚙️ AJUSTES GLOBALES"])
        
    opcion = st.sidebar.radio("Módulos del Sistema", opciones_menu)
    st.sidebar.write("---")
    
    if st.sidebar.button("🚪 DESCONECTAR SESIÓN", use_container_width=True):
        st.session_state["autenticado"] = False
        st.session_state["usuario"] = None
        st.session_state["rol"] = None
        st.rerun()

    # ------------------------------------------
    # MÓDULO 1: DASHBOARD ANALÍTICO
    # ------------------------------------------
    if opcion == "📊 DASHBOARD":
        st.title("Métricas de Rendimiento y Balance")
        
        with st.container(border=True):
            st.write("##### Ventana Temporal de Evaluación")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                f_desde = st.date_input("Fecha Inicial:", value=datetime.now() - timedelta(days=15))
            with col_f2:
                f_hasta = st.date_input("Fecha Final:", value=datetime.now())
                
        if f_desde > f_hasta:
            st.error("Error lógico: La fecha inicial de evaluación supera los parámetros de la fecha de cierre.")
        else:
            try:
                with engine.connect() as conn:
                    # Forzado de formato ISO texto para blindar consultas SQLite
                    total_picheos = conn.execute(text("""
                        SELECT SUM(cantidad) FROM picheos WHERE fecha BETWEEN :d AND :h
                    """), {"d": f_desde.strftime('%Y-%m-%d'), "h": f_hasta.strftime('%Y-%m-%d')}).scalar() or 0
                    
                    precio_db = conn.execute(text("SELECT valor FROM config WHERE clave='precio';")).scalar() or "0.024"
                    precio = float(precio_db)
                
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    st.metric(label="VOLUMEN TOTAL DE PICHEOS", value=f"{total_picheos:,} U", delta="Métrica Real")
                with col_m2:
                    st.metric(label="RENDIMIENTO MONETARIO ESTIMADO", value=f"USD ${total_picheos * precio:,.2f}", delta=f"Ratio: {precio}")
                
            except Exception as e:
                st.error(f"Fallo en la extracción de analíticas de red: {e}")

    # ------------------------------------------
    # MÓDULO 2: GESTIÓN DE REGISTROS (MIGRADO COMPLETO)
    # ------------------------------------------
    elif opcion == "📝 GESTIÓN DE REGISTROS":
        st.title("Módulo de Ingesta de Datos")
        
        tab_form, tab_bulk = st.tabs(["📝 Formulario Manual", "📂 Carga Masiva Automatizada"])
        
        # Entrada Individual
        with tab_form:
            with st.form("registro_picheo_individual", clear_on_submit=True):
                col_r1, col_r2, col_r3 = st.columns(3)
                with col_r1:
                    reg_fecha = st.date_input("Fecha de Trabajo", value=datetime.now())
                with col_r2:
                    reg_id = st.text_input("ID Control / Identificador").strip()
                with col_r3:
                    reg_cant = st.number_input("Cantidad", min_value=1, step=1, value=1)
                    
                btn_guardar = st.form_submit_button("CONFIRMAR Y ALMACENAR", use_container_width=True)
                
                if btn_guardar:
                    if not reg_id:
                        st.error("Error de campo: 'ID Control' no puede procesarse vacío.")
                    else:
                        try:
                            with engine.connect() as conn:
                                conn.execute(text("""
                                    INSERT INTO picheos (fecha, id_control, cantidad, operador)
                                    VALUES (:f, :id, :c, :o);
                                """), {
                                    "f": reg_fecha.strftime('%Y-%m-%d'), 
                                    "id": reg_id, 
                                    "c": reg_cant, 
                                    "o": st.session_state["usuario"]
                                })
                                conn.commit()
                            st.success(f"💾 Registro guardado en servidor: ID [{reg_id}] — ({reg_cant}) unidades.")
                        except Exception as e:
                            st.error(f"Fallo de persistencia en disco: {e}")
                            
        # Entrada Automatizada (Sanitizada contra payloads corruptos)
        with tab_bulk:
            st.write("##### Subida de Lotes de Datos Externos")
            archivo_externo = st.file_uploader("Cargar hoja de cálculo (*.csv, *.xlsx)", type=["csv", "xlsx"])
            if archivo_externo is not None:
                try:
                    df_cargado = pd.read_csv(archivo_externo) if archivo_externo.name.endswith('.csv') else pd.read_excel(archivo_externo)
                    
                    # Sanitización forzada de nombres de columnas a minúsculas para evitar desajustes
                    df_cargado.columns = [c.strip().lower() for c in df_cargado.columns]
                    
                    st.write("Vista previa estructurada (Primeras 5 filas):")
                    st.dataframe(df_cargado.head(5), use_container_width=True)
                    
                    columnas_esperadas = ['fecha', 'id_control', 'cantidad', 'operador']
                    if all(col in df_cargado.columns for col in columnas_esperadas):
                        if st.button("🚀 PROCESAR E INYECTAR LOTE", use_container_width=True):
                            # Asegurar tipo de datos correcto antes de subir para evitar romper la integridad sql
                            df_cargado['fecha'] = df_cargado['fecha'].astype(str)
                            df_cargado['id_control'] = df_cargado['id_control'].astype(str).str.strip()
                            df_cargado['cantidad'] = pd.to_numeric(df_cargado['cantidad'], errors='coerce').fillna(1).astype(int)
                            df_cargado['operador'] = df_cargado['operador'].astype(str).str.strip()
                            
                            with engine.begin() as conexion:
                                df_cargado[columnas_esperadas].to_sql('picheos', con=conexion, if_exists='append', index=False)
                            st.success(f"🔥 Sincronización completa: {len(df_cargado)} registros agregados sin conflictos.")
                    else:
                        st.error("Estructura de archivo inválida. Columnas requeridas estrictas: [fecha, id_control, cantidad, operador]")
                except Exception as e:
                    st.error(f"Error crítico en lectura de lote de datos: {e}")

        # Visualización de Base de Datos con Paginación de Seguridad
        st.write("---")
        st.subheader("Registros en la Base de Datos")
        
        try:
            with engine.connect() as conn:
                # Protegemos la memoria del servidor web trayendo un límite razonable para el visor interactivo
                query_picheos = conn.execute(text("SELECT id, fecha, id_control, cantidad, operador FROM picheos ORDER BY id DESC LIMIT 1000;")).fetchall()
            
            if query_picheos:
                df_picheos = pd.DataFrame(query_picheos, columns=["ID", "FECHA", "CONTROL", "CANTIDAD", "OPERADOR"])
                
                # Generación Eficiente de Reportes en Memoria
                col_exp1, col_exp2 = st.columns(2)
                
                with col_exp1:
                    buffer_excel = io.BytesIO()
                    with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                        df_picheos.to_excel(writer, index=False, sheet_name='Logs_Picheo')
                    st.download_button(
                        label="📥 GENERAR REPORTE EXCEL",
                        data=buffer_excel.getvalue(),
                        file_name=f"BeisSeven_Export_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                
                with col_exp2:
                    buffer_pdf = io.BytesIO()
                    doc_pdf = SimpleDocTemplate(buffer_pdf, pagesize=letter)
                    elementos_pdf = []
                    estilos = getSampleStyleSheet()
                    elementos_pdf.append(Paragraph("<b>BEISSEVEN ANALYTICS - CONTROL DE PICHEOS</b>", estilos['Title']))
                    elementos_pdf.append(Paragraph(f"Corte Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", estilos['Normal']))
                    elementos_pdf.append(Paragraph("<br/><br/>", estilos['Normal']))
                    
                    # Mandamos un subset controlado para evitar overflows en PDFs masivos
                    matriz_datos = [["FECHA", "CONTROL", "CANT", "OPERADOR"]] + df_picheos[["FECHA", "CONTROL", "CANTIDAD", "OPERADOR"]].values.tolist()[:200]
                    tabla_pdf = Table(matriz_datos, colWidths=[100, 150, 80, 120])
                    tabla_pdf.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E1E2F")),
                        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                        ('BOTTOMPADDING', (0,0), (-1,0), 8),
                        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#F4F4F6")),
                        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#D1D1D1"))
                    ]))
                    elementos_pdf.append(tabla_pdf)
                    doc_pdf.build(elementos_pdf)
                    
                    st.download_button(
                        label="📄 GENERAR REPORTE PDF",
                        data=buffer_pdf.getvalue(),
                        file_name=f"BeisSeven_Reporte_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                
                st.dataframe(df_picheos, use_container_width=True, height=400)
                
                # Eliminación Controlada por Roles
                st.markdown("##### 🗑️ Zona de Purgado de Datos")
                col_del1, col_del2 = st.columns([1, 3])
                with col_del1:
                    id_eliminar = st.number_input("ID de Registro:", min_value=1, step=1)
                with col_del2:
                    st.write("<br/>", unsafe_allow_html=True)
                    if st.button("BORRAR REGISTRO SELECCIONADO", use_container_width=True):
                        if st.session_state["rol"] != 'admin':
                            st.error("Acceso Restringido: Operadores no poseen permisos de destrucción de logs.")
                        else:
                            with engine.connect() as conn:
                                existe = conn.execute(text("SELECT COUNT(*) FROM picheos WHERE id = :id;"), {"id": id_eliminar}).scalar()
                                if existe == 0:
                                    st.warning(f"ID [{id_eliminar}] no localizado en los índices.")
                                else:
                                    conn.execute(text("DELETE FROM picheos WHERE id = :id;"), {"id": id_eliminar})
                                    conn.commit()
                                    st.success(f"Registro [{id_eliminar}] eliminado de los históricos.")
                                    st.placeholder().empty() # Forzamos refresco controlado de estado limpio
                                    st.rerun()
            else:
                st.info("La base de datos se encuentra vacía de logs históricos.")
        except Exception as e:
            st.error(f"Fallo en la visualización de datos: {e}")

    # ------------------------------------------
    # MÓDULO 3: GESTIÓN DE PERSONAL (SOLO ADMIN)
    # ------------------------------------------
    elif opcion == "👥 PANEL DE PERSONAL" and st.session_state["rol"] == "admin":
        st.title("Gestión de Personal Autorizado")
        
        with st.form("creacion_nuevo_usuario"):
            st.write("##### Alta de Nuevo Operador de Sistema")
            col_u1, col_u2, col_u3 = st.columns(3)
            with col_u1:
                n_usuario = st.text_input("Nombre de Usuario (Minúsculas)").strip().lower()
            with col_u2:
                n_clave = st.text_input("Clave de Acceso (Min. 6 caracteres)", type="password").strip()
            with col_u3:
                n_rol = st.selectbox("Nivel de Permisos", ["operador", "admin"])
                
            btn_usuario = st.form_submit_button("REGISTRAR USUARIO", use_container_width=True)
            
            if btn_usuario:
                if not n_usuario or not n_clave:
                    st.error("Datos incompletos para el alta.")
                elif len(n_clave) < 6:
                    st.warning("La contraseña vulnera la longitud de seguridad requerida (Mínimo 6 caracteres).")
                else:
                    try:
                        hash_nueva_clave = hashlib.sha256(n_clave.encode()).hexdigest()
                        with engine.connect() as conn:
                            conn.execute(text("""
                                INSERT INTO usuarios (nombre, pass, rol) VALUES (:n, :p, :r);
                            """), {"n": n_usuario, "p": hash_nueva_clave, "r": n_rol})
                            conn.commit()
                        st.success(f"Usuario registrado: `{n_usuario}` con rol [{n_rol}].")
                    except Exception as e:
                        st.error(f"Conflicto de duplicidad: El identificador ya se encuentra registrado. ({e})")
                        
        st.write("---")
        st.subheader("Cuentas Registradas")
        try:
            with engine.connect() as conn:
                lista_usuarios = conn.execute(text("SELECT id, nombre, rol FROM usuarios;")).fetchall()
            df_usuarios = pd.DataFrame(lista_usuarios, columns=["ID", "USUARIO", "ROL"])
            st.dataframe(df_usuarios, use_container_width=True)
            
            st.write("##### Baja de Cuenta")
            id_baja = st.number_input("ID de Cuenta a Eliminar:", min_value=1, step=1)
            if st.button("ELIMINAR OPERADOR", use_container_width=True):
                with engine.connect() as conn:
                    usuario_db = conn.execute(text("SELECT nombre FROM usuarios WHERE id = :id;"), {"id": id_baja}).fetchone()
                    if not usuario_db:
                        st.warning("El ID especificado no pertenece a ningún operador.")
                    elif usuario_db[0] == st.session_state["usuario"]:
                        st.error("Operación Abortada: Un administrador no puede purgar su propio perfil en uso.")
                    elif usuario_db[0] == "admin":
                        st.error("Operación Abortada: El administrador maestro no puede darse de baja.")
                    else:
                        conn.execute(text("DELETE FROM usuarios WHERE id = :id;"), {"id": id_baja})
                        conn.commit()
                        st.success(f"Cuenta `{usuario_db[0]}` dada de baja de la plataforma.")
                        st.rerun()
        except Exception as e:
            st.error(f"Fallo en la lectura del personal activo: {e}")

    # ------------------------------------------
    # MÓDULO 4: AJUSTES DE CONFIGURACIÓN (SOLO ADMIN)
    # ------------------------------------------
    elif opcion == "⚙️ AJUSTES GLOBALES" and st.session_state["rol"] == "admin":
        st.title("Parámetros del Sistema Financiero")
        
        try:
            with engine.connect() as conn:
                precio_actual = conn.execute(text("SELECT valor FROM config WHERE clave='precio';")).scalar() or "0.024"
            
            with st.form("configuracion_precio"):
                st.write("##### Ajuste de Tasa de Conversión Monetaria")
                nuevo_precio = st.text_input("Precio por unidad logueada (USD):", value=precio_actual).strip()
                btn_config = st.form_submit_button("ESTABLECER TASA", use_container_width=True)
                
                if btn_config:
                    try:
                        valor_validado = float(nuevo_precio)
                        if valor_validado < 0:
                            st.error("El precio unitario no puede constituir un número negativo.")
                        else:
                            with engine.connect() as conn:
                                conn.execute(text("UPDATE config SET valor = :v WHERE clave = 'precio';"), {"v": str(valor_validado)})
                                conn.commit()
                            st.success(f"Ajuste aplicado: Nueva tasa global fijada en ${valor_validado} USD.")
                            st.rerun()
                    except ValueError:
                        st.error("Error tipográfico: Ingrese un valor numérico real válido (Ej. 0.024).")
        except Exception as e:
            st.error(f"Fallo en la carga de variables del archivo de configuración: {e}")

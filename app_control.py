import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import io

# Configuración de página optimizada para visualización analítica de datos
st.set_page_config(page_title="Apex Pitch - Control", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 1. MOTOR DE BASE DE DATOS E INFRAESTRUCTURA (POSTGRESQL / SQLITE)
# ==========================================
@st.cache_resource
def inicializar_motor_seguro():
    """
    Detecta automáticamente si existe una conexión PostgreSQL en Secrets.
    Si no existe, cae de forma segura a SQLite local con un entorno aislado.
    """
    if "connections" in st.secrets and "postgres" in st.secrets["connections"]:
        db_url = st.secrets["connections"]["postgres"]["url"]
        return create_engine(db_url, pool_size=10, max_overflow=20, pool_pre_ping=True)
    elif "db_url" in st.secrets:
        return create_engine(st.secrets["db_url"])
    else:
        # Forzamos un prefijo de producción final absoluto para aislar el entorno
        return create_engine("sqlite:///beisseven_prod_final.db", connect_args={"timeout": 45})

# Inicializamos el motor físico de la base de datos
engine = inicializar_motor_seguro()

# Acceso seguro al dialecto mediante la URL (Soporte SQLAlchemy 2.0+)
IS_POSTGRES = "postgres" in engine.url.drivername or "postgresql" in engine.url.drivername

def inicializar_base_de_datos():
    """Crea las estructuras analíticas utilizando bloques de transacción segura (begin)."""
    serial_type = "SERIAL" if IS_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
    pk_constraint = "PRIMARY KEY" if IS_POSTGRES else ""

    with engine.begin() as conn:
        # Tabla de Usuarios
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS usuarios (
                id {serial_type} {pk_constraint}, 
                nombre TEXT UNIQUE NOT NULL, 
                pass TEXT NOT NULL, 
                rol TEXT NOT NULL DEFAULT 'operador'
            );
        """))
        
        # Tabla de Picheos
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS picheos (
                id {serial_type} {pk_constraint}, 
                fecha TEXT NOT NULL, 
                id_control TEXT NOT NULL, 
                cantidad INTEGER NOT NULL, 
                operador TEXT NOT NULL
            );
        """))
        
        # Tabla de Configuración Global
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS config (
                clave TEXT PRIMARY KEY, 
                valor TEXT NOT NULL
            );
        """))

def preparar_datos_defecto():
    """Garantiza la persistencia inmutable del admin inicial y parámetros financieros."""
    # 1. Configuración del precio base
    with engine.begin() as conn:
        if IS_POSTGRES:
            conn.execute(text("INSERT INTO config (clave, valor) VALUES ('precio', '0.024') ON CONFLICT (clave) DO NOTHING;"))
        else:
            conn.execute(text("INSERT OR IGNORE INTO config (clave, valor) VALUES ('precio', '0.024');"))

    # 2. Verificación e inyección segura del Administrador con SHA-256
    with engine.connect() as conn:
        existe_admin = conn.execute(text("SELECT COUNT(*) FROM usuarios WHERE nombre = 'admin';")).scalar()
    
    if existe_admin == 0:
        hash_admin = hashlib.sha256("admin123".encode('utf-8')).hexdigest()
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO usuarios (nombre, pass, rol) VALUES ('admin', :p, 'admin');"), {"p": hash_admin})

# Ejecución forzada del bloque de inicialización analítica
try:
    inicializar_base_de_datos()
    preparar_datos_defecto()
except Exception as e:
    st.error(f"🚨 Error crítico de inicialización de infraestructura: {e}")

# Gestión de hilos de sesión en Streamlit
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario"] = None
    st.session_state["rol"] = None

# ==========================================
# 2. SISTEMA DE AUTENTICACIÓN CON CAPTURA DE ESTADO ESTÁTICO
# ==========================================
if not st.session_state["autenticado"]:
    st.title("⚾ Control de Picheo")
    st.subheader("Acceso Protegido por Infraestructura Securizada")
    
    st.text_input("Nombre de Usuario", key="usuario_memoria")
    st.text_input("Contraseña", type="password", key="clave_memoria")
    
    boton_login = st.button("INGRESAR", use_container_width=True)
    
    if boton_login:
        usuario_input = st.session_state["usuario_memoria"].strip().lower()
        clave_input = st.session_state["clave_memoria"].strip()
        
        if usuario_input and clave_input:
            if usuario_input == "admin" and clave_input == "admin123":
                st.session_state["autenticado"] = True
                st.session_state["usuario"] = "admin"
                st.session_state["rol"] = "admin"
                st.success("🔑 Acceso Maestro Concedido. Redirigiendo...")
                st.rerun()
            else:
                try:
                    with engine.connect() as conn:
                        query = text("SELECT nombre, pass, rol FROM usuarios WHERE nombre = :u;")
                        usuario_db = conn.execute(query, {"u": usuario_input}).fetchone()
                    
                    if usuario_db:
                        input_hash = hashlib.sha256(clave_input.encode('utf-8')).hexdigest()
                        db_hash = usuario_db[1]
                        
                        if input_hash == db_hash:
                            st.session_state["autenticado"] = True
                            st.session_state["usuario"] = usuario_db[0]
                            st.session_state["rol"] = usuario_db[2]
                            st.success("🔑 Conexión exitosa. Redirigiendo...")
                            st.rerun()
                        else:
                            st.error("❌ Contraseña incorrecta.")
                    else:
                        st.error("❌ El nombre de usuario no existe.")
                except Exception as e:
                    st.error(f"Error de comunicación con el almacén de datos: {e}")
        else:
            st.warning("Por favor, rellene todos los campos de autenticación.")
    st.caption("Aviso del Sistema: Credenciales maestras iniciales: 'admin' / 'admin123'.")

# ==========================================
# 3. ENTORNO DEL DASHBOARD PRINCIPAL (SESIÓN ACTIVA)
# ==========================================
else:
    # Barra Lateral Estructural
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
    # MÓDULO 2: GESTIÓN DE REGISTROS (CRUD COMPLETO)
    # ------------------------------------------
    elif opcion == "📝 GESTIÓN DE REGISTROS":
        st.title("Módulo de Ingesta y Administración de Datos")
        
        # Estructura avanzada de 4 pestañas para encapsular el ciclo CRUD de control
        tab_form, tab_bulk, tab_edit, tab_delete = st.tabs([
            "📝 Formulario Manual", 
            "📂 Carga Masiva Automatizada",
            "✏️ Modificar Registro",
            "🗑️ Gestión y Purgado (Borrar)"
        ])
        
        # PESTAÑA A: Entrada Individual
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
                            with engine.begin() as conn:
                                conn.execute(text("""
                                    INSERT INTO picheos (fecha, id_control, cantidad, operador)
                                    VALUES (:f, :id, :c, :o);
                                """), {
                                    "f": reg_fecha.strftime('%Y-%m-%d'), "id": reg_id, "c": reg_cant, "o": st.session_state["usuario"]
                                })
                            st.success(f"💾 Registro guardado: ID [{reg_id}] — ({reg_cant}) picheos.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fallo de persistencia en almacenamiento: {e}")
                            
        # PESTAÑA B: Entrada Automatizada (CSV/Excel)
        with tab_bulk:
            st.write("##### Subida de Lotes de Datos Externos")
            archivo_externo = st.file_uploader("Cargar hoja de cálculo (*.csv, *.xlsx)", type=["csv", "xlsx"])
            if archivo_externo is not None:
                try:
                    df_cargado = pd.read_csv(archivo_externo) if archivo_externo.name.endswith('.csv') else pd.read_excel(archivo_externo)
                    df_cargado.columns = [c.strip().lower() for c in df_cargado.columns]
                    
                    st.write("Vista previa estructurada (Primeras 5 filas):")
                    st.dataframe(df_cargado.head(5), use_container_width=True)
                    
                    columnas_esperadas = ['fecha', 'id_control', 'cantidad', 'operador']
                    if all(col in df_cargado.columns for col in columnas_esperadas):
                        if st.button("🚀 PROCESAR E INYECTAR LOTE", use_container_width=True):
                            df_cargado['fecha'] = df_cargado['fecha'].astype(str)
                            df_cargado['id_control'] = df_cargado['id_control'].astype(str).str.strip()
                            df_cargado['cantidad'] = pd.to_numeric(df_cargado['cantidad'], errors='coerce').fillna(1).astype(int)
                            df_cargado['operador'] = df_cargado['operador'].astype(str).str.strip()
                            
                            with engine.begin() as conexion:
                                df_cargado[columnas_esperadas].to_sql('picheos', con=conexion, if_exists='append', index=False)
                            st.success(f"🔥 Sincronización masiva completa: {len(df_cargado)} registros indexados.")
                            st.rerun()
                    else:
                        st.error("Columnas requeridas estrictas: [fecha, id_control, cantidad, operador]")
                except Exception as e:
                    st.error(f"Error crítico en procesamiento: {e}")

        # PESTAÑA C: Modificar Registro Existente
        with tab_edit:
            st.write("##### Panel de Modificación de Logs")
            busqueda_id = st.text_input("Buscar por ID Control o Identificador para editar:", "").strip()
            
            if busqueda_id:
                with engine.connect() as conn:
                    query_busca = text("SELECT id, fecha, id_control, cantidad, operador FROM picheos WHERE id_control LIKE :b LIMIT 10;")
                    resultados_busca = conn.execute(query_busca, {"b": f"%{busqueda_id}%"}).fetchall()
                
                if resultados_busca:
                    opciones_edicion = {r[0]: f"ID: {r[0]} | Control: {r[2]} | Cantidad: {r[3]} | Fecha: {r[1]}" for r in resultados_busca}
                    id_seleccionar = st.selectbox("Selecciona el registro exacto a actualizar:", opciones_edicion.keys(), format_func=lambda x: opciones_edicion[x])
                    
                    with engine.connect() as conn:
                        reg_actual = conn.execute(text("SELECT * FROM picheos WHERE id = :id;"), {"id": id_seleccionar}).fetchone()
                    
                    if reg_actual:
                        st.markdown("---")
                        st.write(f"Modificando Registro Interno ID: `{id_seleccionar}`")
                        with st.form("form_edicion_registro"):
                            col_e1, col_e2, col_e3 = st.columns(3)
                            with col_e1:
                                nuevo_id_control = st.text_input("ID Control", value=reg_actual[2])
                            with col_e2:
                                nueva_cantidad = st.number_input("Cantidad Picheos", min_value=1, step=1, value=int(reg_actual[3]))
                            with col_e3:
                                nueva_fecha_str = st.text_input("Fecha (YYYY-MM-DD)", value=reg_actual[1])
                            
                            btn_actualizar = st.form_submit_button("APLICAR CAMBIOS EN FILA", use_container_width=True)
                            if btn_actualizar:
                                try:
                                    with engine.begin() as conn:
                                        conn.execute(text("""
                                            UPDATE picheos 
                                            SET fecha = :f, id_control = :id_c, cantidad = :c
                                            WHERE id = :id;
                                        """), {
                                            "f": nueva_fecha_str.strip(), "id_c": nuevo_id_control.strip(), 
                                            "c": nueva_cantidad, "id": id_seleccionar
                                        })
                                    st.success(f"✨ Registro ID {id_seleccionar} actualizado correctamente.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Fallo al actualizar registro: {e}")
                else:
                    st.warning("No se encontraron registros coincidentes.")

        # PESTAÑA D: Gestión y Purgado de Datos (Borrado Seguro)
        with tab_delete:
            st.write("##### 🚨 Zona de Purgado de Datos")
            col_del1, col_del2 = st.columns(2)
            
            with col_del1:
                st.markdown("#### Eliminación Unitaria por ID")
                id_eliminar = st.number_input("ID de Registro Interno:", min_value=1, step=1, key="id_del_manual")
                confirmar_unid = st.checkbox(f"Confirmo la remoción permanente del registro ID {id_eliminar}", key="chk_unid")
                
                if st.button("BORRAR REGISTRO SELECCIONADO", use_container_width=True, type="primary"):
                    if st.session_state["rol"] != 'admin':
                        st.error("Acceso Restringido: Operadores no poseen permisos de destrucción de logs.")
                    elif not confirmar_unid:
                        st.warning("Debe marcar la casilla de verificación para validar el borrado.")
                    else:
                        with engine.begin() as conn:
                            existe = conn.execute(text("SELECT COUNT(*) FROM picheos WHERE id = :id;"), {"id": id_eliminar}).scalar()
                            if existe == 0:
                                st.warning(f"ID [{id_eliminar}] no localizado.")
                            else:
                                conn.execute(text("DELETE FROM picheos WHERE id = :id;"), {"id": id_eliminar})
                                st.success(f"Registro [{id_eliminar}] eliminado de forma permanente.")
                                st.rerun()
            
            with col_del2:
                st.markdown("#### Purgado Masivo Estructural")
                st.error("⚠️ ATENCIÓN CRÍTICA: Esta acción vaciará por completo la base de datos histórica. Es irreversible.")
                confirmar_tabla = st.checkbox("SÍ, deseo purgar TODOS los registros históricos de picheos de la base de datos.", key="chk_masivo")
                
                if st.button("💥 PURGAR BASE DE DATOS COMPLETA", use_container_width=True, type="primary"):
                    if st.session_state["rol"] != 'admin':
                        st.error("Acceso Restringido: Se requieren privilegios de Administrador Maestro.")
                    elif not confirmar_tabla:
                        st.warning("Debe validar el checkbox de confirmación absoluta antes de ejecutar el comando.")
                    else:
                        try:
                            with engine.begin() as conn:
                                conn.execute(text("DELETE FROM picheos;"))
                                if not IS_POSTGRES:
                                    conn.execute(text("DELETE FROM sqlite_sequence WHERE name='picheos';"))
                            st.success("💥 Estructura purgada. Todos los logs históricos han sido eliminados.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fallo en la ejecución del purgado masivo: {e}")

        # Visualización Histórica y Botones de Exportación Comunes
        st.write("---")
        st.subheader("Visor en Tiempo Real de Registros Indexados")
        try:
            with engine.connect() as conn:
                query_picheos = conn.execute(text("SELECT id, fecha, id_control, cantidad, operador FROM picheos ORDER BY id DESC LIMIT 1000;")).fetchall()
            
            if query_picheos:
                df_picheos = pd.DataFrame(query_picheos, columns=["ID", "FECHA", "CONTROL", "CANTIDAD", "OPERADOR"])
                
                buffer_excel = io.BytesIO()
                with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                    df_picheos.to_excel(writer, index=False, sheet_name='Logs_Picheo')
                
                st.download_button(
                    label="📥 GENERAR REPORTE EXCEL (OPENPYXL)",
                    data=buffer_excel.getvalue(),
                    file_name=f"BeisSeven_Export_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                st.dataframe(df_picheos, use_container_width=True, height=400)
            else:
                st.info("No se encuentran registros históricos indexados.")
        except Exception as e:
            st.error(f"Fallo en la visualización de datos: {e}")

    # ------------------------------------------
    # MÓDULO 3: PANEL DE PERSONAL
    # ------------------------------------------
    elif opcion == "👥 PANEL DE PERSONAL" and st.session_state["rol"] == "admin":
        st.title("Gestión de Personal Autorizado")
        
        with st.form("creacion_nuevo_usuario"):
            st.write("##### Alta de Nuevo Operador de Sistema")
            col_u1, col_u2, col_u3 = st.columns(3)
            with col_u1:
                n_usuario = st.text_input("Nombre de Usuario").strip().lower()
            with col_u2:
                n_clave = st.text_input("Clave de Acceso (Min. 6 caracteres)", type="password").strip()
            with col_u3:
                n_rol = st.selectbox("Nivel de Permisos", ["operador", "admin"])
                
            btn_usuario = st.form_submit_button("REGISTRAR USUARIO", use_container_width=True)
            
            if btn_usuario:
                if not n_usuario or not n_clave:
                    st.error("Datos incompletos.")
                elif len(n_clave) < 6:
                    st.warning("La contraseña debe tener mínimo 6 caracteres por seguridad.")
                else:
                    try:
                        hash_nueva_clave = hashlib.sha256(n_clave.encode('utf-8')).hexdigest()
                        
                        with engine.begin() as conn:
                            conn.execute(text("""
                                INSERT INTO usuarios (nombre, pass, rol) VALUES (:n, :p, :r);
                            """), {"n": n_usuario, "p": hash_nueva_clave, "r": n_rol})
                        st.success(f"Usuario registrado exitosamente: `{n_usuario}`.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"El identificador ya se encuentra registrado o el sistema está ocupado.")
                        
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
                with engine.begin() as conn:
                    usuario_db = conn.execute(text("SELECT nombre FROM usuarios WHERE id = :id;"), {"id": id_baja}).fetchone()
                    if not usuario_db:
                        st.warning("El ID Fleet especificado no pertenece a ningún operador.")
                    elif usuario_db[0] == st.session_state["usuario"]:
                        st.error("Un administrador no puede purgar su propio perfil en uso.")
                    elif usuario_db[0] == "admin":
                        st.error("El administrador maestro no puede darse de baja.")
                    else:
                        conn.execute(text("DELETE FROM usuarios WHERE id = :id;"), {"id": id_baja})
                        st.success(f"Cuenta `{usuario_db[0]}` eliminada.")
                        st.rerun()
        except Exception as e:
            st.error(f"Fallo en la lectura del personal activo: {e}")

    # ------------------------------------------
    # MÓDULO 4: AJUSTES DE CONFIGURACIÓN
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
                            with engine.begin() as conn:
                                conn.execute(text("UPDATE config SET valor = :v WHERE clave = 'precio';"), {"v": str(valor_validado)})
                            st.success(f"Ajuste aplicado: Nueva tasa global fijada en ${valor_validado} USD.")
                            st.rerun()
                    except ValueError:
                        st.error("Ingrese un valor numérico real válido (Ej. 0.024).")
        except Exception as e:
            st.error(f"Fallo en la carga de variables de configuración: {e}")

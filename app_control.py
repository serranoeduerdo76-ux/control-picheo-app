import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import io

# Configuración de interfaz profesional de alta densidad de datos
st.set_page_config(
    page_title="Apex Pitch - Analytics System", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Estilos CSS unificados en una sola línea para evitar fallos de parseo en Python 3.14+
CSS_PRODUCCION = "<style>.metric-card {background-color: #161B26; border-left: 5px solid #00E676; padding: 24px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); margin-bottom: 15px;} .metric-label {color: #8B949E; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;} .metric-value {color: #FFFFFF; font-size: 38px; font-weight: 700; font-family: 'Courier New', monospace; margin-top: 5px;} .stTabs [data-baseweb='tab-list'] {gap: 8px;} .stTabs [data-baseweb='tab'] {background-color: #161B26; border-radius: 4px 4px 0px 0px; padding: 10px 20px; color: #FFFFFF;} .stTabs [data-baseweb='tab']:hover {color: #00E676;}</style>"
st.markdown(CSS_PRODUCCION, unsafe_with_html=True)

# ==========================================
# 1. CONEXIÓN Y VERIFICACIÓN DE NEON (POSTGRESQL)
# ==========================================
@st.cache_resource
def conectar_base_datos_neon():
    url_conexion = None
    if "connections" in st.secrets and "postgres" in st.secrets["connections"]:
        url_conexion = st.secrets["connections"]["postgres"]["url"]
    elif "db_url" in st.secrets:
        url_conexion = st.secrets["db_url"]
        
    if url_conexion:
        if url_conexion.startswith("postgres://"):
            url_conexion = url_conexion.replace("postgres://", "postgresql://", 1)
        if "channel_binding=" in url_conexion:
            url_conexion = url_conexion.replace("&channel_binding=require", "").replace("channel_binding=require&", "").replace("channel_binding=require", "")
        return create_engine(url_conexion, pool_size=5, max_overflow=10, pool_pre_ping=True)
    else:
        st.error("🚨 ERROR DE INFRAESTRUCTURA: No se detectó la URL de Neon en los Secrets.")
        st.stop()

engine = conectar_base_datos_neon()

def asegurar_estructura_tablas():
    with engine.begin() as conexion:
        conexion.execute(text("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY, 
                nombre_usuario TEXT UNIQUE NOT NULL, 
                contrasena_hash TEXT NOT NULL, 
                rol_acceso TEXT NOT NULL DEFAULT 'operador'
            );
        """))
        conexion.execute(text("""
            CREATE TABLE IF NOT EXISTS registros_picheo (
                id SERIAL PRIMARY KEY, 
                fecha_registro TEXT NOT NULL, 
                id_control TEXT NOT NULL, 
                cantidad_picheos INTEGER NOT NULL, 
                operador_responsable TEXT NOT NULL
            );
        """))
        conexion.execute(text("""
            CREATE TABLE IF NOT EXISTS configuracion_global (
                clave_parametro TEXT PRIMARY KEY, 
                valor_parametro TEXT NOT NULL
            );
        """))

def inicializar_valores_sistema():
    with engine.begin() as conexion:
        conexion.execute(text("""
            INSERT INTO configuracion_global (clave_parametro, valor_parametro) 
            VALUES ('tarifa_unidad', '0.024') 
            ON CONFLICT (clave_parametro) DO NOTHING;
        """))
    with engine.connect() as conexion:
        cuenta_admin_existe = conexion.execute(text("SELECT COUNT(*) FROM usuarios WHERE nombre_usuario = 'admin';")).scalar()
    if cuenta_admin_existe == 0:
        hash_maestro = hashlib.sha256("admin123".encode('utf-8')).hexdigest()
        with engine.begin() as conexion:
            conexion.execute(text("INSERT INTO usuarios (nombre_usuario, contrasena_hash, rol_acceso) VALUES ('admin', :hash, 'admin');"), {"hash": hash_maestro})

try:
    asegurar_estructura_tablas()
    inicializar_valores_sistema()
except Exception as error_conexion:
    st.error(f"🚨 Error de sincronización con el servidor Neon: {error_conexion}")
    st.stop()

if "sesion_activa" not in st.session_state:
    st.session_state["sesion_activa"] = False
    st.session_state["usuario_actual"] = None
    st.session_state["rol_actual"] = None

# ==========================================
# 2. PANTALLA DE CONTROL DE ACCESO (LOGIN)
# ==========================================
if not st.session_state["sesion_activa"]:
    st.markdown("<h1 style='text-align: center; color: #FFFFFF;'>⚾ APEX PITCH</h1>", unsafe_with_html=True)
    st.markdown("<p style='text-align: center; color: #8B949E;'>Scouting & Pitch Data Management System</p>", unsafe_with_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        with st.container(border=True):
            input_usuario = st.text_input("Nombre de Usuario").strip().lower()
            input_contrasena = st.text_input("Contraseña de Seguridad", type="password").strip()
            st.write("")
            if st.button("INICIAR SESIÓN", use_container_width=True, type="primary"):
                if input_usuario == "admin" and input_contrasena == "admin123":
                    st.session_state["sesion_activa"] = True
                    st.session_state["usuario_actual"] = "admin"
                    st.session_state["rol_actual"] = "admin"
                    st.rerun()
                else:
                    try:
                        with engine.connect() as conexion:
                            consulta = text("SELECT nombre_usuario, contrasena_hash, rol_acceso FROM usuarios WHERE nombre_usuario = :usr;")
                            registro = conexion.execute(consulta, {"usr": input_usuario}).mappings().fetchone()
                        if registro:
                            if hashlib.sha256(input_contrasena.encode('utf-8')).hexdigest() == registro["contrasena_hash"] or input_contrasena == registro["contrasena_hash"]:
                                st.session_state["sesion_activa"] = True
                                st.session_state["usuario_actual"] = registro["nombre_usuario"]
                                st.session_state["rol_actual"] = registro["rol_acceso"]
                                st.rerun()
                            else:
                                st.error("Contraseña incorrecta.")
                        else:
                            st.error("Usuario no registrado.")
                    except Exception as e:
                        st.error(f"Error: {e}")

# ==========================================
# 3. ENTORNO DE TRABAJO (SESIÓN ACTIVA)
# ==========================================
else:
    # Barra lateral estilizada
    st.sidebar.markdown("<h2 style='color: #00E676; margin-bottom: 0;'>⚾ APEX PITCH</h2>", unsafe_with_html=True)
    st.sidebar.markdown("<p style='color: #8B949E; font-size: 12px;'>Professional Scouting Log</p>", unsafe_with_html=True)
    st.sidebar.write("---")
    st.sidebar.markdown(f"👤 **Usuario:** `{st.session_state['usuario_actual'].upper()}`")
    st.sidebar.markdown(f"🔑 **Permisos:** `{st.session_state['rol_actual'].upper()}`")
    st.sidebar.write("---")
    
    modulos_disponibles = ["📊 Resumen General", "📝 Registro de Picheos"]
    if st.session_state["rol_actual"] == "admin":
        modulos_disponibles.extend(["👥 Control de Personal", "⚙️ Ajustes del Sistema"])
        
    modulo_seleccionado = st.sidebar.radio("MENÚ DE NAVEGACIÓN", modulos_disponibles)
    st.sidebar.write("---")
    
    if st.sidebar.button("🚪 CERRAR SESIÓN", use_container_width=True):
        st.session_state["sesion_activa"] = False
        st.session_state["usuario_actual"] = None
        st.session_state["rol_actual"] = None
        st.rerun()

    # ------------------------------------------
    # MÓDULO A: RESUMEN GENERAL (DASHBOARD)
    # ------------------------------------------
    if modulo_seleccionado == "📊 Resumen General":
        st.subheader("Métricas de Rendimiento")
        
        col_fecha_1, col_fecha_2 = st.columns([3, 1])
        with col_fecha_1:
            with st.container(border=True):
                c1, c2 = st.columns(2)
                with c1:
                    fecha_inicio = st.date_input("Fecha Inicial:", value=datetime.now() - timedelta(days=15))
                with c2:
                    fecha_termino = st.date_input("Fecha Final:", value=datetime.now())
                    
        if fecha_inicio > fecha_termino:
            st.error("Error: Rango de fechas inválido.")
        else:
            try:
                with engine.connect() as conexion:
                    volumen_picheos = conexion.execute(text("""
                        SELECT SUM(cantidad_picheos) FROM registros_picheo 
                        WHERE fecha_registro BETWEEN :inicio AND :termino
                    """), {"inicio": fecha_inicio.strftime('%Y-%m-%d'), "termino": fecha_termino.strftime('%Y-%m-%d')}).scalar() or 0
                    
                    tarifa_db = conexion.execute(text("SELECT valor_parametro FROM configuracion_global WHERE clave_parametro='tarifa_unidad';")).scalar() or "0.024"
                    tarifa_unidad = float(tarifa_db)
                
                st.write("")
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-label">Volumen Total de Picheos</div>
                            <div class="metric-value">{volumen_picheos:,}</div>
                        </div>
                    """, unsafe_with_html=True)
                with col_m2:
                    st.markdown(f"""
                        <div class="metric-card" style="border-left-color: #00B0FF;">
                            <div class="metric-label">Rendimiento Monetario (USD)</div>
                            <div class="metric-value">${volumen_picheos * tarifa_unidad:,.2f}</div>
                        </div>
                    """, unsafe_with_html=True)
                
            except Exception as e:
                st.error(f"Error al calcular métricas: {e}")

    # ------------------------------------------
    # MÓDULO B: REGISTRO DE PICHEOS (CRUD)
    # ------------------------------------------
    elif modulo_seleccionado == "📝 Registro de Picheos":
        st.subheader("Panel de Operaciones")
        
        pestana_manual, pestana_archivo, pestana_edicion, pestana_borrado = st.tabs([
            "➕ Ficha Manual", "📂 Importar Lote (Excel/CSV)", "✏️ Corregir Historial", "🗑️ Remoción Crítica"
        ])
        
        with pestana_manual:
            with st.form("formulario_ingreso_manual", clear_on_submit=True):
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    form_fecha = st.date_input("Fecha de Operación", value=datetime.now())
                with col_m2:
                    form_codigo_control = st.text_input("Código de Control / Identificador").strip()
                with col_m3:
                    form_cantidad = st.number_input("Cantidad de Picheos", min_value=1, step=1, value=1)
                    
                if st.form_submit_button("COMPROMETER REGISTRO", use_container_width=True):
                    if not form_codigo_control:
                        st.error("El campo 'Código de Control' es obligatorio.")
                    else:
                        try:
                            with engine.begin() as conexion:
                                conexion.execute(text("""
                                    INSERT INTO registros_picheo (fecha_registro, id_control, cantidad_picheos, operador_responsable)
                                    VALUES (:fecha, :id_c, :cant, :operador);
                                """), {"fecha": form_fecha.strftime('%Y-%m-%d'), "id_c": form_codigo_control, "cant": form_cantidad, "operador": st.session_state["usuario_actual"]})
                            st.success(f"Registro exitoso: [{form_codigo_control}] guardado en la nube.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fallo de almacenamiento: {e}")
                            
        with pestana_archivo:
            st.markdown("##### Carga Masiva de Planillas")
            archivo_subido = st.file_uploader("Subir archivo compatible", type=["csv", "xlsx"])
            if archivo_subido is not None:
                try:
                    df_datos = pd.read_csv(archivo_subido) if archivo_subido.name.endswith('.csv') else pd.read_excel(archivo_subido)
                    df_datos.columns = [columna.strip().lower() for columna in df_datos.columns]
                    st.dataframe(df_datos.head(5), use_container_width=True)
                    
                    columnas_necesarias = ['fecha_registro', 'id_control', 'cantidad_picheos', 'operador_responsable']
                    if all(col in df_datos.columns for col in columnas_necesarias):
                        if st.button("🚀 INICIAR IMPORTACIÓN MASIVA", use_container_width=True):
                            df_datos['fecha_registro'] = df_datos['fecha_registro'].astype(str)
                            df_datos['id_control'] = df_datos['id_control'].astype(str).str.strip()
                            df_datos['cantidad_picheos'] = pd.to_numeric(df_datos['cantidad_picheos'], errors='coerce').fillna(1).astype(int)
                            df_datos['operador_responsable'] = df_datos['operador_responsable'].astype(str).str.strip()
                            with engine.begin() as conexion:
                                df_datos[columnas_necesarias].to_sql('registros_picheo', con=conexion, if_exists='append', index=False)
                            st.success("Carga por lote completada con éxito.")
                            st.rerun()
                    else:
                        st.error("El formato de columnas no coincide con el estándar del sistema.")
                except Exception as e:
                    st.error(f"Error: {e}")

        with pestana_edicion:
            st.markdown("##### Modificación y Ajustes")
            codigo_buscado = st.text_input("Buscar por Código de Control:").strip()
            if codigo_buscado:
                with engine.connect() as conexion:
                    coincidencias = conexion.execute(text("SELECT id, fecha_registro, id_control, cantidad_picheos, operador_responsable FROM registros_picheo WHERE id_control LIKE :b LIMIT 10;"), {"b": f"%{codigo_buscado}%"}).fetchall()
                if coincidencias:
                    opciones_filas = {f[0]: f"ID: {f[0]} | Código: {f[2]} | Cantidad: {f[3]}" for f in coincidencias}
                    id_seleccionado = st.selectbox("Seleccione la fila exacta:", opciones_filas.keys(), format_func=lambda x: opciones_filas[x])
                    with engine.connect() as conexion:
                        val = conexion.execute(text("SELECT * FROM registros_picheo WHERE id = :id;"), {"id": id_seleccionado}).fetchone()
                    if val:
                        with st.form("form_ed_valores"):
                            c_ed1, c_ed2, c_ed3 = st.columns(3)
                            with c_ed1: n_code = st.text_input("Código Control", value=val[2])
                            with c_ed2: n_cant = st.number_input("Cantidad", min_value=1, value=int(val[3]))
                            with c_ed3: n_fech = st.text_input("Fecha (AAAA-MM-DD)", value=val[1])
                            if st.form_submit_button("GUARDAR CAMBIOS"):
                                with engine.begin() as conn:
                                    conn.execute(text("UPDATE registros_picheo SET fecha_registro=:f, id_control=:idc, cantidad_picheos=:c WHERE id=:id;"), {"f": n_fech, "idc": n_code, "c": n_cant, "id": id_seleccionado})
                                st.success("Registro modificado.")
                                st.rerun()
                else:
                    st.warning("No se encontraron registros.")

        with pestana_borrado:
            st.markdown("##### 🚨 Zona Alta de Seguridad")
            if st.session_state["rol_actual"] != 'admin':
                st.warning("Acceso bloqueado: Requiere perfil de Administrador.")
            else:
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    with st.container(border=True):
                        st.markdown("#### Eliminar Fila Única")
                        id_del = st.number_input("ID Fila:", min_value=1, step=1)
                        if st.button("ELIMINAR REGISTRO", type="primary", use_container_width=True):
                            with engine.begin() as conn:
                                conn.execute(text("DELETE FROM registros_picheo WHERE id = :id;"), {"id": id_del})
                            st.success("Fila removida.")
                            st.rerun()
                with col_b2:
                    with st.container(border=True):
                        st.markdown("#### Purgar Base de Datos")
                        st.error("Esta acción vaciará por completo las tablas de Neon.")
                        check_purgar = st.checkbox("Confirmo el vaciado absoluto.")
                        if st.button("BORRAR TODO EL HISTORIAL", type="primary", use_container_width=True) and check_purgar:
                            with engine.begin() as conn:
                                conn.execute(text("DELETE FROM registros_picheo;"))
                            st.success("Base de datos limpia.")
                            st.rerun()

        # Tabla general en tiempo real
        st.write("---")
        try:
            with engine.connect() as conexion:
                todos_los_datos = conexion.execute(text("SELECT id, fecha_registro, id_control, cantidad_picheos, operador_responsable FROM registros_picheo ORDER BY id DESC;")).fetchall()
            if todos_los_datos:
                df_total = pd.DataFrame(todos_los_datos, columns=["ID FILA", "FECHA", "CÓDIGO CONTROL", "CANTIDAD PICHEOS", "OPERADOR ENCARGADO"])
                
                buffer_descarga = io.BytesIO()
                with pd.ExcelWriter(buffer_descarga, engine='openpyxl') as writer:
                    df_total.to_excel(writer, index=False, sheet_name='Historial_Completo')
                
                st.download_button(
                    label=f"📥 EXPORTAR REPORTE INTEGRAL DE NEON ({len(df_total)} REGISTROS)",
                    data=buffer_descarga.getvalue(),
                    file_name=f"Reporte_Total_ApexPitch_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
                st.markdown("##### Vista de Monitoreo (Últimos 100 registros)")
                st.dataframe(df_total.head(100), use_container_width=True, height=350)
            else:
                st.info("No hay datos registrados en el servidor Neon actualmente.")
        except Exception as e:
            st.error(f"Error de visualización: {e}")

    # ------------------------------------------
    # MÓDULO C: CONTROL DE PERSONAL (ADMIN)
    # ------------------------------------------
    elif modulo_seleccionado == "👥 Control de Personal" and st.session_state["rol_actual"] == "admin":
        st.subheader("Gestión de Usuarios")
        with st.form("formulario_alta_usuarios"):
            col_us1, col_us2, col_us3 = st.columns(3)
            with col_us1: n_user = st.text_input("Usuario").strip().lower()
            with col_us2: n_pass = st.text_input("Contraseña", type="password").strip()
            with col_us3: n_rol = st.selectbox("Perfil de Permisos", ["operador", "admin"])
            if st.form_submit_button("REGISTRAR CUENTA", use_container_width=True):
                if n_user and len(n_pass) >= 6:
                    try:
                        h_pass = hashlib.sha256(n_pass.encode('utf-8')).hexdigest()
                        with engine.begin() as conn:
                            conn.execute(text("INSERT INTO usuarios (nombre_usuario, contrasena_hash, rol_acceso) VALUES (:n, :h, :r);"), {"n": n_user, "h": h_pass, "r": n_rol})
                        st.success("Usuario creado con éxito.")
                        st.rerun()
                    except: st.error("El usuario ya existe.")
                else: st.warning("Complete los campos (Contraseña mínimo 6 caracteres).")
                
        with engine.connect() as conn:
            usrs = conn.execute(text("SELECT id, nombre_usuario, rol_acceso FROM usuarios;")).fetchall()
        st.dataframe(pd.DataFrame(usrs, columns=["ID PERFIL", "USUARIO", "ROL"]), use_container_width=True)

    # ------------------------------------------
    # MÓDULO D: AJUSTES DEL SISTEMA (ADMIN)
    # ------------------------------------------
    elif modulo_seleccionado == "⚙️ Ajustes del Sistema" and st.session_state["rol_actual"] == "admin":
        st.subheader("Configuración Global del Software")
        try:
            with engine.connect() as conn:
                tar_vigente = conn.execute(text("SELECT valor_parametro FROM configuracion_global WHERE clave_parametro='tarifa_unidad';")).scalar() or "0.024"
            with st.form("form_tasa"):
                input_tasa = st.text_input("Tarifa por Unidad (USD):", value=tar_vigente).strip()
                if st.form_submit_button("ESTABLECER NUEVA TASA", use_container_width=True):
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE configuracion_global SET valor_parametro = :v WHERE clave_parametro = 'tarifa_unidad';"), {"v": str(float(input_tasa))})
                    st.success("Tasa global actualizada.")
                    st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

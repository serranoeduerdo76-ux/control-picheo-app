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

# 2. INYECCIÓN DE CSS AVANZADO (UI PREMIUM)
st.markdown("""
    <style>
        /* Deshabilitar márgenes superiores por defecto para ganar espacio */
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 1rem;
        }
        
        /* Tarjetas de Métricas Avanzadas (Estilo Marcador Deportivo) */
        .metric-card {
            background: linear-gradient(135deg, #161B26 0%, #1A202C 100%);
            border-left: 5px solid #00E676;
            padding: 22px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.4);
            margin-bottom: 15px;
            transition: transform 0.2s;
        }
        .metric-card:hover {
            transform: translateY(-2px);
        }
        .metric-label {
            color: #8B949E;
            font-size: 13px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1.2px;
        }
        .metric-value {
            color: #FFFFFF;
            font-size: 40px;
            font-weight: 700;
            font-family: 'Courier New', monospace;
            margin-top: 5px;
            text-shadow: 0 0 10px rgba(0, 230, 118, 0.2);
        }
        
        /* Estilización Estricta de Pestañas (Tabs) */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            border-bottom: 1px solid #161B26;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: #111622;
            border: 1px solid #161B26;
            border-radius: 6px 6px 0px 0px;
            padding: 12px 24px;
            color: #8B949E;
            font-weight: 600;
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background-color: #161B26;
            color: #00E676 !important;
            border-bottom: 2px solid #00E676;
        }
    </style>
""", unsafe_with_html=True)

# ==========================================
# 3. MOTOR DE INFRAESTRUCTURA DE DATOS (NEON)
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
        # Tabla de Credenciales y Roles
        conexion.execute(text("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY, 
                nombre_usuario TEXT UNIQUE NOT NULL, 
                contrasena_hash TEXT NOT NULL, 
                rol_acceso TEXT NOT NULL DEFAULT 'operador'
            );
        """))
        # Tabla de Logs de Picheo con Tipo de Datos DATE nativo para optimizar índices y velocidad
        conexion.execute(text("""
            CREATE TABLE IF NOT EXISTS registros_picheo (
                id SERIAL PRIMARY KEY, 
                fecha_registro DATE NOT NULL, 
                id_control TEXT NOT NULL, 
                cantidad_picheos INTEGER NOT NULL, 
                operador_responsable TEXT NOT NULL
            );
        """))
        # Tabla de Variables de Entorno del Sistema
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
# 4. CONTROL DE ACCESO (LOGIN INTERFAZ)
# ==========================================
if not st.session_state["sesion_activa"]:
    st.write("")
    st.write("")
    st.markdown("<h1 style='text-align: center; color: #FFFFFF; font-weight: 800; letter-spacing: 2px;'>⚾ APEX PITCH</h1>", unsafe_with_html=True)
    st.markdown("<p style='text-align: center; color: #8B949E; font-size: 14px;'>Professional Scouting & Pitch Data Analytics</p>", unsafe_with_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1.2, 1.5, 1.2])
    with col_l2:
        with st.container(border=True):
            input_usuario = st.text_input("Identificador de Usuario").strip().lower()
            input_contrasena = st.text_input("Clave de Acceso", type="password").strip()
            st.write("")
            if st.button("ACCEDER AL SISTEMA", use_container_width=True, type="primary"):
                try:
                    with engine.connect() as conexion:
                        consulta = text("SELECT nombre_usuario, contrasena_hash, rol_acceso FROM usuarios WHERE nombre_usuario = :usr;")
                        registro = conexion.execute(consulta, {"usr": input_usuario}).mappings().fetchone()
                    
                    if registro:
                        pass_hash = hashlib.sha256(input_contrasena.encode('utf-8')).hexdigest()
                        if pass_hash == registro["contrasena_hash"] or input_contrasena == registro["contrasena_hash"]:
                            st.session_state["sesion_activa"] = True
                            st.session_state["usuario_actual"] = registro["nombre_usuario"]
                            st.session_state["rol_actual"] = registro["rol_acceso"]
                            st.rerun()
                        else:
                            st.error("🔒 Credenciales incorrectas.")
                    else:
                        st.error("❌ Usuario no registrado en la base central.")
                except Exception as e:
                    st.error(f"Error de autenticación: {e}")

# ==========================================
# 5. ENTORNO DE OPERACIÓN DE DATOS (DASHBOARD)
# ==========================================
else:
    # Configuración de Menú Lateral (Sidebar)
    st.sidebar.markdown("<h2 style='color: #00E676; font-weight: 800; margin-bottom: 0;'>⚾ APEX PITCH</h2>", unsafe_with_html=True)
    st.sidebar.markdown("<p style='color: #8B949E; font-size: 11px; text-transform: uppercase;'>Scouting Dashboard v2.1</p>", unsafe_with_html=True)
    st.sidebar.write("---")
    st.sidebar.markdown(f"👤 **Usuario:** `{st.session_state['usuario_actual'].upper()}`")
    st.sidebar.markdown(f"🔑 **Nivel:** `{st.session_state['rol_actual'].upper()}`")
    st.sidebar.write("---")
    
    modulos_disponibles = ["📊 Resumen General", "📝 Registro de Picheos"]
    if st.session_state["rol_actual"] == "admin":
        modulos_disponibles.extend(["👥 Control de Personal", "⚙️ Ajustes del Sistema"])
        
    modulo_seleccionado = st.sidebar.radio("MÓDULOS DEL SISTEMA", modulos_disponibles)
    st.sidebar.write("---")
    
    if st.sidebar.button("🚪 FINALIZAR SESIÓN", use_container_width=True):
        st.session_state["sesion_activa"] = False
        st.session_state["usuario_actual"] = None
        st.session_state["rol_actual"] = None
        st.rerun()

    # ------------------------------------------
    # MÓDULO A: DASHBOARD ANALÍTICO GENERAL
    # ------------------------------------------
    if modulo_seleccionado == "📊 Resumen General":
        st.title("Métricas del Sistema")
        
        # Filtro temporal avanzado
        with st.container(border=True):
            st.markdown("<p style='font-weight: 600; margin-bottom: 5px;'>Rango de Fechas de Evaluación</p>", unsafe_with_html=True)
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                fecha_inicio = st.date_input("Fecha Inicial:", value=datetime.now() - timedelta(days=15))
            with col_f2:
                fecha_termino = st.date_input("Fecha Final:", value=datetime.now())
                    
        if fecha_inicio > fecha_termino:
            st.error("Error crítico: La fecha inicial no puede superar a la fecha final.")
        else:
            try:
                with engine.connect() as conexion:
                    volumen_picheos = conexion.execute(text("""
                        SELECT SUM(cantidad_picheos) FROM registros_picheo 
                        WHERE fecha_registro BETWEEN :inicio AND :termino
                    """), {"inicio": fecha_inicio, "termino": fecha_termino}).scalar() or 0
                    
                    tarifa_db = conexion.execute(text("SELECT valor_parametro FROM configuracion_global WHERE clave_parametro='tarifa_unidad';")).scalar() or "0.024"
                    tarifa_unidad = float(tarifa_db)
                
                st.write("")
                # Renderizado de KPIs con CSS inyectado
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
                            <div class="metric-label">Rendimiento Monetario Bruto</div>
                            <div class="metric-value">${volumen_picheos * tarifa_unidad:,.2f}</div>
                        </div>
                    """, unsafe_with_html=True)
                
            except Exception as e:
                st.error(f"Error en consulta analítica: {e}")

    # ------------------------------------------
    # MÓDULO B: OPERACIONES DE DATOS (CRUD COMPLETE)
    # ------------------------------------------
    elif modulo_seleccionado == "📝 Registro de Picheos":
        st.title("Panel de Trabajo")
        
        p_manual, p_archivo, p_edicion, p_borrado = st.tabs([
            "➕ Ficha Manual", "📂 Subir Archivo Excel/CSV", "✏️ Corregir Datos", "🗑️ Eliminación Segura"
        ])
        
        with p_manual:
            with st.form("formulario_ingreso_manual", clear_on_submit=True):
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    form_fecha = st.date_input("Fecha de Operación", value=datetime.now())
                with col_m2:
                    form_codigo_control = st.text_input("Código de Control / Identificador").strip()
                with col_m3:
                    form_cantidad = st.number_input("Cantidad de Picheos", min_value=1, step=1, value=1)
                    
                if st.form_submit_button("GUARDAR EN BASE DE DATOS", use_container_width=True):
                    if not form_codigo_control:
                        st.error("El campo 'Código de Control' es obligatorio.")
                    else:
                        try:
                            with engine.begin() as conexion:
                                conexion.execute(text("""
                                    INSERT INTO registros_picheo (fecha_registro, id_control, cantidad_picheos, operador_responsable)
                                    VALUES (:fecha, :id_c, :cant, :operador);
                                """), {"fecha": form_fecha, "id_c": form_codigo_control, "cant": form_cantidad, "operador": st.session_state["usuario_actual"]})
                            st.success(f"Dato guardado correctamente. Código asignado: {form_codigo_control}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fallo de persistencia: {e}")
                            
        with p_archivo:
            st.markdown("### Importación Masiva por Lotes")
            archivo_subido = st.file_uploader("Subir hoja de cálculo compatible", type=["csv", "xlsx"])
            if archivo_subido is not None:
                try:
                    df_datos = pd.read_csv(archivo_subido) if archivo_subido.name.endswith('.csv') else pd.read_excel(archivo_subido)
                    df_datos.columns = [col.strip().lower() for col in df_datos.columns]
                    
                    columnas_necesarias = ['fecha_registro', 'id_control', 'cantidad_picheos', 'operador_responsable']
                    if all(col in df_datos.columns for col in columnas_necesarias):
                        st.dataframe(df_datos.head(5), use_container_width=True)
                        if st.button("🚀 PROCESAR E INYECTAR LOTE", use_container_width=True):
                            # Limpieza profunda de tipos de datos antes de subir
                            df_datos['fecha_registro'] = pd.to_datetime(df_datos['fecha_registro']).dt.date
                            df_datos['id_control'] = df_datos['id_control'].astype(str).str.strip()
                            df_datos['cantidad_picheos'] = pd.to_numeric(df_datos['cantidad_picheos'], errors='coerce').fillna(0).astype(int)
                            df_datos['operador_responsable'] = df_datos['operador_responsable'].astype(str).str.strip()
                            
                            with engine.begin() as conexion:
                                df_datos[columnas_necesarias].to_sql('registros_picheo', con=conexion, if_exists='append', index=False)
                            st.success("Transacción masiva completada en Neon.")
                            st.rerun()
                    else:
                        st.error("Estructura inválida. Columnas requeridas: fecha_registro, id_control, cantidad_picheos, operador_responsable")
                except Exception as e:
                    st.error(f"Fallo de parseo: {e}")

        with p_edicion:
            st.markdown("### Modificación de Registros")
            codigo_buscado = st.text_input("Buscar Identificador / Código:").strip()
            if codigo_buscado:
                with engine.connect() as conexion:
                    coincidencias = conexion.execute(text("""
                        SELECT id, fecha_registro, id_control, cantidad_picheos 
                        FROM registros_picheo WHERE id_control ILIKE :b LIMIT 10;
                    """), {"b": f"%{codigo_buscado}%"}).fetchall()
                if coincidencias:
                    opciones_filas = {f[0]: f"ID: {f[0]} | Código: {f[2]} | Picheos: {f[3]}" for f in coincidencias}
                    id_seleccionado = st.selectbox("Seleccionar registro exacto:", opciones_filas.keys(), format_func=lambda x: opciones_filas[x])
                    
                    with engine.connect() as conexion:
                        val = conexion.execute(text("SELECT id, fecha_registro, id_control, cantidad_picheos FROM registros_picheo WHERE id = :id;"), {"id": id_seleccionado}).fetchone()
                    if val:
                        with st.form("form_ed_valores"):
                            c_ed1, c_ed2, c_ed3 = st.columns(3)
                            with c_ed1: n_code = st.text_input("Código Control", value=val[2])
                            with c_ed2: n_cant = st.number_input("Cantidad", min_value=1, value=int(val[3]))
                            with c_ed3: n_fech = st.date_input("Fecha", value=val[1])
                            if st.form_submit_button("MODIFICAR VALORES"):
                                with engine.begin() as conn:
                                    conn.execute(text("""
                                        UPDATE registros_picheo 
                                        SET fecha_registro=:f, id_control=:idc, cantidad_picheos=:c WHERE id=:id;
                                    """), {"f": n_fech, "idc": n_code, "c": n_cant, "id": id_seleccionado})
                                st.success("Registro sincronizado de manera exitosa.")
                                st.rerun()
                else:
                    st.warning("No se encontraron registros activos con ese criterio.")

        with p_borrado:
            st.markdown("### 🚨 Panel de Eliminación")
            if st.session_state["rol_actual"] != 'admin':
                st.warning("Módulo bloqueado. Requiere privilegios administrativos.")
            else:
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    with st.container(border=True):
                        st.markdown("#### Borrar por ID")
                        id_del = st.number_input("ID único de fila:", min_value=1, step=1)
                        if st.button("ELIMINAR PERMANENTEMENTE", type="primary", use_container_width=True):
                            with engine.begin() as conn:
                                conn.execute(text("DELETE FROM registros_picheo WHERE id = :id;"), {"id": id_del})
                            st.success(f"Fila {id_del} destruida.")
                            st.rerun()
                with col_b2:
                    with st.container(border=True):
                        st.markdown("#### Purgar Servidor")
                        st.error("Peligro: Vaciará por completo la tabla de picheos en Neon.")
                        check_purgar = st.checkbox("Entiendo los riesgos y confirmo el vaciado.")
                        if st.button("EJECUTAR PURGA MÁXIMA", type="primary", use_container_width=True) and check_purgar:
                            with engine.begin() as conn:
                                conn.execute(text("TRUNCATE TABLE registros_picheo;"))
                            st.success("Servidor restaurado a cero.")
                            st.rerun()

        # Monitor de datos en tiempo real
        st.write("---")
        try:
            with engine.connect() as conexion:
                todos_los_datos = conexion.execute(text("SELECT id, fecha_registro, id_control, cantidad_picheos, operador_responsable FROM registros_picheo ORDER BY id DESC;")).fetchall()
            if todos_los_datos:
                df_total = pd.DataFrame(todos_los_datos, columns=["ID FILA", "FECHA", "CÓDIGO CONTROL", "CANTIDAD PICHEOS", "OPERADOR ENCARGADO"])
                
                # Buffer de exportación directa a Excel
                buffer_descarga = io.BytesIO()
                with pd.ExcelWriter(buffer_descarga, engine='openpyxl') as writer:
                    df_total.to_excel(writer, index=False, sheet_name='Historial_Completo')
                
                st.download_button(
                    label=f"📥 EXPORTAR HISTORIAL COMPLETO DE NEON ({len(df_total)} REGISTROS)",
                    data=buffer_descarga.getvalue(),
                    file_name=f"Reporte_Total_ApexPitch_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
                st.markdown("##### Vista de Monitoreo (Últimos 100 registros)")
                st.dataframe(df_total.head(100), use_container_width=True, height=380)
            else:
                st.info("La base de datos se encuentra vacía.")
        except Exception as e:
            st.error(f"Error de visualización en el grid: {e}")

    # ------------------------------------------
    # MÓDULO C: SEGURIDAD Y CONTROL DE PERSONAL
    # ------------------------------------------
    elif modulo_seleccionado == "👥 Control de Personal" and st.session_state["rol_actual"] == "admin":
        st.title("Gestión de Usuarios")
        with st.form("formulario_alta_usuarios"):
            col_us1, col_us2, col_us3 = st.columns(3)
            with col_us1: n_user = st.text_input("Nombre de Usuario").strip().lower()
            with col_us2: n_pass = st.text_input("Contraseña", type="password").strip()
            with col_us3: n_rol = st.selectbox("Perfil de Permisos", ["operador", "admin"])
            if st.form_submit_button("CREAR CUENTA", use_container_width=True):
                if n_user and len(n_pass) >= 6:
                    try:
                        h_pass = hashlib.sha256(n_pass.encode('utf-8')).hexdigest()
                        with engine.begin() as conn:
                            conn.execute(text("INSERT INTO usuarios (nombre_usuario, contrasena_hash, rol_acceso) VALUES (:n, :h, :r);"), {"n": n_user, "h": h_pass, "r": n_rol})
                        st.success(f"Cuenta para '{n_user}' activa.")
                        st.rerun()
                    except: 
                        st.error("El identificador ya se encuentra registrado.")
                else: 
                    st.warning("La contraseña debe contener un mínimo de 6 caracteres.")
                
        with engine.connect() as conn:
            usrs = conn.execute(text("SELECT id, nombre_usuario, rol_acceso FROM usuarios ORDER BY id ASC;")).fetchall()
        st.dataframe(pd.DataFrame(usrs, columns=["ID PERFIL", "USUARIO", "ROL ACCESO"]), use_container_width=True)

    # ------------------------------------------
    # MÓDULO D: CONFIGURACIÓN GLOBAL
    # ------------------------------------------
    elif modulo_seleccionado == "⚙️ Ajustes del Sistema" and st.session_state["rol_actual"] == "admin":
        st.title("Ajustes del Sistema")
        try:
            with engine.connect() as conn:
                tar_vigente = conn.execute(text("SELECT valor_parametro FROM configuracion_global WHERE clave_parametro='tarifa_unidad';")).scalar() or "0.024"
            with st.form("form_tasa"):
                input_tasa = st.text_input("Tarifa por Unidad de Picheo (USD):", value=tar_vigente).strip()
                if st.form_submit_button("MODIFICAR TASA DE CÁLCULO", use_container_width=True):
                    try:
                        tasa_validada = str(float(input_tasa))
                        with engine.begin() as conn:
                            conn.execute(text("UPDATE configuracion_global SET valor_parametro = :v WHERE clave_parametro = 'tarifa_unidad';"), {"v": tasa_validada})
                        st.success("Parámetro financiero actualizado globalmente.")
                        st.rerun()
                    except ValueError:
                        st.error("Error: Ingrese un valor numérico válido (use punto para los decimales).")
        except Exception as e:
            st.error(f"Fallo de lectura de parámetros: {e}")

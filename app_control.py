import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import io

# Configuración de interfaz profesional de alta densidad de datos
st.set_page_config(
    page_title="Apex Pitch - Sistema de Control", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# ==========================================
# 1. CONEXIÓN Y VERIFICACIÓN DE NEON (POSTGRESQL)
# ==========================================
@st.cache_resource
def conectar_base_datos_neon():
    """
    Busca de forma estricta las credenciales de Neon en los Secrets de Streamlit.
    Garantiza compatibilidad con el prefijo 'postgresql://' requerido por SQLAlchemy.
    """
    url_conexion = None
    
    # Intenta leer ambas estructuras comunes de Secrets
    if "connections" in st.secrets and "postgres" in st.secrets["connections"]:
        url_conexion = st.secrets["connections"]["postgres"]["url"]
    elif "db_url" in st.secrets:
        url_conexion = st.secrets["db_url"]
        
    if url_conexion:
        # Corrección de protocolo antiguo si es necesario
        if url_conexion.startswith("postgres://"):
            url_conexion = url_conexion.replace("postgres://", "postgresql://", 1)
        
        # Parámetros optimizados para mantener conexiones persistentes y seguras en la nube
        return create_engine(
            url_conexion, 
            pool_size=10, 
            max_overflow=20, 
            pool_pre_ping=True
        )
    else:
        st.error("🚨 ERROR DE INFRAESTRUCTURA: No se detectó la URL de Neon en los Secrets de Streamlit.")
        st.info("Por favor, verifica que 'db_url' o 'connections.postgres' estén configurados en el panel web.")
        st.stop()

# Inicialización del motor de datos de producción
engine = conectar_base_datos_neon()

def asegurar_estructura_tablas():
    """Garantiza la existencia de las tablas en Neon con tipos de datos óptimos."""
    with engine.begin() as conexion:
        # Tabla de Acceso de Usuarios
        conexion.execute(text("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY, 
                nombre_usuario TEXT UNIQUE NOT NULL, 
                contrasena_hash TEXT NOT NULL, 
                rol_acceso TEXT NOT NULL DEFAULT 'operador'
            );
        """))
        
        # Tabla Principal de Muestras de Picheos
        conexion.execute(text("""
            CREATE TABLE IF NOT EXISTS registros_picheo (
                id SERIAL PRIMARY KEY, 
                fecha_registro TEXT NOT NULL, 
                id_control TEXT NOT NULL, 
                cantidad_picheos INTEGER NOT NULL, 
                operador_responsable TEXT NOT NULL
            );
        """))
        
        # Tabla de Parámetros Globales
        conexion.execute(text("""
            CREATE TABLE IF NOT EXISTS configuracion_global (
                clave_parametro TEXT PRIMARY KEY, 
                valor_parametro TEXT NOT NULL
            );
        """))

def inicializar_valores_sistema():
    """Inserta la tarifa monetaria por defecto y la cuenta maestra si la base de datos está limpia."""
    with engine.begin() as conexion:
        conexion.execute(text("""
            INSERT INTO configuracion_global (clave_parametro, valor_parametro) 
            VALUES ('tarifa_unidad', '0.024') 
            ON CONFLICT (clave_parametro) DO NOTHING;
        """))

    with engine.connect() as conexion:
        cuenta_admin_existe = conexion.execute(
            text("SELECT COUNT(*) FROM usuarios WHERE nombre_usuario = 'admin';")
        ).scalar()
    
    if cuenta_admin_existe == 0:
        hash_maestro = hashlib.sha256("admin123".encode('utf-8')).hexdigest()
        with engine.begin() as conexion:
            conexion.execute(
                text("""
                    INSERT INTO usuarios (nombre_usuario, contrasena_hash, rol_acceso) 
                    VALUES ('admin', :hash, 'admin');
                """), 
                {"hash": hash_maestro}
            )

# Despliegue seguro de persistencia
try:
    asegurar_estructura_tablas()
    inicializar_valores_sistema()
except Exception as error_conexion:
    st.error(f"🚨 Error de sincronización con el servidor Neon: {error_conexion}")
    st.stop()

# Inicialización del estado de la sesión
if "sesion_activa" not in st.session_state:
    st.session_state["sesion_activa"] = False
    st.session_state["usuario_actual"] = None
    st.session_state["rol_actual"] = None

# ==========================================
# 2. PANTALLA DE CONTROL DE ACCESO (LOGIN)
# ==========================================
if not st.session_state["sesion_activa"]:
    st.title("⚾ Apex Pitch - Autenticación")
    
    input_usuario = st.text_input("Nombre de Usuario").strip().lower()
    input_contrasena = st.text_input("Contraseña de Seguridad", type="password").strip()
    
    if st.button("INGRESAR AL SISTEMA", use_container_width=True):
        if input_usuario and input_contrasena:
            # Bypass Maestro Directo (Resolución de bloqueos)
            if input_usuario == "admin" and input_contrasena == "admin123":
                st.session_state["sesion_activa"] = True
                st.session_state["usuario_actual"] = "admin"
                st.session_state["rol_actual"] = "admin"
                st.success("Acceso Maestro Autorizado.")
                st.rerun()
            else:
                # Consulta de Credenciales en Neon
                try:
                    with engine.connect() as conexion:
                        consulta = text("""
                            SELECT nombre_usuario, contrasena_hash, rol_acceso 
                            FROM usuarios WHERE nombre_usuario = :usr;
                        """)
                        registro = conexion.execute(consulta, {"usr": input_usuario}).mappings().fetchone()
                    
                    if registro:
                        hash_guardado = registro["contrasena_hash"]
                        rol_usuario = registro["rol_acceso"]
                        nombre_db = registro["nombre_usuario"]
                        
                        hash_entrada = hashlib.sha256(input_contrasena.encode('utf-8')).hexdigest()
                        
                        # Validación híbrida (soporta hash moderno o texto plano recuperado)
                        if hash_entrada == hash_guardado or input_contrasena == hash_guardado:
                            st.session_state["sesion_activa"] = True
                            st.session_state["usuario_actual"] = nombre_db
                            st.session_state["rol_actual"] = rol_usuario
                            st.success("Acceso Autorizado.")
                            st.rerun()
                        else:
                            st.error("La contraseña ingresada no es válida.")
                    else:
                        st.error("El usuario indicado no se encuentra registrado.")
                except Exception as error_login:
                    st.error(f"Error de autenticación: {error_login}")
        else:
            st.warning("Por favor, complete ambos campos para continuar.")

# ==========================================
# 3. ENTORNO DE TRABAJO (SESIÓN ACTIVA)
# ==========================================
else:
    # Panel de Navegación Lateral Estilizado
    st.sidebar.title("⚾ Navegación")
    st.sidebar.markdown(f"**Operador:** `{st.session_state['usuario_actual'].upper()}`")
    st.sidebar.markdown(f"**Permisos:** `{st.session_state['rol_actual'].upper()}`")
    st.sidebar.write("---")
    
    modulos_disponibles = ["📊 Resumen General", "📝 Registro de Picheos"]
    if st.session_state["rol_actual"] == "admin":
        modulos_disponibles.extend(["👥 Control de Personal", "⚙️ Ajustes del Sistema"])
        
    modulo_seleccionado = st.sidebar.radio("Secciones del Sistema", modulos_disponibles)
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
        st.title("Métricas del Sistema")
        
        with st.container(border=True):
            st.write("##### Rango de Fechas de Evaluación")
            col_fecha_1, col_fecha_2 = st.columns(2)
            with col_fecha_1:
                fecha_inicio = st.date_input("Fecha Inicial:", value=datetime.now() - timedelta(days=15))
            with col_fecha_2:
                fecha_termino = st.date_input("Fecha Final:", value=datetime.now())
                
        if fecha_inicio > fecha_termino:
            st.error("Error: La fecha de inicio no puede ser posterior a la fecha final.")
        else:
            try:
                with engine.connect() as conexion:
                    volumen_picheos = conexion.execute(text("""
                        SELECT SUM(cantidad_picheos) FROM registros_picheo 
                        WHERE fecha_registro BETWEEN :inicio AND :termino
                    """), {
                        "inicio": fecha_inicio.strftime('%Y-%m-%d'), 
                        "termino": fecha_termino.strftime('%Y-%m-%d')
                    }).scalar() or 0
                    
                    tarifa_db = conexion.execute(
                        text("SELECT valor_parametro FROM configuracion_global WHERE clave_parametro='tarifa_unidad';")
                    ).scalar() or "0.024"
                    tarifa_unidad = float(tarifa_db)
                
                col_metrica_1, col_metrica_2 = st.columns(2)
                with col_metrica_1:
                    st.metric(label="VOLUMEN TOTAL DE PICHEOS", value=f"{volumen_picheos:,}")
                with col_metrica_2:
                    st.metric(label="RENDIMIENTO MONETARIO (USD)", value=f"${volumen_picheos * tarifa_unidad:,.2f}")
                
            except Exception as error_dashboard:
                st.error(f"Error al calcular métricas: {error_dashboard}")

    # ------------------------------------------
    # MÓDULO B: REGISTRO DE PICHEOS (CRUD)
    # ------------------------------------------
    elif modulo_seleccionado == "📝 Registro de Picheos":
        st.title("Panel de Trabajo")
        
        pestana_manual, pestana_archivo, pestana_edicion, pestana_borrado = st.tabs([
            "➕ Ficha Manual", 
            "📂 Subir Archivo Excel/CSV",
            "✏️ Corregir Datos",
            "🗑️ Eliminar Registros"
        ])
        
        # 1. Ficha Manual
        with pestana_manual:
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
                        st.error("El campo 'Código de Control' es mandatorio.")
                    else:
                        try:
                            with engine.begin() as conexion:
                                conexion.execute(text("""
                                    INSERT INTO registros_picheo (fecha_registro, id_control, cantidad_picheos, operador_responsable)
                                    VALUES (:fecha, :id_c, :cant, :operador);
                                """), {
                                    "fecha": form_fecha.strftime('%Y-%m-%d'), 
                                    "id_c": form_codigo_control, 
                                    "cant": form_cantidad, 
                                    "operador": st.session_state["usuario_actual"]
                                })
                            st.success(f"Registro exitoso: Código [{form_codigo_control}] guardado.")
                            st.rerun()
                        except Exception as error_guardado:
                            st.error(f"Fallo de almacenamiento: {error_guardado}")
                            
        # 2. Subida de Archivo Lote
        with pestana_archivo:
            st.write("##### Importar Datos Masivos")
            archivo_subido = st.file_uploader("Selecciona archivo de datos", type=["csv", "xlsx"])
            if archivo_subido is not None:
                try:
                    df_datos = pd.read_csv(archivo_subido) if archivo_subido.name.endswith('.csv') else pd.read_excel(archivo_subido)
                    df_datos.columns = [columna.strip().lower() for columna in df_datos.columns]
                    
                    st.write("Muestra preliminar del archivo:")
                    st.dataframe(df_datos.head(5), use_container_width=True)
                    
                    columnas_necesarias = ['fecha_registro', 'id_control', 'cantidad_picheos', 'operador_responsable']
                    if all(col in df_datos.columns for col in columnas_necesarias):
                        if st.button("🚀 PROCESAR E IMPORTAR TODO EL ARCHIVO", use_container_width=True):
                            df_datos['fecha_registro'] = df_datos['fecha_registro'].astype(str)
                            df_datos['id_control'] = df_datos['id_control'].astype(str).str.strip()
                            df_datos['cantidad_picheos'] = pd.to_numeric(df_datos['cantidad_picheos'], errors='coerce').fillna(1).astype(int)
                            df_datos['operador_responsable'] = df_datos['operador_responsable'].astype(str).str.strip()
                            
                            with engine.begin() as conexion:
                                df_datos[columnas_necesarias].to_sql('registros_picheo', con=conexion, if_exists='append', index=False)
                            st.success(f"Proceso finalizado. {len(df_datos)} filas integradas en Neon.")
                            st.rerun()
                    else:
                        st.error("Estructura incorrecta. Las columnas deben ser exactamente: fecha_registro, id_control, cantidad_picheos, operador_responsable")
                except Exception as error_excel:
                    st.error(f"Error de procesamiento: {error_excel}")

        # 3. Corregir e Modificar
        with pestana_edicion:
            st.write("##### Modificación de Valores")
            codigo_buscado = st.text_input("Ingresa el Código de Control exacto a modificar:", "").strip()
            
            if codigo_buscado:
                with engine.connect() as conexion:
                    consulta_edicion = text("""
                        SELECT id, fecha_registro, id_control, cantidad_picheos, operador_responsable 
                        FROM registros_picheo WHERE id_control LIKE :busqueda LIMIT 10;
                    """)
                    coincidencias = conexion.execute(consulta_edicion, {"busqueda": f"%{codigo_buscado}%"}).fetchall()
                
                if coincidencias:
                    opciones_filas = {fila[0]: f"Fila ID: {fila[0]} | Código: {fila[2]} | Picheos: {fila[3]} | Fecha: {fila[1]}" for fila in coincidencias}
                    id_seleccionado = st.selectbox("Seleccione el registro exacto a editar:", opciones_filas.keys(), format_func=lambda x: opciones_filas[x])
                    
                    with engine.connect() as conexion:
                        valores_actuales = conexion.execute(text("SELECT * FROM registros_picheo WHERE id = :id;"), {"id": id_seleccionado}).fetchone()
                    
                    if valores_actuales:
                        st.markdown("---")
                        with st.form("formulario_edicion_valores"):
                            col_ed1, col_ed2, col_ed3 = st.columns(3)
                            with col_ed1:
                                nuevo_codigo = st.text_input("Código de Control", value=valores_actuales[2])
                            with col_ed2:
                                nueva_cant_picheos = st.number_input("Cantidad", min_value=1, step=1, value=int(valores_actuales[3]))
                            with col_ed3:
                                nueva_fecha_str = st.text_input("Fecha (AAAA-MM-DD)", value=valores_actuales[1])
                            
                            if st.form_submit_button("COMPROMETER CAMBIOS", use_container_width=True):
                                try:
                                    with engine.begin() as conexion:
                                        conexion.execute(text("""
                                            UPDATE registros_picheo 
                                            SET fecha_registro = :f, id_control = :idc, cantidad_picheos = :c
                                            WHERE id = :id;
                                        """), {
                                            "f": nueva_fecha_str.strip(), 
                                            "idc": nuevo_codigo.strip(), 
                                            "c": nueva_cant_picheos, 
                                            "id": id_seleccionado
                                        })
                                    st.success("Cambios grabados con éxito.")
                                    st.rerun()
                                except Exception as error_modificar:
                                    st.error(f"Error de actualización: {error_modificar}")
                else:
                    st.warning("No se hallaron coincidencias en el servidor.")

        # 4. Eliminar Registros
        with pestana_borrado:
            st.write("##### 🚨 Remoción de Datos")
            col_b1, col_b2 = st.columns(2)
            
            with col_b1:
                st.markdown("#### Eliminar Fila por ID")
                id_a_eliminar = st.number_input("Número de Fila ID:", min_value=1, step=1)
                check_seguridad_uno = st.checkbox("Confirmo la remoción de esta fila unitaria.", key="chk_seg_1")
                
                if st.button("EJECUTAR ELIMINACIÓN", use_container_width=True, type="primary"):
                    if st.session_state["rol_actual"] != 'admin':
                        st.error("Permisos denegados. Módulo exclusivo de administración.")
                    elif not check_seguridad_uno:
                        st.warning("Debe tildar la confirmación de seguridad.")
                    else:
                        with engine.begin() as conexion:
                            fila_existe = conexion.execute(text("SELECT COUNT(*) FROM registros_picheo WHERE id = :id;"), {"id": id_a_eliminar}).scalar()
                            if fila_existe == 0:
                                st.warning(f"El ID {id_a_eliminar} no existe en las tablas.")
                            else:
                                conexion.execute(text("DELETE FROM registros_picheo WHERE id = :id;"), {"id": id_a_eliminar})
                                st.success("Fila eliminada permanentemente de Neon.")
                                st.rerun()
            
            with col_b2:
                st.markdown("#### Purgar Base de Datos")
                st.error("⚠️ Acción crítica: Limpiará de forma definitiva toda la tabla histórica de picheos.")
                check_seguridad_tabla = st.checkbox("SÍ, deseo vaciar por completo el historial de picheos de Neon.", key="chk_seg_tabla")
                
                if st.button("VACIAR HISTORIAL COMPLETO", use_container_width=True, type="primary"):
                    if st.session_state["rol_actual"] != 'admin':
                        st.error("Acceso denegado.")
                    elif not check_seguridad_tabla:
                        st.warning("Debe validar la casilla de confirmación absoluta.")
                    else:
                        try:
                            with engine.begin() as conexion:
                                conexion.execute(text("DELETE FROM registros_picheo;"))
                            st.success("Tabla purgada. Neon se encuentra limpio de picheos.")
                            st.rerun()
                        except Exception as error_purga:
                            st.error(f"Error en vaciado de tablas: {error_purga}")

        # Visor de Datos Global
        st.write("---")
        st.subheader("Historial en Tiempo Real (Últimos 1000 registros)")
        try:
            with engine.connect() as conexion:
                consulta_tabla = text("""
                    SELECT id, fecha_registro, id_control, cantidad_picheos, operador_responsable 
                    FROM registros_picheo ORDER BY id DESC LIMIT 1000;
                """)
                datos_servidor = conexion.execute(consulta_tabla).fetchall()
            
            if datos_servidor:
                df_historial = pd.DataFrame(
                    datos_servidor, 
                    columns=["ID FILA", "FECHA", "CÓDIGO CONTROL", "CANTIDAD PICHEOS", "OPERADOR ENCARGADO"]
                )
                
                buffer_descarga = io.BytesIO()
                with pd.ExcelWriter(buffer_descarga, engine='openpyxl') as writer:
                    df_historial.to_excel(writer, index=False, sheet_name='Historial_Picheos')
                
                st.download_button(
                    label="📥 GENERAR REPORTE EXCEL (PROX)",
                    data=buffer_descarga.getvalue(),
                    file_name=f"Reporte_ApexPitch_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                st.dataframe(df_historial, use_container_width=True, height=400)
            else:
                st.info("No se registran datos indexados en la base de datos de Neon.")
        except Exception as error_tabla_general:
            st.error(f"Error de lectura en visualización de tablas: {error_tabla_general}")

    # ------------------------------------------
    # MÓDULO C: CONTROL DE PERSONAL (ADMIN)
    # ------------------------------------------
    elif modulo_seleccionado == "👥 Control de Personal" and st.session_state["rol_actual"] == "admin":
        st.title("Administración de Personal de Operaciones")
        
        with st.form("formulario_alta_usuarios"):
            st.write("##### Alta de Nuevos Operadores")
            col_us1, col_us2, col_us3 = st.columns(3)
            with col_us1:
                nuevo_nombre_usr = st.text_input("Nombre de Usuario").strip().lower()
            with col_us2:
                nueva_clave_usr = st.text_input("Contraseña (Min. 6 caracteres)", type="password").strip()
            with col_us3:
                nuevo_rol_usr = st.selectbox("Perfil de Permisos", ["operador", "admin"])
                
            if st.form_submit_button("REGISTRAR NUEVA CUENTA", use_container_width=True):
                if not nuevo_nombre_usr or not nueva_clave_usr:
                    st.error("Todos los campos de usuario son requeridos.")
                elif len(nueva_clave_usr) < 6:
                    st.warning("La contraseña debe tener una longitud mínima de 6 caracteres.")
                else:
                    try:
                        hash_clave = hashlib.sha256(nueva_clave_usr.encode('utf-8')).hexdigest()
                        with engine.begin() as conexion:
                            conexion.execute(text("""
                                INSERT INTO usuarios (nombre_usuario, contrasena_hash, rol_acceso) 
                                VALUES (:nom, :hash, :rol);
                            """), {"nom": nuevo_nombre_usr, "hash": hash_clave, "rol": nuevo_rol_usr})
                        st.success(f"Cuenta de usuario `{nuevo_nombre_usr}` creada.")
                        st.rerun()
                    except Exception as error_usuarios:
                        st.error("El nombre de usuario ya se encuentra registrado.")
                        
        st.write("---")
        st.subheader("Cuentas de Personal Habilitadas")
        try:
            with engine.connect() as conexion:
                usuarios_db = conexion.execute(text("SELECT id, nombre_usuario, rol_acceso FROM usuarios;")).fetchall()
            df_usuarios = pd.DataFrame(usuarios_db, columns=["ID PERFIL", "USUARIO", "ROL"])
            st.dataframe(df_usuarios, use_container_width=True)
            
            st.write("##### Baja de Cuentas")
            id_cuenta_baja = st.number_input("ID de la Cuenta a dar de Baja:", min_value=1, step=1)
            if st.button("ELIMINAR ACCESO DE USUARIO", use_container_width=True):
                with engine.begin() as conexion:
                    usuario_registro = conexion.execute(text("SELECT nombre_usuario FROM usuarios WHERE id = :id;"), {"id": id_cuenta_baja}).fetchone()
                    if not usuario_registro:
                        st.warning("El ID ingresado no coincide con ninguna cuenta activa.")
                    elif usuario_registro[0] == st.session_state["usuario_actual"]:
                        st.error("Un usuario administrador no puede revocar sus propios permisos en sesión activa.")
                    elif usuario_registro[0] == "admin":
                        st.error("La cuenta primaria 'admin' no puede ser dada de baja por seguridad.")
                    else:
                        conexion.execute(text("DELETE FROM usuarios WHERE id = :id;"), {"id": id_cuenta_baja})
                        st.success(f"Permisos revocados para el usuario `{usuario_registro[0]}`.")
                        st.rerun()
        except Exception as error_lista_usuarios:
            st.error(f"Error al cargar perfiles: {error_lista_usuarios}")

    # ------------------------------------------
    # MÓDULO D: AJUSTES DEL SISTEMA (ADMIN)
    # ------------------------------------------
    elif modulo_seleccionado == "⚙️ Ajustes del Sistema" and st.session_state["rol_actual"] == "admin":
        st.title("Ajustes del Sistema")
        
        try:
            with engine.connect() as conexion:
                tarifa_vigente = conexion.execute(text("SELECT valor_parametro FROM configuracion_global WHERE clave_parametro='tarifa_unidad';")).scalar() or "0.024"
            
            with st.form("formulario_configuracion_tasa"):
                st.write("##### Configuración de Parámetros Financieros")
                input_nueva_tarifa = st.text_input("Tasa/Tarifa por Unidad de Picheo (USD):", value=tarifa_vigente).strip()
                
                if st.form_submit_button("ESTABLECER NUEVA TASA", use_container_width=True):
                    try:
                        tarifa_validada = float(input_nueva_tarifa)
                        if tarifa_validada < 0:
                            st.error("La tarifa del sistema no puede constituir un valor negativo.")
                        else:
                            with engine.begin() as conexion:
                                conexion.execute(text("""
                                    UPDATE configuracion_global SET valor_parametro = :val 
                                    WHERE clave_parametro = 'tarifa_unidad';
                                """), {"val": str(tarifa_validada)})
                            st.success(f"Cambio aplicado. Nueva tarifa fijada en ${tarifa_validada} USD.")
                            st.rerun()
                    except ValueError:
                        st.error("Formato inválido. Ingrese una expresión numérica válida (Ej. 0.024).")
        except Exception as error_config:
            st.error(f"Error al leer parámetros globales: {error_config}")

import streamlit as st
from sqlalchemy import text
import pandas as pd
import hashlib
from datetime import datetime, timedelta

# Configuración de página de Streamlit estilo BeisSeven
st.set_page_config(page_title="BeisSeven - Gestión de Picheo", layout="wide")

# 1. Conexión segura a tu base de datos PostgreSQL en Neon
conn = st.connection("postgresql", type="sql")

# 2. Inicialización estructural de tablas en la nube si no existen
with conn.session as session:
    # Tabla de usuarios
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nombre TEXT UNIQUE NOT NULL,
            pass TEXT NOT NULL,
            rol TEXT NOT NULL
        );
    """))
    # Tabla de picheos/lanzamientos
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS picheos (
            id SERIAL PRIMARY KEY,
            fecha DATE NOT NULL,
            id_control TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            operador TEXT NOT NULL
        );
    """))
    # Tabla de configuraciones (Precio/Constante de conversión)
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS config (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        );
    """))
    # Insertar valores por defecto iniciales si la base está vacía
    session.execute(text("INSERT INTO config (clave, valor) VALUES ('precio', '0.024') ON CONFLICT (clave) DO NOTHING;"))
    admin_pass = hashlib.sha256("admin123".encode()).hexdigest()
    session.execute(text("INSERT INTO usuarios (nombre, pass, rol) VALUES ('admin', :pass, 'admin') ON CONFLICT (nombre) DO NOTHING;"), {"pass": admin_pass})
    session.commit()

# --- CONTROL DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario"] = None
    st.session_state["rol"] = None

# ==========================================
# VISTA: INICIO DE SESIÓN
# ==========================================
if not st.session_state["autenticado"]:
    st.markdown("<h1 style='text-align: center; color: #00AAFF;'>⚾ BeisSeven</h1>", unsafe_title=True)
    st.markdown("<h3 style='text-align: center; color: white;'>Sistema de Gestión Web</h3>", unsafe_title=True)
    
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        with st.form("form_login"):
            input_user = st.text_input("Usuario:").strip()
            input_pass = st.text_input("Contraseña:", show="*").strip()
            btn_login = st.form_submit_button("INGRESAR")
            
        if btn_login:
            if not input_user or not input_pass:
                st.warning("Por favor, ingrese usuario y contraseña.")
            else:
                pass_hash = hashlib.sha256(input_pass.encode()).hexdigest()
                df_user = conn.query("SELECT id, nombre, pass, rol FROM usuarios WHERE nombre = :nom AND pass = :pw;", 
                                     params={"nom": input_user, "pw": pass_hash}, ttl=0)
                
                if not df_user.empty:
                    st.session_state["autenticado"] = True
                    st.session_state["usuario"] = df_user.iloc[0]["nombre"]
                    st.session_state["rol"] = df_user.iloc[0]["rol"]
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas.")
else:
    # ==========================================
    # APLICACIÓN PRINCIPAL (LOGUEADO)
    # ==========================================
    # Sidebar de navegación estilo panel de control original
    st.sidebar.markdown(f"<h2 style='color: #00AAFF;'>⚾ BeisSeven</h2>", unsafe_title=True)
    st.sidebar.write(f"**Usuario:** {st.session_state['usuario'].upper()}")
    st.sidebar.write(f"**Rol:** {st.session_state['rol'].upper()}")
    st.sidebar.write("---")
    
    opcion_menu = st.sidebar.radio(
        "Navegación", 
        ["📊 DASHBOARD", "📝 REGISTROS", "👥 USUARIOS", "⚙️ CONFIG"]
    )
    
    st.sidebar.write("---")
    if st.sidebar.button("🚪 CERRAR SESIÓN", use_container_width=True):
        st.session_state["autenticado"] = False
        st.session_state["usuario"] = None
        st.session_state["rol"] = None
        st.rerun()

    # ─── VISTA: DASHBOARD ───
    if opcion_menu == "📊 DASHBOARD":
        st.title("Resumen de Operaciones")
        
        # Filtros Rápidos de Fecha
        with st.container(border=True):
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                fecha_desde = st.date_input("Desde:", datetime.today() - timedelta(days=30))
            with col_f2:
                fecha_hasta = st.date_input("Hasta:", datetime.today())
            with col_f3:
                st.write("<br/>", unsafe_title=True)
                btn_filtrar = st.button("ACTUALIZAR MÉTRICAS", use_container_width=True)
        
        if fecha_desde > fecha_hasta:
            st.error("La fecha 'Desde' no puede ser mayor que 'Hasta'.")
        else:
            # Consultar métricas en Neon filtradas por rango
            df_resumen = conn.query("SELECT cantidad FROM picheos WHERE fecha BETWEEN :desde AND :hasta;", 
                                    params={"desde": fecha_desde, "hasta": fecha_hasta}, ttl=0)
            
            total_picheos = int(df_resumen["cantidad"].sum()) if not df_resumen.empty else 0
            
            df_p = conn.query("SELECT valor FROM config WHERE clave='precio';", ttl=0)
            precio = float(df_p.iloc[0]["valor"]) if not df_p.empty else 0.024
            
            usd_estimado = total_picheos * precio
            
            # Tarjetas de KPI visuales
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                with st.container(border=True):
                    st.markdown("<p style='text-align: center; font-size: 18px; font-weight: bold;'>TOTAL PICHEOS</p>", unsafe_title=True)
                    st.markdown(f"<h1 style='text-align: center; color: #00AAFF;'>{total_picheos:,}</h1>", unsafe_title=True)
            with col_c2:
                with st.container(border=True):
                    st.markdown("<p style='text-align: center; font-size: 18px; font-weight: bold;'>USD ESTIMADO</p>", unsafe_title=True)
                    st.markdown(f"<h1 style='text-align: center; color: #00FF77;'>${usd_estimado:,.2f}</h1>", unsafe_title=True)

    # ─── VISTA: REGISTROS ───
    elif opcion_menu == "📝 REGISTROS":
        st.title("Gestión de Registros de Picheo")
        
        # Formulario de entrada
        with st.container(border=True):
            col_r1, col_r2, col_r3, col_r4 = st.columns([1.5, 2, 1.5, 1.5])
            with col_r1:
                reg_fecha = st.date_input("Fecha:", datetime.today())
            with col_r2:
                reg_id = st.text_input("ID Control", placeholder="Ej: CTRL-001").strip()
            with col_r3:
                reg_cant = st.number_input("Cantidad:", min_value=1, step=1, value=50)
            with col_r4:
                st.write("<br/>", unsafe_title=True)
                btn_guardar = st.button("GUARDAR DATO", use_container_width=True)
                
        if btn_guardar:
            if not reg_id:
                st.error("Por favor, introduzca un ID de Control válido.")
            else:
                with conn.session as session:
                    session.execute(
                        text("INSERT INTO picheos (fecha, id_control, cantidad, operador) VALUES (:f, :id, :c, :op);"),
                        {"f": reg_fecha, "id": reg_id, "微微": reg_id, "c": reg_cant, "op": st.session_state["usuario"]}
                    )
                    session.commit()
                st.success(f"Registro añadido con éxito: {reg_id} ({reg_cant} lanzamientos)")
                st.rerun()

        st.write("---")
        
        # Obtener los datos actuales de la tabla de Neon
        df_picheos = conn.query("SELECT id, fecha, id_control, cantidad, operador FROM picheos ORDER BY id DESC;", ttl=0)
        
        if df_picheos.empty:
            st.info("Aún no existen registros almacenados en la base de datos.")
        else:
            # Botones nativos web para exportación descargable limpia
            col_exp1, col_exp2 = st.columns([6, 1])
            with col_exp2:
                # Conversión a Excel en memoria usando pandas
                excel_data = df_picheos.to_excel(index=False, engine='openpyxl')
                st.download_button(
                    label="📥 EXCEL",
                    data=df_picheos.to_csv(index=False).encode('utf-8'), # Alternativa directa CSV rápida
                    file_name=f"Reporte_Picheo_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
            # Despliegue de la tabla interactiva de datos
            st.dataframe(df_picheos, use_container_width=True, hide_index=True)
            
            # Sección de eliminación exclusiva para Administradores
            if st.session_state["rol"] == "admin":
                st.write("<br/>", unsafe_title=True)
                id_eliminar = st.number_input("Introduzca el ID numérico del registro que desea remover:", min_value=1, step=1)
                if st.button("🗑️ ELIMINAR REGISTRO SELECCIONADO", type="primary"):
                    with conn.session as session:
                        session.execute(text("DELETE FROM picheos WHERE id = :id;"), {"id": id_eliminar})
                        session.commit()
                    st.success(f"Registro ID {id_eliminar} removido permanentemente de Neon.")
                    st.rerun()

    # ─── VISTA: USUARIOS (SOLO ADMIN) ───
    elif opcion_menu == "👥 USUARIOS":
        st.title("Gestión de Personal")
        
        if st.session_state["rol"] != "admin":
            st.error("🔒 Acceso Restringido. Contacte a un administrador para gestionar usuarios.")
        else:
            with st.container(border=True):
                col_u1, col_u2, col_u3, col_u4 = st.columns(4)
                with col_u1:
                    usr_nom = st.text_input("Nombre de usuario:").strip()
                with col_u2:
                    usr_pass = st.text_input("Contraseña:", show="*").strip()
                with col_u3:
                    usr_rol = st.selectbox("Rol del usuario:", ["operador", "admin"])
                with col_u4:
                    st.write("<br/>", unsafe_title=True)
                    btn_crear_usr = st.button("➕ CREAR USUARIO", use_container_width=True)
            
            if btn_crear_usr:
                if not usr_nom or not usr_pass:
                    st.warning("Nombre y contraseña son campos de llenado obligatorio.")
                else:
                    try:
                        pass_hash = hashlib.sha256(usr_pass.encode()).hexdigest()
                        with conn.session as session:
                            session.execute(
                                text("INSERT INTO usuarios (nombre, pass, rol) VALUES (:n, :p, :r);"),
                                {"n": usr_nom, "p": pass_hash, "r": usr_rol}
                            )
                            session.commit()
                        st.success(f"Usuario '{usr_nom}' dado de alta exitosamente.")
                        st.rerun()
                    except Exception:
                        st.error("El nombre de usuario ya se encuentra registrado.")
                        
            st.write("---")
            df_usrs = conn.query("SELECT id, nombre, rol FROM usuarios ORDER BY id ASC;", ttl=0)
            st.dataframe(df_usrs, use_container_width=True, hide_index=True)
            
            # Borrar usuario
            id_usr_del = st.number_input("ID del usuario a eliminar:", min_value=1, step=1)
            if st.button("🗑️ ELIMINAR USUARIO", type="primary"):
                df_check = conn.query("SELECT nombre FROM usuarios WHERE id = :id;", params={"id": id_usr_del}, ttl=0)
                if not df_check.empty and df_check.iloc[0]["nombre"] == st.session_state["usuario"]:
                    st.error("No puedes eliminar tu propia sesión activa.")
                else:
                    with conn.session as session:
                        session.execute(text("DELETE FROM usuarios WHERE id = :id;"), {"id": id_usr_del})
                        session.commit()
                    st.success("Usuario removido del sistema.")
                    st.rerun()

    # ─── VISTA: CONFIGURACIÓN (SOLO ADMIN) ───
    elif opcion_menu == "⚙️ CONFIG":
        st.title("Configuración del Sistema")
        
        if st.session_state["rol"] != "admin":
            st.error("🔒 Acceso Restringido.")
        else:
            df_p = conn.query("SELECT valor FROM config WHERE clave='precio';", ttl=0)
            precio_actual = df_p.iloc[0]["valor"] if not df_p.empty else "0.024"
            
            with st.container(border=True):
                st.write("**Configuración del Factor Analítico Matemático**")
                nv_precio = st.text_input("Precio por Unidad / Tasa de Conversión (USD):", value=precio_actual).strip()
                btn_save_conf = st.button("GUARDAR CONFIGURACIÓN")
                
            if btn_save_conf:
                try:
                    validar_num = float(nv_precio)
                    if validar_num < 0:
                        st.error("La tasa no puede representar valores negativos.")
                    else:
                        with conn.session as session:
                            session.execute(text("UPDATE config SET valor = :v WHERE clave = 'precio';"), {"v": nv_precio})
                            session.commit()
                        st.success("Configuración analítica guardada con éxito en la nube.")
                        st.rerun()
                except ValueError:
                    st.error("Introduzca un valor numérico válido (use punto para los decimales).")

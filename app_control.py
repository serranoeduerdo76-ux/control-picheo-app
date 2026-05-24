import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# Asumiendo que 'engine' ya viene importado o definido desde tu inicialización previa
# engine = obtener_motor_db()

st.title("⚾ Módulo de Registro")
st.subheader("Espacio preparado para integrar la carga masiva de datos y logs de picheo.")

# Creamos pestañas para separar la carga manual de la carga masiva
tab1, tab2 = st.tabs(["📝 Registro Individual", "📂 Carga Masiva (CSV/Excel)"])

# ==========================================
# PESTAÑA 1: REGISTRO INDIVIDUAL (FORMULARIO)
# ==========================================
with tab1:
    st.write("### Registrar Nuevo Log de Picheo")
    
    with st.form("formulario_picheo", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            lanzador = st.text_input("Nombre del Lanzador")
            tipo_picheo = st.selectbox("Tipo de Lanzamiento", ["Recta (FB)", "Curva (CB)", "Slider (SL)", "Cambio (CH)", "Sinker (SI)"])
        
        with col2:
            velocidad = st.number_input("Velocidad (MPH)", min_value=0.0, max_value=110.0, step=0.1)
            spin_rate = st.number_input("Spin Rate (RPM)", min_value=0, max_value=4000, step=50)
            
        with col3:
            resultado = st.selectbox("Resultado", ["Strike", "Bola", "Hit", "Out", "Jonrón"])
            fecha = st.date_input("Fecha del Evento")
            
        notas = st.text_area("Observaciones del Scouting")
        
        # Botón de envío del formulario
        enviar = st.form_submit_button("Guardar Lanzamiento")
        
        if enviar:
            if lanzador.strip() == "":
                st.error("El nombre del lanzador es obligatorio.")
            else:
                try:
                    with engine.connect() as conn:
                        conn.execute(text("""
                            INSERT INTO logs_picheo (lanzador, tipo_picheo, velocidad, spin_rate, resultado, fecha, notas)
                            VALUES (:lanzador, :tipo_picheo, :velocidad, :spin_rate, :resultado, :fecha, :notas);
                        """), {
                            "lanzador": lanzador,
                            "tipo_picheo": tipo_picheo,
                            "velocidad": velocidad,
                            "spin_rate": spin_rate,
                            "resultado": resultado,
                            "fecha": fecha,
                            "notas": notas
                        })
                        conn.commit()
                    st.success(f"✅ Registro guardado exitosamente para {lanzador}.")
                except Exception as e:
                    st.error(f"Error al guardar en la base de datos: {e}")

# ==========================================
# PESTAÑA 2: CARGA MASIVA
# ==========================================
with tab2:
    st.write("### Importar Logs desde Archivo externo")
    st.info("El archivo debe contener las siguientes columnas: *lanzador, tipo_picheo, velocidad, spin_rate, resultado, fecha, notas*")
    
    archivo_cargado = st.file_uploader("Selecciona un archivo CSV o Excel", type=["csv", "xlsx"])
    
    if archivo_cargado is not None:
        try:
            # Leer el archivo según su extensión
            if archivo_cargado.name.endswith('.csv'):
                df = pd.read_csv(archivo_cargado)
            else:
                df = pd.read_excel(archivo_cargado)
                
            st.write("##### Vista previa de los datos a importar:")
            st.dataframe(df.head())
            
            # Botón para confirmar la inserción masiva
            procesar = st.button("Confirmar Carga Masiva")
            
            if procesar:
                # Validar que las columnas necesarias existan
                columnas_requeridas = ['lanzador', 'tipo_picheo', 'velocidad', 'spin_rate', 'resultado', 'fecha']
                if all(col in df.columns for col in columnas_requeridas):
                    
                    # Carga masiva eficiente usando el método to_sql de pandas conectado a SQLAlchemy
                    with engine.begin() as conexion:
                        df.to_sql('logs_picheo', con=conexion, if_exists='append', index=False)
                        
                    st.success(f"🔥 ¡Éxito! Se han importado {len(df)} registros correctamente.")
                else:
                    st.error("Error: El archivo no cumple con la estructura de columnas requerida.")
                    
        except Exception as e:
            st.error(f"Ocurrió un error al procesar el archivo: {e}")

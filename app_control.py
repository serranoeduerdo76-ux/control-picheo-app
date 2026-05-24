import streamlit as st

# 1. Conexión segura a tu base de datos de Neon
conn = st.connection("postgresql", type="sql")

# 2. Creación automática de la tabla si no existe
with conn.session as session:
    session.execute("""
        CREATE TABLE IF NOT EXISTS mis_datos_neon (
            id SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL,
            cantidad INTEGER,
            notas TEXT
        );
    """)
    session.commit()

st.title("Mi Aplicación con Base de Datos Neon")
st.write("Todos los datos cargados aquí se guardarán permanentemente en la nube.")

# 3. Formulario para ingresar datos
st.subheader("Cargar nuevos datos")
with st.form("formulario_ingreso"):
    nombre_registro = st.text_input("Nombre del registro o producto:")
    cantidad_registro = st.number_input("Cantidad:", min_value=0, step=1)
    notas_registro = st.text_area("Notas o comentarios:")
    
    boton_enviar = st.form_submit_button("Guardar en la Base de Datos")

# 4. Guardar la información al presionar el botón
if boton_enviar:
    if nombre_registro == "":
        st.error("El campo 'Nombre' no puede estar vacío.")
    else:
        with conn.session as session:
            session.execute(
                """
                INSERT INTO mis_datos_neon (nombre, cantidad, notas) 
                VALUES (:nombre, :cantidad, :notas);
                """,
                {"nombre": nombre_registro, "cantidad": cantidad_registro, "notas": notas_registro}
            )
            session.commit()
        st.success(f"¡Guardado correctamente! Se añadió: {nombre_registro}")

# 5. Leer y mostrar los datos guardados en una tabla
st.write("---")
st.subheader("Registros almacenados actualmente:")

df_datos = conn.query("SELECT nombre, cantidad, notas FROM mis_datos_neon ORDER BY id DESC;", ttl=0)

if df_datos.empty:
    st.info("Aún no hay datos guardados.")
else:
    st.dataframe(df_datos, use_container_width=True)

import streamlit as st
import pandas as pd
import json
import re
from collections import Counter
import plotly.express as px

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(page_title="Dashboard FIP - Lectura Operativa", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stMetric {background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #0056b3;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CARGA DE DATOS
# ==========================================
@st.cache_data
def cargar_datos():
    df = pd.read_csv("df_acciones_preparado.csv")
    df['fecha_hecho'] = pd.to_datetime(df['fecha_hecho'], errors='coerce')
    df['descripcion_hecho'] = df['descripcion_hecho'].fillna("")
    df['sectores_afectados_lista'] = df['sectores_afectados_lista'].fillna("Ninguno")
    df['impactos_sectoriales'] = df['impactos_sectoriales'].fillna("{}")
    
    if 'enlace' not in df.columns:
        df['enlace'] = ""
    df['enlace'] = df['enlace'].fillna("")
    return df

df_acciones = cargar_datos()

# ==========================================
# 3. FILTROS HORIZONTALES SUPERIORES
# ==========================================
f_col1, f_col2, f_col3, f_col4 = st.columns(4)

with f_col1:
    lista_sectores = [
        "Todos", "Energético", "Minero", "Hidrocarburos", 
        "Agropecuario", "Ambiental", "Turismo", 
        "Financiero", "Humanitario"
    ]
    sector_sel = st.selectbox("🎯 Sector Estratégico", lista_sectores)

with f_col2:
    lista_deptos = ["Todos"] + sorted(df_acciones['departamento_clean'].dropna().unique())
    depto_sel = st.selectbox("📍 Departamento", lista_deptos)

with f_col3:
    if depto_sel != "Todos":
        mpios_disponibles = sorted(df_acciones[df_acciones['departamento_clean'] == depto_sel]['municipio_clean'].dropna().unique())
    else:
        mpios_disponibles = sorted(df_acciones['municipio_clean'].dropna().unique())
    mpio_sel = st.selectbox("🗺️ Municipio", ["Todos"] + mpios_disponibles)

with f_col4:
    meses_sel = st.selectbox("🕒 Ventana Temporal", [3, 6, 12], index=2, format_func=lambda x: f"Últimos {x} meses")

# ==========================================
# 4. MOTOR DE FILTRADO PRINCIPAL
# ==========================================
df_filtrado = df_acciones.copy()

if not df_filtrado.empty:
    fecha_max = df_filtrado['fecha_hecho'].max()
    fecha_min_filtro = fecha_max - pd.DateOffset(months=meses_sel)
    df_filtrado = df_filtrado[df_filtrado['fecha_hecho'] >= fecha_min_filtro]

if sector_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado['sectores_afectados_lista'].str.contains(sector_sel, case=False, na=False)]

if depto_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado['departamento_clean'] == depto_sel]
if mpio_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado['llave_geo'] == f"{mpio_sel} - {depto_sel}"]

df_unicos = df_filtrado.drop_duplicates(subset=['id_acciones_presencia']).copy()

# ==========================================
# 5. TÍTULO Y CINTA DE KPIs
# ==========================================
st.markdown("<h2 style='text-align: center; color: #333;'>LECTURA OPERATIVA COMPLEMENTARIA</h2>", unsafe_allow_html=True)
st.divider()

if df_filtrado.empty:
    st.warning("⚠️ No hay reportes registrados para esta combinación de filtros.")
    st.stop()

total_reportes = df_unicos['id_acciones_presencia'].nunique()
municipios_afectados = df_unicos['municipio_clean'].nunique()

impactos_pos = 0
impactos_neg = 0
for _, row in df_unicos.iterrows():
    try:
        dic_impactos = json.loads(row['impactos_sectoriales'])
        for sec, pol in dic_impactos.items():
            if sector_sel == "Todos" or sector_sel == sec:
                if pol == "Positivo": impactos_pos += 1
                elif pol == "Negativo": impactos_neg += 1
    except:
        continue

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("🚨 Total Reportes", total_reportes)
kpi2.metric("🗺️ Municipios Afectados", municipios_afectados)
kpi3.metric("🔴 Amenazas (Ataques)", impactos_neg)
kpi4.metric("🟢 Mitigaciones (Estado)", impactos_pos)

# ==========================================
# 6. FILTRO OPERATIVO
# ==========================================
st.write("") 
st.markdown("<div style='text-align: center;'><small><b>FILTRO OPERATIVO (Aplica a gráficos inferiores)</b></small></div>", unsafe_allow_html=True)

_, col_center, _ = st.columns([1, 2, 1])
with col_center:
    filtro_operativo = st.radio(
        "Filtro Operativo",
        options=["⚪ Mostrar Todo", "🔴 Solo Amenazas", "🟢 Solo Mitigaciones"],
        horizontal=True,
        label_visibility="collapsed"
    )

st.divider()

df_bottom = df_unicos.copy()

def evaluar_polaridad(json_str, polaridad_buscada):
    try:
        dic = json.loads(json_str)
        if sector_sel == "Todos":
            return polaridad_buscada in dic.values()
        else:
            return dic.get(sector_sel) == polaridad_buscada
    except:
        return False

if filtro_operativo == "🔴 Solo Amenazas":
    df_bottom = df_bottom[df_bottom['impactos_sectoriales'].apply(lambda x: evaluar_polaridad(x, "Negativo"))]
elif filtro_operativo == "🟢 Solo Mitigaciones":
    df_bottom = df_bottom[df_bottom['impactos_sectoriales'].apply(lambda x: evaluar_polaridad(x, "Positivo"))]

# ==========================================
# 7. BOTONERA DINÁMICA (CROSS-FILTERING)
# ==========================================
st.markdown("#### 🎯 Dinámica de Actores")
st.caption("Principales actores y sus acciones predominantes. Usa los botones para filtrar las tablas inferiores.")

df_mo_temp = df_bottom.dropna(subset=['actor_consolidado', 'tipo_accion_clean']).copy()

if not df_mo_temp.empty:
    top_acciones_filtro = df_mo_temp['tipo_accion_clean'].value_counts().nlargest(4).index.tolist()
    opciones_accion = ["⚪ Todas"] + [f"🔹 {acc}" for acc in top_acciones_filtro]
    
    accion_sel = st.radio("Filtrar por Acción Específica", options=opciones_accion, horizontal=True, label_visibility="collapsed")
    
    if accion_sel != "⚪ Todas":
        accion_real = accion_sel.replace("🔹 ", "")
        df_interactive = df_bottom[df_bottom['tipo_accion_clean'] == accion_real].copy()
    else:
        df_interactive = df_bottom.copy()
else:
    df_interactive = df_bottom.copy()

# ==========================================
# 8. FILA 1: GRÁFICO (100% ANCHO)
# ==========================================
df_mo = df_interactive.dropna(subset=['actor_consolidado', 'tipo_accion_clean']).copy()

if not df_mo.empty:
    df_mo['actor_individual'] = df_mo['actor_consolidado'].str.split(',')
    df_mo_exploded = df_mo.explode('actor_individual')
    df_mo_exploded['actor_individual'] = df_mo_exploded['actor_individual'].str.strip()
    
    top_actores = df_mo_exploded.groupby('actor_individual')['id_acciones_presencia'].nunique().nlargest(5).index
    mo_data = df_mo_exploded[df_mo_exploded['actor_individual'].isin(top_actores)].copy()
    
    top_acciones = mo_data['tipo_accion_clean'].value_counts().nlargest(4).index
    mo_data['Accion_Limpia'] = mo_data['tipo_accion_clean'].apply(lambda x: x if x in top_acciones else 'Otras')
    
    df_plot = mo_data.groupby(['actor_individual', 'Accion_Limpia'])['id_acciones_presencia'].nunique().reset_index()
    df_plot.columns = ['Actor', 'Acción', 'Reportes'] # <-- Corrección de "Total" a "Reportes"
    
    fig = px.bar(
        df_plot,
        x='Reportes',
        y='Actor',
        color='Acción',
        orientation='h', 
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False if accion_sel != "⚪ Todas" else True, # Oculta la leyenda si se usa la botonera
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5, title=None),
        yaxis_title=None,
        xaxis_title=None,
        height=350
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Datos insuficientes para dibujar la dinámica.")

st.write("") 

# ==========================================
# 9. FILA 2: IMPACTO Y NARRATIVA
# ==========================================
col_izq, col_der = st.columns(2, gap="large")

with col_izq:
    st.markdown("#### 📊 Impacto Sectorial")
    st.caption("Distribución del riesgo sobre sectores estratégicos.")
    
    conteo_sectores = Counter()
    for _, row in df_interactive.iterrows():
        try:
            dic_impactos = json.loads(row['impactos_sectoriales'])
            for sec, _ in dic_impactos.items():
                conteo_sectores[sec] += 1
        except:
            continue

    if conteo_sectores:
        df_sec = pd.DataFrame(conteo_sectores.most_common(), columns=["Sector Estratégico", "Total Reportes"])
        st.dataframe(df_sec, use_container_width=True, hide_index=True)
    else:
        st.info("Ninguno de los sectores fue afectado en esta selección.")
        
    st.write("**Economías Ilegales presentes:**")
    # NOTA: Cambia 'renta_ilicita_identificada' si tu base de datos usa otro nombre de columna para las economías ilegales.
    col_renta = 'renta_ilicita_identificada' 
    if col_renta in df_interactive.columns:
        rentas = df_interactive[df_interactive[col_renta].notna() & (df_interactive[col_renta] != 'Ninguna')][col_renta].value_counts()
        if not rentas.empty:
            st.dataframe(rentas.reset_index().rename(columns={col_renta: 'Renta', 'count': 'Frecuencia'}), use_container_width=True, hide_index=True)
        else:
            st.caption("No se reportaron economías ilegales para esta selección.")
    else:
        st.caption("Columna de rentas ilícitas no disponible en la base de datos actual.")

with col_der:
    st.markdown("#### 📝 Narrativa")
    st.caption("Conceptos clave extraídos de los reportes del territorio.")
    
    stopwords = {'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'y', 'o', 'pero', 'si', 'no', 
                 'de', 'del', 'a', 'al', 'en', 'por', 'para', 'con', 'que', 'se', 'su', 'sus', 'como', 
                 'es', 'son', 'fue', 'fueron', 'ha', 'han', 'lo', 'le', 'les', 'más', 'ya', 'este', 'esta',
                 'del', 'sobre', 'entre', 'tambien', 'cuando', 'donde'}
    
    pares_palabras = []
    for texto in df_interactive['descripcion_hecho'].dropna():
        texto_limpio = re.sub(r'[^\w\s]', '', str(texto).lower())
        palabras = [p for p in texto_limpio.split() if p not in stopwords and len(p) > 2]
        for i in range(len(palabras) - 1):
            pares_palabras.append(f"{palabras[i]} {palabras[i+1]}")
            
    conteo = Counter(pares_palabras)
    top_bigramas = conteo.most_common(10)
    
    if top_bigramas:
        df_bigramas = pd.DataFrame(top_bigramas, columns=["Concepto", "Frecuencia"])
        max_frec = int(df_bigramas['Frecuencia'].max())
        
        st.dataframe(
            df_bigramas,
            column_config={
                "Concepto": "Concepto",
                "Frecuencia": st.column_config.ProgressColumn(
                    "Intensidad",
                    format=" ",
                    min_value=0,
                    max_value=max_frec,
                ),
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Textos insuficientes para extraer narrativa.")

# ==========================================
# 10. MÓDULO DE FUENTES (Acordeón)
# ==========================================
st.divider()

with st.expander("🔎 Fuentes (Últimos 50 reportes)"):
    df_fuentes = df_interactive[['fecha_hecho', 'municipio_clean', 'actor_consolidado', 'tipo_accion_clean', 'enlace']].copy()
    df_fuentes['fecha_hecho'] = df_fuentes['fecha_hecho'].dt.strftime('%Y-%m-%d')
    df_fuentes = df_fuentes.rename(columns={
        'fecha_hecho': 'Fecha',
        'municipio_clean': 'Municipio',
        'actor_consolidado': 'Actor',
        'tipo_accion_clean': 'Acción'
    })
    
    df_fuentes = df_fuentes.head(50)
    
    st.dataframe(
        df_fuentes,
        column_config={
            "enlace": st.column_config.LinkColumn(
                "Fuente",
                help="Haz clic para ver la noticia original",
                validate="^https?://", 
                display_text="🔗 Ver noticia"
            )
        },
        use_container_width=True,
        hide_index=True
    )

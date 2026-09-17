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
    meses_sel = st.selectbox("🕒 Ventana Temporal", [3, 6, 12, 24], index=1, format_func=lambda x: f"Últimos {x} meses")

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

df_unicos = df_filtrado.drop_duplicates(subset=['id_acciones_presencia'])

# ==========================================
# 5. TÍTULO Y CINTA DE KPIs (Fijos)
# ==========================================
st.markdown("<h2 style='text-align: center; color: #333;'>LECTURA OPERATIVA COMPLEMENTARIA</h2>", unsafe_allow_html=True)
st.divider()

if df_filtrado.empty:
    st.warning("⚠️ No hay eventos armados registrados para esta combinación de filtros.")
    st.stop()

total_eventos = df_unicos['id_acciones_presencia'].nunique()
total_victimas = df_unicos['total_victimas'].sum()

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
kpi1.metric("🚨 Total Eventos", total_eventos)
kpi2.metric("👥 Total Víctimas", int(total_victimas))
kpi3.metric("🔴 Amenazas (Ataques)", impactos_neg)
kpi4.metric("🟢 Mitigaciones (Estado)", impactos_pos)

# ==========================================
# 6. FILTRO OPERATIVO (Pastillas horizontales)
# ==========================================
st.write("") # Espacio
st.markdown("<div style='text-align: center;'><small><b>FILTRO OPERATIVO (Aplica a los gráficos inferiores)</b></small></div>", unsafe_allow_html=True)

# Centramos el selector usando columnas
_, col_center, _ = st.columns([1, 2, 1])
with col_center:
    filtro_operativo = st.radio(
        "Filtro Operativo",
        options=["⚪ Mostrar Todo", "🔴 Solo Amenazas", "🟢 Solo Mitigaciones"],
        horizontal=True,
        label_visibility="collapsed"
    )

st.divider()

# Aplicar lógica del filtro operativo
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
# 7. PANELES INFERIORES (Con df_bottom)
# ==========================================
col1, col2, col3 = st.columns(3, gap="large")

# --- COLUMNA 1: MODUS OPERANDI ---
with col1:
    st.markdown("#### 🎯 Modus Operandi")
    st.caption("Principales actores y sus acciones predominantes.")
    
    df_mo = df_bottom.dropna(subset=['actor_consolidado', 'tipo_accion_clean']).copy()
    
    if not df_mo.empty:
        # 1. Separar los actores combinados
        df_mo['actor_individual'] = df_mo['actor_consolidado'].str.split(',')
        df_mo_exploded = df_mo.explode('actor_individual')
        df_mo_exploded['actor_individual'] = df_mo_exploded['actor_individual'].str.strip()
        
        # 2. Filtrar Top 5 Actores
        top_actores = df_mo_exploded.groupby('actor_individual')['id_acciones_presencia'].nunique().nlargest(5).index
        mo_data = df_mo_exploded[df_mo_exploded['actor_individual'].isin(top_actores)].copy()
        
        # 3. TRUCO VISUAL: Dejar solo el Top 4 de acciones y agrupar el resto en "Otras"
        top_acciones = mo_data['tipo_accion_clean'].value_counts().nlargest(4).index
        mo_data['Accion_Limpia'] = mo_data['tipo_accion_clean'].apply(lambda x: x if x in top_acciones else 'Otras')
        
        # 4. Agrupar datos exactos para el gráfico
        df_plot = mo_data.groupby(['actor_individual', 'Accion_Limpia'])['id_acciones_presencia'].nunique().reset_index()
        df_plot.columns = ['Actor', 'Acción', 'Total']
        
        # 5. Renderizar con Plotly para estética profesional
        fig = px.bar(
            df_plot,
            x='Total',
            y='Actor',
            color='Acción',
            orientation='h', # Barras horizontales
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        
        # Limpiar la interfaz del gráfico
        fig.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(
                orientation="h", 
                yanchor="top", 
                y=-0.2, 
                xanchor="center", 
                x=0.5,
                title=None
            ),
            yaxis_title=None,
            xaxis_title=None,
            height=320
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Datos insuficientes.")

# --- COLUMNA 2: IMPACTO SECTORIAL ---
with col2:
    st.markdown("#### 📊 Impacto Sectorial")
    st.caption("Distribución del riesgo sobre sectores estratégicos.")
    
    conteo_sectores = Counter()
    for _, row in df_bottom.iterrows():
        try:
            dic_impactos = json.loads(row['impactos_sectoriales'])
            for sec, _ in dic_impactos.items():
                conteo_sectores[sec] += 1
        except:
            continue

    if conteo_sectores:
        df_sec = pd.DataFrame(conteo_sectores.most_common(), columns=["Sector Estratégico", "Total Eventos"])
        st.dataframe(df_sec, use_container_width=True, hide_index=True)
        
        if 'renta_ilicita_identificada' in df_bottom.columns:
            st.write("**Economías Ilegales presentes:**")
            rentas = df_bottom[df_bottom['renta_ilicita_identificada'] != 'Ninguna']['renta_ilicita_identificada'].value_counts()
            if not rentas.empty:
                st.dataframe(rentas.reset_index().rename(columns={'renta_ilicita_identificada': 'Renta', 'count': 'Frecuencia'}), use_container_width=True, hide_index=True)
            else:
                st.caption("Sin rentas asociadas.")
    else:
        st.info("Ninguno de los 8 sectores fue afectado en este cruce.")

# --- COLUMNA 3: NARRATIVA TÁCTICA ---
with col3:
    st.markdown("#### 📝 Narrativa Táctica")
    st.caption("Conceptos clave extraídos de los reportes del territorio.")
    
    stopwords = {'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'y', 'o', 'pero', 'si', 'no', 
                 'de', 'del', 'a', 'al', 'en', 'por', 'para', 'con', 'que', 'se', 'su', 'sus', 'como', 
                 'es', 'son', 'fue', 'fueron', 'ha', 'han', 'lo', 'le', 'les', 'más', 'ya', 'este', 'esta',
                 'del', 'sobre', 'entre', 'tambien', 'cuando', 'donde'}
    
    pares_palabras = []
    for texto in df_bottom['descripcion_hecho'].dropna():
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
                    format=" ",  # Oculta el número
                    min_value=0,
                    max_value=max_frec,
                ),
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Textos insuficientes para extraer narrativa.")
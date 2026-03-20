"""
app.py — Validador de Títulos Académicos
Sistema de uso interno para equipos comerciales
================================================
Ejecutar: streamlit run app.py
"""

import io
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from validador import ValidadorCSV, SEMESTRE_POR_NIVEL, CSV_DECISIONES, CSV_TITULOS

st.set_page_config(page_title="Validador de Títulos", page_icon="🎓", layout="wide", initial_sidebar_state="expanded")

@st.cache_resource
def get_motor():
    return ValidadorCSV()

motor = get_motor()

with st.sidebar:
    st.title("🎓 ValidaTítulos")
    pagina = st.radio("Navegación", ["🔍 Validar título", "📋 Revisión Back", "📂 Cargar datos", "📊 Historial"], label_visibility="collapsed")
    stats = motor.stats()
    st.metric("Total registros", stats["total"])
    st.metric("Aplican", stats["aplican"])
    if st.button("🔄 Recargar base"):
        get_motor.clear()
        st.rerun()

if pagina == "🔍 Validar título":
    st.header("🔍 Validar título académico")
    PAISES = ["Colombia", "México", "Argentina", "Chile", "Perú", "Ecuador", "Venezuela", "Bolivia", "España", "Estados Unidos", "Otro"]
    with st.form("form_validar"):
        titulo = st.text_input("Nombre del título *", placeholder="Ej: Administración de Empresas")
        col1, col2 = st.columns(2)
        universidad = col1.text_input("Universidad", placeholder="Ej: Universidad Nacional")
        pais = col2.selectbox("País", PAISES)
        doc = st.file_uploader("Documento soporte (opcional)", type=["pdf", "png", "jpg", "jpeg"])
        submitted = st.form_submit_button("🔍 Validar título", use_container_width=True)
    if submitted:
        if not titulo.strip():
            st.error("Por favor ingresa el nombre del título")
        else:
            with st.spinner("Consultando base histórica..."):
                r = motor.validar(titulo.strip(), universidad.strip(), pais)
            if r.requiere_revision:
                st.warning(f"⚠️ Requiere revisión Back | Confianza: {r.confianza_pct}% | {r.razon}")
            elif r.aplica:
                st.success(f"✅ Aplica | Nivel: {r.nivel} | Semestre: |r.semestre}· | Confianza: {r.confianza_pct}%")
            else:
                st.error(f"❌ No aplica | Nivel: {r.nivel} | Confianza: {r.confianza_pct}%")
            st.caption(f"Método: {r.metodo} | {r.razon}")
            st.session_state["ultimo_resultado"] = {"titulo": titulo.strip(), "universidad": universidad.strip(), "pais": pais, "resultado": r}
            if r.requiere_revision:
                st.session_state["back_titulo"] = titulo.strip()
                st.session_state["back_pre"] = True

elif pagina == "📋 Revisión Back":
    st.header("📋 Revisión manual — equipo Back")
    st.info("Solo para el equipo Back. Cada decisión guardada mejora el sistema automáticamente.")
    prefill_titulo = st.session_state.get("back_titulo", "")
    ult = st.session_state.get("ultimo_resultado", {})
    NIVELES = ["universitario", "maestría", "especialización", "doctorado", "tecnólogo", "bachillerato"]
    PAISES_B = ["Colombia", "México", "Argentina", "Chile", "Perú", "Ecuador", "Venezuela", "España", "Otro"]
    with st.form("form_back", clear_on_submit=True):
        b_titulo = st.text_input("Título revisado *", value=prefill_titulo, placeholder="Nombre exacto del título")
        bc1, bc2 = st.columns(2)
        b_univ = bc1.text_input("Universidad", value=ult.get("universidad", ""))
        b_pais = bc2.selectbox("País", PAISES_B, index=PAISES_B.index(ult.get("pais", "Colombia")) if ult.get("pais", "Colombia") in PAISES_B else 0)
        bd1, bd2 = st.columns(2)
        b_aplica = bd1.radio("¿E\ste título aplica?", ["✅ Sí, aplica", "❌ No aplica"])
        b_nivel = bd2.selectbox("Nivel académico confirmado", NIVELES)
        b_revisor = st.text_input("Nombre del revisor", placeholder="Ej: Ana Gómez · Área Back")
        b_motivo = st.text_area("Observaciones", placeholder="Ej: Título homologado verificado con acreditación CESU.")
        b_incorp = st.checkbox("✅ Incorporar este título a la base de conocimiento", value=True)
        b_submit = st.form_submit_button("💾 Guardar decisión Back", use_container_width=True)
    if b_submit:
        if not b_titulo.strip():
            st.error("El campo Titulo es obligatorio.")
        else:
            motor.guardar_decision(titulo=b_titulo.strip(), universidad=b_univ.strip(), pais=b_pais, aplica="Sí" in b_aplica, nivel=b_nivel, revisor=b_revisor.strip(), motivo=b_motivo.strip(), incorporar=b_incorp)
            get_motor.clear()
            for k in ("back_titulo", "back_pre", "ultimo_resultado"):
                st.session_state.pop(k, None)
            st.success(f"✅ Decisión guardada correctamente para '{b_titulo.strip()}'")

elif pagina == "📂 Cargar datos":
    st.header("page-icon= 📂 B{Cargar base histórica de títulos")
    st.info("Sube un archivo CSV con tus títulos históricos validados.")
    archivo = st.file_uploader("Selecciona tu archivo CSV", type=["csv"])
    if archivo:
        try:
            df_nuevo = pd.read_csv(archivo)
            st.dataframe(df_nuevo.head(8))
            cols_req = {"nombre_titulo", "aplica", "nivel"}
            cols_falt = cols_req - set(df_nuevo.columns)
            if cols_falt:
                st.error(f"Faltan columnas: {cols_falt}")
            else:
                if st.button("✅ Confirmar carga e importar títulos"):
                    for col in ["universidad", "pais", "semestre"]:
                        if col not in df_nuevo.columns:
                            df_nuevo[col] = "" if col != "semestre" else 5
                    if CSV_TITULNS.exists():
                        df_actual = pd.read_csv(CSW_TITULOS)
                        df_merged = pd.concat([df_actual, df_nuevo], ignore_index=True)
                        df_merged.drop_duplicates(subset=["nombre_titulo"], keep="last", inplace=True)
                    else:
                        df_merged = df_nuevo
                    df_merged.to_csv(CSW_TITULOS, index=False)
                    get_motor.clear()
                    st.success(f"✅ {len(df_nuevn)} títulos importados correctamente.")
        except Exception as e:
            st.error(f"No se pudo leer el archivo: {e}")

elif pagina == "📊 Historial":
    st.header("📊 Historial de decisiones Back")
    if not CSV_DECISIONES.exists():
        st.info("Aún no hay decisiones registradas por el equipo Back.")
    else:
        df = pd.read_csv(CSV_DECISIONES)
        st.dataframe(df, use_container_width=True)
        st.download_button("⬇ Descargar CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="decisiones_back.csv", mime="text/csv")

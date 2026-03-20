"""
app.py - Validador de Títulos Académicos
Sistema de uso interno para equipos comerciales
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
    st.markdown("<div style='padding:0.5rem 0 1.2rem'><div style='font-size:1.35rem;font-weight:700;color:#fff'>🎓 ValidaTítulos</div><div style='font-size:0.72rem;color:#888'>Sistema de uso interno</div></div>", unsafe_allow_html=True)
    pagina = st.radio("Navegación", ["📋 Validar título", "📋 Revisión Back", "📂 Cargar datos", "📊 Historial"], label_visibility="collapsed")
    stats = motor.stats()
    st.markdown(f"<div style='background:#1a1d2e;border-radius:10px;padding:0.7rem 0.9rem;margin-bottom:6px;display:flex;justify-content:space-between'><span style='color:#aaa;font-size:0.78rem'>Total registros</span><span style='color:#fff;font-weight:700'>{stats['total']}</span></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='background:#1a1d2e;border-radius:10px;padding:0.7rem 0.9rem;margin-bottom:6px;display:flex;justify-content:space-between'><span style='color:#aaa;font-size:0.78rem'>Aplican</span><span style='color:#4ade80;font-weight:700'>{stats['aplican']}</span></div>", unsafe_allow_html=True)
    if st.button("🔄 Recargar base", use_container_width=True):
        get_motor.clear()
        st.cache_resource.clear()
        st.rerun()

PAISES = ["Colombia", "México", "Argentina", "Chile", "Perú", "Ecuador", "Venezuela", "Bolivia", "España", "Estados Unidos", "Otro"]

if pagina == "📋 Validar título":
    st.header("📋 Validar título académico")
    st.info("Ingresa los datos del diploma del cliente. El sistema consultará la base histórica y determinará si aplica para planes universitarios.")
    with st.form("form_validar", clear_on_submit=False):
        titulo = st.text_input("Nombre del título *", placeholder="Ej: Administración de Empresas")
        col1, col2 = st.columns(2)
        universidad = col1.text_input("Universidad", placeholder="Ej: Universidad Nacional")
        pais = col2.selectbox("País", PAISES)
        doc = st.file_uploader("Documento soporte (opcional)", type=["pdf", "png", "jpg", "jpeg"])
        submitted = st.form_submit_button("📋 Validar título", use_container_width=True)
    if submitted:
        if not titulo.strip():
            st.error("⚠️ Por favor ingresa el nombre del título antes de continuar.")
        else:
            with st.spinner("Consultando base histórica..."):
                r = motor.validar(titulo.strip(), universidad.strip(), pais)
            if r.requiere_revision:
                st.warning(f"⚠️ Requiere revisión Back | Confianza: {r.confianza_pct}% | {r.razon}")
            elif r.aplica:
                st.success(f"✅ Aplica | Nivel: {r.nivel} | Semestre: {r.semestre}° | Confianza: {r.confianza_pct}%")
            else:
                st.error(f"❌ No aplica | Nivel: {r.nivel} | Confianza: {r.confianza_pct}%")
            st.caption(f"Método: {r.metodo} | {r.razon}")
            st.session_state["ultimo_resultado"] = {"titulo": titulo.strip(), "universidad": universidad.strip(), "pais": pais, "resultado": r}
            if r.requiere_revision:
                st.session_state["back_titulo"] = titulo.strip()
                st.session_state["back_pre"] = True

elif pagina == "📋 Revisión Back":
    st.header("📋 Revisión manual — equipo Back")
    st.warning("Solo para el equipo Back. Cada decisión guardada mejora automáticamente el sistema.")
    prefill_titulo = st.session_state.get("back_titulo", "")
    ult = st.session_state.get("ultimo_resultado", {})
    NIVELES = ["universitario", "maestría", "especialización", "doctorado", "tecnólogo", "bachillerato"]
    PAISES_B = ["Colombia", "México", "Argentina", "Chile", "Perú", "Ecuador", "Venezuela", "España", "Otro"]
    with st.form("form_back", clear_on_submit=True):
        b_titulo = st.text_input("Título revisado *", value=prefill_titulo, placeholder="Nombre exacto del título")
        bc1, bc2 = st.columns(2)
        b_univ = bc1.text_input("Universidad", value=ult.get("universidad", ""), placeholder="Universidad emisora")
        b_pais = bc2.selectbox("País", PAISES_B, index=PAISES_B.index(ult.get("pais", "Colombia")) if ult.get("pais", "Colombia") in PAISES_B else 0)
        bd1, bd2 = st.columns(2)
        b_aplica = bd1.radio("¿Este título aplica?", ["✅ Sí, aplica", "❌ No aplica"])
        b_nivel = bd2.selectbox("Nivel académico confirmado", NIVELES)
        b_revisor = st.text_input("Nombre del revisor", placeholder="Ej: Ana Gómez · Área Back")
        b_motivo = st.text_area("Observaciones / motivo de la decisión", placeholder="Ej: Título homologado, verificado con acreditación CESU.", height=100)
        b_incorp = st.checkbox("✅ Incorporar este título a la base de conocimiento", value=True)
        b_submit = st.form_submit_button("💾 Guardar decisión Back", use_container_width=True)
    if b_submit:
        if not b_titulo.strip():
            st.error("⚠️ El campo Título revisado es obligatorio.")
        else:
            aplica_bool = "Sí" in b_aplica
            motor.guardar_decision(titulo=b_titulo.strip(), universidad=b_univ.strip(), pais=b_pais, aplica=aplica_bool, nivel=b_nivel, revisor=b_revisor.strip(), motivo=b_motivo.strip(), incorporar=b_incorp)
            get_motor.clear()
            for k in ("back_titulo", "back_pre", "ultimo_resultado"):
                st.session_state.pop(k, None)
            st.success(f"✅ Decisión guardada: '{b_titulo.strip()}' → {'Aplica' if aplica_bool else 'No aplica'} · Nivel: {b_nivel}")

elif pagina == "📂 Cargar datos":
    st.header("📂 Cargar base histórica de títulos")
    st.info("Sube un archivo CSV con tus títulos históricos validados. Los nuevos registros se **agregan** a los existentes.")
    archivo = st.file_uploader("Selecciona tu archivo CSV", type=["csv"])
    if archivo:
        try:
            df_nuevo = pd.read_csv(archivo)
            st.markdown(f"**Vista previa** — {len(df_nuevo)} filas detectadas:")
            st.dataframe(df_nuevo.head(8), use_container_width=True, hide_index=True)
            cols_req = {"nombre_titulo", "aplica", "nivel"}
            cols_falt = cols_req - set(df_nuevo.columns)
            if cols_falt:
                st.error(f"⚠️ Faltan columnas obligatorias: **{', '.join(cols_falt)}**")
            else:
                if st.button("✅ Confirmar carga e importar títulos", use_container_width=True):
                    for col in ["universidad", "pais", "semestre"]:
                        if col not in df_nuevo.columns:
                            df_nuevo[col] = "" if col != "semestre" else 5
                    if CSV_TITULOS.exists():
                        df_actual = pd.read_csv(CSV_TITULOS)
                        df_merged = pd.concat([df_actual, df_nuevo], ignore_index=True)
                        df_merged.drop_duplicates(subset=["nombre_titulo"], keep="last", inplace=True)
                    else:
                        df_merged = df_nuevo
                    df_merged.to_csv(CSV_TITULOS, index=False)
                    get_motor.clear()
                    st.success(f"✅ {len(df_nuevo)} títulos importados correctamente. Base actualizada.")
                    st.balloons()
        except Exception as e:
            st.error(f"No se pudo leer el archivo: {e}")
    plantilla = pd.DataFrame([
        {"nombre_titulo": "Administración de Empresas", "universidad": "Universidad Nacional", "pais": "Colombia", "aplica": "", "nivel": "universitario", "semestre": 5},
        {"nombre_titulo": "Maestría en Finanzas", "universidad": "EAFIT", "pais": "Colombia", "aplica": "", "nivel": "maestría", "semestre": 7},
        {"nombre_titulo": "Técnico en Sistemas", "universidad": "SENA", "pais": "Colombia", "aplica": "", "nivel": "bachillerato", "semestre": 1},
    ])
    st.download_button("⬇ Descargar plantilla CSV", data=plantilla.to_csv(index=False).encode("utf-8"), file_name="plantilla_titulos.csv", mime="text/csv", use_container_width=True)

elif pagina == "📊 Historial":
    st.header("📊 Historial de decisiones Back")
    if not CSV_DECISIONES.exists():
        st.info("Aún no hay decisiones registradas por el equipo Back.")
    else:
        df = pd.read_csv(CSV_DECISIONES)
        total = len(df)
        aplican = (df["decision_aplica"].astype(str).str.lower().isin(["true","sí","si","1"])).sum()
        col1, col2, col3 = st.columns(3)
        col1.metric("Total revisiones", total)
        col2.metric("Aprobadas", aplican)
        col3.metric("Rechazadas", total - aplican)
        buscar = st.text_input("🔎 Buscar por título", placeholder="Filtrar resultados...")
        df_show = df.copy()
        if buscar:
            df_show = df_show[df_show["nombre_titulo"].str.contains(buscar, case=False, na=False)]
        st.dataframe(df_show, use_container_width=True, hide_index=True, height=380)
        st.download_button("⬇ Descargar decisiones Back (CSV)", data=df.to_csv(index=False).encode("utf-8"), file_name="decisiones_back.csv", mime="text/csv", use_container_width=True)

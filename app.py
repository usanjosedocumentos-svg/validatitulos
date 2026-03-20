"""
app.py - Validador de Titulos Academicos
Ejecutar: streamlit run app.py
"""
from pathlib import Path
import pandas as pd
import streamlit as st
from validador import ValidadorCSV, SEMESTRE_POR_NIVEL, CSV_DECISIONES, CSV_TITULOS

st.set_page_config(page_title="ValidaTitulos", page_icon=":mortar_board:",
                   layout="wide", initial_sidebar_state="expanded")

@st.cache_resource
def get_motor():
    return ValidadorCSV()

motor = get_motor()


def existe_duplicado(nombre: str, nivel: str) -> bool:
    n  = nombre.strip().lower()
    nv = nivel.strip().lower()
    if CSV_TITULOS.exists():
        df = pd.read_csv(CSV_TITULOS)
        if not df.empty:
            m = (df["nombre_titulo"].astype(str).str.lower().str.strip() == n) & \
                (df["nivel"].astype(str).str.lower().str.strip() == nv)
            if m.any():
                return True
    if CSV_DECISIONES.exists():
        df2 = pd.read_csv(CSV_DECISIONES)
        if not df2.empty and "nivel_confirmado" in df2.columns:
            m2 = (df2["nombre_titulo"].astype(str).str.lower().str.strip() == n) & \
                 (df2["nivel_confirmado"].astype(str).str.lower().str.strip() == nv)
            if m2.any():
                return True
    return False


st.markdown("""
<style>
html, body, [class*="css"] { cursor: auto !important; }
button, [role="button"], a, label { cursor: pointer !important; }
input[type="text"], textarea { cursor: text !important; }
[data-testid="stSidebar"] { background: #0f1117; }
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
div[data-testid="stDataFrame"] td div { color: #111111 !important; font-size:0.85rem !important; }
div[data-testid="stDataFrame"] th div { color: #222222 !important; font-weight:700 !important; background:#f1f5f9 !important; }
</style>
""", unsafe_allow_html=True)


with st.sidebar:
    st.markdown(
        "<div style='padding:0.5rem 0 1.2rem'>"
        "<div style='font-size:1.35rem;font-weight:700;color:#fff'>ValidaTitulos</div>"
        "<div style='font-size:0.72rem;color:#888'>Sistema de uso interno</div>"
        "</div>",
        unsafe_allow_html=True)
    pagina = st.radio("Nav",
        ["Validar titulo", "Revision Back", "Cargar datos", "Historial"],
        label_visibility="collapsed")
    stats = motor.stats()
    total_str = str(stats['total'])
    st.markdown(
        "<div style='background:#1a1d2e;border-radius:8px;padding:0.6rem 0.9rem;"
        "margin-bottom:5px;display:flex;justify-content:space-between'>"
        "<span style='color:#aaa;font-size:0.78rem'>Registros totales</span>"
        "<span style='color:#fff;font-weight:700'>" + total_str + "</span></div>",
        unsafe_allow_html=True)
    aplican_str = str(stats['aplican'])
    st.markdown(
        "<div style='background:#1a1d2e;border-radius:8px;padding:0.6rem 0.9rem;"
        "margin-bottom:5px;display:flex;justify-content:space-between'>"
        "<span style='color:#aaa;font-size:0.78rem'>Aplican</span>"
        "<span style='color:#4ade80;font-weight:700'>" + aplican_str + "</span></div>",
        unsafe_allow_html=True)
    if st.button("Recargar base", use_container_width=True):
        get_motor.clear()
        st.cache_resource.clear()
        st.rerun()

PAISES  = ["Colombia","Mexico","Argentina","Chile","Peru","Ecuador",
           "Venezuela","Bolivia","Espana","Estados Unidos","Otro"]
NIVELES = ["universitario","maestria","especializacion",
           "doctorado","tecnologo","bachillerato"]


# === PAG 1: VALIDAR ===
if pagina == "Validar titulo":
    st.header("Validar titulo academico")
    st.info("Ingresa el titulo del cliente. El Back siempre toma la decision final.")
    with st.form("form_validar", clear_on_submit=False):
        titulo      = st.text_input("Nombre del titulo *",
                                    placeholder="Ej: Administracion de Empresas")
        col1, col2  = st.columns(2)
        universidad = col1.text_input("Universidad",
                                      placeholder="Ej: Universidad Nacional")
        pais        = col2.selectbox("Pais", PAISES)
        st.file_uploader("Documento soporte (opcional)",
                         type=["pdf","png","jpg","jpeg"])
        submitted = st.form_submit_button("Validar titulo", use_container_width=True)
    if submitted:
        if not titulo.strip():
            st.error("Por favor ingresa el nombre del titulo.")
        else:
            with st.spinner("Consultando base historica..."):
                r = motor.validar(titulo.strip(), universidad.strip(), pais)
            nivel_txt = (r.nivel or "").capitalize()
            sem_txt   = str(r.semestre) + " semestre" if r.semestre else "—"
            if r.requiere_revision:
                st.warning("REQUIERE REVISION BACK | Confianza: " +
                           str(r.confianza_pct) + "% | " + r.razon)
                st.session_state["back_titulo"] = titulo.strip()
                st.session_state["back_pre"]    = True
            elif r.aplica:
                st.success("APLICA | Nivel: " + nivel_txt +
                           " | Semestre: " + sem_txt +
                           " | Confianza: " + str(r.confianza_pct) + "%")
            else:
                st.error("NO APLICA | Nivel: " + nivel_txt +
                         " | Confianza: " + str(r.confianza_pct) + "%")
            st.caption("Metodo: " + r.metodo + " | " + r.razon)
            st.session_state["ultimo_resultado"] = {
                "titulo": titulo.strip(), "universidad": universidad.strip(),
                "pais": pais, "resultado": r}⟋
                

except Exception as e:
    st.error("Error al leer el archivo: " + str(e))

"""
app.py - Validador de Titulos Academicos
Ejecutar: streamlit run app.py
"""
from pathlib import Path
import pandas as pd
import streamlit as st
from validador import ValidadorCSV, SEMESTRE_POR_NIVEL, CSV_DECISIONES, CSV_TITULOS

st.set_page_config(page_title="ValidaTitulos", page_icon="ð",
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
/* Cursor normal - fix bloqueo en local */
html, body, [class*="css"] { cursor: auto !important; }
button, [role="button"], a, label { cursor: pointer !important; }
input[type="text"], textarea { cursor: text !important; }

/* Sidebar */
[data-testid="stSidebar"] { background: #0f1117; }
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }

/* Historial - texto oscuro y legible */
div[data-testid="stDataFrame"] td div { color: #111111 !important; font-size:0.85rem !important; }
div[data-testid="stDataFrame"] th div { color: #222222 !important; font-weight:700 !important; background:#f1f5f9 !important; }
</style>
""", unsafe_allow_html=True)


with st.sidebar:
    st.markdown(
        "<div style='padding:0.5rem 0 1.2rem'>"
        "<div style='font-size:1.35rem;font-weight:700;color:#fff'>ð ValidaTitulos</div>"
        "<div style='font-size:0.72rem;color:#888'>Sistema de uso interno</div>"
        "</div>",
        unsafe_allow_html=True)
    pagina = st.radio("Nav",
        ["ð Validar titulo","ð Revision Back","ð Cargar datos","ð Historial"],
        label_visibility="collapsed")
    stats = motor.stats()
    total_str = str(stats['total'])
    st.markdown(
        "<div style='background:#1a1d2e;border-radius:8px;padding:0.6rem 0.9rem;"
        "margin-bottom:5px;display:flex;justify-content:space-between'>"
        "<span style='color:#aaa;font-size:0.78rem'>Registros totales</span>"
        "<span style='color:#fff;font-weight:700'>" + total_str + "</span></div>",
        unsafe_allow_html=True)
    if st.button("ð Recargar base", use_container_width=True):
        get_motor.clear()
        st.cache_resource.clear()
        st.rerun()

PAISES  = ["Colombia","Mexico","Argentina","Chile","Peru","Ecuador",
           "Venezuela","Bolivia","Espana","Estados Unidos","Otro"]
NIVELES = ["universitario","maestria","especializacion",
           "doctorado","tecnologo","bachillerato"]


# âââ PAG 1: VALIDAR ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
if pagina == "ð Validar titulo":
    st.header("ð Validar titulo academico")
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
        submitted = st.form_submit_button("ð Validar titulo",
                                          use_container_width=True)
    if submitted:
        if not titulo.strip():
            st.error("Por favor ingresa el nombre del titulo.")
        else:
            with st.spinner("Consultando base historica..."):
                r = motor.validar(titulo.strip(), universidad.strip(), pais)
            nivel_txt = (r.nivel or "").capitalize()
            sem_txt   = str(r.semestre) + "Â°" if r.semestre else "â"
            if r.requiere_revision:
                st.warning("â ï¸ Requiere revision Back | "
                           "Confianza: " + str(r.confianza_pct) + "% | " + r.razon)
                st.session_state["back_titulo"] = titulo.strip()
                st.session_state["back_pre"]    = True
            elif r.aplica:
                st.success("â Aplica | Nivel: " + nivel_txt +
                           " | Semestre: " + sem_txt +
                           " | Confianza: " + str(r.confianza_pct) + "%")
            else:
                st.error("â No aplica | Nivel: " + nivel_txt +
                         " | Confianza: " + str(r.confianza_pct) + "%")
            st.caption("Metodo: " + r.metodo + " | " + r.razon)
            st.session_state["ultimo_resultado"] = {
                "titulo": titulo.strip(), "universidad": universidad.strip(),
                "pais": pais, "resultado": r}


# âââ PAG 2: BACK âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
elif pagina == "ð Revision Back":
    st.header("ð Revision manual â equipo Back")
    st.warning("Solo para el equipo Back. Cada decision guardada mejora el sistema.")
    prefill  = st.session_state.get("back_titulo", "")
    ult      = st.session_state.get("ultimo_resultado", {})
    PAISES_B = ["Colombia","Mexico","Argentina","Chile","Peru",
                "Ecuador","Venezuela","Espana","Otro"]

    with st.form("form_back", clear_on_submit=True):
        b_titulo  = st.text_input("Titulo revisado *", value=prefill,
                                  placeholder="Nombre exacto del titulo")
        bc1, bc2  = st.columns(2)
        b_univ    = bc1.text_input("Universidad",
                                   value=ult.get("universidad",""))
        idx_pais  = (PAISES_B.index(ult.get("pais","Colombia"))
                     if ult.get("pais","Colombia") in PAISES_B else 0)
        b_pais    = bc2.selectbox("Pais", PAISES_B, index=idx_pais)
        bd1, bd2  = st.columns(2)
        b_aplica  = bd1.radio("Este titulo aplica?",
                              ["â Si, aplica", "â No aplica"])
        b_nivel   = bd2.selectbox("Nivel academico confirmado", NIVELES)
        b_revisor = st.text_input("Nombre del revisor",
                                  placeholder="Ej: Ana Gomez / Area Back")
        b_motivo  = st.text_area("Observaciones",
                                 placeholder="Ej: Verificado con acreditacion CESU.",
                                 height=90)
        b_incorp  = st.checkbox(
            "â Incorporar a la base de conocimiento", value=True,
            help="Valida duplicados por nombre+nivel antes de agregar.")
        b_submit  = st.form_submit_button("ð¾ Guardar decision Back",
                                          use_container_width=True)

    if b_submit:
        if not b_titulo.strip():
            st.error("El campo Titulo es obligatorio.")
        elif b_incorp and existe_duplicado(b_titulo.strip(), b_nivel):
            st.error(
                "â El titulo **'" + b_titulo.strip() + "'** ya existe en la base "
                "con nivel **" + b_nivel + "**. "
                "No se permite duplicar (mismo nombre + nivel). "
                "Si la decision es diferente, desmarca 'Incorporar a la base'.")
        else:
            aplica_bool = "Si" in b_aplica
            motor.guardar_decision(
                titulo=b_titulo.strip(), universidad=b_univ.strip(),
                pais=b_pais, aplica=aplica_bool, nivel=b_nivel,
                revisor=b_revisor.strip(), motivo=b_motivo.strip(),
                incorporar=b_incorp)
            get_motor.clear()
            for k in ("back_titulo","back_pre","ultimo_resultado"):
                st.session_state.pop(k, None)
            decision_txt = "Aplica" if aplica_bool else "No aplica"
            st.success("â Guardado: '" + b_titulo.strip() +
                       "' â " + decision_txt + " Â· Nivel: " + b_nivel)


# âââ PAG 3: CAGGAR DATOS âââââââââââââââââââââââââââââââââââââââââââââââââââââââ
elif pagina == "ð Cargar datos":
    st.header("ð Cargar base historica de titulos")
    st.info("Sube un CSV. Detecta duplicados por **nombre + nivel** "
            "sin importar universidad ni pais.")
    archivo = st.file_uploader("Selecciona tu archivo CSV",
                               type=["csv"], key="csv_uploader")
    if archivo:
        try:
            df_nuevo = pd.read_csv(archivo)
            st.markdown("**Vista previa** â" + str(len(df_nuevo)) + " filas:")
            st.dataframe(df_nuevo.head(8), use_container_width=True,
                         hide_index=True)
            cols_req  = {"nombre_titulo","aplica","nivel"}
            cols_falt = cols_req - set(df_nuevo.columns)
            if cols_falt:
                st.error("Faltan columnas: **" + ", ".join(cols_falt) + "**")
            else:
                df_nuevo["_key"] = (
                    df_nuevo["nombre_titulo"].astype(str).str.lower().str.strip()
                    + "||"
                    + df_nuevo["nivel"].astype(str).str.lower().str.strip())

                dupes_int = df_nuevo[
                    df_nuevo.duplicated(subset=["_key"], keep=False)
                ][["nombre_titulo","nivel"]].drop_duplicates()

                dupes_ext = pd.DataFrame()
                if CSV_TITULOS.exists():
                    df_base = pd.read_csv(CSV_TITULOS)
                    df_base["_key"] = (
                        df_base["nombre_titulo"].astype(str).str.lower().str.strip()
                        + "||"
                        + df_base["nivel"].astype(str).str.lower().str.strip())
                    dupes_ext = df_nuevo[
                        df_nuevo["_key"].isin(df_base["_key"])
                    ][["nombre_titulo","nivel"]].drop_duplicates()

                hay_dupes = len(dupes_int) > 0 or len(dupes_ext) > 0
                if hay_dupes:
                    st.warning("â ï¸ Duplicados detectados (mismo nombre + nivel). "
                               "Elige como manejarlos.")
                    ca, cb = st.columns(2)
                    if len(dupes_int) > 0:
                        ca.markdown("**En el archivo (" + str(len(dupes_int)) + "):**")
                        ca.dataframe(dupes_int.reset_index(drop=True),
                                     use_container_width=True, hide_index=True)
                    if len(dupes_ext) > 0:
                        cb.markdown("**Ya en la base (" + str(len(dupes_ext)) + "):**")
                        cb.dataframe(dupes_ext.reset_index(drop=True),
                                     use_container_width=True, hide_index=True)
                    opcion = st.radio(
                        "Â¿Que hacer con los duplicados?",
                        ["â Omitir (conservar existentes)",
                         "ð Reemplazar (actualizar con nuevos)",
                         "â Cancelar importacion"],
                        index=0)
                else:
                    st.success("â Sin duplicados â " + str(len(df_nuevo)) +
                               " titulos listos.")
                    opcion = "â Omitir (conservar existentes)"

                if st.button("â Confirmar e importar", use_container_width=True,
                             disabled="Cancelar" in opcion):
                    for col in ["universidad","pais","semestre"]:
                        if col not in df_nuevo.columns:
                            df_nuevo[col] = "" if col != "semestre" else 5
                    df_listo = df_nuevo.drop(columns=["_key"], errors="ignore")
                    if CSV_TITULOS.exists():
                        df_base2  = pd.read_csv(CSV_TITULOS)
                        df_merged = pd.concat([df_base2, df_listo],
                                              ignore_index=True)
                        keep = "first" if "Omitir" in opcion else "last"
                        df_merged.drop_duplicates(
                            subset=["nombre_titulo","nivel"],
                            keep=keep, inplace=True)
                    else:
                        df_merged = df_listo
                        df_merged.drop_duplicates(
                            subset=["nombre_titulo","nivel"],
                            keep="last", inplace=True)
                    df_merged.to_csv(CSV_TITULOS, index=False)
                    get_motor.clear()
                    total_d = len(dupes_int) + len(dupes_ext)
                    st.success("â Importacion completada. "
                               "Duplicados manejados: " + str(total_d) + ". "
                               "Base: " + str(len(df_merged)) + " registros unicos.")
                    st.balloons()
        except Exception as e:
            st.error("Error al leer el archivo: " + str(e))

    st.markdown("---")
    plantilla = pd.DataFrame([
        {"nombre_titulo":"Administracion de Empresas","universidad":"Universidad Nacional",
         "pais":"Colombia","aplica":"","nivel":"universitario","semestre":5},
        {"nombre_titulo":"Maestria en Finanzas","universidad":"EAFIT",
         "pais":"Colombia","aplica":"","nivel":"maestria","semestre":7},
        {"nombre_titulo":"Tecnico en Sistemas","universidad":"SENA",
         "pais":"Colombia","aplica":"","nivel":"bachillerato","semestre":1},
    ])
    st.download_button(
        "â¬ Descargar plantilla CSV",
        data=plantilla.to_csv(index=False).encode("utf-8"),
        file_name="plantilla_titulos.csv", mime="text/csv",
        use_container_width=True)


# âââ PAG 4: HISTORIAL ââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
elif pagina == "ð Historial":
    st.header("ð Historial de decisiones Back")
    if not CSV_DECISIONES.exists():
        st.info("Aun no hay decisiones registradas.")
    else:
        df = pd.read_csv(CSV_DECISIONES)
        if df.empty:
            st.info("El historial esta vacio.")
        else:
            total   = len(df)
            aplican = int((df["decision_aplica"].astype(str).str.lower()
                           .isin(["true","si","1"])).sum())
            c1, c2, c3 = st.columns(3)
            c1.metric("Total revisiones", total)
            c2.metric("â Aprobadas",   aplican)
            c3.metric("â Rechazadas", total - aplican)

            st.markdown("---")
            buscar = st.text_input("ð Buscar titulo", placeholder="Filtrar...")
            _, mf2  = st.columns([2,1])
            filtro  = mf2.selectbox("Mostrar",
                                    ["Todas","Solo aprobadas","Solo rechazadas"])

            df_show = df.copy()
            if buscar:
                df_show = df_show[
                    df_show["nombre_titulo"].astype(str)
                    .str.contains(buscar, case=False, na=False)]
            if filtro == "Solo aprobadas":
                df_show = df_show[
                    df_show["decision_aplica"].astype(str).str.lower()
                    .isin(["true","si","1"])]
            elif filtro == "Solo rechazadas":
                df_show = df_show[
                    ~df_show["decision_aplica"].astype(str).str.lower()
                    .isin(["true","si","1"])]

            # Tabla con texto OSCURO y legible
            st.dataframe(
                df_show.style.set_properties(**{
                    "color": "black",
                    "font-size": "14px"
                }),
                use_container_width=True,
                hide_index=True,
                height=400)

            d1, d2 = st.columns(2)
            d1.download_button(
                "â¬ Descargar decisiones CSV",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name="decisiones_back.csv", mime="text/csv",
                use_container_width=True)
            if CSV_TITULOS.exists():
                df_base_dl = pd.read_csv(CSV_TITULOS)
                d2.download_button(
                    "â¬ Descargar base completa CSV",
                    data=df_base_dl.to_csv(index=False).encode("utf-8"),
                    file_name="titulos_historicos.csv", mime="text/csv",
                    use_container_width=True)

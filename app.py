"""
app.py - Validador de Titulos Academicos
"""
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from validador import ValidadorCSV, SEMESTRE_POR_NIVEL, CSV_DECISIONES, CSV_TITULOS

st.set_page_config(page_title="ValidaTitulos", page_icon=":mortar_board:", layout="wide", initial_sidebar_state="expanded")

CSV_CONSULTAS = Path("consultas_log.csv")

@st.cache_resource
def get_motor():
    return ValidadorCSV()

motor = get_motor()

def registrar_consulta(titulo, resultado, nivel, confianza):
    fila = {
        "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "hora": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        "nombre_titulo": titulo.strip(),
        "resultado": resultado,
        "nivel": nivel or "",
        "confianza_pct": confianza
    }
    if CSV_CONSULTAS.exists():
        df = pd.read_csv(CSV_CONSULTAS)
        df = pd.concat([df, pd.DataFrame([fila])], ignore_index=True)
    else:
        df = pd.DataFrame([fila])
    df.to_csv(CSV_CONSULTAS, index=False)

def existe_duplicado(nombre, nivel, excluir_idx=None):
    n = nombre.strip().lower()
    nv = nivel.strip().lower()
    if CSV_TITULOS.exists():
        df = pd.read_csv(CSV_TITULOS)
        if not df.empty:
            m = (df["nombre_titulo"].astype(str).str.lower().str.strip() == n) & (df["nivel"].astype(str).str.lower().str.strip() == nv)
            if m.any():
                return True
    if CSV_DECISIONES.exists():
        df2 = pd.read_csv(CSV_DECISIONES)
        if not df2.empty and "nivel_confirmado" in df2.columns:
            df2_check = df2.drop(index=excluir_idx) if excluir_idx is not None and excluir_idx in df2.index else df2
            m2 = (df2_check["nombre_titulo"].astype(str).str.lower().str.strip() == n) & (df2_check["nivel_confirmado"].astype(str).str.lower().str.strip() == nv)
            if m2.any():
                return True
    return False

st.markdown("""
<style>
html, body { cursor: auto !important; }
button, label { cursor: pointer !important; }
input[type="text"], textarea { cursor: text !important; }
[data-testid="stSidebar"] { background: #0f1117; }
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
div[data-testid="stDataFrame"] td div { color: #111 !important; font-size:0.85rem !important; }
.metric-card { background:#1a1d2e; border-radius:10px; padding:1rem 1.2rem; margin-bottom:8px; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<div style='padding:0.5rem 0 1.2rem'><div style='font-size:1.35rem;font-weight:700;color:#fff'>ValidaTitulos</div><div style='font-size:0.72rem;color:#888'>Sistema de uso interno</div></div>", unsafe_allow_html=True)
    pagina = st.radio("Nav", ["Validar titulo", "Revision Back", "Cargar datos", "Historial", "Dashboard"], label_visibility="collapsed")
    stats = motor.stats()
    st.markdown("<div style='background:#1a1d2e;border-radius:8px;padding:0.6rem 0.9rem;margin-bottom:5px;display:flex;justify-content:space-between'><span style='color:#aaa;font-size:0.78rem'>Registros totales</span><span style='color:#fff;font-weight:700'>" + str(stats['total']) + "</span></div>", unsafe_allow_html=True)
    st.markdown("<div style='background:#1a1d2e;border-radius:8px;padding:0.6rem 0.9rem;margin-bottom:5px;display:flex;justify-content:space-between'><span style='color:#aaa;font-size:0.78rem'>Aplican</span><span style='color:#4ade80;font-weight:700'>" + str(stats['aplican']) + "</span></div>", unsafe_allow_html=True)
    if CSV_CONSULTAS.exists():
        n_consultas = len(pd.read_csv(CSV_CONSULTAS))
        st.markdown("<div style='background:#1a1d2e;border-radius:8px;padding:0.6rem 0.9rem;margin-bottom:5px;display:flex;justify-content:space-between'><span style='color:#aaa;font-size:0.78rem'>Consultas totales</span><span style='color:#60a5fa;font-weight:700'>" + str(n_consultas) + "</span></div>", unsafe_allow_html=True)
    if st.button("Recargar base", use_container_width=True):
        get_motor.clear()
        st.cache_resource.clear()
        st.rerun()

PAISES   = ["Colombia","Mexico","Argentina","Chile","Peru","Ecuador","Venezuela","Bolivia","Espana","Estados Unidos","Otro"]
PAISES_B = ["Colombia","Mexico","Argentina","Chile","Peru","Ecuador","Venezuela","Espana","Otro"]
NIVELES  = ["universitario","maestria","especializacion","doctorado","tecnologo","bachillerato"]


# PAG 1: VALIDAR
if pagina == "Validar titulo":
    st.header("Validar titulo academico")
    st.info("Ingresa el titulo del cliente. El Back siempre toma la decision final.")
    with st.form("form_validar", clear_on_submit=False):
        titulo = st.text_input("Nombre del titulo *", placeholder="Ej: Administracion de Empresas")
        col1, col2 = st.columns(2)
        universidad = col1.text_input("Universidad", placeholder="Ej: Universidad Nacional")
        pais = col2.selectbox("Pais", PAISES)
        st.file_uploader("Documento soporte (opcional)", type=["pdf","png","jpg","jpeg"])
        submitted = st.form_submit_button("Validar titulo", use_container_width=True)
    if submitted:
        if not titulo.strip():
            st.error("Por favor ingresa el nombre del titulo.")
        else:
            with st.spinner("Consultando base historica..."):
                r = motor.validar(titulo.strip(), universidad.strip(), pais)
            nivel_txt = (r.nivel or "").capitalize()
            sem_txt = str(r.semestre) + " semestre" if r.semestre else "--"
            if r.requiere_revision:
                res_txt = "Requiere revision"
                st.warning("REQUIERE REVISION BACK | Confianza: " + str(r.confianza_pct) + "% | " + r.razon)
                st.session_state["back_titulo"] = titulo.strip()
                st.session_state["back_pre"] = True
            elif r.aplica:
                res_txt = "Aplica"
                st.success("APLICA | Nivel: " + nivel_txt + " | Semestre: " + sem_txt + " | Confianza: " + str(r.confianza_pct) + "%")
            else:
                res_txt = "No aplica"
                st.error("NO APLICA | Nivel: " + nivel_txt + " | Confianza: " + str(r.confianza_pct) + "%")
            st.caption("Metodo: " + r.metodo + " | " + r.razon)
            registrar_consulta(titulo.strip(), res_txt, r.nivel, r.confianza_pct)
            st.session_state["ultimo_resultado"] = {"titulo": titulo.strip(), "universidad": universidad.strip(), "pais": pais, "resultado": r}


# PAG 2: BACK
elif pagina == "Revision Back":
    st.header("Revision manual -- equipo Back")
    tab_nueva, tab_editar = st.tabs(["Nueva decision", "Editar decision existente"])

    with tab_nueva:
        st.warning("Solo para el equipo Back. Cada decision guardada mejora el sistema.")
        prefill = st.session_state.get("back_titulo", "")
        ult = st.session_state.get("ultimo_resultado", {})
        with st.form("form_back", clear_on_submit=True):
            b_titulo = st.text_input("Titulo revisado *", value=prefill, placeholder="Nombre exacto del titulo")
            bc1, bc2 = st.columns(2)
            b_univ = bc1.text_input("Universidad", value=ult.get("universidad",""))
            idx_pais = (PAISES_B.index(ult.get("pais","Colombia")) if ult.get("pais","Colombia") in PAISES_B else 0)
            b_pais = bc2.selectbox("Pais", PAISES_B, index=idx_pais)
            bd1, bd2 = st.columns(2)
            b_aplica = bd1.radio("Este titulo aplica?", ["Si, aplica", "No aplica"])
            b_nivel = bd2.selectbox("Nivel academico confirmado", NIVELES)
            b_revisor = st.text_input("Nombre del revisor", placeholder="Ej: Ana Gomez / Area Back")
            b_motivo = st.text_area("Observaciones", placeholder="Ej: Verificado con acreditacion CESU.", height=90)
            b_incorp = st.checkbox("Incorporar a la base de conocimiento", value=True, help="Valida duplicados por nombre+nivel antes de agregar.")
            b_submit = st.form_submit_button("Guardar decision Back", use_container_width=True)
        if b_submit:
            if not b_titulo.strip():
                st.error("El campo Titulo es obligatorio.")
            elif b_incorp and existe_duplicado(b_titulo.strip(), b_nivel):
                st.error("DUPLICADO: El titulo '" + b_titulo.strip() + "' ya existe con nivel '" + b_nivel + "'. Desmarca Incorporar si solo quieres registrar la decision.")
            else:
                aplica_bool = "Si" in b_aplica
                motor.guardar_decision(titulo=b_titulo.strip(), universidad=b_univ.strip(), pais=b_pais, aplica=aplica_bool, nivel=b_nivel, revisor=b_revisor.strip(), motivo=b_motivo.strip(), incorporar=b_incorp)
                get_motor.clear()
                for k in ("back_titulo","back_pre","ultimo_resultado"):
                    st.session_state.pop(k, None)
                st.success("Guardado: '" + b_titulo.strip() + "' -> " + ("Aplica" if aplica_bool else "No aplica") + " | Nivel: " + b_nivel)

    with tab_editar:
        st.info("Busca un registro ya guardado para corregir el titulo, la decision, el nivel o las observaciones.")
        if not CSV_DECISIONES.exists():
            st.warning("Aun no hay decisiones registradas para editar.")
        else:
            df_dec = pd.read_csv(CSV_DECISIONES)
            if df_dec.empty:
                st.warning("El historial de decisiones esta vacio.")
            else:
                buscar_edit = st.text_input("Buscar titulo a editar", placeholder="Escribe parte del nombre...", key="buscar_editar")
                if buscar_edit.strip():
                    df_filtrado = df_dec[df_dec["nombre_titulo"].astype(str).str.contains(buscar_edit.strip(), case=False, na=False)]
                    if df_filtrado.empty:
                        st.warning("No se encontraron registros con ese termino.")
                    else:
                        st.dataframe(df_filtrado[["nombre_titulo","nivel_confirmado","decision_aplica","revisor","motivo"]].reset_index(), use_container_width=True, hide_index=True)
                        indices = df_filtrado.index.tolist()
                        opciones = [str(i) + " - " + str(df_dec.loc[i,"nombre_titulo"]) for i in indices]
                        sel = st.selectbox("Selecciona el registro a editar", opciones, key="sel_editar")
                        if sel:
                            idx_sel = int(sel.split(" - ")[0])
                            row = df_dec.loc[idx_sel]
                            st.markdown("---")
                            st.markdown("**Editando registro #" + str(idx_sel) + "**")
                            with st.form("form_editar", clear_on_submit=False):
                                e_titulo = st.text_input("Titulo *", value=str(row.get("nombre_titulo","")))
                                ec1, ec2 = st.columns(2)
                                e_univ = ec1.text_input("Universidad", value=str(row.get("universidad","")))
                                pais_actual = str(row.get("pais","Colombia"))
                                idx_ep = PAISES_B.index(pais_actual) if pais_actual in PAISES_B else 0
                                e_pais = ec2.selectbox("Pais", PAISES_B, index=idx_ep, key="edit_pais")
                                ed1, ed2 = st.columns(2)
                                aplica_actual = str(row.get("decision_aplica","")).lower() in ["true","si","1"]
                                e_aplica = ed1.radio("Aplica?", ["Si, aplica","No aplica"], index=(0 if aplica_actual else 1), key="edit_aplica")
                                nivel_actual = str(row.get("nivel_confirmado","universitario"))
                                idx_nv = NIVELES.index(nivel_actual) if nivel_actual in NIVELES else 0
                                e_nivel = ed2.selectbox("Nivel confirmado", NIVELES, index=idx_nv, key="edit_nivel")
                                e_revisor = st.text_input("Revisor", value=str(row.get("revisor","")))
                                e_motivo = st.text_area("Observaciones / Motivo de correccion", value=str(row.get("motivo","")), height=90)
                                e_submit = st.form_submit_button("Guardar cambios", use_container_width=True)
                            if e_submit:
                                if not e_titulo.strip():
                                    st.error("El titulo no puede estar vacio.")
                                else:
                                    df_dec.loc[idx_sel, "nombre_titulo"]   = e_titulo.strip()
                                    df_dec.loc[idx_sel, "universidad"]      = e_univ.strip()
                                    df_dec.loc[idx_sel, "pais"]             = e_pais
                                    df_dec.loc[idx_sel, "decision_aplica"]  = "Si" in e_aplica
                                    df_dec.loc[idx_sel, "nivel_confirmado"] = e_nivel
                                    df_dec.loc[idx_sel, "revisor"]          = e_revisor.strip()
                                    df_dec.loc[idx_sel, "motivo"]           = e_motivo.strip()
                                    df_dec.to_csv(CSV_DECISIONES, index=False)
                                    get_motor.clear()
                                    st.success("Registro actualizado correctamente.")
                                    st.rerun()
                else:
                    st.caption("Escribe al menos una letra para buscar registros.")


# PAG 3: CARGAR DATOS
elif pagina == "Cargar datos":
    st.header("Cargar base historica de titulos")
    st.info("Sube un CSV. Detecta duplicados por nombre + nivel sin importar universidad ni pais.")
    archivo = st.file_uploader("Selecciona tu archivo CSV", type=["csv"], key="csv_uploader")
    if archivo:
        try:
            df_nuevo = pd.read_csv(archivo)
            st.markdown("**Vista previa** -- " + str(len(df_nuevo)) + " filas:")
            st.dataframe(df_nuevo.head(8), use_container_width=True, hide_index=True)
            cols_req = {"nombre_titulo","aplica","nivel"}
            cols_falt = cols_req - set(df_nuevo.columns)
            if cols_falt:
                st.error("Faltan columnas: " + ", ".join(cols_falt))
            else:
                df_nuevo["_key"] = (df_nuevo["nombre_titulo"].astype(str).str.lower().str.strip() + "||" + df_nuevo["nivel"].astype(str).str.lower().str.strip())
                dupes_int = df_nuevo[df_nuevo.duplicated(subset=["_key"], keep=False)][["nombre_titulo","nivel"]].drop_duplicates()
                dupes_ext = pd.DataFrame()
                if CSV_TITULOS.exists():
                    df_base = pd.read_csv(CSV_TITULOS)
                    df_base["_key"] = (df_base["nombre_titulo"].astype(str).str.lower().str.strip() + "||" + df_base["nivel"].astype(str).str.lower().str.strip())
                    dupes_ext = df_nuevo[df_nuevo["_key"].isin(df_base["_key"])][["nombre_titulo","nivel"]].drop_duplicates()
                hay_dupes = len(dupes_int) > 0 or len(dupes_ext) > 0
                if hay_dupes:
                    st.warning("Duplicados detectados. Elige como manejarlos.")
                    ca, cb = st.columns(2)
                    if len(dupes_int) > 0:
                        ca.markdown("**En el archivo (" + str(len(dupes_int)) + "):**")
                        ca.dataframe(dupes_int.reset_index(drop=True), use_container_width=True, hide_index=True)
                    if len(dupes_ext) > 0:
                        cb.markdown("**Ya en la base (" + str(len(dupes_ext)) + "):**")
                        cb.dataframe(dupes_ext.reset_index(drop=True), use_container_width=True, hide_index=True)
                    opcion = st.radio("Que hacer con los duplicados?", ["Omitir (conservar existentes)", "Reemplazar (actualizar con nuevos)", "Cancelar importacion"], index=0)
                else:
                    st.success("Sin duplicados -- " + str(len(df_nuevo)) + " titulos listos.")
                    opcion = "Omitir (conservar existentes)"
                if st.button("Confirmar e importar", use_container_width=True, disabled="Cancelar" in opcion):
                    for col in ["universidad","pais","semestre"]:
                        if col not in df_nuevo.columns:
                            df_nuevo[col] = "" if col != "semestre" else 5
                    df_listo = df_nuevo.drop(columns=["_key"], errors="ignore")
                    if CSV_TITULOS.exists():
                        df_base2 = pd.read_csv(CSV_TITULOS)
                        df_merged = pd.concat([df_base2, df_listo], ignore_index=True)
                        keep = "first" if "Omitir" in opcion else "last"
                        df_merged.drop_duplicates(subset=["nombre_titulo","nivel"], keep=keep, inplace=True)
                    else:
                        df_merged = df_listo
                        df_merged.drop_duplicates(subset=["nombre_titulo","nivel"], keep="last", inplace=True)
                    df_merged.to_csv(CSV_TITULOS, index=False)
                    get_motor.clear()
                    st.success("Importacion completada. Base: " + str(len(df_merged)) + " registros unicos.")
                    st.balloons()
        except Exception as e:
            st.error("Error al leer el archivo: " + str(e))
    st.markdown("---")
    plantilla = pd.DataFrame([{"nombre_titulo":"Administracion de Empresas","universidad":"Universidad Nacional","pais":"Colombia","aplica":"","nivel":"universitario","semestre":5},{"nombre_titulo":"Maestria en Finanzas","universidad":"EAFIT","pais":"Colombia","aplica":"","nivel":"maestria","semestre":7}])
    st.download_button("Descargar plantilla CSV", data=plantilla.to_csv(index=False).encode("utf-8"), file_name="plantilla_titulos.csv", mime="text/csv", use_container_width=True)


# PAG 4: HISTORIAL
elif pagina == "Historial":
    st.header("Historial de decisiones Back")
    if not CSV_DECISIONES.exists():
        st.info("Aun no hay decisiones registradas.")
    else:
        df = pd.read_csv(CSV_DECISIONES)
        if df.empty:
            st.info("El historial esta vacio.")
        else:
            total = len(df)
            aplican = int((df["decision_aplica"].astype(str).str.lower().isin(["true","si","1"])).sum())
            c1, c2, c3 = st.columns(3)
            c1.metric("Total revisiones", total)
            c2.metric("Aprobadas", aplican)
            c3.metric("Rechazadas", total - aplican)
            st.markdown("---")
            buscar = st.text_input("Buscar titulo", placeholder="Filtrar...")
            _, mf2 = st.columns([2,1])
            filtro = mf2.selectbox("Mostrar", ["Todas","Solo aprobadas","Solo rechazadas"])
            df_show = df.copy()
            if buscar:
                df_show = df_show[df_show["nombre_titulo"].astype(str).str.contains(buscar, case=False, na=False)]
            if filtro == "Solo aprobadas":
                df_show = df_show[df_show["decision_aplica"].astype(str).str.lower().isin(["true","si","1"])]
            elif filtro == "Solo rechazadas":
                df_show = df_show[~df_show["decision_aplica"].astype(str).str.lower().isin(["true","si","1"])]
            st.dataframe(df_show.style.set_properties(**{"color":"black","font-size":"14px"}), use_container_width=True, hide_index=True, height=400)
            d1, d2 = st.columns(2)
            d1.download_button("Descargar decisiones CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="decisiones_back.csv", mime="text/csv", use_container_width=True)
            if CSV_TITULOS.exists():
                d2.download_button("Descargar base completa CSV", data=pd.read_csv(CSV_TITULOS).to_csv(index=False).encode("utf-8"), file_name="titulos_historicos.csv", mime="text/csv", use_container_width=True)


# PAG 5: DASHBOARD
elif pagina == "Dashboard":
    st.header("Dashboard de consultas")

    if not CSV_CONSULTAS.exists() or pd.read_csv(CSV_CONSULTAS).empty:
        st.info("Aun no hay consultas registradas. Las consultas se registran automaticamente cada vez que se usa la pestaña Validar titulo.")
    else:
        df_c = pd.read_csv(CSV_CONSULTAS)
        df_c["fecha"] = pd.to_datetime(df_c["fecha"], errors="coerce")

        # --- FILTRO DE FECHA ---
        st.markdown("**Filtrar por rango de fechas:**")
        f1, f2, f3 = st.columns([2,2,1])
        fecha_min = df_c["fecha"].min().date() if not df_c["fecha"].isnull().all() else None
        fecha_max = df_c["fecha"].max().date() if not df_c["fecha"].isnull().all() else None
        f_desde = f1.date_input("Desde", value=fecha_min, key="f_desde")
        f_hasta = f2.date_input("Hasta", value=fecha_max, key="f_hasta")
        if f3.button("Ver todo", use_container_width=True):
            f_desde = fecha_min
            f_hasta = fecha_max
        df_f = df_c[(df_c["fecha"].dt.date >= f_desde) & (df_c["fecha"].dt.date <= f_hasta)]

        st.markdown("---")

        # --- METRICAS PRINCIPALES ---
        total_c   = len(df_f)
        aplica_c  = int((df_f["resultado"].astype(str).str.lower() == "aplica").sum())
        no_apl_c  = int((df_f["resultado"].astype(str).str.lower() == "no aplica").sum())
        rev_c     = int((df_f["resultado"].astype(str).str.lower() == "requiere revision").sum())
        tit_unicos = df_f["nombre_titulo"].nunique()

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total consultas",     total_c)
        m2.metric("Aplican",             aplica_c)
        m3.metric("No aplican",          no_apl_c)
        m4.metric("Requieren revision",  rev_c)
        m5.metric("Titulos unicos",      tit_unicos)

        st.markdown("---")

        col_a, col_b = st.columns(2)

        # --- TOP 10 TITULOS MAS CONSULTADOS ---
        with col_a:
            st.subheader("Top 10 titulos mas consultados")
            top_tit = (df_f.groupby("nombre_titulo")
                         .size()
                         .reset_index(name="consultas")
                         .sort_values("consultas", ascending=False)
                         .head(10))
            if top_tit.empty:
                st.info("Sin datos en el periodo seleccionado.")
            else:
                st.dataframe(
                    top_tit.style.set_properties(**{"color":"black","font-size":"14px"})
                           .bar(subset=["consultas"], color="#60a5fa"),
                    use_container_width=True, hide_index=True, height=370)

        # --- DISTRIBUCION POR RESULTADO ---
        with col_b:
            st.subheader("Distribucion por resultado")
            dist = df_f["resultado"].value_counts().reset_index()
            dist.columns = ["resultado","cantidad"]
            if dist.empty:
                st.info("Sin datos.")
            else:
                st.dataframe(
                    dist.style.set_properties(**{"color":"black","font-size":"14px"}),
                    use_container_width=True, hide_index=True)
            st.markdown(" ")
            st.subheader("Distribucion por nivel")
            niv_dist = df_f[df_f["nivel"].astype(str).str.strip() != ""]["nivel"].value_counts().reset_index()
            niv_dist.columns = ["nivel","consultas"]
            if niv_dist.empty:
                st.info("Sin datos de nivel.")
            else:
                st.dataframe(
                    niv_dist.style.set_properties(**{"color":"black","font-size":"14px"}),
                    use_container_width=True, hide_index=True)

        st.markdown("---")

        # --- CONSULTAS POR DIA ---
        st.subheader("Consultas por dia")
        por_dia = (df_f.groupby("fecha").size().reset_index(name="consultas"))
        por_dia["fecha"] = por_dia["fecha"].dt.strftime("%Y-%m-%d")
        if por_dia.empty:
            st.info("Sin datos en el periodo.")
        else:
            st.bar_chart(por_dia.set_index("fecha")["consultas"])

        st.markdown("---")

        # --- DETALLE COMPLETO ---
        with st.expander("Ver log completo de consultas"):
            st.dataframe(
                df_f.sort_values("fecha", ascending=False)
                    .style.set_properties(**{"color":"black","font-size":"13px"}),
                use_container_width=True, hide_index=True, height=350)
            st.download_button(
                "Descargar log de consultas CSV",
                data=df_f.to_csv(index=False).encode("utf-8"),
                file_name="consultas_log.csv", mime="text/csv",
                use_container_width=True)

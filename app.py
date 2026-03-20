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
CSV_PENDIENTES = Path("pendientes_back.csv")   # nuevo: solicitudes esperando decision del Back

COLS_PENDIENTES = ["id","fecha","hora","nombre_titulo","universidad","pais","nivel_detectado","titular","texto_original","estado","revisor","decision","nivel_confirmado","motivo"]

@st.cache_resource
def get_motor():
    return ValidadorCSV()

motor = get_motor()

def registrar_consulta(titulo, resultado, nivel, confianza):
    fila = {"fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "hora": datetime.now(timezone.utc).strftime("%H:%M:%S"), "nombre_titulo": titulo.strip(), "resultado": resultado, "nivel": nivel or "", "confianza_pct": confianza}
    df = pd.concat([pd.read_csv(CSV_CONSULTAS), pd.DataFrame([fila])], ignore_index=True) if CSV_CONSULTAS.exists() else pd.DataFrame([fila])
    df.to_csv(CSV_CONSULTAS, index=False)

def guardar_pendiente(titulo, universidad, pais, nivel, titular, texto_original):
    nuevo_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    fila = {"id": nuevo_id, "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "hora": datetime.now(timezone.utc).strftime("%H:%M:%S"), "nombre_titulo": titulo, "universidad": universidad, "pais": pais, "nivel_detectado": nivel, "titular": titular, "texto_original": texto_original[:300], "estado": "PENDIENTE", "revisor": "", "decision": "", "nivel_confirmado": "", "motivo": ""}
    df = pd.concat([pd.read_csv(CSV_PENDIENTES), pd.DataFrame([fila])], ignore_index=True) if CSV_PENDIENTES.exists() else pd.DataFrame([fila])
    df.to_csv(CSV_PENDIENTES, index=False)
    return nuevo_id

def contar_pendientes():
    if not CSV_PENDIENTES.exists():
        return 0
    df = pd.read_csv(CSV_PENDIENTES)
    return int((df["estado"].astype(str).str.upper() == "PENDIENTE").sum())

def existe_duplicado(nombre, nivel):
    n = nombre.strip().lower()
    nv = nivel.strip().lower()
    if CSV_TITULOS.exists():
        df = pd.read_csv(CSV_TITULOS)
        if not df.empty and ((df["nombre_titulo"].astype(str).str.lower().str.strip() == n) & (df["nivel"].astype(str).str.lower().str.strip() == nv)).any():
            return True
    if CSV_DECISIONES.exists():
        df2 = pd.read_csv(CSV_DECISIONES)
        if not df2.empty and "nivel_confirmado" in df2.columns and ((df2["nombre_titulo"].astype(str).str.lower().str.strip() == n) & (df2["nivel_confirmado"].astype(str).str.lower().str.strip() == nv)).any():
            return True
    return False

def extraer_datos_diploma(texto):
    lineas = [l.strip() for l in texto.strip().split("\n") if l.strip()]
    texto_lower = texto.lower()
    keywords_nivel = {
        "doctorado":       ["doctorado","doctor en","phd","ph.d"],
        "maestria":        ["maestria","master","magister","magister"],
        "especializacion": ["especializacion","especialista en"],
        "tecnologo":       ["tecnologo","tecnologia en","tecnologo"],
        "bachillerato":    ["bachiller","bachillerato","tecnico en"],
        "universitario":   ["ingeniero","ingeniera","administrador","licenciado","licenciada","arquitecto","contador","medico","abogado","psicologo","economista","biologo","quimico","fisico"]
    }
    nivel = "universitario"
    for nv, kws in keywords_nivel.items():
        if any(kw in texto_lower for kw in kws):
            nivel = nv
            break
    titulo = ""
    triggers = ["titulo de","otorga el titulo","grado de","titulo academico","titulo profesional","carrera de","programa de","titulo en"]
    for i, linea in enumerate(lineas):
        if any(tw in linea.lower() for tw in triggers):
            if i + 1 < len(lineas):
                titulo = lineas[i + 1]
                break
    if not titulo:
        for nv, kws in keywords_nivel.items():
            for linea in lineas:
                if any(kw in linea.lower() for kw in kws) and len(linea) > 8:
                    titulo = linea
                    break
            if titulo:
                break
    univ = ""
    for linea in lineas:
        if any(kw in linea.lower() for kw in ["universidad","institucion universitaria","instituto","corporacion","fundacion universitaria","escuela","tecnologico","politecnico"]):
            univ = linea
            break
    pais = "Colombia"
    for clave, valor in {"colombia":"Colombia","mexico":"Mexico","argentina":"Argentina","chile":"Chile","peru":"Peru","ecuador":"Ecuador","venezuela":"Venezuela","espana":"Espana","estados unidos":"Estados Unidos","bolivia":"Bolivia"}.items():
        if clave in texto_lower:
            pais = valor
            break
    titular = ""
    titular_kws = ["otorga a","conferido a","se otorga a","concede a","a nombre de","otorgado a"]
    for i, linea in enumerate(lineas):
        if any(tw in linea.lower() for tw in titular_kws):
            if i + 1 < len(lineas):
                titular = lineas[i + 1]
                break
    return titulo, univ, pais, nivel, titular

st.markdown("""
<style>
html, body { cursor: auto !important; }
button, label { cursor: pointer !important; }
input[type="text"], textarea { cursor: text !important; }
[data-testid="stSidebar"] { background: #0f1117; }
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
div[data-testid="stDataFrame"] td div { color: #111 !important; font-size:0.85rem !important; }
.alerta-pendiente { background: #fef3c7; border-left: 4px solid #f59e0b; padding: 0.8rem 1rem; border-radius: 6px; margin-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

pendientes_count = contar_pendientes()

with st.sidebar:
    st.markdown("<div style='padding:0.5rem 0 1.2rem'><div style='font-size:1.35rem;font-weight:700;color:#fff'>ValidaTitulos</div><div style='font-size:0.72rem;color:#888'>Sistema de uso interno</div></div>", unsafe_allow_html=True)

    # Alerta visual en sidebar si hay pendientes
    if pendientes_count > 0:
        st.markdown("<div style='background:#f59e0b;color:#000;font-weight:700;border-radius:8px;padding:0.5rem 0.9rem;margin-bottom:8px;text-align:center'>PENDIENTES BACK: " + str(pendientes_count) + "</div>", unsafe_allow_html=True)

    pagina = st.radio("Nav", ["Validar titulo", "Ingresar diploma", "Revision Back", "Cargar datos", "Historial", "Dashboard"], label_visibility="collapsed")
    stats = motor.stats()
    st.markdown("<div style='background:#1a1d2e;border-radius:8px;padding:0.6rem 0.9rem;margin-bottom:5px;display:flex;justify-content:space-between'><span style='color:#aaa;font-size:0.78rem'>Registros totales</span><span style='color:#fff;font-weight:700'>" + str(stats['total']) + "</span></div>", unsafe_allow_html=True)
    st.markdown("<div style='background:#1a1d2e;border-radius:8px;padding:0.6rem 0.9rem;margin-bottom:5px;display:flex;justify-content:space-between'><span style='color:#aaa;font-size:0.78rem'>Aplican</span><span style='color:#4ade80;font-weight:700'>" + str(stats['aplican']) + "</span></div>", unsafe_allow_html=True)
    if CSV_CONSULTAS.exists():
        st.markdown("<div style='background:#1a1d2e;border-radius:8px;padding:0.6rem 0.9rem;margin-bottom:5px;display:flex;justify-content:space-between'><span style='color:#aaa;font-size:0.78rem'>Consultas totales</span><span style='color:#60a5fa;font-weight:700'>" + str(len(pd.read_csv(CSV_CONSULTAS))) + "</span></div>", unsafe_allow_html=True)
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
                st.warning("REQUIERE REVISION BACK | Confianza: " + str(r.confianza_pct) + "% | " + r.razon)
                st.session_state["back_titulo"] = titulo.strip()
            elif r.aplica:
                st.success("APLICA | Nivel: " + nivel_txt + " | Semestre: " + sem_txt + " | Confianza: " + str(r.confianza_pct) + "%")
            else:
                st.error("NO APLICA | Nivel: " + nivel_txt + " | Confianza: " + str(r.confianza_pct) + "%")
            st.caption("Metodo: " + r.metodo + " | " + r.razon)
            registrar_consulta(titulo.strip(), "Aplica" if r.aplica else ("Requiere revision" if r.requiere_revision else "No aplica"), r.nivel, r.confianza_pct)
            st.session_state["ultimo_resultado"] = {"titulo": titulo.strip(), "universidad": universidad.strip(), "pais": pais, "resultado": r}


# PAG 2: INGRESAR DIPLOMA
elif pagina == "Ingresar diploma":
    st.header("Ingresar diploma")

    # Alerta si hay pendientes
    if pendientes_count > 0:
        st.markdown("<div class='alerta-pendiente'><b>Aviso:</b> Hay <b>" + str(pendientes_count) + " diploma(s)</b> esperando decision del Back. Ve a <b>Revision Back</b> para aprobarlos.</div>", unsafe_allow_html=True)

    st.info("Pega el texto del diploma. El sistema extrae los datos automaticamente y los envia al Back para su aprobacion.")

    texto_diploma = st.text_area("Texto del diploma *", height=160,
        placeholder="Pega aqui el texto completo del diploma...\nEj: UNIVERSIDAD NACIONAL - OTORGA EL TITULO DE INGENIERO DE SISTEMAS A JUAN PEREZ")

    if texto_diploma.strip():
        titulo_d, univ_d, pais_d, nivel_d, titular_d = extraer_datos_diploma(texto_diploma)

        st.markdown("---")
        st.subheader("Datos extraidos -- Revisa y corrige si es necesario")

        col1, col2 = st.columns(2)
        titulo_f    = col1.text_input("Nombre del titulo *", value=titulo_d, key="d_titulo")
        univ_f      = col2.text_input("Universidad",         value=univ_d,   key="d_univ")
        col3, col4  = st.columns(2)
        idx_p = PAISES.index(pais_d) if pais_d in PAISES else 0
        pais_f      = col3.selectbox("Pais",   PAISES,  index=idx_p, key="d_pais")
        idx_n = NIVELES.index(nivel_d) if nivel_d in NIVELES else 0
        nivel_f     = col4.selectbox("Nivel",  NIVELES, index=idx_n, key="d_nivel")
        titular_f   = st.text_input("Nombre del titular del diploma", value=titular_d, key="d_titular")

        st.markdown("---")

        if st.button("Enviar al Back para aprobacion", use_container_width=True, type="primary"):
            if not titulo_f.strip():
                st.error("El campo Titulo es obligatorio.")
            else:
                nuevo_id = guardar_pendiente(titulo_f.strip(), univ_f.strip(), pais_f, nivel_f, titular_f.strip(), texto_diploma)
                st.success("Solicitud enviada al Back con ID: " + nuevo_id + ". El equipo Back recibira la alerta y aprobara la decision.")
                st.session_state.pop("d_titulo", None)
                st.rerun()
    else:
        st.markdown("""
**Como funciona el flujo:**
1. Pega el texto del diploma en el campo de arriba
2. El sistema detecta titulo, universidad, pais, nivel y titular
3. Corrige los datos si es necesario
4. Haz clic en **Enviar al Back**
5. El equipo Back ve la alerta, revisa y aprueba o rechaza
        """)


# PAG 3: REVISION BACK
elif pagina == "Revision Back":
    st.header("Revision manual -- equipo Back")

    # --- ALERTA DE PENDIENTES ---
    if pendientes_count > 0:
        st.markdown("<div class='alerta-pendiente'><b>ATENCION:</b> Tienes <b>" + str(pendientes_count) + " diploma(s) pendiente(s)</b> esperando tu decision. Revisalos en la pestana de abajo.</div>", unsafe_allow_html=True)

    tab_pendientes, tab_nueva, tab_editar = st.tabs(["PENDIENTES (" + str(pendientes_count) + ")", "Nueva decision", "Editar decision"])

    # ---- TAB PENDIENTES ----
    with tab_pendientes:
        if not CSV_PENDIENTES.exists() or pendientes_count == 0:
            st.info("No hay diplomas pendientes de aprobacion.")
        else:
            df_pend = pd.read_csv(CSV_PENDIENTES)
            df_solo_pend = df_pend[df_pend["estado"].astype(str).str.upper() == "PENDIENTE"].reset_index(drop=True)
            st.markdown("**" + str(len(df_solo_pend)) + " diploma(s) esperando tu decision:**")
            for i, row in df_solo_pend.iterrows():
                idx_real = df_pend[df_pend["id"].astype(str) == str(row["id"])].index[0]
                with st.expander("PENDIENTE -- " + str(row.get("nombre_titulo","")) + " | " + str(row.get("fecha","")) + " " + str(row.get("hora",""))):
                    col_info, col_form = st.columns([1,1])
                    with col_info:
                        st.markdown("**Datos del diploma:**")
                        st.write("Titulo: " + str(row.get("nombre_titulo","")))
                        st.write("Universidad: " + str(row.get("universidad","")))
                        st.write("Pais: " + str(row.get("pais","")))
                        st.write("Nivel detectado: " + str(row.get("nivel_detectado","")))
                        st.write("Titular: " + str(row.get("titular","")))
                        if str(row.get("texto_original","")):
                            st.markdown("**Texto original:**")
                            st.caption(str(row.get("texto_original","")))
                    with col_form:
                        st.markdown("**Decision del Back:**")
                        p_aplica  = st.radio("Aplica?", ["Si, aplica","No aplica"], key="p_aplica_"+str(row["id"]))
                        nv_actual = str(row.get("nivel_detectado","universitario"))
                        idx_nv = NIVELES.index(nv_actual) if nv_actual in NIVELES else 0
                        p_nivel   = st.selectbox("Confirmar nivel", NIVELES, index=idx_nv, key="p_nivel_"+str(row["id"]))
                        p_revisor = st.text_input("Tu nombre (revisor)", key="p_revisor_"+str(row["id"]), placeholder="Ej: Ana Gomez")
                        p_motivo  = st.text_area("Observaciones", key="p_motivo_"+str(row["id"]), height=80, placeholder="Ej: Verificado. Aplica para programa X.")
                        p_incorp  = st.checkbox("Incorporar a la base", value=True, key="p_incorp_"+str(row["id"]))

                        ca, cr = st.columns(2)
                        aprobar  = ca.button("Aprobar", key="aprobar_"+str(row["id"]),  use_container_width=True, type="primary")
                        rechazar = cr.button("Rechazar", key="rechazar_"+str(row["id"]), use_container_width=True)

                        if aprobar or rechazar:
                            aplica_bool = "Si" in p_aplica if aprobar else False
                            df_pend.loc[idx_real, "estado"]          = "APROBADO" if aprobar else "RECHAZADO"
                            df_pend.loc[idx_real, "revisor"]         = p_revisor.strip()
                            df_pend.loc[idx_real, "decision"]        = "Aplica" if aplica_bool else "No aplica"
                            df_pend.loc[idx_real, "nivel_confirmado"]= p_nivel
                            df_pend.loc[idx_real, "motivo"]          = p_motivo.strip()
                            df_pend.to_csv(CSV_PENDIENTES, index=False)
                            # Guardar en decisiones_back.csv
                            motor.guardar_decision(titulo=str(row["nombre_titulo"]), universidad=str(row.get("universidad","")), pais=str(row.get("pais","Colombia")), aplica=aplica_bool, nivel=p_nivel, revisor=p_revisor.strip(), motivo=p_motivo.strip(), incorporar=p_incorp)
                            get_motor.clear()
                            estado_txt = "APROBADO" if aprobar else "RECHAZADO"
                            st.success("Diploma " + estado_txt + " correctamente.")
                            st.rerun()

    # ---- TAB NUEVA DECISION ----
    with tab_nueva:
        st.warning("Solo para el equipo Back. Cada decision guardada mejora el sistema.")
        prefill = st.session_state.get("back_titulo", "")
        ult = st.session_state.get("ultimo_resultado", {})
        with st.form("form_back", clear_on_submit=True):
            b_titulo  = st.text_input("Titulo revisado *", value=prefill, placeholder="Nombre exacto del titulo")
            bc1, bc2  = st.columns(2)
            b_univ    = bc1.text_input("Universidad", value=ult.get("universidad",""))
            idx_pais  = (PAISES_B.index(ult.get("pais","Colombia")) if ult.get("pais","Colombia") in PAISES_B else 0)
            b_pais    = bc2.selectbox("Pais", PAISES_B, index=idx_pais)
            bd1, bd2  = st.columns(2)
            b_aplica  = bd1.radio("Este titulo aplica?", ["Si, aplica", "No aplica"])
            b_nivel   = bd2.selectbox("Nivel academico confirmado", NIVELES)
            b_revisor = st.text_input("Nombre del revisor", placeholder="Ej: Ana Gomez")
            b_motivo  = st.text_area("Observaciones", height=80)
            b_incorp  = st.checkbox("Incorporar a la base de conocimiento", value=True)
            b_submit  = st.form_submit_button("Guardar decision Back", use_container_width=True)
        if b_submit:
            if not b_titulo.strip():
                st.error("El campo Titulo es obligatorio.")
            elif b_incorp and existe_duplicado(b_titulo.strip(), b_nivel):
                st.error("DUPLICADO: '" + b_titulo.strip() + "' ya existe con nivel '" + b_nivel + "'.")
            else:
                aplica_bool = "Si" in b_aplica
                motor.guardar_decision(titulo=b_titulo.strip(), universidad=b_univ.strip(), pais=b_pais, aplica=aplica_bool, nivel=b_nivel, revisor=b_revisor.strip(), motivo=b_motivo.strip(), incorporar=b_incorp)
                get_motor.clear()
                for k in ("back_titulo","ultimo_resultado"):
                    st.session_state.pop(k, None)
                st.success("Guardado: '" + b_titulo.strip() + "' -> " + ("Aplica" if aplica_bool else "No aplica"))

    # ---- TAB EDITAR ----
    with tab_editar:
        st.info("Busca un registro ya guardado para corregir cualquier campo.")
        if not CSV_DECISIONES.exists():
            st.warning("Aun no hay decisiones registradas.")
        else:
            df_dec = pd.read_csv(CSV_DECISIONES)
            if df_dec.empty:
                st.warning("El historial esta vacio.")
            else:
                buscar_edit = st.text_input("Buscar titulo", placeholder="Escribe parte del nombre...", key="buscar_editar")
                if buscar_edit.strip():
                    df_f2 = df_dec[df_dec["nombre_titulo"].astype(str).str.contains(buscar_edit.strip(), case=False, na=False)]
                    if df_f2.empty:
                        st.warning("No se encontraron registros.")
                    else:
                        st.dataframe(df_f2[["nombre_titulo","nivel_confirmado","decision_aplica","revisor","motivo"]].reset_index(), use_container_width=True, hide_index=True)
                        opciones = [str(i) + " - " + str(df_dec.loc[i,"nombre_titulo"]) for i in df_f2.index.tolist()]
                        sel = st.selectbox("Selecciona el registro", opciones, key="sel_editar")
                        if sel:
                            idx_sel = int(sel.split(" - ")[0])
                            row = df_dec.loc[idx_sel]
                            with st.form("form_editar", clear_on_submit=False):
                                e_titulo  = st.text_input("Titulo *", value=str(row.get("nombre_titulo","")))
                                ec1, ec2  = st.columns(2)
                                e_univ    = ec1.text_input("Universidad", value=str(row.get("universidad","")))
                                pa = str(row.get("pais","Colombia"))
                                e_pais    = ec2.selectbox("Pais", PAISES_B, index=(PAISES_B.index(pa) if pa in PAISES_B else 0), key="edit_pais")
                                ed1, ed2  = st.columns(2)
                                apl_act   = str(row.get("decision_aplica","")).lower() in ["true","si","1"]
                                e_aplica  = ed1.radio("Aplica?", ["Si, aplica","No aplica"], index=(0 if apl_act else 1), key="edit_aplica")
                                nv_act    = str(row.get("nivel_confirmado","universitario"))
                                e_nivel   = ed2.selectbox("Nivel", NIVELES, index=(NIVELES.index(nv_act) if nv_act in NIVELES else 0), key="edit_nivel")
                                e_revisor = st.text_input("Revisor", value=str(row.get("revisor","")))
                                e_motivo  = st.text_area("Motivo de correccion", value=str(row.get("motivo","")), height=80)
                                e_submit  = st.form_submit_button("Guardar cambios", use_container_width=True)
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
                                    st.success("Registro actualizado.")
                                    st.rerun()
                else:
                    st.caption("Escribe al menos una letra para buscar.")


# PAG 4: CARGAR DATOS
elif pagina == "Cargar datos":
    st.header("Cargar base historica de titulos")
    st.info("Sube un CSV. Detecta duplicados por nombre + nivel.")
    archivo = st.file_uploader("Selecciona tu archivo CSV", type=["csv"], key="csv_uploader")
    if archivo:
        try:
            df_nuevo = pd.read_csv(archivo)
            st.markdown("**Vista previa** -- " + str(len(df_nuevo)) + " filas:")
            st.dataframe(df_nuevo.head(8), use_container_width=True, hide_index=True)
            cols_falt = {"nombre_titulo","aplica","nivel"} - set(df_nuevo.columns)
            if cols_falt:
                st.error("Faltan columnas: " + ", ".join(cols_falt))
            else:
                df_nuevo["_key"] = df_nuevo["nombre_titulo"].astype(str).str.lower().str.strip() + "||" + df_nuevo["nivel"].astype(str).str.lower().str.strip()
                dupes_int = df_nuevo[df_nuevo.duplicated(subset=["_key"], keep=False)][["nombre_titulo","nivel"]].drop_duplicates()
                dupes_ext = pd.DataFrame()
                if CSV_TITULOS.exists():
                    df_base = pd.read_csv(CSV_TITULOS)
                    df_base["_key"] = df_base["nombre_titulo"].astype(str).str.lower().str.strip() + "||" + df_base["nivel"].astype(str).str.lower().str.strip()
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
                    opcion = st.radio("Que hacer?", ["Omitir (conservar existentes)", "Reemplazar (actualizar con nuevos)", "Cancelar importacion"], index=0)
                else:
                    st.success("Sin duplicados -- " + str(len(df_nuevo)) + " titulos listos.")
                    opcion = "Omitir (conservar existentes)"
                if st.button("Confirmar e importar", use_container_width=True, disabled="Cancelar" in opcion):
                    for col in ["universidad","pais","semestre"]:
                        if col not in df_nuevo.columns:
                            df_nuevo[col] = "" if col != "semestre" else 5
                    df_listo = df_nuevo.drop(columns=["_key"], errors="ignore")
                    if CSV_TITULOS.exists():
                        df_merged = pd.concat([pd.read_csv(CSV_TITULOS), df_listo], ignore_index=True)
                        df_merged.drop_duplicates(subset=["nombre_titulo","nivel"], keep=("first" if "Omitir" in opcion else "last"), inplace=True)
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
    plantilla = pd.DataFrame([{"nombre_titulo":"Administracion de Empresas","universidad":"Universidad Nacional","pais":"Colombia","aplica":"","nivel":"universitario","semestre":5}])
    st.download_button("Descargar plantilla CSV", data=plantilla.to_csv(index=False).encode("utf-8"), file_name="plantilla_titulos.csv", mime="text/csv", use_container_width=True)


# PAG 5: HISTORIAL
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


# PAG 6: DASHBOARD
elif pagina == "Dashboard":
    st.header("Dashboard de consultas")
    if not CSV_CONSULTAS.exists() or pd.read_csv(CSV_CONSULTAS).empty:
        st.info("Aun no hay consultas registradas.")
    else:
        df_c = pd.read_csv(CSV_CONSULTAS)
        df_c["fecha"] = pd.to_datetime(df_c["fecha"], errors="coerce")
        f1, f2 = st.columns(2)
        fecha_min = df_c["fecha"].min().date() if not df_c["fecha"].isnull().all() else None
        fecha_max = df_c["fecha"].max().date() if not df_c["fecha"].isnull().all() else None
        f_desde = f1.date_input("Desde", value=fecha_min)
        f_hasta = f2.date_input("Hasta", value=fecha_max)
        df_f = df_c[(df_c["fecha"].dt.date >= f_desde) & (df_c["fecha"].dt.date <= f_hasta)]
        st.markdown("---")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total consultas",    len(df_f))
        m2.metric("Aplican",            int((df_f["resultado"].astype(str).str.lower() == "aplica").sum()))
        m3.metric("No aplican",         int((df_f["resultado"].astype(str).str.lower() == "no aplica").sum()))
        m4.metric("Requieren revision", int((df_f["resultado"].astype(str).str.lower() == "requiere revision").sum()))
        m5.metric("Titulos unicos",     df_f["nombre_titulo"].nunique())
        st.markdown("---")
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Top 10 titulos mas consultados")
            top = df_f.groupby("nombre_titulo").size().reset_index(name="consultas").sort_values("consultas", ascending=False).head(10)
            if not top.empty:
                st.dataframe(top.style.set_properties(**{"color":"black","font-size":"14px"}).bar(subset=["consultas"], color="#60a5fa"), use_container_width=True, hide_index=True, height=370)
        with col_b:
            st.subheader("Por resultado")
            dist = df_f["resultado"].value_counts().reset_index()
            dist.columns = ["resultado","cantidad"]
            st.dataframe(dist.style.set_properties(**{"color":"black","font-size":"14px"}), use_container_width=True, hide_index=True)
            st.subheader("Por nivel")
            niv_d = df_f[df_f["nivel"].astype(str).str.strip() != ""]["nivel"].value_counts().reset_index()
            niv_d.columns = ["nivel","consultas"]
            if not niv_d.empty:
                st.dataframe(niv_d.style.set_properties(**{"color":"black","font-size":"14px"}), use_container_width=True, hide_index=True)
        st.markdown("---")
        st.subheader("Consultas por dia")
        por_dia = df_f.groupby("fecha").size().reset_index(name="consultas")
        por_dia["fecha"] = por_dia["fecha"].dt.strftime("%Y-%m-%d")
        if not por_dia.empty:
            st.bar_chart(por_dia.set_index("fecha")["consultas"])
        with st.expander("Ver log completo"):
            st.dataframe(df_f.sort_values("fecha", ascending=False).style.set_properties(**{"color":"black","font-size":"13px"}), use_container_width=True, hide_index=True, height=350)
            st.download_button("Descargar log CSV", data=df_f.to_csv(index=False).encode("utf-8"), file_name="consultas_log.csv", mime="text/csv", use_container_width=True)

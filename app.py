"""
app.py - Validador de Titulos Academicos
Pendientes se guardan en GitHub via API para persistencia real.
Configura en Streamlit Secrets: GITHUB_TOKEN y GITHUB_REPO
"""
from pathlib import Path
from datetime import datetime, timezone
import base64, json, io, urllib.request, urllib.error
import unicodedata
import pandas as pd
import streamlit as st
from validador import ValidadorCSV, SEMESTRE_POR_NIVEL, CSV_DECISIONES, CSV_TITULOS

st.set_page_config(page_title="ValidaTitulos", page_icon=":mortar_board:", layout="wide", initial_sidebar_state="expanded")

CSV_CONSULTAS = Path("consultas_log.csv")

@st.cache_resource
def get_motor():
    return ValidadorCSV()
motor = get_motor()

def get_github_config():
    try:
        gh_token = st.secrets["GITHUB_TOKEN"]
        gh_repo  = st.secrets.get("GITHUB_REPO", "usanjosedocumentos-svg/validatitulos")
    except Exception:
        gh_token = ""
        gh_repo  = "usanjosedocumentos-svg/validatitulos"
    return gh_token, gh_repo

def gh_get_pendientes():
    gh_token, gh_repo = get_github_config()
    if not gh_token:
        cols = ["id","fecha","hora","nombre_titulo","universidad","pais","nivel_detectado","titular","texto_diploma","estado","revisor","decision","nivel_confirmado","motivo"]
        return pd.DataFrame(columns=cols), None
    api_url = "https://api.github.com/repos/" + gh_repo + "/contents/pendientes_back.csv"
    req = urllib.request.Request(api_url,
        headers={"Authorization": "token " + gh_token, "Accept": "application/vnd.github.v3+json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data    = json.loads(r.read().decode())
            sha     = data["sha"]
            content = base64.b64decode(data["content"].replace("\n","")).decode("utf-8")
            df      = pd.read_csv(io.StringIO(content))
            return df, sha
    except Exception:
        cols = ["id","fecha","hora","nombre_titulo","universidad","pais","nivel_detectado","titular","texto_diploma","estado","revisor","decision","nivel_confirmado","motivo"]
        return pd.DataFrame(columns=cols), None

def gh_save_pendientes(df, sha, mensaje="Update pendientes_back.csv"):
    gh_token, gh_repo = get_github_config()
    if not gh_token:
        return False, "No hay GITHUB_TOKEN configurado en Streamlit Secrets."
    api_url = "https://api.github.com/repos/" + gh_repo + "/contents/pendientes_back.csv"
    csv_str = df.to_csv(index=False)
    b64c    = base64.b64encode(csv_str.encode("utf-8")).decode("ascii")
    body    = {"message": mensaje, "content": b64c, "branch": "main"}
    if sha:
        body["sha"] = sha
    req = urllib.request.Request(api_url, data=json.dumps(body).encode("utf-8"), method="PUT",
        headers={"Authorization": "token " + gh_token, "Accept": "application/vnd.github.v3+json", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return True, None
    except urllib.error.HTTPError as e:
        return False, str(e.code) + ": " + e.read().decode()[:200]
    except Exception as e:
        return False, str(e)

def contar_pendientes():
    df, _ = gh_get_pendientes()
    if df.empty or "estado" not in df.columns:
        return 0
    return int((df["estado"].astype(str).str.upper() == "PENDIENTE").sum())

def registrar_consulta(titulo, resultado, nivel, confianza):
    fila = {"fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "hora":  datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "nombre_titulo": titulo, "resultado": resultado,
            "nivel": nivel or "", "confianza_pct": confianza}
    df = pd.concat([pd.read_csv(CSV_CONSULTAS), pd.DataFrame([fila])], ignore_index=True) if CSV_CONSULTAS.exists() else pd.DataFrame([fila])
    df.to_csv(CSV_CONSULTAS, index=False)

def similar(a, b):
    """Similitud entre dos strings - tolerante a ortografia y acentos."""
    def norm(s):
        s = unicodedata.normalize("NFD", str(s).lower().strip())
        return "".join(c for c in s if unicodedata.category(c) != "Mn")
    an = norm(a); bn = norm(b)
    if an == bn: return 1.0
    if an in bn or bn in an: return 0.85
    wa = set(an.split()); wb = set(bn.split())
    if not wa or not wb: return 0.0
    comunes = wa & wb
    return len(comunes) / max(len(wa), len(wb))

def existe_duplicado(nombre, nivel):
    n, nv = nombre.strip().lower(), nivel.strip().lower()
    if CSV_TITULOS.exists():
        df = pd.read_csv(CSV_TITULOS)
        if not df.empty and ((df["nombre_titulo"].astype(str).str.lower().str.strip()==n)&(df["nivel"].astype(str).str.lower().str.strip()==nv)).any():
            return True
    if CSV_DECISIONES.exists():
        df2 = pd.read_csv(CSV_DECISIONES)
        if not df2.empty and "nivel_confirmado" in df2.columns:
            if ((df2["nombre_titulo"].astype(str).str.lower().str.strip()==n)&(df2["nivel_confirmado"].astype(str).str.lower().str.strip()==nv)).any():
                return True
    return False

def extraer_datos_diploma(texto):
    lineas = [l.strip() for l in texto.strip().split("\n") if l.strip()]
    tl = texto.lower()
    kn = {"doctorado":["doctorado","doctor en","phd"],"maestria":["maestria","master","magister"],
          "especializacion":["especializacion","especialista en"],"tecnologo":["tecnologo","tecnologia en"],
          "bachillerato":["bachiller","bachillerato","tecnico en"],
          "universitario":["ingeniero","ingeniera","administrador","licenciado","arquitecto","contador","medico","abogado","psicologo","economista"]}
    nivel = "universitario"
    for nv, kws in kn.items():
        if any(k in tl for k in kws): nivel = nv; break
    titulo = ""
    for i,linea in enumerate(lineas):
        if any(t in linea.lower() for t in ["titulo de","otorga el titulo","grado de","programa de","titulo en"]):
            if i+1 < len(lineas): titulo = lineas[i+1]; break
    if not titulo:
        for nv, kws in kn.items():
            for linea in lineas:
                if any(k in linea.lower() for k in kws) and len(linea)>8: titulo=linea; break
            if titulo: break
    univ = ""
    for linea in lineas:
        if any(k in linea.lower() for k in ["universidad","institucion universitaria","corporacion","fundacion universitaria","tecnologico","politecnico"]):
            univ=linea; break
    pais = "Colombia"
    for c,v in {"colombia":"Colombia","mexico":"Mexico","argentina":"Argentina","chile":"Chile","peru":"Peru","ecuador":"Ecuador","venezuela":"Venezuela","espana":"Espana","bolivia":"Bolivia","estados unidos":"Estados Unidos"}.items():
        if c in tl: pais=v; break
    titular=""
    for i,linea in enumerate(lineas):
        if any(t in linea.lower() for t in ["otorga a","conferido a","se otorga a","a nombre de"]):
            if i+1<len(lineas): titular=lineas[i+1]; break
    return titulo, univ, pais, nivel, titular

st.markdown("""
<style>
html, body { cursor: auto !important; }
button, label { cursor: pointer !important; }
input[type="text"], textarea { cursor: text !important; }
[data-testid="stSidebar"] { background: #0f1117; }
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
div[data-testid="stDataFrame"] td div { color: #111 !important; font-size:0.85rem !important; }
</style>
""", unsafe_allow_html=True)

pendientes_count = contar_pendientes()
gh_token, _ = get_github_config()
secrets_ok = bool(gh_token)

with st.sidebar:
    st.markdown("<div style='padding:0.5rem 0 1.2rem'><div style='font-size:1.35rem;font-weight:700;color:#fff'>ValidaTitulos</div><div style='font-size:0.72rem;color:#888'>Sistema de uso interno</div></div>", unsafe_allow_html=True)
    if not secrets_ok:
        st.markdown("<div style='background:#ef4444;color:#fff;font-weight:700;border-radius:8px;padding:0.5rem 0.9rem;margin-bottom:8px;text-align:center;font-size:0.75rem'>Config. Secrets requerida</div>", unsafe_allow_html=True)
    elif pendientes_count > 0:
        st.markdown("<div style='background:#f59e0b;color:#000;font-weight:700;border-radius:8px;padding:0.5rem 0.9rem;margin-bottom:8px;text-align:center'>PENDIENTES BACK: " + str(pendientes_count) + "</div>", unsafe_allow_html=True)
    pagina = st.radio("Nav", ["Validar titulo","Ingresar diploma","Revision Back","Cargar datos","Historial","Dashboard"], label_visibility="collapsed")
    stats = motor.stats()
    st.markdown("<div style='background:#1a1d2e;border-radius:8px;padding:0.6rem 0.9rem;margin-bottom:5px;display:flex;justify-content:space-between'><span style='color:#aaa;font-size:0.78rem'>Registros totales</span><span style='color:#fff;font-weight:700'>" + str(stats['total']) + "</span></div>", unsafe_allow_html=True)
    st.markdown("<div style='background:#1a1d2e;border-radius:8px;padding:0.6rem 0.9rem;margin-bottom:5px;display:flex;justify-content:space-between'><span style='color:#aaa;font-size:0.78rem'>Aplican</span><span style='color:#4ade80;font-weight:700'>" + str(stats['aplican']) + "</span></div>", unsafe_allow_html=True)
    if CSV_CONSULTAS.exists():
        st.markdown("<div style='background:#1a1d2e;border-radius:8px;padding:0.6rem 0.9rem;margin-bottom:5px;display:flex;justify-content:space-between'><span style='color:#aaa;font-size:0.78rem'>Consultas totales</span><span style='color:#60a5fa;font-weight:700'>" + str(len(pd.read_csv(CSV_CONSULTAS))) + "</span></div>", unsafe_allow_html=True)
    if st.button("Recargar base", use_container_width=True):
        get_motor.clear(); st.cache_resource.clear(); st.rerun()

PAISES   = ["Colombia","Mexico","Argentina","Chile","Peru","Ecuador","Venezuela","Bolivia","Espana","Estados Unidos","Otro"]
PAISES_B = ["Colombia","Mexico","Argentina","Chile","Peru","Ecuador","Venezuela","Espana","Otro"]
NIVELES  = ["universitario","maestria","especializacion","doctorado","tecnologo","bachillerato"]


if pagina == "Validar titulo":
    st.header("Validar titulo academico")
    if pendientes_count > 0:
        st.warning("El Back tiene " + str(pendientes_count) + " solicitud(es) pendiente(s) por aprobar.")

    tab_consultar, tab_solicitar = st.tabs(["Consultar titulo", "Solicitar validacion al Back"])

    # ---- PESTAÃA 1: CONSULTAR ----
    with tab_consultar:
        st.info("Ingresa el titulo y universidad para verificar si ya existe una decision del Back.")
        c1, c2 = st.columns(2)
        busq_titulo = c1.text_input("Nombre del titulo", placeholder="Ej: TecnÃ³logo en Mercadotecnia", key="busq_t")
        busq_univ   = c2.text_input("Universidad (opcional)", placeholder="Ej: Universidad de Santander", key="busq_u")

        if st.button("Consultar", use_container_width=True, key="btn_consultar"):
            if not busq_titulo.strip():
                st.error("Ingresa el nombre del titulo.")
            else:

                resultado_encontrado = False

                # Buscar en decisiones_back.csv
                if CSV_DECISIONES.exists():
                    df_dec = pd.read_csv(CSV_DECISIONES)
                    if not df_dec.empty and "nombre_titulo" in df_dec.columns:
                        # Calcular similitud para cada registro
                        df_dec["_sim_t"] = df_dec["nombre_titulo"].astype(str).apply(lambda x: similar(x, busq_titulo.strip()))
                        df_dec["_sim_u"] = df_dec["universidad"].astype(str).apply(lambda x: similar(x, busq_univ.strip())) if busq_univ.strip() else pd.Series([1.0]*len(df_dec))
                        # Umbral: titulo >70% similar
                        df_match = df_dec[(df_dec["_sim_t"] >= 0.70)].copy()
                        # Si hay universidad, filtrar tambiÃ©n por similitud de universidad >60%
                        if busq_univ.strip():
                            df_match = df_match[df_match["_sim_u"] >= 0.60]
                        df_match = df_match.sort_values("_sim_t", ascending=False)
                        if not df_match.empty:
                            resultado_encontrado = True
                            st.success("Se encontraron " + str(len(df_match)) + " decision(es) del Back para este titulo:")
                            for _, row in df_match.iterrows():
                                aplica = str(row.get("decision_aplica","")).lower() in ["true","1","si"]
                                nivel  = str(row.get("nivel_confirmado",""))
                                motivo = str(row.get("motivo",""))
                                revisor = str(row.get("revisor",""))
                                univ_r  = str(row.get("universidad",""))
                                sim_pct = int(row["_sim_t"]*100)
                                with st.container():
                                    st.markdown("---")
                                    col_r1, col_r2 = st.columns([2,1])
                                    with col_r1:
                                        st.write("Titulo registrado: **" + str(row.get("nombre_titulo","")) + "**")
                                        if univ_r and univ_r != "nan": st.write("Universidad: " + univ_r)
                                        if motivo and motivo != "nan": st.info("Observacion del Back: " + motivo)
                                        if revisor and revisor != "nan": st.caption("Revisado por: " + revisor)
                                    with col_r2:
                                        if aplica:
                                            st.success("APLICA")
                                            if nivel and nivel != "nan": st.write("Nivel: " + nivel.capitalize())
                                        else:
                                            st.error("NO APLICA")
                                        st.caption("Similitud: " + str(sim_pct) + "%")
                                registrar_consulta(busq_titulo.strip(), "Aplica" if aplica else "No aplica", nivel, 0)

                # Buscar si esta PENDIENTE en el Back
                if not resultado_encontrado:
                    df_p_check, _ = gh_get_pendientes()
                    if not df_p_check.empty and "nombre_titulo" in df_p_check.columns:
                        df_p_check["_sim"] = df_p_check["nombre_titulo"].astype(str).apply(lambda x: similar(x, busq_titulo.strip()))
                        df_pend_match = df_p_check[(df_p_check["_sim"]>=0.70) & (df_p_check["estado"].astype(str).str.upper()=="PENDIENTE")]
                        if not df_pend_match.empty:
                            resultado_encontrado = True
                            st.warning("Este titulo esta pendiente de decision del Back. El equipo lo revisara pronto.")
                            for _, rp in df_pend_match.iterrows():
                                st.caption("Titulo en espera: " + str(rp.get("nombre_titulo","")) + " | Enviado: " + str(rp.get("fecha","")))

                if not resultado_encontrado:
                    st.info("No se encontro decision previa para este titulo. Ve a la pestana **Solicitar validacion al Back** para enviarlo.")

    # ---- PESTAÃA 2: SOLICITAR ----
    with tab_solicitar:
        st.warning("Usa esta pestana solo si la consulta en la pestana anterior no arrojÃ³ resultados.")
        with st.form("form_validar", clear_on_submit=True):
            titulo      = st.text_input("Nombre del titulo *", placeholder="Ej: Administracion de Empresas")
            col1, col2  = st.columns(2)
            universidad = col1.text_input("Universidad", placeholder="Ej: Universidad Nacional")
            pais        = col2.selectbox("Pais", PAISES)
            col3, col4  = st.columns(2)
            nivel_manual = col3.selectbox("Nivel academico (opcional)", ["-- Seleccionar --"] + NIVELES)
            titular      = col4.text_input("Nombre del titular (opcional)")
            submitted    = st.form_submit_button("Enviar al Back para aprobacion", use_container_width=True, type="primary")
        if submitted:
            if not titulo.strip():
                st.error("Por favor ingresa el nombre del titulo.")
            else:
                nivel_enviar = nivel_manual if nivel_manual != "-- Seleccionar --" else "universitario"
                pais_enviar  = pais if pais in PAISES_B else "Otro"
                nuevo_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                df_p, sha_p = gh_get_pendientes()
                nueva = pd.DataFrame([{
                    "id": nuevo_id,
                    "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "hora":  datetime.now(timezone.utc).strftime("%H:%M:%S"),
                    "nombre_titulo":   titulo.strip(),
                    "universidad":     universidad.strip(),
                    "pais":            pais_enviar,
                    "nivel_detectado": nivel_enviar,
                    "titular":         titular.strip(),
                    "texto_diploma":   "",
                    "estado":          "PENDIENTE",
                    "revisor": "", "decision": "", "nivel_confirmado": "", "motivo": ""
                }])
                df_p = pd.concat([df_p, nueva], ignore_index=True)
                ok, err = gh_save_pendientes(df_p, sha_p, "New request: " + titulo.strip())
                if ok:
                    registrar_consulta(titulo.strip(), "Enviado al Back", nivel_enviar, 0)
                    st.success("Solicitud enviada al Back correctamente.")
                    st.info("El equipo Back recibira la alerta y tomara la decision.")
                else:
                    st.error("Error al enviar: " + str(err))


elif pagina == "Ingresar diploma":
    st.header("Ingresar diploma")
    if not secrets_ok:
        st.error("Para usar esta funcion configura GITHUB_TOKEN en Streamlit Secrets. Ve a Manage app > Settings > Secrets.")
        st.code('GITHUB_TOKEN = "ghp_tu_token_aqui"\nGITHUB_REPO = "usanjosedocumentos-svg/validatitulos"', language="toml")
    else:
        if pendientes_count > 0:
            st.warning("Hay " + str(pendientes_count) + " diploma(s) pendiente(s) esperando decision del Back.")
        st.info("Pega el texto del diploma. El sistema extrae los datos y los envia al Back para aprobacion.")
        texto_diploma = st.text_area("Texto del diploma *", height=160,
            placeholder="Pega aqui el texto del diploma...\nEj: UNIVERSIDAD NACIONAL\nOTORGA EL TITULO DE INGENIERO DE SISTEMAS A JUAN PEREZ")
        if texto_diploma.strip():
            titulo_d, univ_d, pais_d, nivel_d, titular_d = extraer_datos_diploma(texto_diploma)
            st.markdown("---")
            st.subheader("Datos detectados -- Revisa y corrige si es necesario")
            col1, col2 = st.columns(2)
            titulo_f = col1.text_input("Nombre del titulo *", value=titulo_d, key="d_titulo")
            univ_f   = col2.text_input("Universidad", value=univ_d, key="d_univ")
            col3, col4 = st.columns(2)
            pais_f  = col3.selectbox("Pais",  PAISES,  index=(PAISES.index(pais_d)  if pais_d  in PAISES  else 0), key="d_pais")
            nivel_f = col4.selectbox("Nivel", NIVELES, index=(NIVELES.index(nivel_d) if nivel_d in NIVELES else 0), key="d_nivel")
            titular_f = st.text_input("Nombre del titular", value=titular_d, key="d_titular")
            st.markdown("---")
            if st.button("Enviar al Back para aprobacion", use_container_width=True, type="primary"):
                if not titulo_f.strip(): st.error("El campo Titulo es obligatorio.")
                else:
                    nuevo_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                    df_p, sha_p = gh_get_pendientes()
                    nueva = pd.DataFrame([{"id":nuevo_id,"fecha":datetime.now(timezone.utc).strftime("%Y-%m-%d"),"hora":datetime.now(timezone.utc).strftime("%H:%M:%S"),"nombre_titulo":titulo_f.strip(),"universidad":univ_f.strip(),"pais":pais_f,"nivel_detectado":nivel_f,"titular":titular_f.strip(),"texto_diploma":texto_diploma[:400],"estado":"PENDIENTE","revisor":"","decision":"","nivel_confirmado":"","motivo":""}])
                    df_p = pd.concat([df_p, nueva], ignore_index=True)
                    ok, err = gh_save_pendientes(df_p, sha_p, "Add pending: " + titulo_f.strip())
                    if ok: st.success("Enviado al Back correctamente."); st.balloons(); st.rerun()
                    else:  st.error("Error al guardar: " + str(err))
        else:
            st.markdown("**Como funciona:**\n1. Pega el texto del diploma\n2. Revisa los datos detectados\n3. Clic en Enviar al Back\n4. El Back ve la alerta y aprueba o rechaza")


elif pagina == "Revision Back":
    st.header("Revision manual -- equipo Back")
    if not secrets_ok:
        st.warning("Configura GITHUB_TOKEN en Streamlit Secrets para usar los pendientes.")
    elif pendientes_count > 0:
        st.error("ATENCION: Tienes " + str(pendientes_count) + " diploma(s) PENDIENTE(S) esperando tu decision.")

    tab_pendientes, tab_nueva, tab_editar = st.tabs(["PENDIENTES (" + str(pendientes_count) + ")", "Nueva decision", "Editar decision"])

    with tab_pendientes:
        if not secrets_ok:
            st.info("Configura GITHUB_TOKEN en Secrets para ver pendientes.")
        else:
            df_p, sha_p = gh_get_pendientes()
            df_solo = df_p[df_p["estado"].astype(str).str.upper()=="PENDIENTE"] if not df_p.empty and "estado" in df_p.columns else pd.DataFrame()
            if df_solo.empty: st.info("No hay diplomas pendientes.")
            else:
                st.markdown("**" + str(len(df_solo)) + " diploma(s) esperando tu decision:**")
                for _, row in df_solo.iterrows():
                    row_id   = str(row.get("id",""))
                    titulo_p = str(row.get("nombre_titulo",""))
                    fecha_p  = str(row.get("fecha","")) + " " + str(row.get("hora",""))
                    with st.expander("PENDIENTE -- " + titulo_p + "   |   " + fecha_p, expanded=True):
                        col_i, col_f = st.columns([1,1])
                        with col_i:
                            st.markdown("**Datos del diploma:**")
                            st.write("Titulo: " + titulo_p)
                            st.write("Universidad: " + str(row.get("universidad","")))
                            st.write("Pais: " + str(row.get("pais","")))
                            st.write("Nivel detectado: " + str(row.get("nivel_detectado","")))
                            st.write("Titular: " + str(row.get("titular","")))
                            txt = str(row.get("texto_diploma",""))
                            if txt: st.markdown("**Texto original:**"); st.caption(txt[:300])
                        with col_f:
                            st.markdown("**Tu decision:**")
                            p_aplica  = st.radio("Aplica?", ["Si, aplica","No aplica"], key="apl_"+row_id)
                            nv_act    = str(row.get("nivel_detectado","universitario"))
                            p_nivel   = st.selectbox("Confirmar nivel", NIVELES, index=(NIVELES.index(nv_act) if nv_act in NIVELES else 0), key="niv_"+row_id)
                            p_revisor = st.text_input("Tu nombre", key="rev_"+row_id, placeholder="Ej: Ana Gomez")
                            p_motivo  = st.text_area("Observaciones", key="mot_"+row_id, height=80)
                            p_incorp  = st.checkbox("Incorporar a la base", value=True, key="inc_"+row_id)
                            ca, cr    = st.columns(2)
                            aprobar   = ca.button("Aprobar",  key="ok_"+row_id, use_container_width=True, type="primary")
                            rechazar  = cr.button("Rechazar", key="no_"+row_id, use_container_width=True)
                            if aprobar or rechazar:
                                aplica_bool = ("Si" in p_aplica) and aprobar
                                idx = df_p[df_p["id"].astype(str)==row_id].index
                                if len(idx)>0:
                                    i = idx[0]
                                    df_p.loc[i,"estado"]           = "APROBADO" if aprobar else "RECHAZADO"
                                    df_p.loc[i,"decision"]         = "Aplica" if aplica_bool else "No aplica"
                                    df_p.loc[i,"nivel_confirmado"] = p_nivel
                                    df_p.loc[i,"revisor"]          = p_revisor.strip()
                                    df_p.loc[i,"motivo"]           = p_motivo.strip()
                                    ok, err = gh_save_pendientes(df_p, sha_p, ("Approve" if aprobar else "Reject")+": "+titulo_p)
                                    if ok:
                                        motor.guardar_decision(titulo=titulo_p, universidad=str(row.get("universidad","")), pais=str(row.get("pais","Colombia")), aplica=aplica_bool, nivel=p_nivel, revisor=p_revisor.strip(), motivo=p_motivo.strip(), incorporar=p_incorp)
                                        get_motor.clear()
                                        st.success("Diploma " + ("APROBADO" if aprobar else "RECHAZADO") + ".")
                                        st.rerun()
                                    else: st.error("Error al guardar: "+str(err))

    with tab_nueva:
        st.warning("Solo para el equipo Back.")
        prefill = st.session_state.get("back_titulo","")
        ult = st.session_state.get("ultimo_resultado",{})
        with st.form("form_back", clear_on_submit=True):
            b_titulo  = st.text_input("Titulo revisado *", value=prefill)
            bc1, bc2  = st.columns(2)
            b_univ    = bc1.text_input("Universidad", value=ult.get("universidad",""))
            b_pais    = bc2.selectbox("Pais", PAISES_B, index=(PAISES_B.index(ult.get("pais","Colombia")) if ult.get("pais","Colombia") in PAISES_B else 0))
            bd1, bd2  = st.columns(2)
            b_aplica  = bd1.radio("Este titulo aplica?", ["Si, aplica","No aplica"])
            b_nivel   = bd2.selectbox("Nivel academico confirmado", NIVELES)
            b_revisor = st.text_input("Nombre del revisor")
            b_motivo  = st.text_area("Observaciones", height=80)
            b_incorp  = st.checkbox("Incorporar a la base de conocimiento", value=True)
            b_submit  = st.form_submit_button("Guardar decision Back", use_container_width=True)
        if b_submit:
            if not b_titulo.strip(): st.error("El campo Titulo es obligatorio.")
            elif b_incorp and existe_duplicado(b_titulo.strip(), b_nivel): st.error("DUPLICADO: '"+b_titulo.strip()+"' ya existe con nivel '"+b_nivel+"'.")
            else:
                aplica_bool = "Si" in b_aplica
                motor.guardar_decision(titulo=b_titulo.strip(), universidad=b_univ.strip(), pais=b_pais, aplica=aplica_bool, nivel=b_nivel, revisor=b_revisor.strip(), motivo=b_motivo.strip(), incorporar=b_incorp)
                get_motor.clear()
                for k in ("back_titulo","ultimo_resultado"): st.session_state.pop(k,None)
                st.success("Guardado: '"+b_titulo.strip()+"' -> "+("Aplica" if aplica_bool else "No aplica"))

    with tab_editar:
        if not CSV_DECISIONES.exists(): st.warning("Aun no hay decisiones registradas.")
        else:
            df_dec = pd.read_csv(CSV_DECISIONES)
            if df_dec.empty: st.info("No hay decisiones para editar.")
            else:
                buscar_edit = st.text_input("Buscar titulo", placeholder="Escribe parte del nombre...", key="buscar_editar")
                if buscar_edit.strip():
                    df_f2 = df_dec[df_dec["nombre_titulo"].astype(str).str.contains(buscar_edit.strip(),case=False,na=False)]
                    if df_f2.empty: st.warning("No se encontraron registros.")
                    else:
                        st.dataframe(df_f2[["nombre_titulo","nivel_confirmado","decision_aplica","revisor","motivo"]].reset_index(), use_container_width=True, hide_index=True)
                        opciones = [str(i)+" - "+str(df_dec.loc[i,"nombre_titulo"]) for i in df_f2.index.tolist()]
                        sel = st.selectbox("Selecciona el registro", opciones, key="sel_editar")
                        if sel:
                            idx_sel = int(sel.split(" - ")[0]); row = df_dec.loc[idx_sel]
                            with st.form("form_editar", clear_on_submit=False):
                                e_titulo = st.text_input("Titulo *", value=str(row.get("nombre_titulo","")))
                                ec1,ec2  = st.columns(2)
                                e_univ   = ec1.text_input("Universidad", value=str(row.get("universidad","")))
                                pa = str(row.get("pais","Colombia"))
                                e_pais   = ec2.selectbox("Pais", PAISES_B, index=(PAISES_B.index(pa) if pa in PAISES_B else 0), key="edit_pais")
                                ed1,ed2  = st.columns(2)
                                apl_act  = str(row.get("decision_aplica","")).lower() in ["true","si","1"]
                                e_aplica = ed1.radio("Aplica?", ["Si, aplica","No aplica"], index=(0 if apl_act else 1), key="edit_aplica")
                                nv_act   = str(row.get("nivel_confirmado","universitario"))
                                e_nivel  = ed2.selectbox("Nivel", NIVELES, index=(NIVELES.index(nv_act) if nv_act in NIVELES else 0), key="edit_nivel")
                                e_revisor = st.text_input("Revisor", value=str(row.get("revisor","")))
                                e_motivo  = st.text_area("Motivo", value=str(row.get("motivo","")), height=80)
                                e_submit  = st.form_submit_button("Guardar cambios", use_container_width=True)
                            if e_submit:
                                if not e_titulo.strip(): st.error("El titulo no puede estar vacio.")
                                else:
                                    df_dec.loc[idx_sel,"nombre_titulo"]=e_titulo.strip(); df_dec.loc[idx_sel,"universidad"]=e_univ.strip()
                                    df_dec.loc[idx_sel,"pais"]=e_pais; df_dec.loc[idx_sel,"decision_aplica"]="Si" in e_aplica
                                    df_dec.loc[idx_sel,"nivel_confirmado"]=e_nivel; df_dec.loc[idx_sel,"revisor"]=e_revisor.strip(); df_dec.loc[idx_sel,"motivo"]=e_motivo.strip()
                                    df_dec.to_csv(CSV_DECISIONES,index=False); get_motor.clear(); st.success("Registro actualizado."); st.rerun()
                else: st.caption("Escribe al menos una letra para buscar.")


elif pagina == "Cargar datos":
    st.header("Cargar base historica de titulos")
    archivo = st.file_uploader("Selecciona tu archivo CSV", type=["csv"], key="csv_uploader")
    if archivo:
        try:
            df_nuevo = pd.read_csv(archivo)
            st.dataframe(df_nuevo.head(8), use_container_width=True, hide_index=True)
            cols_falt = {"nombre_titulo","aplica","nivel"} - set(df_nuevo.columns)
            if cols_falt: st.error("Faltan columnas: "+", ".join(cols_falt))
            else:
                df_nuevo["_key"] = df_nuevo["nombre_titulo"].astype(str).str.lower().str.strip()+"||"+df_nuevo["nivel"].astype(str).str.lower().str.strip()
                dupes_int = df_nuevo[df_nuevo.duplicated(subset=["_key"],keep=False)][["nombre_titulo","nivel"]].drop_duplicates()
                dupes_ext = pd.DataFrame()
                if CSV_TITULOS.exists():
                    df_base = pd.read_csv(CSV_TITULOS); df_base["_key"]=df_base["nombre_titulo"].astype(str).str.lower().str.strip()+"||"+df_base["nivel"].astype(str).str.lower().str.strip()
                    dupes_ext = df_nuevo[df_nuevo["_key"].isin(df_base["_key"])][["nombre_titulo","nivel"]].drop_duplicates()
                hay_dupes = len(dupes_int)>0 or len(dupes_ext)>0
                if hay_dupes:
                    st.warning("Duplicados detectados.")
                    ca,cb=st.columns(2)
                    if len(dupes_int)>0: ca.markdown("**En el archivo:**"); ca.dataframe(dupes_int.reset_index(drop=True),use_container_width=True,hide_index=True)
                    if len(dupes_ext)>0: cb.markdown("**Ya en la base:**"); cb.dataframe(dupes_ext.reset_index(drop=True),use_container_width=True,hide_index=True)
                    opcion = st.radio("Que hacer?",["Omitir (conservar existentes)","Reemplazar (actualizar con nuevos)","Cancelar importacion"],index=0)
                else: st.success("Sin duplicados -- "+str(len(df_nuevo))+" titulos listos."); opcion="Omitir (conservar existentes)"
                if st.button("Confirmar e importar",use_container_width=True,disabled="Cancelar" in opcion):
                    for col in ["universidad","pais","semestre"]:
                        if col not in df_nuevo.columns: df_nuevo[col]="" if col!="semestre" else 5
                    df_listo = df_nuevo.drop(columns=["_key"],errors="ignore")
                    if CSV_TITULOS.exists():
                        df_merged=pd.concat([pd.read_csv(CSV_TITULOS),df_listo],ignore_index=True)
                        df_merged.drop_duplicates(subset=["nombre_titulo","nivel"],keep=("first" if "Omitir" in opcion else "last"),inplace=True)
                    else: df_merged=df_listo; df_merged.drop_duplicates(subset=["nombre_titulo","nivel"],keep="last",inplace=True)
                    df_merged.to_csv(CSV_TITULOS,index=False); get_motor.clear()
                    st.success("Importacion completada. Base: "+str(len(df_merged))+" registros."); st.balloons()
        except Exception as e: st.error("Error: "+str(e))
    st.markdown("---")
    plantilla = pd.DataFrame([{"nombre_titulo":"Administracion de Empresas","universidad":"Universidad Nacional","pais":"Colombia","aplica":"","nivel":"universitario","semestre":5}])
    st.download_button("Descargar plantilla CSV",data=plantilla.to_csv(index=False).encode("utf-8"),file_name="plantilla_titulos.csv",mime="text/csv",use_container_width=True)


elif pagina == "Historial":
    st.header("Historial de decisiones Back")
    if not CSV_DECISIONES.exists(): st.info("Aun no hay decisiones registradas.")
    else:
        df = pd.read_csv(CSV_DECISIONES)
        if df.empty: st.info("El historial esta vacio.")
        else:
            total=len(df); aplican=int((df["decision_aplica"].astype(str).str.lower().isin(["true","si","1"])).sum())
            c1,c2,c3=st.columns(3); c1.metric("Total",total); c2.metric("Aprobadas",aplican); c3.metric("Rechazadas",total-aplican)
            st.markdown("---")
            buscar=st.text_input("Buscar titulo",placeholder="Filtrar...")
            _,mf2=st.columns([2,1]); filtro=mf2.selectbox("Mostrar",["Todas","Solo aprobadas","Solo rechazadas"])
            df_show=df.copy()
            if buscar: df_show=df_show[df_show["nombre_titulo"].astype(str).str.contains(buscar,case=False,na=False)]
            if filtro=="Solo aprobadas": df_show=df_show[df_show["decision_aplica"].astype(str).str.lower().isin(["true","si","1"])]
            elif filtro=="Solo rechazadas": df_show=df_show[~df_show["decision_aplica"].astype(str).str.lower().isin(["true","si","1"])]
            st.dataframe(df_show.style.set_properties(**{"color":"black","font-size":"14px"}),use_container_width=True,hide_index=True,height=400)
            d1,d2=st.columns(2)
            d1.download_button("Descargar decisiones CSV",data=df.to_csv(index=False).encode("utf-8"),file_name="decisiones_back.csv",mime="text/csv",use_container_width=True)
            if CSV_TITULOS.exists(): d2.download_button("Descargar base completa CSV",data=pd.read_csv(CSV_TITULOS).to_csv(index=False).encode("utf-8"),file_name="titulos_historicos.csv",mime="text/csv",use_container_width=True)


elif pagina == "Dashboard":
    st.header("Dashboard de consultas")
    if not CSV_CONSULTAS.exists() or pd.read_csv(CSV_CONSULTAS).empty: st.info("Aun no hay consultas registradas.")
    else:
        df_c=pd.read_csv(CSV_CONSULTAS); df_c["fecha"]=pd.to_datetime(df_c["fecha"],errors="coerce")
        f1,f2=st.columns(2)
        fecha_min=df_c["fecha"].min().date() if not df_c["fecha"].isnull().all() else None
        fecha_max=df_c["fecha"].max().date() if not df_c["fecha"].isnull().all() else None
        f_desde=f1.date_input("Desde",value=fecha_min); f_hasta=f2.date_input("Hasta",value=fecha_max)
        df_f=df_c[(df_c["fecha"].dt.date>=f_desde)&(df_c["fecha"].dt.date<=f_hasta)]
        st.markdown("---")
        m1,m2,m3,m4,m5=st.columns(5)
        m1.metric("Total",len(df_f)); m2.metric("Aplican",int((df_f["resultado"].astype(str).str.lower()=="aplica").sum()))
        m3.metric("No aplican",int((df_f["resultado"].astype(str).str.lower()=="no aplica").sum()))
        m4.metric("Requieren revision",int((df_f["resultado"].astype(str).str.lower()=="requiere revision").sum()))
        m5.metric("Titulos unicos",df_f["nombre_titulo"].nunique())
        st.markdown("---")
        col_a,col_b=st.columns(2)
        with col_a:
            st.subheader("Top 10 mas consultados")
            top=df_f.groupby("nombre_titulo").size().reset_index(name="consultas").sort_values("consultas",ascending=False).head(10)
            if not top.empty: st.dataframe(top.style.set_properties(**{"color":"black","font-size":"14px"}).bar(subset=["consultas"],color="#60a5fa"),use_container_width=True,hide_index=True,height=370)
        with col_b:
            st.subheader("Por resultado")
            dist=df_f["resultado"].value_counts().reset_index(); dist.columns=["resultado","cantidad"]
            st.dataframe(dist.style.set_properties(**{"color":"black","font-size":"14px"}),use_container_width=True,hide_index=True)
            st.subheader("Por nivel")
            niv_d=df_f[df_f["nivel"].astype(str).str.strip()!=""]["nivel"].value_counts().reset_index(); niv_d.columns=["nivel","consultas"]
            if not niv_d.empty: st.dataframe(niv_d.style.set_properties(**{"color":"black","font-size":"14px"}),use_container_width=True,hide_index=True)
        st.markdown("---")
        st.subheader("Consultas por dia")
        por_dia=df_f.groupby("fecha").size().reset_index(name="consultas"); por_dia["fecha"]=por_dia["fecha"].dt.strftime("%Y-%m-%d")
        if not por_dia.empty: st.bar_chart(por_dia.set_index("fecha")["consultas"])
        with st.expander("Ver log completo"):
            st.dataframe(df_f.sort_values("fecha",ascending=False).style.set_properties(**{"color":"black","font-size":"13px"}),use_container_width=True,hide_index=True,height=350)
            st.download_button("Descargar log CSV",data=df_f.to_csv(index=False).encode("utf-8"),file_name="consultas_log.csv",mime="text/csv",use_container_width=True)

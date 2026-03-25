"""
app.py - ValidaTitulos
Toda la persistencia va a GitHub via API. Sin archivos locales para datos criticos.
"""
from pathlib import Path
from datetime import datetime, timezone
import base64, json, io, urllib.request, urllib.error, unicodedata, re
import pandas as pd
import streamlit as st
from validador import ValidadorCSV, SEMESTRE_POR_NIVEL, CSV_DECISIONES, CSV_TITULOS

st.set_page_config(page_title="ValidaTitulos", page_icon=":mortar_board:", layout="wide", initial_sidebar_state="expanded")

CSV_CONSULTAS = Path("consultas_log.csv")
PAISES   = ["Colombia","Mexico","Argentina","Chile","Peru","Ecuador","Venezuela","Bolivia","Espana","Estados Unidos","Otro"]
PAISES_B = ["Colombia","Mexico","Argentina","Chile","Peru","Ecuador","Venezuela","Espana","Otro"]
NIVELES  = ["universitario","maestria","especializacion","doctorado","tecnologo","tecnico","bachillerato"]

# Diccionario de palabras truncadas por encoding roto
_FIX_WORDS = {
    'TCNICO':'TECNICO','TCNICA':'TECNICA','TECNLOGO':'TECNOLOGO','TECNLOGA':'TECNOLOGO',
    'ADMINISTRACIN':'ADMINISTRACION','ESPAOL':'ESPANOL','PRODUCCIN':'PRODUCCION',
    'GESTINDE':'GESTION DE','INTEGRADADE':'INTEGRADA DE','LICENCIACIN':'LICENCIACION',
}

def clean_text(s):
    """Elimina caracteres no-ASCII y corrige palabras truncadas por encoding roto."""
    if not s: return ''
    # Eliminar chars no imprimibles y no-ASCII
    import re as _re
    r = _re.sub(r'[^\x20-\x7E]', '', str(s))
    r = _re.sub(r'\s+', ' ', r).strip().strip('"').strip("'")
    # Corregir palabras truncadas
    words = r.split()
    words = [_FIX_WORDS.get(w.upper(), w) for w in words]
    return ' '.join(words)

def get_gh_config():
    try:
        return st.secrets["GITHUB_TOKEN"], st.secrets.get("GITHUB_REPO","usanjosedocumentos-svg/validatitulos")
    except Exception:
        return "", "usanjosedocumentos-svg/validatitulos"

def _gh_read(filename):
    token, repo = get_gh_config()
    if not token: return pd.DataFrame(), None
    url = "https://api.github.com/repos/" + repo + "/contents/" + filename
    req = urllib.request.Request(url, headers={"Authorization":"token "+token,"Accept":"application/vnd.github.v3+json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode())
            content = base64.b64decode(d["content"].replace("\n","")).decode("utf-8")
            return pd.read_csv(io.StringIO(content)), d["sha"]
    except Exception:
        return pd.DataFrame(), None

def _gh_write(filename, df, sha, mensaje):
    token, repo = get_gh_config()
    if not token: return False, "Sin GITHUB_TOKEN en Secrets"
    url = "https://api.github.com/repos/" + repo + "/contents/" + filename
    csv_str = df.to_csv(index=False)
    body = {"message": mensaje, "content": base64.b64encode(csv_str.encode()).decode(), "branch": "main"}
    if sha: body["sha"] = sha
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="PUT",
        headers={"Authorization":"token "+token,"Accept":"application/vnd.github.v3+json","Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15): return True, None
    except urllib.error.HTTPError as e: return False, str(e.code)+": "+e.read().decode()[:200]
    except Exception as e: return False, str(e)

@st.cache_data(ttl=30)
def leer_decisiones():
    df, sha = _gh_read("decisiones_back.csv")
    if df.empty:
        df = pd.DataFrame(columns=["nombre_titulo","universidad","pais","nivel_confirmado","decision_aplica","revisor","motivo","fecha","incorporar","semestre"])
    return df, sha

@st.cache_data(ttl=30)
def leer_pendientes():
    df, sha = _gh_read("pendientes_back.csv")
    if df.empty:
        df = pd.DataFrame(columns=["id","fecha","hora","nombre_titulo","universidad","pais","nivel_detectado","titular","texto_diploma","estado","revisor","decision","nivel_confirmado","motivo"])
    return df, sha

def contar_pendientes():
    df, _ = leer_pendientes()
    if df.empty or "estado" not in df.columns: return 0
    return int((df["estado"].astype(str).str.upper() == "PENDIENTE").sum())

def guardar_decision(titulo, universidad, pais, nivel, aplica, revisor, motivo, incorporar=True):
    df, sha = leer_decisiones()
    titulo     = clean_text(titulo)
    universidad = clean_text(universidad)
    motivo      = clean_text(motivo)
    revisor     = clean_text(revisor)
    nueva = pd.DataFrame([{"nombre_titulo":titulo,"universidad":universidad,"pais":pais,"nivel_confirmado":nivel,"decision_aplica":str(aplica),"revisor":revisor,"motivo":motivo,"fecha":datetime.now(timezone.utc).strftime("%Y-%m-%d"),"incorporar":str(incorporar).lower(),"semestre":SEMESTRE_POR_NIVEL.get(nivel,"")}])
    df = pd.concat([df, nueva], ignore_index=True)
    ok, err = _gh_write("decisiones_back.csv", df, sha, "Add decision: "+titulo[:50])
    leer_decisiones.clear()
    return ok, err

def guardar_pendiente(titulo, universidad, pais, nivel, titular, texto):
    df, sha = leer_pendientes()
    titulo     = clean_text(titulo)
    universidad = clean_text(universidad)
    nid = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    nueva = pd.DataFrame([{"id":nid,"fecha":datetime.now(timezone.utc).strftime("%Y-%m-%d"),"hora":datetime.now(timezone.utc).strftime("%H:%M:%S"),"nombre_titulo":titulo,"universidad":universidad,"pais":pais,"nivel_detectado":nivel,"titular":titular,"texto_diploma":texto[:400] if texto else "","estado":"PENDIENTE","revisor":"","decision":"","nivel_confirmado":"","motivo":""}])
    df = pd.concat([df, nueva], ignore_index=True)
    ok, err = _gh_write("pendientes_back.csv", df, sha, "Add pending: "+titulo[:50])
    leer_pendientes.clear()
    return ok, err, nid

def actualizar_pendiente(row_id, estado, nivel, revisor, motivo, decision):
    df, sha = leer_pendientes()
    idx = df[df["id"].astype(str) == str(row_id)].index
    if len(idx) == 0: return False, "ID no encontrado"
    i = idx[0]
    df.loc[i,"estado"] = estado
    df.loc[i,"nivel_confirmado"] = nivel
    df.loc[i,"revisor"] = revisor
    df.loc[i,"motivo"] = motivo
    df.loc[i,"decision"] = decision
    ok, err = _gh_write("pendientes_back.csv", df, sha, estado+": "+str(df.loc[i,"nombre_titulo"])[:40])
    leer_pendientes.clear()
    return ok, err

def registrar_consulta(titulo, resultado, nivel, confianza):
    fila = {"fecha":datetime.now(timezone.utc).strftime("%Y-%m-%d"),"hora":datetime.now(timezone.utc).strftime("%H:%M:%S"),"nombre_titulo":titulo,"resultado":resultado,"nivel":nivel or "","confianza_pct":confianza}
    df = pd.concat([pd.read_csv(CSV_CONSULTAS), pd.DataFrame([fila])], ignore_index=True) if CSV_CONSULTAS.exists() else pd.DataFrame([fila])
    df.to_csv(CSV_CONSULTAS, index=False)

def normalizar(s):
    s = unicodedata.normalize("NFD", str(s).lower().strip())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def similar(a, b):
    na, nb = normalizar(a), normalizar(b)
    if na == nb: return 1.0
    if na in nb or nb in na: return 0.9
    wa = [w for w in na.split() if len(w) > 2]
    wb = [w for w in nb.split() if len(w) > 2]
    if not wa or not wb: return 0.0
    sb = set(wb)
    return sum(1 for w in wa if w in sb) / max(len(wa), len(wb))

def buscar_decision(titulo, universidad=""):
    df, _ = leer_decisiones()
    if df.empty or "nombre_titulo" not in df.columns: return None
    df = df.copy()
    df["_sim_t"] = df["nombre_titulo"].astype(str).apply(lambda x: similar(x, titulo))
    if universidad.strip():
        df["_sim_u"] = df["universidad"].astype(str).apply(lambda x: similar(x, universidad))
        matches = df[(df["_sim_t"] >= 0.72) & (df["_sim_u"] >= 0.60)]
    else:
        matches = df[df["_sim_t"] >= 0.72]
    if matches.empty: return None
    return matches.sort_values("_sim_t", ascending=False).iloc[0]

def buscar_pendiente_activo(titulo):
    df, _ = leer_pendientes()
    if df.empty or "nombre_titulo" not in df.columns: return None
    df = df.copy()
    df["_sim"] = df["nombre_titulo"].astype(str).apply(lambda x: similar(x, titulo))
    matches = df[(df["_sim"] >= 0.72) & (df["estado"].astype(str).str.upper() == "PENDIENTE")]
    if matches.empty: return None
    return matches.sort_values("_sim", ascending=False).iloc[0]

def extraer_datos_diploma(texto):
    lineas = [l.strip() for l in texto.strip().split("\n") if l.strip()]
    tl = texto.lower()
    kn = {"doctorado":["doctorado","doctor en","phd"],"maestria":["maestria","master","magister"],"especializacion":["especializacion","especialista en"],"tecnologo":["tecnologo","tecnologia en"],"tecnico":["tecnico laboral","tecnico en","formacion tecnica"],"bachillerato":["bachiller","bachillerato"],"universitario":["ingeniero","ingeniera","administrador","licenciado","arquitecto","contador","medico","abogado","psicologo","economista"]}
    nivel = "universitario"
    for nv, kws in kn.items():
        if any(k in tl for k in kws): nivel = nv; break
    titulo = ""
    for i, linea in enumerate(lineas):
        if any(t in linea.lower() for t in ["titulo de","otorga el titulo","grado de","programa de","titulo en"]):
            if i + 1 < len(lineas): titulo = lineas[i+1]; break
    if not titulo:
        for nv, kws in kn.items():
            for linea in lineas:
                if any(k in linea.lower() for k in kws) and len(linea) > 8: titulo = linea; break
            if titulo: break
    univ = ""
    for linea in lineas:
        if any(k in linea.lower() for k in ["universidad","institucion universitaria","corporacion","fundacion universitaria","tecnologico","politecnico","sena"]):
            univ = linea; break
    pais = "Colombia"
    for c, v in {"colombia":"Colombia","mexico":"Mexico","argentina":"Argentina","chile":"Chile","peru":"Peru","ecuador":"Ecuador"}.items():
        if c in tl: pais = v; break
    titular = ""
    for i, linea in enumerate(lineas):
        if any(t in linea.lower() for t in ["otorga a","conferido a","se otorga a","a nombre de"]):
            if i + 1 < len(lineas): titular = lineas[i+1]; break
    return titulo, univ, pais, nivel, titular

@st.cache_data(ttl=30)
def leer_documentos():
    df, sha = _gh_read("documentos_back.csv")
    if df.empty:
        df = pd.DataFrame(columns=["id","fecha","hora","nombre_titulo","universidad","pais",
                                    "nivel","titular","tipo_archivo","nombre_archivo",
                                    "archivo_b64","estado","revisor","decision","motivo"])
    return df, sha

def guardar_documento(nombre_titulo, universidad, pais, nivel, titular,
                       tipo_archivo, nombre_archivo, archivo_b64):
    df, sha = leer_documentos()
    nid = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    nueva = pd.DataFrame([{
        "id": nid,
        "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "hora":  datetime.now(timezone.utc).strftime("%H:%M:%S"),
        "nombre_titulo": clean_text(nombre_titulo),
        "universidad":   clean_text(universidad),
        "pais":          pais,
        "nivel":         nivel,
        "titular":       clean_text(titular),
        "tipo_archivo":  tipo_archivo,
        "nombre_archivo":nombre_archivo,
        "archivo_b64":   archivo_b64[:200] + "..." if len(archivo_b64)>200 else archivo_b64,
        "estado":        "PENDIENTE",
        "revisor":"","decision":"","motivo":""
    }])
    df = pd.concat([df, nueva], ignore_index=True)
    ok, err = _gh_write("documentos_back.csv", df, sha, "New doc upload: "+nombre_titulo[:40])
    leer_documentos.clear()
    return ok, err, nid

def contar_docs_pendientes():
    df, _ = leer_documentos()
    if df.empty or "estado" not in df.columns: return 0
    return int((df["estado"].astype(str).str.upper() == "PENDIENTE").sum())

@st.cache_resource
def get_motor():
    return ValidadorCSV()
motor = get_motor()

st.markdown("""
<style>
html,body{cursor:auto!important}
button,label{cursor:pointer!important}
[data-testid="stSidebar"]{background:#0f1117}
[data-testid="stSidebar"] *{color:#e0e0e0!important}
div[data-testid="stDataFrame"] td div{color:#111!important;font-size:.85rem!important}
</style>
""", unsafe_allow_html=True)

pendientes_n = contar_pendientes()
df_dec_side, _ = leer_decisiones()
_titulos_base = len(pd.read_csv(CSV_TITULOS)) if CSV_TITULOS.exists() else 0
total_side   = _titulos_base + len(df_dec_side)
aplican_side = int((df_dec_side["decision_aplica"].astype(str).str.lower().isin(["true","1","si"])).sum()) if not df_dec_side.empty else 0
secrets_ok   = bool(get_gh_config()[0])

def _card(label, value, color="#fff"):
    return "<div style='background:#1a1d2e;border-radius:8px;padding:.6rem .9rem;margin-bottom:5px;display:flex;justify-content:space-between'><span style='color:#aaa;font-size:.78rem'>"+label+"</span><span style='color:"+color+";font-weight:700'>"+str(value)+"</span></div>"

with st.sidebar:
    st.markdown("<div style='padding:.5rem 0 1.2rem'><div style='font-size:1.35rem;font-weight:700;color:#fff'>ValidaTitulos</div><div style='font-size:.72rem;color:#888'>Sistema de uso interno</div></div>", unsafe_allow_html=True)
    if not secrets_ok:
        st.markdown("<div style='background:#ef4444;color:#fff;font-weight:700;border-radius:8px;padding:.5rem .9rem;margin-bottom:8px;text-align:center;font-size:.75rem'>Config. Secrets requerida</div>", unsafe_allow_html=True)
    elif pendientes_n > 0:
        st.markdown("<div style='background:#f59e0b;color:#000;font-weight:700;border-radius:8px;padding:.5rem .9rem;margin-bottom:8px;text-align:center'>PENDIENTES BACK: "+str(pendientes_n)+"</div>", unsafe_allow_html=True)
    docs_pend = contar_docs_pendientes()
    if docs_pend > 0:
        st.markdown("<div style='background:#3b82f6;color:#fff;font-weight:700;border-radius:8px;padding:.5rem .9rem;margin-bottom:8px;text-align:center'>DOCS PENDIENTES: "+str(docs_pend)+"</div>", unsafe_allow_html=True)
    pagina = st.radio("Nav", ["Validar titulo","Cargar Documento","Ingresar diploma","Revision Back","Cargar datos","Historial","Dashboard"], label_visibility="collapsed")
    st.markdown(_card("Registros totales", total_side), unsafe_allow_html=True)
    st.markdown(_card("Aplican", aplican_side, "#4ade80"), unsafe_allow_html=True)
    if CSV_CONSULTAS.exists():
        st.markdown(_card("Consultas totales", len(pd.read_csv(CSV_CONSULTAS)), "#60a5fa"), unsafe_allow_html=True)
    if st.button("Recargar base", use_container_width=True):
        leer_decisiones.clear(); leer_pendientes.clear(); get_motor.clear(); st.rerun()


if pagina == "Validar titulo":
    st.header("Validar titulo academico")
    if pendientes_n > 0:
        st.warning("El Back tiene "+str(pendientes_n)+" solicitud(es) pendiente(s) por aprobar.")
    tab_con, tab_sol = st.tabs(["Consultar titulo", "Solicitar validacion al Back"])

    with tab_con:
        st.info("Ingresa el titulo para verificar si ya existe decision del Back.")
        c1, c2 = st.columns(2)
        busq_t = c1.text_input("Nombre del titulo *", placeholder="Ej: Tecnologo en Mercadotecnia", key="bt")
        busq_u = c2.text_input("Universidad (opcional)", placeholder="Ej: SENA", key="bu")
        if st.button("Consultar", use_container_width=True, type="primary", key="btn_c"):
            if not busq_t.strip():
                st.error("Ingresa el nombre del titulo.")
            else:
                with st.spinner("Buscando..."):
                    dec_f  = buscar_decision(busq_t.strip(), busq_u.strip())
                    pend_f = buscar_pendiente_activo(busq_t.strip())
                if dec_f is not None:
                    aplica   = str(dec_f.get("decision_aplica","")).lower() in ["true","1","si"]
                    nivel    = str(dec_f.get("nivel_confirmado",""))
                    motivo   = str(dec_f.get("motivo",""))
                    revisor  = str(dec_f.get("revisor",""))
                    univ_r   = str(dec_f.get("universidad",""))
                    sim_pct  = int(float(dec_f.get("_sim_t",1))*100)
                    st.markdown("---")
                    cr1, cr2 = st.columns([2,1])
                    with cr1:
                        st.write("**Titulo registrado:** "+str(dec_f.get("nombre_titulo","")))
                        if univ_r and univ_r != "nan": st.write("Universidad: "+univ_r)
                        if motivo and motivo not in ("nan",""): st.info("Observacion del Back: "+motivo)
                        if revisor and revisor not in ("nan",""): st.caption("Revisado por: "+revisor)
                    with cr2:
                        if aplica: st.success("APLICA")
                        else: st.error("NO APLICA")
                        if nivel and nivel != "nan": st.write("Nivel: "+nivel.capitalize())
                        st.caption("Similitud: "+str(sim_pct)+"%")
                    registrar_consulta(busq_t.strip(), "Aplica" if aplica else "No aplica", nivel, sim_pct)
                elif pend_f is not None:
                    sim2 = int(float(pend_f.get("_sim",1))*100)
                    st.warning("Este titulo esta pendiente de decision del Back ("+str(sim2)+"% similitud).")
                    st.caption("En espera: "+str(pend_f.get("nombre_titulo",""))+" | Enviado: "+str(pend_f.get("fecha","")))
                else:
                    st.info("No se encontro decision previa. Ve a **Solicitar validacion al Back**.")

    with tab_sol:
        st.warning("Usa esta pestana solo si la consulta anterior no arrojo resultados.")
        with st.form("form_sol", clear_on_submit=True):
            tit_s   = st.text_input("Nombre del titulo *", placeholder="Ej: Administracion de Empresas")
            s1, s2  = st.columns(2)
            univ_s  = s1.text_input("Universidad", placeholder="Ej: SENA")
            pais_s  = s2.selectbox("Pais", PAISES)
            s3, s4  = st.columns(2)
            niv_s   = s3.selectbox("Nivel academico", ["-- Seleccionar --"] + NIVELES)
            titu_s  = s4.text_input("Nombre del titular (opcional)")
            btn_env = st.form_submit_button("Enviar al Back para aprobacion", use_container_width=True, type="primary")
        if btn_env:
            if not tit_s.strip():
                st.error("El campo Titulo es obligatorio.")
            else:
                niv_env  = niv_s if niv_s != "-- Seleccionar --" else "universitario"
                pais_env = pais_s if pais_s in PAISES_B else "Otro"
                with st.spinner("Verificando..."):
                    dd = buscar_decision(tit_s.strip(), univ_s.strip())
                    pd2 = buscar_pendiente_activo(tit_s.strip())
                if dd is not None:
                    aplica_dd = str(dd.get("decision_aplica","")).lower() in ["true","1","si"]
                    sim_dd = int(float(dd.get("_sim_t",1))*100)
                    st.warning("Ya existe decision del Back para titulo similar ("+str(sim_dd)+"% similitud).")
                    st.success("APLICA | Nivel: "+str(dd.get("nivel_confirmado","")).capitalize()) if aplica_dd else st.error("NO APLICA")
                    mot_dd = str(dd.get("motivo",""))
                    if mot_dd and mot_dd not in ("nan",""): st.info("Observacion: "+mot_dd)
                elif pd2 is not None:
                    sim_pd = int(float(pd2.get("_sim",1))*100)
                    st.warning("Titulo similar ya esta en espera del Back ("+str(sim_pd)+"% similitud).")
                else:
                    with st.spinner("Enviando al Back..."):
                        ok, err, nid = guardar_pendiente(tit_s.strip(), univ_s.strip(), pais_env, niv_env, titu_s.strip(), "")
                    if ok:
                        registrar_consulta(tit_s.strip(), "Enviado al Back", niv_env, 0)
                        st.success("Solicitud enviada al Back correctamente.")
                        st.info("El equipo Back recibira la alerta y tomara la decision.")
                    else:
                        st.error("Error al enviar: "+str(err))


elif pagina == "Cargar Documento":
    st.header("Cargar Documento de Titulo")
    st.info("Sube el diploma o certificado del cliente. El Back lo vera de inmediato y tomara la decision.")

    if not secrets_ok:
        st.error("Configura GITHUB_TOKEN en Streamlit Secrets para usar esta funcion.")
        st.stop()

    docs_pend_n = contar_docs_pendientes()
    if docs_pend_n > 0:
        st.warning("Hay "+str(docs_pend_n)+" documento(s) pendiente(s) esperando revision del Back.")

    with st.form("form_doc", clear_on_submit=True):
        st.subheader("Datos del titulo")
        fd1, fd2 = st.columns(2)
        doc_titulo   = fd1.text_input("Nombre del titulo *", placeholder="Ej: Tecnologo en Gestion Logistica")
        doc_univ     = fd2.text_input("Universidad *", placeholder="Ej: SENA")
        fd3, fd4     = st.columns(2)
        doc_pais     = fd3.selectbox("Pais", PAISES)
        doc_nivel    = fd4.selectbox("Nivel academico", NIVELES)
        doc_titular  = st.text_input("Nombre del titular", placeholder="Ej: Juan Perez Gomez")
        st.markdown("---")
        st.subheader("Documento soporte")
        doc_archivo  = st.file_uploader(
            "Sube el diploma o certificado (JPG, PNG, PDF) *",
            type=["jpg","jpeg","png","pdf"],
            help="Maximo 5MB. El Back podra visualizarlo directamente."
        )
        doc_submit = st.form_submit_button("Enviar al Back para revision", use_container_width=True, type="primary")

    if doc_submit:
        if not doc_titulo.strip():
            st.error("El nombre del titulo es obligatorio.")
        elif not doc_univ.strip():
            st.error("La universidad es obligatoria.")
        elif doc_archivo is None:
            st.error("Debes subir al menos un documento soporte.")
        else:
            # Verificar si ya existe decision para este titulo
            dec_dup = buscar_decision(doc_titulo.strip(), doc_univ.strip())
            if dec_dup is not None:
                aplica_x = str(dec_dup.get("decision_aplica","")).lower() in ["true","1","si"]
                st.warning("Ya existe una decision del Back para este titulo.")
                if aplica_x:
                    st.success("APLICA | Nivel: "+str(dec_dup.get("nivel_confirmado","")).capitalize())
                else:
                    st.error("NO APLICA")
                mot_x = str(dec_dup.get("motivo",""))
                if mot_x and mot_x not in ("nan",""):
                    st.info("Observacion del Back: "+mot_x)
            else:
                with st.spinner("Subiendo documento..."):
                    import base64 as _b64
                    archivo_bytes = doc_archivo.read()
                    if len(archivo_bytes) > 5 * 1024 * 1024:
                        st.error("El archivo supera 5MB. Por favor reduce el tamano.")
                    else:
                        archivo_b64_str = _b64.b64encode(archivo_bytes).decode("ascii")
                        tipo = doc_archivo.type or "application/octet-stream"
                        nombre_arch = doc_archivo.name
                        ok, err, nid = guardar_documento(
                            doc_titulo.strip(), doc_univ.strip(), doc_pais,
                            doc_nivel, doc_titular.strip(),
                            tipo, nombre_arch, archivo_b64_str
                        )
                    if ok:
                        registrar_consulta(doc_titulo.strip(), "Documento cargado", doc_nivel, 0)
                        st.success("Documento enviado al Back correctamente. ID: "+nid)
                        st.info("El equipo Back recibira la alerta azul y podra visualizar el documento.")
                        st.balloons()
                    else:
                        st.error("Error al subir el documento: "+str(err))

elif pagina == "Ingresar diploma":
    st.header("Ingresar diploma")
    if not secrets_ok:
        st.error("Configura GITHUB_TOKEN en Streamlit Secrets.")
        st.code('GITHUB_TOKEN = "tu_token"\nGITHUB_REPO = "usanjosedocumentos-svg/validatitulos"', language="toml")
        st.stop()
    if pendientes_n > 0:
        st.warning("Hay "+str(pendientes_n)+" diploma(s) pendiente(s) esperando decision del Back.")
    st.info("Pega el texto del diploma. El sistema extrae los datos y los envia al Back.")
    texto = st.text_area("Texto del diploma *", height=150, placeholder="Pega aqui el texto del diploma...")
    if texto.strip():
        t, u, p, n, tit_d = extraer_datos_diploma(texto)
        st.markdown("---"); st.subheader("Datos detectados")
        d1, d2 = st.columns(2)
        titulo_d = d1.text_input("Titulo *", value=t, key="dd_t")
        univ_d   = d2.text_input("Universidad", value=u, key="dd_u")
        d3, d4   = st.columns(2)
        pais_d   = d3.selectbox("Pais", PAISES, index=(PAISES.index(p) if p in PAISES else 0), key="dd_p")
        nivel_d  = d4.selectbox("Nivel", NIVELES, index=(NIVELES.index(n) if n in NIVELES else 0), key="dd_n")
        tit_din  = st.text_input("Titular", value=tit_d, key="dd_tit")
        st.markdown("---")
        if st.button("Enviar al Back para aprobacion", use_container_width=True, type="primary"):
            if not titulo_d.strip():
                st.error("El campo Titulo es obligatorio.")
            else:
                dec_dup = buscar_decision(titulo_d.strip(), univ_d.strip())
                if dec_dup is not None:
                    aplica_x = str(dec_dup.get("decision_aplica","")).lower() in ["true","1","si"]
                    st.warning("Ya existe decision para este titulo.")
                    st.success("APLICA") if aplica_x else st.error("NO APLICA")
                else:
                    with st.spinner("Enviando..."):
                        ok, err, nid = guardar_pendiente(titulo_d.strip(), univ_d.strip(), pais_d, nivel_d, tit_din.strip(), texto)
                    if ok: st.success("Enviado al Back. ID: "+nid); st.balloons(); st.rerun()
                    else: st.error("Error: "+str(err))
    else:
        st.markdown("**Como funciona:** Pega el texto del diploma, revisa los datos detectados y haz clic en Enviar al Back.")


elif pagina == "Revision Back":
    st.header("Revision manual -- equipo Back")
    if not secrets_ok:
        st.warning("Configura GITHUB_TOKEN en Streamlit Secrets.")
    elif pendientes_n > 0:
        st.error("ATENCION: Tienes "+str(pendientes_n)+" diploma(s) PENDIENTE(S) esperando tu decision.")
    tab_p, tab_n, tab_e = st.tabs(["PENDIENTES ("+str(pendientes_n)+")", "Nueva decision", "Editar decision"])

    with tab_p:
        if not secrets_ok:
            st.info("Configura GITHUB_TOKEN para ver pendientes.")
        else:
            df_p, _ = leer_pendientes()
            solo = df_p[df_p["estado"].astype(str).str.upper() == "PENDIENTE"] if not df_p.empty and "estado" in df_p.columns else pd.DataFrame()
            if solo.empty:
                st.info("No hay diplomas pendientes de aprobacion.")
            else:
                st.markdown("**"+str(len(solo))+" diploma(s) esperando tu decision:**")
                for _, row in solo.iterrows():
                    rid   = str(row.get("id",""))
                    tit_p = str(row.get("nombre_titulo",""))
                    fp    = str(row.get("fecha",""))+" "+str(row.get("hora",""))
                    with st.expander("PENDIENTE -- "+tit_p+"  |  "+fp, expanded=True):
                        ci, cf = st.columns([1,1])
                        with ci:
                            st.markdown("**Datos:**")
                            st.write("Titulo: "+tit_p)
                            st.write("Universidad: "+str(row.get("universidad","")))
                            st.write("Pais: "+str(row.get("pais","")))
                            st.write("Nivel detectado: "+str(row.get("nivel_detectado","")))
                            st.write("Titular: "+str(row.get("titular","")))
                            txt = str(row.get("texto_diploma",""))
                            if txt and txt != "nan": st.markdown("**Texto original:**"); st.caption(txt[:300])
                        with cf:
                            st.markdown("**Tu decision:**")
                            nv_d = str(row.get("nivel_detectado","universitario"))
                            p_ap = st.radio("Aplica?", ["Si, aplica","No aplica"], key="apl_"+rid)
                            p_nv = st.selectbox("Confirmar nivel", NIVELES, index=(NIVELES.index(nv_d) if nv_d in NIVELES else 0), key="niv_"+rid)
                            p_rv = st.text_input("Tu nombre", key="rev_"+rid, placeholder="Ej: Ana Gomez")
                            p_mo = st.text_area("Observaciones", key="mot_"+rid, height=80)
                            p_in = st.checkbox("Incorporar a la base", value=True, key="inc_"+rid)
                            ca, cr = st.columns(2)
                            apro = ca.button("Aprobar",  key="ok_"+rid, use_container_width=True, type="primary")
                            rech = cr.button("Rechazar", key="no_"+rid, use_container_width=True)
                            if apro or rech:
                                aplica_b  = ("Si" in p_ap) and apro
                                estado_n  = "APROBADO" if apro else "RECHAZADO"
                                dec_n     = "Aplica" if aplica_b else "No aplica"
                                with st.spinner("Guardando..."):
                                    ok1, e1 = actualizar_pendiente(rid, estado_n, p_nv, p_rv.strip(), p_mo.strip(), dec_n)
                                    ok2, e2 = guardar_decision(tit_p, str(row.get("universidad","")), str(row.get("pais","Colombia")), p_nv, aplica_b, p_rv.strip(), p_mo.strip(), p_in)
                                if ok1 and ok2:
                                    get_motor.clear()
                                    st.success("Diploma "+estado_n+" y guardado en historial.")
                                    st.rerun()
                                else:
                                    if not ok1: st.error("Error actualizando pendiente: "+str(e1))
                                    if not ok2: st.error("Error guardando historial: "+str(e2))

    with tab_docs:
        if not secrets_ok:
            st.info("Configura GITHUB_TOKEN para ver documentos.")
        else:
            df_docs, sha_docs = leer_documentos()
            docs_solo = df_docs[df_docs["estado"].astype(str).str.upper() == "PENDIENTE"] if not df_docs.empty and "estado" in df_docs.columns else pd.DataFrame()
            if docs_solo.empty:
                st.info("No hay documentos pendientes de revision.")
            else:
                st.markdown("**"+str(len(docs_solo))+" documento(s) esperando tu revision:**")
                for _, doc_row in docs_solo.iterrows():
                    doc_id    = str(doc_row.get("id",""))
                    doc_tit   = str(doc_row.get("nombre_titulo",""))
                    doc_date  = str(doc_row.get("fecha",""))+" "+str(doc_row.get("hora",""))
                    doc_univ2 = str(doc_row.get("universidad",""))
                    doc_tipo  = str(doc_row.get("tipo_archivo",""))
                    doc_arch  = str(doc_row.get("nombre_archivo",""))
                    doc_b64   = str(doc_row.get("archivo_b64",""))
                    with st.expander("DOCUMENTO -- "+doc_tit+"  |  "+doc_date, expanded=True):
                        col_doc_i, col_doc_f = st.columns([1,1])
                        with col_doc_i:
                            st.markdown("**Datos:**")
                            st.write("Titulo: "+doc_tit)
                            st.write("Universidad: "+doc_univ2)
                            st.write("Pais: "+str(doc_row.get("pais","")))
                            st.write("Nivel: "+str(doc_row.get("nivel","")))
                            st.write("Titular: "+str(doc_row.get("titular","")))
                            st.write("Archivo: "+doc_arch)
                            # Mostrar vista previa del documento
                            if doc_b64 and not doc_b64.endswith("...") and len(doc_b64) > 100:
                                import base64 as _b64
                                try:
                                    doc_bytes = _b64.b64decode(doc_b64)
                                    if "image" in doc_tipo:
                                        st.image(doc_bytes, caption=doc_arch, use_column_width=True)
                                    elif "pdf" in doc_tipo:
                                        st.markdown("**Vista previa PDF:**")
                                        pdf_b64_display = _b64.b64encode(doc_bytes).decode()
                                        pdf_html = "<iframe src='data:application/pdf;base64,"+pdf_b64_display+"' width='100%' height='400px'></iframe>"
                                        st.markdown(pdf_html, unsafe_allow_html=True)
                                    # Boton de descarga
                                    st.download_button("Descargar "+doc_arch, data=doc_bytes, file_name=doc_arch, mime=doc_tipo, key="dl_"+doc_id)
                                except Exception as ex:
                                    st.warning("No se pudo previsualizar: "+str(ex))
                            elif doc_b64.endswith("..."):
                                st.caption("Archivo grande - descarga disponible si se recarga completo")
                        with col_doc_f:
                            st.markdown("**Tu decision:**")
                            idx_doc = df_docs[df_docs["id"].astype(str)==doc_id].index
                            nv_doc  = str(doc_row.get("nivel","universitario"))
                            dap = st.radio("Aplica?", ["Si, aplica","No aplica"], key="dap_"+doc_id)
                            dnv = st.selectbox("Confirmar nivel", NIVELES, index=(NIVELES.index(nv_doc) if nv_doc in NIVELES else 0), key="dnv_"+doc_id)
                            drv = st.text_input("Tu nombre", key="drv_"+doc_id, placeholder="Ej: Ana Gomez")
                            dmo = st.text_area("Observaciones", key="dmo_"+doc_id, height=80)
                            din = st.checkbox("Incorporar a la base", value=True, key="din_"+doc_id)
                            dca, dcr = st.columns(2)
                            dapr = dca.button("Aprobar",  key="doka_"+doc_id, use_container_width=True, type="primary")
                            drec = dcr.button("Rechazar", key="dnoa_"+doc_id, use_container_width=True)
                            if dapr or drec:
                                aplica_doc = ("Si" in dap) and dapr
                                estado_doc = "APROBADO" if dapr else "RECHAZADO"
                                if len(idx_doc) > 0:
                                    with st.spinner("Guardando..."):
                                        df_docs.loc[idx_doc[0],"estado"]   = estado_doc
                                        df_docs.loc[idx_doc[0],"revisor"]  = drv.strip()
                                        df_docs.loc[idx_doc[0],"decision"] = "Aplica" if aplica_doc else "No aplica"
                                        df_docs.loc[idx_doc[0],"motivo"]   = dmo.strip()
                                        ok_d, err_d = _gh_write("documentos_back.csv", df_docs, sha_docs, estado_doc+": "+doc_tit[:40])
                                        ok_h = ok_e2 = True; err_h = err_e2 = None
                                        if ok_d:
                                            leer_documentos.clear()
                                            ok_h, err_h = guardar_decision(doc_tit, doc_univ2, str(doc_row.get("pais","Colombia")), dnv, aplica_doc, drv.strip(), dmo.strip(), din)
                                    if ok_d and ok_h:
                                        get_motor.clear()
                                        st.success("Documento "+estado_doc+" y guardado en historial.")
                                        st.rerun()
                                    else:
                                        if not ok_d: st.error("Error doc: "+str(err_d))
                                        if not ok_h: st.error("Error historial: "+str(err_h))

    with tab_n:
        st.warning("Solo para el equipo Back.")
        with st.form("form_back_nueva", clear_on_submit=True):
            b_t  = st.text_input("Titulo revisado *")
            b1, b2 = st.columns(2)
            b_u  = b1.text_input("Universidad")
            b_p  = b2.selectbox("Pais", PAISES_B)
            b3, b4 = st.columns(2)
            b_ap = b3.radio("Este titulo aplica?", ["Si, aplica","No aplica"])
            b_nv = b4.selectbox("Nivel confirmado", NIVELES)
            b_rv = st.text_input("Nombre del revisor")
            b_mo = st.text_area("Observaciones", height=80)
            b_in = st.checkbox("Incorporar a la base", value=True)
            b_sb = st.form_submit_button("Guardar decision", use_container_width=True)
        if b_sb:
            if not b_t.strip():
                st.error("El campo Titulo es obligatorio.")
            else:
                with st.spinner("Guardando..."):
                    ok, err = guardar_decision(b_t.strip(), b_u.strip(), b_p, b_nv, "Si" in b_ap, b_rv.strip(), b_mo.strip(), b_in)
                if ok: get_motor.clear(); st.success("Guardado: '"+b_t.strip()+"' -> "+("Aplica" if "Si" in b_ap else "No aplica"))
                else: st.error("Error: "+str(err))

    with tab_e:
        df_de, sha_de = leer_decisiones()
        if df_de.empty:
            st.info("No hay decisiones para editar.")
        else:
            busq_e = st.text_input("Buscar titulo", placeholder="Escribe parte del nombre...", key="be")
            if busq_e.strip():
                df_fe = df_de[df_de["nombre_titulo"].astype(str).str.contains(busq_e.strip(), case=False, na=False)]
                if df_fe.empty:
                    st.warning("No se encontraron registros.")
                else:
                    st.dataframe(df_fe[["nombre_titulo","nivel_confirmado","decision_aplica","revisor","motivo"]].reset_index(), use_container_width=True, hide_index=True)
                    opc = [str(i)+" - "+str(df_de.loc[i,"nombre_titulo"]) for i in df_fe.index.tolist()]
                    sel = st.selectbox("Selecciona el registro", opc, key="se")
                    if sel:
                        ix = int(sel.split(" - ")[0])
                        rw = df_de.loc[ix]
                        with st.form("form_editar", clear_on_submit=False):
                            e_t = st.text_input("Titulo *", value=str(rw.get("nombre_titulo","")))
                            e1, e2 = st.columns(2)
                            e_u = e1.text_input("Universidad", value=str(rw.get("universidad","")))
                            pa  = str(rw.get("pais","Colombia"))
                            e_p = e2.selectbox("Pais", PAISES_B, index=(PAISES_B.index(pa) if pa in PAISES_B else 0), key="ep")
                            e3, e4 = st.columns(2)
                            aa  = str(rw.get("decision_aplica","")).lower() in ["true","si","1"]
                            e_a = e3.radio("Aplica?", ["Si, aplica","No aplica"], index=(0 if aa else 1), key="ea")
                            nva = str(rw.get("nivel_confirmado","universitario"))
                            e_n = e4.selectbox("Nivel", NIVELES, index=(NIVELES.index(nva) if nva in NIVELES else 0), key="en")
                            e_r = st.text_input("Revisor", value=str(rw.get("revisor","")))
                            e_m = st.text_area("Observaciones", value=str(rw.get("motivo","")), height=80)
                            e_s = st.form_submit_button("Guardar cambios", use_container_width=True)
                        if e_s:
                            if not e_t.strip(): st.error("El titulo no puede estar vacio.")
                            else:
                                df_de.loc[ix,"nombre_titulo"]   = e_t.strip()
                                df_de.loc[ix,"universidad"]      = e_u.strip()
                                df_de.loc[ix,"pais"]             = e_p
                                df_de.loc[ix,"decision_aplica"]  = "Si" in e_a
                                df_de.loc[ix,"nivel_confirmado"] = e_n
                                df_de.loc[ix,"revisor"]          = e_r.strip()
                                df_de.loc[ix,"motivo"]           = e_m.strip()
                                ok_e, err_e = _gh_write("decisiones_back.csv", df_de, sha_de, "Edit: "+e_t.strip()[:40])
                                if ok_e: leer_decisiones.clear(); st.success("Registro actualizado."); st.rerun()
                                else: st.error("Error: "+str(err_e))
            else:
                st.caption("Escribe al menos una letra para buscar.")


elif pagina == "Cargar datos":
    st.header("Cargar base historica de titulos")
    st.info("Sube un CSV con columnas: nombre_titulo, aplica, nivel (+ opcionales: universidad, pais, semestre)")
    archivo = st.file_uploader("Selecciona tu archivo CSV", type=["csv"])
    if archivo:
        try:
            df_n = pd.read_csv(archivo)
            st.markdown("**Vista previa** -- "+str(len(df_n))+" filas:")
            st.dataframe(df_n.head(8), use_container_width=True, hide_index=True)
            falt = {"nombre_titulo","aplica","nivel"} - set(df_n.columns)
            if falt:
                st.error("Faltan columnas: "+", ".join(falt))
            else:
                df_dc, sha_dc = leer_decisiones()
                df_n["_key"] = df_n["nombre_titulo"].astype(str).str.lower().str.strip()
                dup_int = df_n[df_n.duplicated("_key",keep=False)][["nombre_titulo","nivel"]].drop_duplicates()
                dup_ext = pd.DataFrame()
                if not df_dc.empty and "nombre_titulo" in df_dc.columns:
                    keys_dc = set(df_dc["nombre_titulo"].astype(str).str.lower().str.strip())
                    dup_ext = df_n[df_n["_key"].isin(keys_dc)][["nombre_titulo","nivel"]].drop_duplicates()
                if len(dup_int) > 0 or len(dup_ext) > 0:
                    st.warning("Duplicados detectados.")
                    cc1, cc2 = st.columns(2)
                    if len(dup_int) > 0: cc1.markdown("**En el archivo ("+str(len(dup_int))+"):**"); cc1.dataframe(dup_int.reset_index(drop=True), use_container_width=True, hide_index=True)
                    if len(dup_ext) > 0: cc2.markdown("**Ya en la base ("+str(len(dup_ext))+"):**"); cc2.dataframe(dup_ext.reset_index(drop=True), use_container_width=True, hide_index=True)
                    opcion = st.radio("Que hacer?", ["Omitir existentes","Reemplazar con nuevos","Cancelar"])
                else:
                    st.success("Sin duplicados -- "+str(len(df_n))+" titulos listos.")
                    opcion = "Omitir existentes"
                if st.button("Confirmar e importar", use_container_width=True, disabled="Cancelar" in opcion):
                    for col in ["universidad","pais","semestre","motivo","revisor"]:
                        if col not in df_n.columns: df_n[col] = ""
                    df_imp = df_n.rename(columns={"aplica":"decision_aplica","nivel":"nivel_confirmado"})
                    df_imp["fecha"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    df_imp["incorporar"] = "true"
                    if df_dc.empty:
                        df_merged = df_imp
                    else:
                        df_merged = pd.concat([df_dc, df_imp], ignore_index=True)
                        keep = "first" if "Omitir" in opcion else "last"
                        df_merged.drop_duplicates(subset=["nombre_titulo","nivel_confirmado"], keep=keep, inplace=True)
                    ok_i, err_i = _gh_write("decisiones_back.csv", df_merged, sha_dc, "Import "+str(len(df_imp))+" titles")
                    if ok_i: leer_decisiones.clear(); st.success("Importacion completada. Base: "+str(len(df_merged))+" registros."); st.balloons()
                    else: st.error("Error: "+str(err_i))
        except Exception as e:
            st.error("Error al leer el archivo: "+str(e))
    st.markdown("---")
    plantilla = pd.DataFrame([{"nombre_titulo":"Administracion de Empresas","universidad":"SENA","pais":"Colombia","aplica":"True","nivel":"universitario","semestre":5}])
    st.download_button("Descargar plantilla CSV", data=plantilla.to_csv(index=False).encode(), file_name="plantilla_titulos.csv", mime="text/csv", use_container_width=True)


elif pagina == "Historial":
    st.header("Historial de decisiones Back")
    df_h, _ = leer_decisiones()
    if df_h.empty:
        st.info("Aun no hay decisiones registradas.")
    else:
        aplican_h  = int((df_h["decision_aplica"].astype(str).str.lower().isin(["true","si","1"])).sum())
        c1, c2, c3 = st.columns(3)
        c1.metric("Total revisiones", len(df_h))
        c2.metric("Aprobadas", aplican_h)
        c3.metric("Rechazadas", len(df_h)-aplican_h)
        st.markdown("---")
        buscar_h = st.text_input("Buscar titulo", placeholder="Filtrar...")
        _, mf = st.columns([2,1])
        filtro_h = mf.selectbox("Mostrar", ["Todas","Solo aprobadas","Solo rechazadas"])
        df_show = df_h.copy()
        if buscar_h:
            df_show = df_show[df_show["nombre_titulo"].astype(str).str.contains(buscar_h, case=False, na=False)]
        if filtro_h == "Solo aprobadas":
            df_show = df_show[df_show["decision_aplica"].astype(str).str.lower().isin(["true","si","1"])]
        elif filtro_h == "Solo rechazadas":
            df_show = df_show[~df_show["decision_aplica"].astype(str).str.lower().isin(["true","si","1"])]
        cols_s = [c for c in ["nombre_titulo","universidad","nivel_confirmado","decision_aplica","revisor","motivo","fecha"] if c in df_show.columns]
        st.dataframe(df_show[cols_s].style.set_properties(**{"color":"black","font-size":"14px"}), use_container_width=True, hide_index=True, height=450)
        st.download_button("Descargar historial CSV", data=df_h.to_csv(index=False).encode(), file_name="decisiones_back.csv", mime="text/csv", use_container_width=True)


elif pagina == "Dashboard":
    st.header("Dashboard de consultas")
    df_dec_d, _ = leer_decisiones()
    if not df_dec_d.empty:
        st.subheader("Resumen de decisiones del Back")
        ap_d = int((df_dec_d["decision_aplica"].astype(str).str.lower().isin(["true","si","1"])).sum())
        md1, md2, md3 = st.columns(3)
        md1.metric("Total decisiones", len(df_dec_d))
        md2.metric("Aplican", ap_d)
        md3.metric("No aplican", len(df_dec_d)-ap_d)
        st.markdown("---")
    if not CSV_CONSULTAS.exists() or pd.read_csv(CSV_CONSULTAS).empty:
        st.info("Aun no hay consultas registradas en esta sesion.")
    else:
        df_c = pd.read_csv(CSV_CONSULTAS)
        df_c["fecha"] = pd.to_datetime(df_c["fecha"], errors="coerce")
        f1, f2 = st.columns(2)
        fmin = df_c["fecha"].min().date() if not df_c["fecha"].isnull().all() else None
        fmax = df_c["fecha"].max().date() if not df_c["fecha"].isnull().all() else None
        f_desde = f1.date_input("Desde", value=fmin)
        f_hasta = f2.date_input("Hasta", value=fmax)
        df_f = df_c[(df_c["fecha"].dt.date >= f_desde) & (df_c["fecha"].dt.date <= f_hasta)]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total consultas", len(df_f))
        m2.metric("Aplican", int((df_f["resultado"].astype(str).str.lower()=="aplica").sum()))
        m3.metric("No aplican", int((df_f["resultado"].astype(str).str.lower()=="no aplica").sum()))
        m4.metric("Titulos unicos", df_f["nombre_titulo"].nunique())
        st.markdown("---")
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Top 10 mas consultados")
            top = df_f.groupby("nombre_titulo").size().reset_index(name="consultas").sort_values("consultas",ascending=False).head(10)
            if not top.empty:
                st.dataframe(top.style.set_properties(**{"color":"black","font-size":"14px"}).bar(subset=["consultas"],color="#60a5fa"), use_container_width=True, hide_index=True, height=370)
        with col_b:
            st.subheader("Por resultado")
            dist = df_f["resultado"].value_counts().reset_index(); dist.columns = ["resultado","cantidad"]
            st.dataframe(dist.style.set_properties(**{"color":"black","font-size":"14px"}), use_container_width=True, hide_index=True)
        st.markdown("---")
        st.subheader("Consultas por dia")
        por_dia = df_f.groupby("fecha").size().reset_index(name="consultas")
        por_dia["fecha"] = por_dia["fecha"].dt.strftime("%Y-%m-%d")
        if not por_dia.empty: st.bar_chart(por_dia.set_index("fecha")["consultas"])
        st.download_button("Descargar log CSV", data=df_f.to_csv(index=False).encode(), file_name="consultas_log.csv", mime="text/csv", use_container_width=True)

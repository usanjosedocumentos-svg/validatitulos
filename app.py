""" app.py - ValidaTitulos - Con sistema de roles y permisos """
import streamlit as st
import io
import csv as _csv
import unicodedata
import re
import pandas as pd
from pathlib import Path
import uuid
import urllib.request, urllib.error, json, base64
from datetime import datetime, timezone
from validador import ValidadorCSV, CSV_TITULOS, CSV_DECISIONES

# ══════════════════════════════════════════════════════════════════
# SISTEMA DE ROLES Y PERMISOS
# ══════════════════════════════════════════════════════════════════
ROLES_DEFAULT = {
    "validador": [
        "deyci.londono@bluhartmann.com","diego.guevara@bluhartmann.com",
        "maria.blanco@bluhartmann.com","andres.baracaldo@bluhartmann.com",
        "jakelin.camacho@bluhartmann.com","gina.cardenas@bluhartmann.com",
        "carolina.rodriguez@bluhartmann.com","magda.medina@bluhartmann.com",
        "brenda.cubides@bluhartmann.com","jhonatan.alarcon@bluhartmann.com",
        "lessy.pena@bluhartmann.com","damaris.rincon@bluhartmann.com",
        "anny.jimenez@bluhartmann.com","brandon.ramos@bluhartmann.com",
        "miguel.ditta@bluhartmann.com","daniel.perdomo@bluhartmann.com",
        "jenny.ospina@bluhartmann.com","david.fuentes@bluhartmann.com",
        "julieth.sema@bluhartmann.com","erika.montes@bluhartmann.com"
    ],
    "back": [
        "cristian.talero@bluhartmann.com","michael.montiel@bluhartmann.com",
        "kevin.guevara@bluhartmann.com","laura.sanchez@bluhartmann.com",
        "lizeth.ordonez@bluhartmann.com","maria.manosalva@bluhartmann.com",
        "nicolas.garcia@bluhartmann.com"
    ],
    "admin": [
        "lady.quinones@bluhartmann.com","jessica.romero@bluhartmann.com"
    ]
}

CSV_ROLES = Path(__file__).parent / "roles_usuarios.csv"

def cargar_roles():
    if CSV_ROLES.exists():
        try:
            df = pd.read_csv(CSV_ROLES)
            roles = {"validador": [], "back": [], "admin": []}
            for _, row in df.iterrows():
                rol = str(row.get("rol","")).strip().lower()
                email = str(row.get("email","")).strip().lower()
                if rol in roles and email:
                    roles[rol].append(email)
            return roles
        except:
            pass
    return ROLES_DEFAULT

def guardar_roles_csv(roles_dict):
    filas = []
    for rol, emails in roles_dict.items():
        for email in emails:
            filas.append({"rol": rol, "email": email.lower().strip()})
    df = pd.DataFrame(filas)
    df.to_csv(CSV_ROLES, index=False)
    contenido = df.to_csv(index=False)
    escribir_github("roles_usuarios.csv", contenido, "Actualizar roles de usuarios")

def obtener_rol(email, roles):
    email = email.lower().strip()
    for rol, lista in roles.items():
        if email in [e.lower().strip() for e in lista]:
            return rol
    return None

# ══════════════════════════════════════════════════════════════════
# PERMISOS POR ROL
# ══════════════════════════════════════════════════════════════════
PERMISOS = {
    "validador": ["Validar titulo", "Ingresar diploma"],
    "back":      ["Validar titulo", "Ingresar diploma", "Revision Back", "Historial"],
    "admin":     ["Validar titulo", "Ingresar diploma", "Revision Back", "Cargar datos", "Historial", "Dashboard", "Administrar Roles"]
}

def tiene_permiso(rol, pagina):
    if rol is None:
        return False
    return pagina in PERMISOS.get(rol, [])

# ══════════════════════════════════════════════════════════════════
# FUNCIONES UTILITARIAS
# ══════════════════════════════════════════════════════════════════
def normalizar(texto: str) -> str:
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()

BASE_DIR = Path(__file__).parent
CSV_PENDIENTES  = BASE_DIR / "pendientes_back.csv"
CSV_CONTADOR    = BASE_DIR / "consultas_contador.csv"
CSV_SOLICITUDES = BASE_DIR / "solicitudes_pendientes.csv"
DIPLOMAS_DIR    = BASE_DIR / "diplomas"
DIPLOMAS_DIR.mkdir(exist_ok=True)
NIVELES = ["bachillerato","tecnico","tecnologo","universitario","especializacion","maestria","doctorado"]

def df_a_csv_seguro(df: pd.DataFrame) -> str:
    df = df.copy()
    for col in df.select_dtypes(include="object").columns:
        df[col] = (df[col].astype(str).str.replace("\n"," ",regex=False).str.replace("\r"," ",regex=False))
    buf = io.StringIO()
    df.to_csv(buf, index=False, quoting=_csv.QUOTE_ALL)
    return buf.getvalue()

@st.cache_data(ttl=60)
def leer_contador():
    try:
        if CSV_CONTADOR.exists():
            df = pd.read_csv(CSV_CONTADOR)
            if "fecha" not in df.columns:
                df["fecha"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            return df
    except: pass
    return pd.DataFrame(columns=["titulo","fecha","consultas"])

def registrar_consulta(titulo):
    try:
        df = leer_contador()
        titulo = str(titulo).strip().upper()
        if not titulo: return
        fecha_hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        nueva = pd.DataFrame([{"titulo": titulo, "fecha": fecha_hoy, "consultas": 1}])
        df = pd.concat([df, nueva], ignore_index=True)
        df.to_csv(CSV_CONTADOR, index=False)
        escribir_github("consultas_contador.csv", df_a_csv_seguro(df), f"Consulta: {titulo[:40]}")
        leer_contador.clear()
    except: pass

def escribir_github(nombre_archivo, contenido, mensaje_commit):
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo  = st.secrets["GITHUB_REPO"]
        url   = f"https://api.github.com/repos/{repo}/contents/{nombre_archivo}"
        hdrs  = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        req_g = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req_g) as r: sha = json.loads(r.read())["sha"]
        except urllib.error.HTTPError as e:
            sha = None if e.code == 404 else (_ for _ in ()).throw(e)
        b64  = base64.b64encode(contenido.encode("utf-8")).decode("utf-8")
        body = {"message": mensaje_commit, "content": b64}
        if sha: body["sha"] = sha
        req_p = urllib.request.Request(url, data=json.dumps(body).encode(), method="PUT",
                    headers={**hdrs, "Content-Type": "application/json"})
        urllib.request.urlopen(req_p)
        return True
    except Exception as e:
        st.error(f"Error GitHub: {e}"); return False

@st.cache_data(ttl=30)
def leer_solicitudes():
    if CSV_SOLICITUDES.exists():
        try:
            df = pd.read_csv(CSV_SOLICITUDES)
            if "titulo" not in df.columns and "nombre_titulo" in df.columns: df["titulo"] = df["nombre_titulo"]
            if "nombre" not in df.columns and "asesor" in df.columns: df["nombre"] = df["asesor"]
            return df
        except: pass
    return pd.DataFrame(columns=["id","titulo","nombre_titulo","universidad","pais","nombre","asesor","fecha","estado","diploma_path","notas","motivo_rechazo"])

@st.cache_data(ttl=0)
def leer_decisiones():
    try:
        token = st.secrets.get("GITHUB_TOKEN",""); repo = st.secrets.get("GITHUB_REPO","")
        if token and repo:
            url = f"https://raw.githubusercontent.com/{repo}/main/decisiones_back.csv"
            req = urllib.request.Request(url, headers={"Authorization": f"token {token}"})
            with urllib.request.urlopen(req, timeout=8) as r:
                raw = r.read().decode("utf-8","replace")
            df = pd.read_csv(io.StringIO(raw))
            df.to_csv(CSV_DECISIONES, index=False)
            return df
    except: pass
    try: return pd.read_csv(CSV_DECISIONES) if CSV_DECISIONES.exists() else pd.DataFrame()
    except: return pd.DataFrame()

def guardar_solicitud(nombre, titulo, universidad, pais, diploma_path, notas=""):
    df  = leer_solicitudes()
    nid = str(uuid.uuid4())[:8].upper()
    nueva = {"id":nid,"fecha":datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
             "nombre":nombre.strip().upper(),"asesor":nombre.strip().upper(),
             "titulo":titulo.strip().upper(),"nombre_titulo":titulo.strip().upper(),
             "universidad":universidad.strip().upper() if universidad else "","pais":pais,
             "estado":"PENDIENTE","diploma_path":str(diploma_path) if diploma_path else "","notas":notas,"motivo_rechazo":""}
    df = pd.concat([df, pd.DataFrame([nueva])], ignore_index=True)
    df.to_csv(CSV_SOLICITUDES, index=False)
    escribir_github("solicitudes_pendientes.csv", df_a_csv_seguro(df), f"Add solicitud: {titulo.strip().upper()[:40]}")
    return nid

def actualizar_estado_solicitud(sol_id, nuevo_estado):
    df = leer_solicitudes()
    df.loc[df["id"]==sol_id,"estado"] = nuevo_estado
    df.to_csv(CSV_SOLICITUDES, index=False)
    escribir_github("solicitudes_pendientes.csv", df_a_csv_seguro(df), f"Update {sol_id}: {nuevo_estado}")

@st.cache_resource
def get_motor(): return ValidadorCSV()

# ══════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE PÁGINA
# ══════════════════════════════════════════════════════════════════
st.set_page_config(page_title="ValidaTitulos", layout="wide", page_icon="🎓")
st.markdown("""<style>
.btn-pendiente{background:#f97316;color:#fff;border-radius:8px;padding:10px 0;font-weight:700;font-size:1rem;text-align:center;margin-bottom:8px;}
.rol-badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:0.8rem;font-weight:600;margin-bottom:8px;}
.rol-validador{background:#1d4ed8;color:#fff;}
.rol-back{background:#7c3aed;color:#fff;}
.rol-admin{background:#dc2626;color:#fff;}
[data-testid="stSidebar"]{background:#111827;}
[data-testid="stSidebar"] *{color:#f3f4f6 !important;}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# AUTENTICACIÓN Y CONTROL DE ACCESO
# ══════════════════════════════════════════════════════════════════
roles_config = cargar_roles()

if "usuario_email" not in st.session_state:
    st.session_state.usuario_email = ""
if "usuario_rol" not in st.session_state:
    st.session_state.usuario_rol = None

# Pantalla de login si no hay sesión
if not st.session_state.usuario_email:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("# 🎓 ValidaTitulos")
        st.markdown("### Sistema de Validación Académica")
        st.markdown("---")
        st.markdown("**Ingresa tu correo institucional para continuar**")
        email_input = st.text_input("Correo electrónico", placeholder="nombre@bluhartmann.com", key="login_email")
        if st.button("Ingresar", type="primary", use_container_width=True):
            if email_input.strip():
                rol = obtener_rol(email_input.strip(), roles_config)
                if rol:
                    st.session_state.usuario_email = email_input.strip().lower()
                    st.session_state.usuario_rol   = rol
                    st.rerun()
                else:
                    st.error("❌ Correo no autorizado. Contacta al administrador.")
            else:
                st.warning("Ingresa tu correo para continuar.")
    st.stop()

# Usuario autenticado
usuario_email = st.session_state.usuario_email
usuario_rol   = st.session_state.usuario_rol
paginas_disponibles = PERMISOS.get(usuario_rol, [])

ROL_LABELS = {"validador": "VALIDADOR", "back": "BACK OFFICE", "admin": "ADMINISTRADOR"}
ROL_CSS    = {"validador": "rol-validador", "back": "rol-back", "admin": "rol-admin"}

# ══════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("<div style='font-size:1.3rem;font-weight:700;margin-bottom:2px'>🎓 ValidaTitulos</div>", unsafe_allow_html=True)
    st.caption("Sistema de uso interno")
    st.markdown(f"<div class='rol-badge {ROL_CSS.get(usuario_rol,"")}'>👤 {ROL_LABELS.get(usuario_rol,"")} — {usuario_email.split('@')[0]}</div>", unsafe_allow_html=True)

    df_sol_sb = leer_solicitudes()
    n_pend = 0
    if usuario_rol in ["back","admin"] and not df_sol_sb.empty:
        n_pend = len(df_sol_sb[df_sol_sb["estado"]=="PENDIENTE"])
    if n_pend:
        st.markdown(f"<div class='btn-pendiente'>PENDIENTES BACK: {n_pend}</div>", unsafe_allow_html=True)

    pagina = st.radio("Navegacion", paginas_disponibles, label_visibility="collapsed")

    if st.button("🚪 Cerrar sesión", use_container_width=True):
        st.session_state.usuario_email = ""
        st.session_state.usuario_rol   = None
        st.rerun()

    st.divider()

    # Resumen solo para back y admin
    if usuario_rol in ["back","admin"]:
        df_d = leer_decisiones()
        if not df_d.empty:
            aplica_col = "decision_aplica" if "decision_aplica" in df_d.columns else "aplica"
            nivel_col  = "nivel_confirmado" if "nivel_confirmado" in df_d.columns else "nivel"
            df_d["_ap"]  = df_d[aplica_col].astype(str).str.lower().isin(["true","1","si"])
            df_d["_niv"] = df_d[nivel_col].astype(str).str.lower().str.strip()
            total    = len(df_d)
            aplican  = int(df_d["_ap"].sum())
            no_aplic = total - aplican
            tecnicos   = int(df_d["_niv"].str.contains("tecnico", na=False).sum())
            tecnologos = int(df_d["_niv"].str.contains("tecnologo", na=False).sum())
            pct_ap = round(aplican/total*100,1) if total else 0
            pct_no = round(no_aplic/total*100,1) if total else 0
            st.markdown("### 📊 Resumen General")
            m1,m2,m3,m4 = st.columns(4)
            m1.metric("📋 Total", total)
            m2.metric("✅ Aplican", aplican, delta=f"{pct_ap}%")
            m3.metric("❌ No Aplican", no_aplic, delta=f"-{pct_no}%", delta_color="inverse")
            m4.metric("🎓 Téc+Tecnól", tecnicos+tecnologos)

    if st.button("Recargar base", use_container_width=True):
        get_motor.clear(); st.cache_data.clear(); st.rerun()

motor = get_motor()

# ══════════════════════════════════════════════════════════════════
# PÁGINAS
# ══════════════════════════════════════════════════════════════════

# ── VALIDAR TÍTULO ───────────────────────────────────────────────
if pagina == "Validar titulo":
    st.title("Validar titulo academico")
    if usuario_rol in ["back","admin"] and n_pend:
        st.info(f"El Back tiene {n_pend} solicitud(es) pendiente(s) para aprobar.")

    tab1, tab2 = st.tabs(["Consultar titulo","Solicitar validacion al Back"])
    with tab1:
        st.info("Ingresa el titulo para verificar si ya existe decision del Back.")
        c1,c2 = st.columns([2,1])
        titulo_input = c1.text_input("Nombre del titulo *", placeholder="Ej: Tecnologo en Mercadotecnia")
        univ_input   = c2.text_input("Universidad (opcional)", placeholder="Ej: SENA")
        if st.button("Consultar", type="primary", use_container_width=True):
            if not titulo_input.strip():
                st.warning("Ingresa al menos el nombre del titulo.")
            else:
                tu = titulo_input.strip().upper()
                uu = univ_input.strip().upper()
                leer_decisiones.clear()
                res = motor.validar(tu, uu if uu else None)
                registrar_consulta(tu)
                if res is None or res.requiere_revision or res.metodo not in ["back_exacto"]:
                    palabras = [p for p in tu.split() if len(p) > 3]
                    df_dc2   = leer_decisiones()
                    relacionados = []
                    if not df_dc2.empty and palabras:
                        for _, fila in df_dc2.iterrows():
                            nombre = str(fila.get("nombre_titulo","")).upper()
                            if any(p in nombre for p in palabras):
                                relacionados.append(fila)
                    if relacionados:
                        st.warning("⚠️ Titulo no encontrado exactamente. Títulos relacionados:")
                        for r in relacionados[:8]:
                            ap  = str(r.get("decision_aplica","")).lower() in ["true","1","si"]
                            niv = str(r.get("nivel_confirmado","")).strip()
                            nom = str(r.get("nombre_titulo","")).strip()
                            mot = str(r.get("motivo","")).strip()
                            rev = str(r.get("revisor","")).strip()
                            icono = "✅" if ap else "❌"
                            with st.expander(f"{icono} {nom} — {niv}"):
                                st.markdown(f"**Aplica:** {'SI' if ap else 'NO'} | **Nivel:** {niv}")
                                if mot and mot.lower() not in ["nan","none",""]: st.info(f"💬 {mot}")
                                if rev and rev.lower() not in ["nan","none",""]: st.caption(f"Autorizado por: {rev}")
                    else:
                        st.warning("⚠️ Titulo no encontrado en la base. Puedes solicitar validacion al Back.")
                elif res.aplica:
                    st.success(f"✅ APLICA — Nivel: {res.nivel if res.nivel else ''}")
                    leer_decisiones.clear()
                    df_dc = leer_decisiones()
                    if not df_dc.empty:
                        match = df_dc[df_dc["nombre_titulo"].astype(str).str.upper().str.strip() == tu]
                        if not match.empty:
                            rm  = match.iloc[-1]
                            mot = str(rm.get("motivo","")).strip()
                            rev = str(rm.get("revisor","")).strip()
                            niv = str(rm.get("nivel_confirmado","")).strip()
                            st.markdown("---")
                            ca,cb = st.columns(2)
                            ca.markdown(f"**Aplica:** SI ✅")
                            cb.markdown(f"**Nivel:** {niv}")
                            if mot and mot.lower() not in ["nan","none",""]: st.info(f"💬 Observacion del Back: {mot}")
                            if rev and rev.lower() not in ["nan","none",""]: st.caption(f"Autorizado por: {rev}")
                else:
                    st.error(f"❌ NO APLICA — Nivel: {res.nivel if res.nivel else ''}")
                    leer_decisiones.clear()
                    df_dc = leer_decisiones()
                    if not df_dc.empty:
                        match = df_dc[df_dc["nombre_titulo"].astype(str).str.upper().str.strip() == tu]
                        if not match.empty:
                            rm  = match.iloc[-1]
                            mot = str(rm.get("motivo","")).strip()
                            rev = str(rm.get("revisor","")).strip()
                            niv = str(rm.get("nivel_confirmado","")).strip()
                            st.markdown("---")
                            ca,cb = st.columns(2)
                            ca.markdown(f"**Aplica:** NO ❌")
                            cb.markdown(f"**Nivel:** {niv}")
                            if mot and mot.lower() not in ["nan","none",""]: st.info(f"💬 Observacion del Back: {mot}")
                            if rev and rev.lower() not in ["nan","none",""]: st.caption(f"Autorizado por: {rev}")
    with tab2:
        st.markdown("### Solicitar validacion al Back")
        with st.form("form_sol"):
            sn  = st.text_input("Tu nombre *", value=usuario_email.split("@")[0].replace("."," ").title())
            st2 = st.text_input("Titulo a validar *", value=titulo_input if "titulo_input" in dir() and titulo_input else "")
            su  = st.text_input("Universidad")
            sp  = st.selectbox("Pais",["Colombia","Venezuela","Ecuador","Peru","Otro"])
            ss  = st.text_area("Notas",height=60)
            sd  = st.file_uploader("Diploma (opcional)",type=["jpg","jpeg","png","pdf"])
            sbtn= st.form_submit_button("Enviar al Back",type="primary",use_container_width=True)
            if sbtn:
                if not sn.strip() or not st2.strip():
                    st.error("Nombre y titulo obligatorios.")
                else:
                    df_ck = leer_solicitudes(); tn = st2.strip().upper()
                    ya = False
                    if not df_ck.empty and "estado" in df_ck.columns:
                        tp = df_ck[df_ck["estado"]=="PENDIENTE"].get("titulo",pd.Series([])).str.upper().str.strip()
                        ya = tp.str.contains(tn[:20],na=False).any()
                    if ya:
                        st.warning(f"El titulo ya está PENDIENTE.")
                    else:
                        dp=""
                        if sd:
                            ext=Path(sd.name).suffix; fn=f"{uuid.uuid4().hex[:8]}{ext}"; (DIPLOMAS_DIR/fn).write_bytes(sd.read()); dp=fn
                        sid=guardar_solicitud(sn,st2,su,sp,dp,ss); st.cache_data.clear(); st.success(f"Solicitud #{sid} enviada.")

# ── INGRESAR DIPLOMA ─────────────────────────────────────────────
elif pagina == "Ingresar diploma":
    st.title("Ingresar diploma")
    with st.form("form_dip"):
        dn    = st.text_input("Tu nombre *", value=usuario_email.split("@")[0].replace("."," ").title())
        dt    = st.text_input("Titulo *")
        du    = st.text_input("Universidad")
        dpais = st.selectbox("Pais",["Colombia","Venezuela","Ecuador","Peru","Otro"])
        df2   = st.file_uploader("Diploma *",type=["jpg","jpeg","png","pdf"])
        dnotas= st.text_area("Observaciones",height=60)
        dsub  = st.form_submit_button("Cargar diploma",type="primary",use_container_width=True)
        if dsub:
            if not dn.strip() or not dt.strip() or not df2:
                st.error("Nombre, titulo y archivo obligatorios.")
            else:
                ext=Path(df2.name).suffix; fn=f"{uuid.uuid4().hex[:8]}{ext}"; (DIPLOMAS_DIR/fn).write_bytes(df2.read())
                sid=guardar_solicitud(dn,dt,du,dpais,fn,dnotas); st.cache_data.clear(); st.success(f"Diploma cargado. Solicitud #{sid} enviada.")

# ── REVISION BACK ────────────────────────────────────────────────
elif pagina == "Revision Back":
    st.markdown("## Revision Back")
    df_sol = leer_solicitudes()
    pend   = df_sol[df_sol["estado"]=="PENDIENTE"] if not df_sol.empty else pd.DataFrame()
    if pend.empty:
        st.success("No hay solicitudes pendientes.")
    else:
        st.info(f"{len(pend)} solicitud(es) esperando decision.")
        for _, row in pend.iterrows():
            td = row.get("titulo", row.get("nombre_titulo","Sin titulo"))
            nd = row.get("nombre", row.get("asesor",""))
            with st.expander(f"#{row['id']} - {td} - {nd} - {row['fecha']}"):
                cd,cf = st.columns([1,1])
                with cd:
                    st.markdown("**Documento adjunto**")
                    _dp = str(row.get("diploma_path","")).strip()
                    dp  = DIPLOMAS_DIR/_dp if _dp and _dp.lower() not in ["nan","none",""] else None
                    if dp and dp.exists():
                        if dp.suffix.lower() in [".jpg",".jpeg",".png"]: st.image(str(dp),use_container_width=True)
                        else:
                            with open(dp,"rb") as f: st.download_button("Descargar PDF",f.read(),file_name=dp.name)
                    else: st.caption("Sin documento.")
                with cf:
                    with st.form(f"fb_{row['id']}"):
                        bt = st.text_input("Titulo",value=td)
                        bu = st.text_input("Universidad",value=str(row.get("universidad","")))
                        bp = st.text_input("Pais",value=str(row.get("pais","Colombia")))
                        ba = st.radio("Aplica?",["Si","No"],horizontal=True,key=f"ba_{row['id']}")
                        bn = st.selectbox("Nivel",NIVELES,key=f"bn_{row['id']}")
                        br = st.text_input("Revisor",key=f"br_{row['id']}", value=usuario_email.split("@")[0].replace("."," ").upper())
                        bm = st.text_area("Observacion del Back Office",height=80,key=f"bm_{row['id']}")
                        bi = st.checkbox("Incorporar a base",value=True,key=f"bi_{row['id']}")
                        bs = st.form_submit_button("Guardar decision",type="primary",use_container_width=True)
                        if bs and bt.strip():
                            if not br.strip(): st.error("⚠️ El campo Revisor es obligatorio.")
                            elif not bm.strip(): st.error("⚠️ La Observacion es obligatoria.")
                            else:
                                av = (ba=="Si")
                                motor.guardar_decision(titulo=bt.strip().upper(),universidad=bu.strip().upper(),
                                    pais=bp,aplica=av,nivel=bn,revisor=br.strip(),motivo=bm.strip().replace(",",""),incorporar=bi)
                                actualizar_estado_solicitud(row["id"],"APROBADA" if av else "RECHAZADA")
                                if bi: get_motor.clear()
                                st.cache_data.clear(); st.success("Decision guardada."); st.rerun()

    st.divider(); st.markdown("### Historial decisiones Back")
    leer_decisiones.clear()
    dfd = leer_decisiones()
    if not dfd.empty:
        st.dataframe(dfd, use_container_width=True, hide_index=True)
        op = ["-- Seleccionar --"]+[f"Fila {i}: {r.get('nombre_titulo','')[:35]}" for i,r in dfd.iterrows()]
        se = st.selectbox("Fila a eliminar:",op,key="sel_e")
        if se!="-- Seleccionar --":
            fn_e = int(se.split(":")[0].replace("Fila","").strip())
            if st.button("Confirmar eliminacion",type="primary",key="btn_e"):
                dfd_fresh = leer_decisiones()
                d2 = dfd_fresh.drop(index=fn_e).reset_index(drop=True)
                if escribir_github("decisiones_back.csv",df_a_csv_seguro(d2),f"Eliminar fila {fn_e}"):
                    st.success("Eliminado."); st.cache_data.clear(); st.rerun()
    else: st.info("Sin decisiones.")

    st.divider(); st.markdown("### Editar decision existente")
    leer_decisiones.clear()
    dfe = leer_decisiones()
    if not dfe.empty:
        fc1,fc2 = st.columns(2)
        filtro_titulo  = fc1.text_input("🔍 Filtrar por nombre del título", key="filtro_titulo_ed", placeholder="Ej: TECNOLOGO EN SISTEMAS")
        filtro_estado  = fc2.selectbox("📋 Filtrar por estado",["Todos","✅ Aprobados","❌ Rechazados"],key="filtro_estado_ed")
        dfe_f = dfe.copy()
        if filtro_titulo.strip():
            dfe_f = dfe_f[dfe_f["nombre_titulo"].astype(str).str.upper().str.contains(filtro_titulo.strip().upper(),na=False)]
        if filtro_estado=="✅ Aprobados":
            dfe_f = dfe_f[dfe_f["decision_aplica"].astype(str).str.lower().isin(["true","1","si","yes"])]
        elif filtro_estado=="❌ Rechazados":
            dfe_f = dfe_f[~dfe_f["decision_aplica"].astype(str).str.lower().isin(["true","1","si","yes"])]
        st.caption(f"Mostrando {len(dfe_f)} de {len(dfe)} decisiones")
        if dfe_f.empty:
            st.info("No hay decisiones que coincidan con los filtros.")
        else:
            ope = ["-- Seleccionar --"]+[f"{r.get('nombre_titulo','')[:50]} | {r.get('universidad','')[:20]}" for i,r in dfe_f.iterrows()]
            see = st.selectbox("Decision a editar:",ope,key="sel_ed")
            titulo_sel = ""
            if see != "-- Seleccionar --":
                titulo_sel = see.split("|")[0].strip()
                mascara    = dfe["nombre_titulo"].astype(str).str.strip().str.upper() == titulo_sel.upper()
                if mascara.any():
                    fe_idx = int(dfe[mascara].index[0])
                    re_row = dfe.loc[fe_idx]
                    with st.form(f"fe_{titulo_sel[:15]}_{fe_idx}"):
                        et = st.text_input("Titulo",value=str(re_row.get("nombre_titulo","")))
                        eu = st.text_input("Universidad",value=str(re_row.get("universidad","")))
                        ea = st.radio("Aplica?",["Si","No"],horizontal=True,
                            index=0 if str(re_row.get("decision_aplica","")).lower() in ["true","1","si"] else 1,key="eaa")
                        niv_actual = str(re_row.get("nivel_confirmado","tecnico"))
                        en = st.selectbox("Nivel",NIVELES,index=NIVELES.index(niv_actual) if niv_actual in NIVELES else 0,key="enn")
                        er = st.text_input("Revisor",value=str(re_row.get("revisor","")),key="err")
                        em = st.text_area("Observacion",value=str(re_row.get("motivo","")),height=80,key="emm")
                        esb= st.form_submit_button("Guardar cambios",use_container_width=True,type="primary")
                        if esb and et.strip() and titulo_sel:
                            dfe_fresh = leer_decisiones()
                            m_f = dfe_fresh["nombre_titulo"].astype(str).str.strip().str.upper() == titulo_sel.upper()
                            if m_f.any():
                                ix = dfe_fresh[m_f].index[0]
                                dfe_fresh.at[ix,"nombre_titulo"]  = et.strip().upper()
                                dfe_fresh.at[ix,"universidad"]    = eu.strip().upper()
                                dfe_fresh.at[ix,"decision_aplica"]= (ea=="Si")
                                dfe_fresh.at[ix,"nivel_confirmado"]= en
                                dfe_fresh.at[ix,"revisor"]        = er.strip()
                                dfe_fresh.at[ix,"motivo"]         = em.strip().replace(",","")
                                if escribir_github("decisiones_back.csv",df_a_csv_seguro(dfe_fresh),f"Editar: {titulo_sel[:40]}"):
                                    st.success("Actualizado."); st.cache_data.clear(); st.rerun()
                else:
                    st.warning("No se encontró ese registro en la base.")
    else: st.info("Sin decisiones para editar.")

# ── CARGAR DATOS ─────────────────────────────────────────────────
elif pagina == "Cargar datos":
    st.title("Cargar datos")
    arch = st.file_uploader("CSV de titulos",type=["csv"])
    if arch:
        try:
            try: dfn = pd.read_csv(arch); st.dataframe(dfn.head(10),use_container_width=True)
            except UnicodeDecodeError:
                arch.seek(0); dfn = pd.read_csv(arch,encoding="latin-1"); st.dataframe(dfn.head(10),use_container_width=True)
            if st.button("Confirmar carga",type="primary"):
                dfn.columns=[c.lower().strip() for c in dfn.columns]
                if "nombre_titulo" not in dfn.columns and "titulo" in dfn.columns: dfn["nombre_titulo"]=dfn["titulo"]
                dfn["nombre_titulo"]=dfn["nombre_titulo"].astype(str).str.upper().str.strip()
                dfn=dfn.drop_duplicates(subset=["nombre_titulo"])
                if CSV_TITULOS.exists():
                    db=pd.read_csv(CSV_TITULOS); dt=pd.concat([db,dfn],ignore_index=True).drop_duplicates(subset=["nombre_titulo"])
                else: dt=dfn
                dt.to_csv(CSV_TITULOS,index=False)
                if escribir_github("titulos.csv",dt.to_csv(index=False),f"Carga: {len(dfn)} titulos"):
                    get_motor.clear(); st.cache_data.clear(); st.success(f"{len(dfn)} titulos cargados.")
        except Exception as e: st.error(f"Error: {e}")

# ── HISTORIAL ────────────────────────────────────────────────────
elif pagina == "Historial":
    st.title("Historial de validaciones")
    leer_decisiones.clear()
    dfh = leer_decisiones()
    if dfh.empty: st.info("Sin decisiones registradas.")
    else:
        bus = st.text_input("Buscar titulo o universidad")
        if bus.strip(): dfh = dfh[dfh.apply(lambda r: bus.upper() in str(r).upper(),axis=1)]
        st.dataframe(dfh,use_container_width=True,hide_index=True)
        st.caption(f"Total: {len(dfh)}")

# ── DASHBOARD ────────────────────────────────────────────────────
elif pagina == "Dashboard":
    st.title("Dashboard — ValidaTitulos")
    dfd=leer_decisiones(); dfs=leer_solicitudes()
    dfb=pd.read_csv(CSV_TITULOS) if CSV_TITULOS.exists() else pd.DataFrame()
    c1,c2,c3,c4=st.columns(4)
    td=len(dfd)
    an=int(dfd["decision_aplica"].astype(str).str.lower().isin(["true","1","si"]).sum()) if not dfd.empty and "decision_aplica" in dfd.columns else 0
    c1.metric("Titulos en base",len(dfb)); c2.metric("Decisiones Back",td); c3.metric("Aplican",an); c4.metric("No aplican",td-an)
    if td>0: st.progress(an/td, text=f"{round(an/td*100,1)}% aplican")
    if not dfd.empty:
        st.divider(); ca,cb=st.columns(2)
        with ca:
            st.markdown("**Titulos mas consultados**")
            top=dfd["nombre_titulo"].value_counts().head(10).reset_index(); top.columns=["Titulo","Decisiones"]
            st.dataframe(top,use_container_width=True,hide_index=True)
        with cb:
            st.markdown("**Decisiones por universidad**")
            if "universidad" in dfd.columns:
                unv=dfd["universidad"].value_counts().head(10).reset_index(); unv.columns=["Universidad","Decisiones"]
                st.dataframe(unv,use_container_width=True,hide_index=True)
        if "revisor" in dfd.columns:
            st.divider(); st.markdown("**Medicion del Back por revisor**")
            rv=dfd["revisor"].value_counts().reset_index(); rv.columns=["Revisor","Decisiones"]
            st.dataframe(rv,use_container_width=True,hide_index=True)
        if "fecha" in dfd.columns:
            st.divider(); st.markdown("**Decisiones por fecha**")
            dfd["fdia"]=pd.to_datetime(dfd["fecha"],errors="coerce").dt.date
            pf=dfd.groupby("fdia").size().reset_index(name="Decisiones"); st.bar_chart(pf.set_index("fdia"))
    if not dfs.empty:
        st.divider(); est=dfs["estado"].value_counts().reset_index(); est.columns=["Estado","Cantidad"]
        st.markdown("**Solicitudes por estado**"); st.dataframe(est,use_container_width=True,hide_index=True)

# ── ADMINISTRAR ROLES ────────────────────────────────────────────
elif pagina == "Administrar Roles":
    st.title("🔐 Administración de Roles y Accesos")
    st.info("Solo los administradores pueden modificar estos accesos.")

    roles_actuales = cargar_roles()
    tabs_r = st.tabs(["👁️ Ver Roles", "➕ Agregar Usuario", "✏️ Cambiar Rol", "❌ Revocar Acceso"])

    with tabs_r[0]:
        st.markdown("### Usuarios por Rol")
        for rol, label in [("admin","🔴 ADMINISTRATIVO"),("back","🟣 BACK OFFICE"),("validador","🔵 VALIDADORES")]:
            with st.expander(f"{label} — {len(roles_actuales.get(rol,[]))} usuarios"):
                for email in roles_actuales.get(rol,[]):
                    st.markdown(f"- {email}")

    with tabs_r[1]:
        st.markdown("### Agregar nuevo usuario")
        nuevo_email = st.text_input("Correo del usuario *", placeholder="nombre@bluhartmann.com", key="nuevo_email")
        nuevo_rol   = st.selectbox("Rol *",["validador","back","admin"],key="nuevo_rol")
        if st.button("Agregar usuario", type="primary", key="btn_agregar"):
            if not nuevo_email.strip():
                st.error("Ingresa el correo del usuario.")
            else:
                email_n = nuevo_email.strip().lower()
                rol_actual = obtener_rol(email_n, roles_actuales)
                if rol_actual:
                    st.warning(f"El usuario ya existe con rol: {rol_actual}")
                else:
                    roles_actuales[nuevo_rol].append(email_n)
                    guardar_roles_csv(roles_actuales)
                    st.success(f"✅ {email_n} agregado como {nuevo_rol}")
                    st.rerun()

    with tabs_r[2]:
        st.markdown("### Cambiar rol de usuario existente")
        todos_emails = []
        for lista in roles_actuales.values(): todos_emails.extend(lista)
        todos_emails = sorted(todos_emails)
        email_cambiar = st.selectbox("Seleccionar usuario", ["-- Seleccionar --"]+todos_emails, key="email_cambiar")
        if email_cambiar != "-- Seleccionar --":
            rol_act = obtener_rol(email_cambiar, roles_actuales)
            st.info(f"Rol actual: **{rol_act}**")
            nuevo_rol_c = st.selectbox("Nuevo rol",["validador","back","admin"],key="nuevo_rol_c")
            if st.button("Cambiar rol", type="primary", key="btn_cambiar"):
                for rol in roles_actuales:
                    if email_cambiar in roles_actuales[rol]:
                        roles_actuales[rol].remove(email_cambiar)
                roles_actuales[nuevo_rol_c].append(email_cambiar)
                guardar_roles_csv(roles_actuales)
                st.success(f"✅ Rol de {email_cambiar} cambiado a {nuevo_rol_c}")
                st.rerun()

    with tabs_r[3]:
        st.markdown("### Revocar acceso de usuario")
        todos_e2 = []
        for lista in roles_actuales.values(): todos_e2.extend(lista)
        todos_e2 = sorted(todos_e2)
        email_rev = st.selectbox("Seleccionar usuario a revocar",["-- Seleccionar --"]+todos_e2,key="email_rev")
        if email_rev != "-- Seleccionar --" and email_rev not in ["lady.quinones@bluhartmann.com","jessica.romero@bluhartmann.com"]:
            st.warning(f"⚠️ Se eliminará el acceso de {email_rev}")
            if st.button("Revocar acceso",type="primary",key="btn_rev"):
                for rol in roles_actuales:
                    if email_rev in roles_actuales[rol]:
                        roles_actuales[rol].remove(email_rev)
                guardar_roles_csv(roles_actuales)
                st.success(f"✅ Acceso revocado para {email_rev}")
                st.rerun()
        elif email_rev in ["lady.quinones@bluhartmann.com","jessica.romero@bluhartmann.com"]:
            st.error("❌ No se puede revocar el acceso a los administradores principales.")

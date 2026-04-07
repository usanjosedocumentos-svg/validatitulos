""" app.py - ValidaTitulos - Sistema de roles v2 | Deploy corregido """
import streamlit as st
import io, csv as _csv, unicodedata, re
import pandas as pd
from pathlib import Path
import uuid, urllib.request, urllib.error, json, base64
from datetime import datetime, timezone
from validador import ValidadorCSV, CSV_TITULOS, CSV_DECISIONES

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
    "admin": ["lady.quinones@bluhartmann.com","jessica.romero@bluhartmann.com"]
}
PERMISOS = {
    "validador": ["Validar titulo", "Ingresar diploma", "Historial"],
    "back":      ["Validar titulo", "Ingresar diploma", "Revision Back", "Historial"],
    "admin":     ["Validar titulo", "Ingresar diploma", "Revision Back", "Cargar datos", "Historial", "Dashboard", "Administrar Roles"]
}
ROL_LABELS = {"validador":"VALIDADOR","back":"BACK OFFICE","admin":"ADMINISTRADOR"}
ROL_CSS    = {"validador":"#1d4ed8","back":"#7c3aed","admin":"#dc2626"}
BASE_DIR         = Path(__file__).parent
CSV_ROLES        = BASE_DIR / "roles_usuarios.csv"
CSV_CONTADOR     = BASE_DIR / "consultas_contador.csv"
CSV_SOLICITUDES  = BASE_DIR / "solicitudes_pendientes.csv"
DIPLOMAS_DIR     = BASE_DIR / "diplomas"
DIPLOMAS_DIR.mkdir(exist_ok=True)
NIVELES = ["bachillerato","tecnico","tecnologo","universitario","especializacion","maestria","doctorado"]

def df_a_csv_seguro(df):
    df = df.copy()
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.replace("\n"," ",regex=False).str.replace("\r"," ",regex=False)
    buf = io.StringIO()
    df.to_csv(buf, index=False, quoting=_csv.QUOTE_ALL)
    return buf.getvalue()

def escribir_github(nombre_archivo, contenido, mensaje_commit):
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo  = st.secrets["GITHUB_REPO"]
        url = f"https://api.github.com/repos/{repo}/contents/{nombre_archivo}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as r:
                sha = json.loads(r.read())["sha"]
        except urllib.error.HTTPError as e:
            sha = None if e.code == 404 else (_ for _ in ()).throw(e)
        b64 = base64.b64encode(contenido.encode("utf-8")).decode("utf-8")
        body = {"message": mensaje_commit, "content": b64}
        if sha:
            body["sha"] = sha
        request = urllib.request.Request(url, data=json.dumps(body).encode(), method="PUT",
            headers={**headers, "Content-Type":"application/json"})
        urllib.request.urlopen(request)
        return True
    except Exception as e:
        st.error(f"Error GitHub: {e}")
        return False

def cargar_roles():
    if CSV_ROLES.exists():
        try:
            df = pd.read_csv(CSV_ROLES)
            roles = {k:[] for k in ROLES_DEFAULT}
            for _,row in df.iterrows():
                rol=str(row.get("rol","")).strip().lower()
                email=str(row.get("email","")).strip().lower()
                if rol in roles and email:
                    roles[rol].append(email)
            return roles
        except:
            pass
    return {k:list(v) for k,v in ROLES_DEFAULT.items()}

def guardar_roles_csv(roles_dict):
    filas = [{"rol":rol,"email":email} for rol,lst in roles_dict.items() for email in lst]
    df = pd.DataFrame(filas)
    df.to_csv(CSV_ROLES,index=False)
    escribir_github("roles_usuarios.csv",df.to_csv(index=False),"Actualizar roles")

def obtener_rol(email, roles):
    email = email.lower().strip()
    for rol,lista in roles.items():
        if email in [e.lower().strip() for e in lista]:
            return rol
    return None

@st.cache_data(ttl=60)
def leer_contador():
    try:
        if CSV_CONTADOR.exists():
            df = pd.read_csv(CSV_CONTADOR)
            if "fecha" not in df.columns:
                df["fecha"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            return df
    except:
        pass
    return pd.DataFrame(columns=["titulo","fecha","consultas"])

def registrar_consulta(titulo):
    try:
        df = leer_contador()
        titulo = str(titulo).strip().upper()
        if not titulo:
            return
        nueva = pd.DataFrame([{"titulo":titulo,"fecha":datetime.now(timezone.utc).strftime("%Y-%m-%d"),"consultas":1}])
        df = pd.concat([df,nueva],ignore_index=True)
        df.to_csv(CSV_CONTADOR,index=False)
        escribir_github("consultas_contador.csv",df_a_csv_seguro(df),f"Consulta: {titulo[:40]}")
        leer_contador.clear()
    except:
        pass

@st.cache_data(ttl=30)
def leer_solicitudes():
    if CSV_SOLICITUDES.exists():
        try:
            df = pd.read_csv(CSV_SOLICITUDES)
            if "titulo" not in df.columns and "nombre_titulo" in df.columns:
                df["titulo"]=df["nombre_titulo"]
            if "nombre" not in df.columns and "asesor" in df.columns:
                df["nombre"]=df["asesor"]
            return df
        except:
            pass
    return pd.DataFrame(columns=["id","titulo","nombre_titulo","universidad","pais","nombre","asesor","fecha","estado","diploma_path","notas","motivo_rechazo"])

def guardar_solicitud(nombre,titulo,universidad,pais,diploma_path,notas=""):
    df = leer_solicitudes()
    nid = str(uuid.uuid4())[:8].upper()
    nueva = {"id":nid,"fecha":datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "nombre":nombre.strip().upper(),"asesor":nombre.strip().upper(),
        "titulo":titulo.strip().upper(),"nombre_titulo":titulo.strip().upper(),
        "universidad":universidad.strip().upper() if universidad else "",
        "pais":pais,"estado":"PENDIENTE","diploma_path":str(diploma_path) if diploma_path else "","notas":notas,"motivo_rechazo":""}
    df = pd.concat([df,pd.DataFrame([nueva])],ignore_index=True)
    df.to_csv(CSV_SOLICITUDES,index=False)
    escribir_github("solicitudes_pendientes.csv",df_a_csv_seguro(df),f"Add: {titulo.strip().upper()[:40]}")
    return nid

def actualizar_estado_solicitud(sol_id,nuevo_estado):
    df = leer_solicitudes()
    df.loc[df["id"]==sol_id,"estado"]=nuevo_estado
    df.to_csv(CSV_SOLICITUDES,index=False)
    escribir_github("solicitudes_pendientes.csv",df_a_csv_seguro(df),f"Update {sol_id}: {nuevo_estado}")

def get_motor():
    token = st.secrets.get("GITHUB_TOKEN","")
    repo  = st.secrets.get("GITHUB_REPO","")
    return ValidadorCSV(token=token, repo=repo)

st.set_page_config(page_title="ValidaTitulos",layout="wide",page_icon="🎓")
st.markdown("""<style>
[data-testid="stSidebar"]{background:#111827;}
[data-testid="stSidebar"] *{color:#f3f4f6 !important;}
.btn-pend{background:#f97316;color:#fff;border-radius:8px;padding:10px 0;font-weight:700;font-size:1rem;text-align:center;margin-bottom:8px;}
</style>""",unsafe_allow_html=True)

roles_config = cargar_roles()
if "u_email" not in st.session_state: st.session_state.u_email = ""
if "u_rol" not in st.session_state: st.session_state.u_rol = None

if not st.session_state.u_email:
    _,col,_ = st.columns([1,2,1])
    with col:
        st.markdown("<br><br>",unsafe_allow_html=True)
        st.image("https://img.icons8.com/color/96/diploma.png",width=80)
        st.markdown("## 🎓 ValidaTitulos")
        em = st.text_input("Correo",placeholder="nombre@bluhartmann.com",key="inp_email",label_visibility="collapsed")
        if st.button("Ingresar",type="primary",use_container_width=True):
            if em.strip():
                rol = obtener_rol(em.strip(),roles_config)
                if rol:
                    st.session_state.u_email = em.strip().lower()
                    st.session_state.u_rol = rol
                    st.rerun()
                else:
                    st.error("Correo no autorizado.")
            else:
                st.warning("Ingresa tu correo.")
    st.stop()

u_email = st.session_state.u_email
u_rol   = st.session_state.u_rol
paginas = PERMISOS.get(u_rol,[])

with st.sidebar:
    st.markdown("<div style='font-size:1.3rem;font-weight:700'>🎓 ValidaTitulos</div>",unsafe_allow_html=True)
    st.caption("Sistema de uso interno")
    color = ROL_CSS.get(u_rol,"#6b7280")
    st.markdown(f"<div style='background:{color};color:#fff;border-radius:8px;padding:4px 10px;font-size:0.8rem;font-weight:600;margin-bottom:6px'>👤 {ROL_LABELS.get(u_rol,'')} - {u_email.split('@')[0]}</div>",unsafe_allow_html=True)
    df_sol_sb = leer_solicitudes()
    n_pend = len(df_sol_sb[df_sol_sb["estado"]=="PENDIENTE"]) if not df_sol_sb.empty and u_rol in ["back","admin"] else 0
    if n_pend:
        st.markdown(f"<div class='btn-pend'>PENDIENTES BACK: {n_pend}</div>",unsafe_allow_html=True)
    pagina = st.radio("Nav",paginas,label_visibility="collapsed")
    if st.button("Cerrar sesion",use_container_width=True):
        st.session_state.u_email=""
        st.session_state.u_rol=None
        st.rerun()
    st.divider()

motor = get_motor()

if pagina=="Validar titulo":
    st.title("Validar titulo academico")
    tab1,tab2 = st.tabs(["Consultar titulo","Solicitar validacion al Back"])
    with tab1:
        st.info("Ingresa el titulo para verificar si ya existe decision del Back.")
        c1,c2 = st.columns([2,1])
        titulo_input = c1.text_input("Nombre del titulo *",placeholder="Ej: Tecnologo en Mercadeo")
        univ_input   = c2.text_input("Universidad (opcional)",placeholder="Ej: SENA")
        if st.button("Consultar",type="primary",use_container_width=True):
            if not titulo_input.strip():
                st.warning("Ingresa el nombre del titulo.")
            else:
                tu = titulo_input.strip().upper()
                motor.recargar()
                res = motor.validar(tu)
                registrar_consulta(tu)
                if res.requiere_revision:
                    st.warning("No encontrado. Solicita validacion al Back.")
                elif res.aplica:
                    st.success(f"APLICA - Nivel: {res.nivel or ''}")
                    if res.razon:
                        st.info(f"Observacion: {res.razon}")
                else:
                    st.error(f"NO APLICA - Nivel: {res.nivel or ''}")
                    if res.razon:
                        st.info(f"Observacion: {res.razon}")
    with tab2:
        st.markdown("### Solicitar validacion al Back")
        with st.form("form_sol"):
            sn  = st.text_input("Tu nombre *",value=u_email.split("@")[0].replace("."," ").title())
            st2 = st.text_input("Titulo *")
            su  = st.text_input("Universidad")
            sp  = st.selectbox("Pais",["Colombia","Venezuela","Ecuador","Peru","Otro"])
            ss  = st.text_area("Notas",height=60)
            sd  = st.file_uploader("Diploma (opcional)",type=["jpg","jpeg","png","pdf"])
            if st.form_submit_button("Enviar al Back",type="primary",use_container_width=True):
                if not sn.strip() or not st2.strip():
                    st.error("Nombre y titulo obligatorios.")
                else:
                    dp=""
                    if sd:
                        ext=Path(sd.name).suffix
                        fn=f"{uuid.uuid4().hex[:8]}{ext}"
                        (DIPLOMAS_DIR/fn).write_bytes(sd.read())
                        dp=fn
                    sid=guardar_solicitud(sn,st2,su,sp,dp,ss)
                    st.cache_data.clear()
                    st.success(f"Solicitud #{sid} enviada.")

elif pagina=="Ingresar diploma":
    st.title("Ingresar diploma")
    with st.form("form_dip"):
        dn=st.text_input("Tu nombre *",value=u_email.split("@")[0].replace("."," ").title())
        dt=st.text_input("Titulo *")
        du=st.text_input("Universidad")
        dpais=st.selectbox("Pais",["Colombia","Venezuela","Ecuador","Peru","Otro"])
        df2=st.file_uploader("Diploma *",type=["jpg","jpeg","png","pdf"])
        dnotas=st.text_area("Observaciones",height=60)
        if st.form_submit_button("Cargar diploma",type="primary",use_container_width=True):
            if not dn.strip() or not dt.strip() or not df2:
                st.error("Nombre, titulo y archivo son obligatorios.")
            else:
                ext=Path(df2.name).suffix
                fn=f"{uuid.uuid4().hex[:8]}{ext}"
                (DIPLOMAS_DIR/fn).write_bytes(df2.read())
                sid=guardar_solicitud(dn,dt,du,dpais,fn,dnotas)
                st.cache_data.clear()
                st.success(f"Diploma cargado. #{sid}")

elif pagina=="Revision Back":
    st.title("Revision Back")
    df_sol=leer_solicitudes()
    pend=df_sol[df_sol["estado"]=="PENDIENTE"] if not df_sol.empty else pd.DataFrame()
    if pend.empty:
        st.success("No hay solicitudes pendientes.")
    else:
        st.info(f"{len(pend)} solicitud(es) pendiente(s).")
        for _,row in pend.iterrows():
            td=row.get("titulo",row.get("nombre_titulo","Sin titulo"))
            nd=row.get("nombre",row.get("asesor",""))
            with st.expander(f"#{row['id']} - {td} - {nd} - {row['fecha']}"):
                cd,cf=st.columns([1,1])
                with cd:
                    st.markdown("**Documento adjunto**")
                    _dp=str(row.get("diploma_path","")).strip()
                    dp=DIPLOMAS_DIR/_dp if _dp and _dp not in ["nan","None",""] else None
                    if dp and dp.exists():
                        if dp.suffix.lower() in [".jpg",".jpeg",".png"]:
                            st.image(str(dp),use_container_width=True)
                        else:
                            with open(dp,"rb") as f:
                                st.download_button("Descargar PDF",f.read(),file_name=dp.name)
                    else:
                        st.caption("Sin documento.")
                with cf:
                    with st.form(f"fb_{row['id']}"):
                        bt=st.text_input("Titulo",value=td)
                        bu=st.text_input("Universidad",value=str(row.get("universidad","")))
                        bp=st.text_input("Pais",value=str(row.get("pais","Colombia")))
                        ba=st.radio("Aplica?",["Si","No"],horizontal=True,key=f"ba_{row['id']}")
                        bn=st.selectbox("Nivel",NIVELES,key=f"bn_{row['id']}")
                        br=st.text_input("Revisor",value=u_email.split("@")[0].replace("."," ").upper(),key=f"br_{row['id']}")
                        bm=st.text_area("Observacion del Back *",height=80,key=f"bm_{row['id']}")
                        if st.form_submit_button("Guardar decision",type="primary",use_container_width=True):
                            if not br.strip():
                                st.error("Revisor obligatorio.")
                            elif not bm.strip():
                                st.error("Observacion obligatoria.")
                            else:
                                motor.guardar_decision(
                                    titulo=bt.strip().upper(),
                                    universidad=bu.strip().upper(),
                                    pais=bp,aplica=(ba=="Si"),nivel=bn,
                                    revisor=br.strip(),motivo=bm.strip().replace(",",""))
                                actualizar_estado_solicitud(row["id"],"APROBADA" if ba=="Si" else "RECHAZADA")
                                st.cache_data.clear()
                                st.success("Decision guardada correctamente.")
                                st.rerun()
    st.divider()
    st.markdown("### Historial decisiones Back")
    dfd=pd.read_csv(CSV_DECISIONES) if CSV_DECISIONES.exists() else pd.DataFrame()
    if not dfd.empty:
        st.dataframe(dfd,use_container_width=True,hide_index=True)
    else:
        st.info("Sin decisiones registradas.")

elif pagina=="Cargar datos":
    st.title("Cargar datos")
    arch=st.file_uploader("CSV de titulos",type=["csv"])
    if arch:
        try:
            try: dfn=pd.read_csv(arch)
            except UnicodeDecodeError: arch.seek(0); dfn=pd.read_csv(arch,encoding="latin-1")
            st.dataframe(dfn.head(10),use_container_width=True)
            if st.button("Confirmar carga",type="primary"):
                dfn.columns=[c.lower().strip() for c in dfn.columns]
                if "nombre_titulo" not in dfn.columns and "titulo" in dfn.columns:
                    dfn["nombre_titulo"]=dfn["titulo"]
                dfn["nombre_titulo"]=dfn["nombre_titulo"].astype(str).str.upper().str.strip()
                dfn=dfn.drop_duplicates(subset=["nombre_titulo"])
                dt=pd.concat([pd.read_csv(CSV_TITULOS),dfn],ignore_index=True).drop_duplicates(subset=["nombre_titulo"]) if CSV_TITULOS.exists() else dfn
                dt.to_csv(CSV_TITULOS,index=False)
                if escribir_github("titulos.csv",dt.to_csv(index=False),f"Carga: {len(dfn)} titulos"):
                    st.cache_data.clear()
                    st.success(f"{len(dfn)} titulos cargados.")
        except Exception as e:
            st.error(f"Error: {e}")

elif pagina=="Historial":
    st.title("Historial de validaciones")
    dfh=pd.read_csv(CSV_DECISIONES) if CSV_DECISIONES.exists() else pd.DataFrame()
    if dfh.empty:
        st.info("Sin decisiones registradas.")
    else:
        bus=st.text_input("Buscar titulo o universidad")
        if bus.strip():
            dfh=dfh[dfh.apply(lambda r: bus.upper() in str(r).upper(),axis=1)]
        st.dataframe(dfh,use_container_width=True,hide_index=True)
        st.caption(f"Total: {len(dfh)}")

elif pagina=="Dashboard":
    st.title("Dashboard - ValidaTitulos")
    dfd=pd.read_csv(CSV_DECISIONES) if CSV_DECISIONES.exists() else pd.DataFrame()
    dfs=leer_solicitudes()
    dfb=pd.read_csv(CSV_TITULOS) if CSV_TITULOS.exists() else pd.DataFrame()
    c1,c2,c3,c4=st.columns(4)
    td=len(dfd)
    an=int(dfd["decision_aplica"].astype(str).str.lower().isin(["true","1","si"]).sum()) if not dfd.empty and "decision_aplica" in dfd.columns else 0
    c1.metric("Titulos en base",len(dfb)); c2.metric("Decisiones Back",td); c3.metric("Aplican",an); c4.metric("No aplican",td-an)
    if td>0: st.progress(an/td,text=f"{round(an/td*100,1)}% aplican")
    if not dfd.empty:
        st.divider(); ca,cb=st.columns(2)
        with ca:
            st.markdown("**Mas consultados**")
            st.dataframe(dfd["nombre_titulo"].value_counts().head(10).reset_index().rename(columns={"nombre_titulo":"Titulo","count":"N"}),use_container_width=True,hide_index=True)
        with cb:
            if "universidad" in dfd.columns:
                st.markdown("**Por universidad**")
                st.dataframe(dfd["universidad"].value_counts().head(10).reset_index().rename(columns={"universidad":"Universidad","count":"N"}),use_container_width=True,hide_index=True)

elif pagina=="Administrar Roles":
    st.title("Administracion de Roles")
    roles_actuales=cargar_roles()
    t1,t2,t3,t4=st.tabs(["Ver Roles","Agregar","Cambiar Rol","Revocar"])
    with t1:
        for rol,label in [("admin","ADMINISTRATIVO"),("back","BACK OFFICE"),("validador","VALIDADORES")]:
            with st.expander(f"{label} - {len(roles_actuales.get(rol,[]))} usuarios"):
                for email in sorted(roles_actuales.get(rol,[])): st.markdown(f"- {email}")
    with t2:
        ne=st.text_input("Correo del nuevo usuario *",placeholder="nombre@bluhartmann.com")
        nr=st.selectbox("Rol *",["validador","back","admin"])
        if st.button("Agregar usuario",type="primary"):
            if not ne.strip(): st.error("Ingresa el correo.")
            else:
                em_n=ne.strip().lower()
                if obtener_rol(em_n,roles_actuales): st.warning(f"Ya existe: {obtener_rol(em_n,roles_actuales)}")
                else:
                    roles_actuales[nr].append(em_n); guardar_roles_csv(roles_actuales)
                    st.success(f"{em_n} agregado como {nr}"); st.rerun()
    with t3:h
        todos=[e for lst in roles_actuales.values() for e in lst]
        ec=st.selectbox("Usuario",["-- Seleccionar --"]+sorted(todos))
        if ec!="-- Seleccionar --":
            st.info(f"Rol actual: {obtener_rol(ec,roles_actuales)}")
            nrc=st.selectbox("Nuevo rol",["validador","back","admin"])
            if st.button("Cambiar rol",type="primary"):
                for r in roles_actuales:
                    if ec in roles_actuales[r]: roles_actuales[r].remove(ec)
                roles_actuales[nrc].append(ec); guardar_roles_csv(roles_actuales)
                st.success(f"{ec} ahora es {nrc}"); st.rerun()
    with t4:
        ADMINS_PROT=["lady.quinones@bluhartmann.com","jessica.romero@bluhartmann.com"]
        todos2=[e for lst in roles_actuales.values() for e in lst if e not in ADMINS_PROT]
        er2=st.selectbox("Usuario a revocar",["-- Seleccionar --"]+sorted(todos2))
        if er2!="-- Seleccionar --":
            st.warning(f"Se revocara acceso de: {er2}")
            if st.button("Confirmar revocacion",type="primary"):
                for r in roles_actuales:
                    if er2 in roles_actuales[r]: roles_actuales[r].remove(er2)
                guardar_roles_csv(roles_actuales); st.success(f"Acceso revocado: {er2}"); st.rerun()
        st.info("Los administradores principales no pueden ser revocados.")

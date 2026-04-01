"""
app.py - ValidaTitulos - Interfaz Streamlit
"""
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

def normalizar(texto: str) -> str:
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()

def similitud_bigramas(a: str, b: str) -> float:
    def bigs(s):
        s = normalizar(s)
        return set(s[i:i+2] for i in range(len(s)-1)) if len(s) > 1 else {s}
    ba, bb = bigs(a), bigs(b)
    if not ba or not bb: return 0.0
    return 2 * len(ba & bb) / (len(ba) + len(bb))


BASE_DIR        = Path(__file__).parent
CSV_PENDIENTES  = BASE_DIR / "pendientes_back.csv"
CSV_SOLICITUDES = BASE_DIR / "solicitudes_pendientes.csv"
DIPLOMAS_DIR    = BASE_DIR / "diplomas"
DIPLOMAS_DIR.mkdir(exist_ok=True)
NIVELES = ["bachillerato","tecnico","tecnologo","universitario","especializacion","maestria","doctorado"]


def df_a_csv_seguro(df: pd.DataFrame) -> str:
    """Convierte DataFrame a CSV con QUOTE_ALL para proteger campos con comas."""
    df = df.copy()
    for col in df.select_dtypes(include="object").columns:
        df[col] = (df[col].astype(str)
                   .str.replace("\n", " ", regex=False)
                   .str.replace("\r", " ", regex=False))
    buf = io.StringIO()
    df.to_csv(buf, index=False, quoting=_csv.QUOTE_ALL)
    return buf.getvalue()

def escribir_github(nombre_archivo, contenido, mensaje_commit):
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo  = st.secrets["GITHUB_REPO"]
        url   = f"https://api.github.com/repos/{repo}/contents/{nombre_archivo}"
        req_g = urllib.request.Request(url, headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"})
        try:
            with urllib.request.urlopen(req_g) as r: sha = json.loads(r.read())["sha"]
        except urllib.error.HTTPError as e:
            sha = None if e.code == 404 else (_ for _ in ()).throw(e)
        b64 = base64.b64encode(contenido.encode("utf-8")).decode("utf-8")
        body = {"message": mensaje_commit, "content": b64}
        if sha: body["sha"] = sha
        req_p = urllib.request.Request(url, data=json.dumps(body).encode(), method="PUT",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json", "Content-Type": "application/json"})
        with urllib.request.urlopen(req_p): pass
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

@st.cache_data(ttl=30)
def leer_decisiones():
    try: return pd.read_csv(CSV_DECISIONES) if CSV_DECISIONES.exists() else pd.DataFrame()
    except: return pd.DataFrame()

def guardar_solicitud(nombre, titulo, universidad, pais, diploma_path, notas=""):
    df = leer_solicitudes()
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

st.set_page_config(page_title="ValidaTitulos", layout="wide", page_icon="🎓")
st.markdown("""<style>
.btn-pendiente{background:#f97316;color:#fff;border-radius:8px;padding:10px 0;font-weight:700;font-size:1rem;text-align:center;margin-bottom:8px;}
[data-testid="stSidebar"]{background:#111827;}
[data-testid="stSidebar"] *{color:#f3f4f6 !important;}
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<div style='font-size:1.3rem;font-weight:700;margin-bottom:4px'>🎓 ValidaTitulos</div>", unsafe_allow_html=True)
    st.caption("Sistema de uso interno")
    df_sol_sb = leer_solicitudes()
    n_pend = len(df_sol_sb[df_sol_sb["estado"]=="PENDIENTE"]) if not df_sol_sb.empty else 0
    if n_pend:
        st.markdown(f"<div class='btn-pendiente'>PENDIENTES BACK: {n_pend}</div>", unsafe_allow_html=True)
    pagina = st.radio("Navegacion", ["Validar titulo","Ingresar diploma","Revision Back","Cargar datos","Historial","Dashboard"], label_visibility="collapsed")
    st.divider()
    df_d = leer_decisiones()
    if df_d.empty:
        st.info("No hay decisiones registradas aun.")
    else:
        aplica_col = "decision_aplica" if "decision_aplica" in df_d.columns else "aplica"
        nivel_col  = "nivel_confirmado" if "nivel_confirmado" in df_d.columns else "nivel"
        df_d["_ap"]  = df_d[aplica_col].astype(str).str.lower().isin(["true","1","si"])
        df_d["_niv"] = df_d[nivel_col].astype(str).str.lower().str.strip()
        total      = len(df_d)
        aplican    = int(df_d["_ap"].sum())
        no_aplican = total - aplican
        tecnicos   = int(df_d["_niv"].str.contains("tecnico",  na=False).sum())
        tecnologos = int(df_d["_niv"].str.contains("tecnologo", na=False).sum())
        univ       = int(df_d["_niv"].str.contains("universitario", na=False).sum())
        bach       = int(df_d["_niv"].str.contains("bachillerato", na=False).sum())
        tec_ap     = int(df_d[df_d["_niv"].str.contains("tecnico", na=False)]["_ap"].sum())
        tec_no     = tecnicos  - tec_ap
        tlog_ap    = int(df_d[df_d["_niv"].str.contains("tecnologo", na=False)]["_ap"].sum())
        tlog_no    = tecnologos - tlog_ap
        pct_ap     = round(aplican/total*100, 1) if total else 0
        pct_no     = round(no_aplican/total*100, 1) if total else 0

        st.markdown("### 📊 Resumen General")
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("📋 Total Títulos",          total)
        m2.metric("✅ Aplican",                aplican,    delta=f"{pct_ap}%")
        m3.metric("❌ No Aplican",             no_aplican, delta=f"-{pct_no}%", delta_color="inverse")
        m4.metric("🎓 Técnicos + Tecnólogos",  tecnicos + tecnologos)
        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🥧 Distribución Aplica / No Aplica")
            html_pie1 = (
                "<div style='background:#1e293b;border-radius:12px;padding:16px'>"
                "<canvas id='pie1' width='320' height='260'></canvas></div>"
                "<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>"
                "<script>new Chart(document.getElementById('pie1'),{"
                "type:'doughnut',"
                "data:{labels:['✅ Aplica','❌ No Aplica'],"
                "datasets:[{data:[" + str(aplican) + "," + str(no_aplican) + "],"
                "backgroundColor:['#22c55e','#ef4444'],borderWidth:2,borderColor:'#0f172a'}]},"
                "options:{plugins:{legend:{position:'bottom',labels:{color:'#f1f5f9',font:{size:13}}},"
                "tooltip:{callbacks:{label:function(c){return c.label+': '+c.raw+' ('+Math.round(c.raw/" + str(total) + "*100)+'%)'}}}},"
                "cutout:'55%'}});</script>"
            )
            st.components.v1.html(html_pie1, height=300)

        with col2:
            st.markdown("#### 📊 Títulos por Nivel")
            html_bar1 = (
                "<div style='background:#1e293b;border-radius:12px;padding:16px'>"
                "<canvas id='bar1' width='320' height='260'></canvas></div>"
                "<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>"
                "<script>new Chart(document.getElementById('bar1'),{"
                "type:'bar',"
                "data:{labels:['T\u00e9cnico','Tecn\u00f3logo','Universitario','Bachillerato'],"
                "datasets:[{label:'Cantidad',data:[" + str(tecnicos) + "," + str(tecnologos) + "," + str(univ) + "," + str(bach) + "],"
                "backgroundColor:['#3b82f6','#8b5cf6','#f59e0b','#6b7280'],borderRadius:6,borderWidth:0}]},"
                "options:{plugins:{legend:{display:false}},"
                "scales:{x:{ticks:{color:'#f1f5f9'},grid:{color:'#334155'}},"
                "y:{ticks:{color:'#f1f5f9',stepSize:5},grid:{color:'#334155'},beginAtZero:true}}}});</script>"
            )
            st.components.v1.html(html_bar1, height=300)

        st.markdown("---")
        st.markdown("#### Técnicos vs Tecnólogos — Detalle Aplica / No Aplica")
        col3, col4 = st.columns(2)
        with col3:
            st.markdown("**🔵 Técnicos — Total: " + str(tecnicos) + "**")
            html_tec = (
                "<div style='background:#1e293b;border-radius:12px;padding:12px;text-align:center'>"
                "<canvas id='pie_tec' width='260' height='220'></canvas></div>"
                "<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>"
                "<script>new Chart(document.getElementById('pie_tec'),{"
                "type:'doughnut',"
                "data:{labels:['✅ Aplica','❌ No Aplica'],"
                "datasets:[{data:[" + str(tec_ap) + "," + str(tec_no) + "],"
                "backgroundColor:['#22c55e','#ef4444'],borderWidth:2,borderColor:'#0f172a'}]},"
                "options:{plugins:{legend:{position:'bottom',labels:{color:'#f1f5f9',font:{size:12}}}},cutout:'50%'}});</script>"
            )
            st.components.v1.html(html_tec, height=270)
        with col4:
            st.markdown("**🟣 Tecnólogos — Total: " + str(tecnologos) + "**")
            html_tlog = (
                "<div style='background:#1e293b;border-radius:12px;padding:12px;text-align:center'>"
                "<canvas id='pie_tlog' width='260' height='220'></canvas></div>"
                "<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>"
                "<script>new Chart(document.getElementById('pie_tlog'),{"
                "type:'doughnut',"
                "data:{labels:['✅ Aplica','❌ No Aplica'],"
                "datasets:[{data:[" + str(tlog_ap) + "," + str(tlog_no) + "],"
                "backgroundColor:['#8b5cf6','#ef4444'],borderWidth:2,borderColor:'#0f172a'}]},"
                "options:{plugins:{legend:{position:'bottom',labels:{color:'#f1f5f9',font:{size:12}}}},cutout:'50%'}});</script>"
            )
            st.components.v1.html(html_tlog, height=270)

    if st.button("Recargar base", use_container_width=True):
        get_motor.clear(); st.cache_data.clear(); st.rerun()

motor = get_motor()
if pagina == "Validar titulo":
    st.title("Validar titulo academico")
    if n_pend: st.info(f"El Back tiene {n_pend} solicitud(es) pendiente(s) para aprobar.")
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
                tu = titulo_input.strip().upper(); uu = univ_input.strip().upper()
                res = motor.validar(tu, uu if uu else None)
                if res is None or res.requiere_revision:
                    st.warning("⚠️ Titulo no encontrado en la base. Puedes solicitar validacion al Back.")
                elif res.aplica:
                    st.success(f"✅ APLICA — Nivel: {res.nivel if res.nivel else ''}")
                    df_dc = leer_decisiones()
                    if not df_dc.empty:
                        match = df_dc[df_dc["nombre_titulo"].str.upper().str.strip() == tu]
                        if not match.empty:
                            rm = match.iloc[-1]
                            mot = str(rm.get("motivo","")).strip(); rev = str(rm.get("revisor","")).strip()
                            ap  = str(rm.get("decision_aplica","")).strip()
                            niv = str(rm.get("nivel_confirmado","")).strip()
                            ap_bool = ap.lower() in ["true","1","si"]
                            if ap_bool and mot and mot.lower() not in ["nan","none",""]:
                                st.markdown("---"); st.markdown("### Informacion del Back Office")
                                ca,cb = st.columns(2)
                                ca.markdown(f"**Aplica:** SI")
                                cb.markdown(f"**Nivel:** {niv}")
                                st.info(f"💬 Observacion del Back Office: {mot}")
                                if rev and rev.lower() not in ["nan","none",""]:
                                    st.caption(f"Autorizado por: {rev}")
                else:
                    st.error(f"❌ NO APLICA — Nivel: {res.nivel if res.nivel else ''}")
                    df_dc = leer_decisiones()
                    if not df_dc.empty:
                        match = df_dc[df_dc["nombre_titulo"].str.upper().str.strip() == tu]
                        if not match.empty:
                            rm = match.iloc[-1]
                            mot = str(rm.get("motivo","")).strip(); rev = str(rm.get("revisor","")).strip()
                            ap  = str(rm.get("decision_aplica","")).strip()
                            niv = str(rm.get("nivel_confirmado","")).strip()
                            ap_bool = ap.lower() in ["true","1","si"]
                            if not ap_bool and mot and mot.lower() not in ["nan","none",""]:
                                st.markdown("---"); st.markdown("### Informacion del Back Office")
                                ca,cb = st.columns(2)
                                ca.markdown(f"**Aplica:** NO")
                                cb.markdown(f"**Nivel:** {niv}")
                                st.info(f"💬 Observacion del Back Office: {mot}")
                                if rev and rev.lower() not in ["nan","none",""]:
                                    st.caption(f"Autorizado por: {rev}")
    with tab2:
        st.markdown("### Solicitar validacion al Back")
        with st.form("form_sol"):
            sn=st.text_input("Tu nombre *"); st2=st.text_input("Titulo a validar *", value=titulo_input if titulo_input else "")
            su=st.text_input("Universidad"); sp=st.selectbox("Pais",["Colombia","Venezuela","Ecuador","Peru","Otro"])
            ss=st.text_area("Notas",height=60); sd=st.file_uploader("Diploma (opcional)",type=["jpg","jpeg","png","pdf"])
            sbtn=st.form_submit_button("Enviar al Back",type="primary",use_container_width=True)
        if sbtn:
            if not sn.strip() or not st2.strip(): st.error("Nombre y titulo obligatorios.")
            else:
                df_ck = leer_solicitudes(); tn = st2.strip().upper()
                ya = False
                if not df_ck.empty and "estado" in df_ck.columns:
                    tp = df_ck[df_ck["estado"]=="PENDIENTE"].get("titulo",pd.Series([])).str.upper().str.strip()
                    ya = tp.str.contains(tn[:20],na=False).any()
                if ya:
                    st.warning(f"El titulo {tn} ya esta PENDIENTE. No es necesario enviarlo de nuevo.")
                else:
                    dp=""
                    if sd:
                        ext=Path(sd.name).suffix; fn=f"{uuid.uuid4().hex[:8]}{ext}"; (DIPLOMAS_DIR/fn).write_bytes(sd.read()); dp=fn
                    sid=guardar_solicitud(sn,st2,su,sp,dp,ss); st.cache_data.clear(); st.success(f"Solicitud #{sid} enviada.")

elif pagina == "Ingresar diploma":
    st.title("Ingresar diploma")
    with st.form("form_dip"):
        dn=st.text_input("Tu nombre *"); dt=st.text_input("Titulo *"); du=st.text_input("Universidad")
        dpais=st.selectbox("Pais",["Colombia","Venezuela","Ecuador","Peru","Otro"])
        df2=st.file_uploader("Diploma *",type=["jpg","jpeg","png","pdf"]); dnotas=st.text_area("Observaciones",height=60)
        dsub=st.form_submit_button("Cargar diploma",type="primary",use_container_width=True)
    if dsub:
        if not dn.strip() or not dt.strip() or not df2: st.error("Nombre, titulo y archivo obligatorios.")
        else:
            ext=Path(df2.name).suffix; fn=f"{uuid.uuid4().hex[:8]}{ext}"; (DIPLOMAS_DIR/fn).write_bytes(df2.read())
            sid=guardar_solicitud(dn,dt,du,dpais,fn,dnotas); st.cache_data.clear(); st.success(f"Diploma cargado. Solicitud #{sid} enviada.")

elif pagina == "Revision Back":
    st.markdown("## Revision Back")
    df_sol=leer_solicitudes(); pend=df_sol[df_sol["estado"]=="PENDIENTE"] if not df_sol.empty else pd.DataFrame()
    if pend.empty: st.success("No hay solicitudes pendientes.")
    else:
        st.info(f"{len(pend)} solicitud(es) esperando decision.")
        for _,row in pend.iterrows():
            td=row.get("titulo",row.get("nombre_titulo","Sin titulo")); nd=row.get("nombre",row.get("asesor",""))
            with st.expander(f"#{row['id']} - {td} - {nd} - {row['fecha']}"):
                cd,cf=st.columns([1,1])
                with cd:
                    st.markdown("**Documento adjunto**")
                    _dp_val=str(row.get("diploma_path","")).strip()
                    dp=DIPLOMAS_DIR/_dp_val if _dp_val and _dp_val.lower() not in ["nan","none",""] else None
                    if dp and dp.exists():
                        if dp.suffix.lower() in [".jpg",".jpeg",".png"]: st.image(str(dp),use_container_width=True)
                        else:
                            with open(dp,"rb") as f: st.download_button("Descargar PDF",f.read(),file_name=dp.name)
                    else: st.caption("Sin documento.")
                with cf:
                    with st.form(f"fb_{row['id']}"):
                        bt=st.text_input("Titulo",value=td); bu=st.text_input("Universidad",value=str(row.get("universidad","")))
                        bp=st.text_input("Pais",value=str(row.get("pais","Colombia")))
                        ba=st.radio("Aplica?",["Si","No"],horizontal=True,key=f"ba_{row['id']}")
                        bn=st.selectbox("Nivel",NIVELES,key=f"bn_{row['id']}")
                        br=st.text_input("Revisor",key=f"br_{row['id']}")
                        bm=st.text_area("Observacion del Back Office",height=80,key=f"bm_{row['id']}")
                        bi=st.checkbox("Incorporar a base",value=True,key=f"bi_{row['id']}")
                        bs=st.form_submit_button("Guardar decision",type="primary",use_container_width=True)
                    if bs and bt.strip():
                        av=(ba=="Si")
                        motor.guardar_decision(titulo=bt.strip().upper(),universidad=bu.strip().upper(),pais=bp,aplica=av,nivel=bn,revisor=br.strip(),motivo=bm.strip().replace(",",""),incorporar=bi)
                        actualizar_estado_solicitud(row["id"],"APROBADA" if av else "RECHAZADA")
                        if bi: get_motor.clear()
                        st.cache_data.clear(); st.success("Decision guardada."); st.rerun()
    st.divider(); st.markdown("### Historial decisiones Back")
    if CSV_DECISIONES.exists():
        dfd=pd.read_csv(CSV_DECISIONES)
        if not dfd.empty:
            st.dataframe(dfd,use_container_width=True,hide_index=True)
            op=["-- Seleccionar --"]+[f"Fila {i}: {r.get('nombre_titulo','')[:35]}" for i,r in dfd.iterrows()]
            se=st.selectbox("Fila a eliminar:",op,key="sel_e")
            if se!="-- Seleccionar --":
                fn=int(se.split(":")[0].replace("Fila","").strip())
                if st.button("Confirmar eliminacion",type="primary",key="btn_e"):
                    d2=dfd.drop(index=fn).reset_index(drop=True)
                    if escribir_github("decisiones_back.csv",d2.to_csv(index=False),f"Eliminar fila {fn}"):
                        st.success("Eliminado."); st.cache_data.clear(); st.rerun()
        else: st.info("Sin decisiones.")
    else: st.info("Sin decisiones.")
    st.divider(); st.markdown("### Editar decision existente")
    if CSV_DECISIONES.exists():
        dfe=pd.read_csv(CSV_DECISIONES)
        if not dfe.empty:
            ope=["-- Seleccionar --"]+[f"Fila {i}: {r.get('nombre_titulo','')[:35]} — {r.get('universidad','')}" for i,r in dfe.iterrows()]
            see=st.selectbox("Decision a editar:",ope,key="sel_ed")
            if see!="-- Seleccionar --":
                fe=int(see.split(":")[0].replace("Fila","").strip()); re=dfe.iloc[fe]
                with st.form(f"fe_{fe}"):
                    et=st.text_input("Titulo",value=str(re.get("nombre_titulo","")))
                    eu=st.text_input("Universidad",value=str(re.get("universidad","")))
                    ea=st.radio("Aplica?",["Si","No"],horizontal=True,index=0 if str(re.get("decision_aplica","")).lower() in ["true","1","si"] else 1,key="eaa")
                    en=st.selectbox("Nivel",NIVELES,index=NIVELES.index(re.get("nivel_confirmado","tecnico")) if re.get("nivel_confirmado","tecnico") in NIVELES else 0,key="enn")
                    er=st.text_input("Revisor",value=str(re.get("revisor","")),key="err")
                    em=st.text_area("Observacion",value=str(re.get("motivo","")),height=80,key="emm")
                    esb=st.form_submit_button("Guardar cambios",use_container_width=True,type="primary")
                if esb and et.strip():
                    dfe.at[fe,"nombre_titulo"]=et.strip().upper(); dfe.at[fe,"universidad"]=eu.strip().upper()
                    dfe.at[fe,"decision_aplica"]=(ea=="Si"); dfe.at[fe,"nivel_confirmado"]=en
                    dfe.at[fe,"revisor"]=er.strip(); dfe.at[fe,"motivo"]=em.strip().replace(",","")
                    if escribir_github("decisiones_back.csv",dfe.to_csv(index=False),f"Editar fila {fe}"):
                        st.success("Actualizado."); st.cache_data.clear(); st.rerun()
        else: st.info("Sin decisiones para editar.")
    else: st.info("Sin decisiones para editar.")

elif pagina == "Cargar datos":
    st.title("Cargar datos")
    arch=st.file_uploader("CSV de titulos",type=["csv"])
    if arch:
        try:
            try:
                dfn=pd.read_csv(arch); st.dataframe(dfn.head(10),use_container_width=True)
            except UnicodeDecodeError:
                arch.seek(0)
                dfn=pd.read_csv(arch, encoding='latin-1'); st.dataframe(dfn.head(10),use_container_width=True)
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

elif pagina == "Historial":
    st.title("Historial de validaciones")
    dfh=leer_decisiones()
    if dfh.empty: st.info("Sin decisiones registradas.")
    else:
        bus=st.text_input("Buscar titulo o universidad")
        if bus.strip(): dfh=dfh[dfh.apply(lambda r: bus.upper() in str(r).upper(),axis=1)]
        st.dataframe(dfh,use_container_width=True,hide_index=True); st.caption(f"Total: {len(dfh)}")

elif pagina == "Dashboard":
    st.title("Dashboard — ValidaTitulos")
    dfd=leer_decisiones(); dfs=leer_solicitudes()
    dfb=pd.read_csv(CSV_TITULOS) if CSV_TITULOS.exists() else pd.DataFrame()
    c1,c2,c3,c4=st.columns(4)
    td=len(dfd); an=int(dfd["decision_aplica"].astype(str).str.lower().isin(["true","1","si"]).sum()) if not dfd.empty and "decision_aplica" in dfd.columns else 0
    c1.metric("Titulos en base",len(dfb)); c2.metric("Decisiones Back",td); c3.metric("Aplican",an); c4.metric("No aplican",td-an)
    if an+td-an>0: st.progress(an/td if td>0 else 0, text=f"{round(an/td*100,1) if td>0 else 0}% aplican")
    if not dfd.empty:
        st.divider(); ca,cb=st.columns(2)
        with ca:
            st.markdown("**Titulos mas consultados**"); top=dfd["nombre_titulo"].value_counts().head(10).reset_index()
            top.columns=["Titulo","Decisiones"]; st.dataframe(top,use_container_width=True,hide_index=True)
        with cb:
            st.markdown("**Decisiones por universidad**")
            if "universidad" in dfd.columns:
                unv=dfd["universidad"].value_counts().head(10).reset_index(); unv.columns=["Universidad","Decisiones"]
                st.dataframe(unv,use_container_width=True,hide_index=True)
        st.divider(); st.markdown("**Medicion del Back por revisor**")
        if "revisor" in dfd.columns:
            rv=dfd["revisor"].value_counts().reset_index(); rv.columns=["Revisor","Decisiones"]
            st.dataframe(rv,use_container_width=True,hide_index=True)
        st.divider(); st.markdown("**Decisiones por fecha**")
        if "fecha" in dfd.columns:
            dfd["fdia"]=pd.to_datetime(dfd["fecha"],errors="coerce").dt.date
            pf=dfd.groupby("fdia").size().reset_index(name="Decisiones"); st.bar_chart(pf.set_index("fdia"))
        st.divider(); st.markdown("**Decisiones por nivel**")
        if "nivel_confirmado" in dfd.columns:
            nv=dfd["nivel_confirmado"].value_counts().reset_index(); nv.columns=["Nivel","Cantidad"]
            st.dataframe(nv,use_container_width=True,hide_index=True)
    else: st.info("El dashboard se llenara cuando el Back procese solicitudes.")
    if not dfs.empty:
        st.divider(); est=dfs["estado"].value_counts().reset_index(); est.columns=["Estado","Cantidad"]
        st.markdown("**Solicitudes por estado**"); st.dataframe(est,use_container_width=True,hide_index=True)
        cn="nombre" if "nombre" in dfs.columns else "asesor" if "asesor" in dfs.columns else None
        if cn:
            st.markdown("**Asesores con mas solicitudes**")
            ase=dfs[cn].value_counts().head(10).reset_index(); ase.columns=["Asesor","Solicitudes"]
            st.dataframe(ase,use_container_width=True,hide_index=True)

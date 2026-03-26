"""
app.py — ValidaTitulos · Interfaz Streamlit
============================================
Ejecutar:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import uuid, shutil
from datetime import datetime, timezone

from validador import ValidadorCSV, CSV_TITULOS, CSV_DECISIONES

BASE_DIR = Path(__file__).parent
CSV_SOLICITUDES = BASE_DIR / "solicitudes_pendientes.csv"
DIPLOMAS_DIR = BASE_DIR / "diplomas"
DIPLOMAS_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="ValidaTitulos", page_icon="📋", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
[data-testid="stSidebar"] { background-color: #1a1a1a !important; }
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
.res-ok { background:#0d2b1a; border:1px solid #1d7a40; border-radius:8px; padding:1rem 1.25rem; margin:.5rem 0; }
.res-no { background:#2b0d0d; border:1px solid #7a1a1a; border-radius:8px; padding:1rem 1.25rem; margin:.5rem 0; }
.res-rev { background:#2b220d; border:1px solid #8a6a10; border-radius:8px; padding:1rem 1.25rem; margin:.5rem 0; }
.badge-ok { background:#1d7a40; color:#d4f5e2; padding:3px 10px; border-radius:4px; font-size:13px; font-weight:600; }
.badge-no { background:#7a1a1a; color:#f5d4d4; padding:3px 10px; border-radius:4px; font-size:13px; font-weight:600; }
.badge-rev { background:#8a6a10; color:#f5e8c0; padding:3px 10px; border-radius:4px; font-size:13px; font-weight:600; }
.barra-bg { background:#333; border-radius:4px; height:8px; margin:.5rem 0; }
.btn-pendiente { background:#c47b00 !important; color:#fff !important; font-weight:700 !important; border:none !important; border-radius:6px; padding:8px 0; text-align:center; width:100%; display:block; margin-bottom:.75rem; }
</Style>
""", unsafe_allow_html=True)

def leer_solicitudes():
    if CSV_SOLICITUDES.exists():
        try: return pd.read_csv(CSV_SOLICITUDES, dtype=str).fillna("")
        except: pass
    return pd.DataFrame(columns=["id","fecha","nombre","titulo","universidad","pais","estado","diploma_path","notas"])

def guardar_solicitud(nombre, titulo, universidad, pais, diploma_path, notas=""):
    df = leer_solicitudes()
    nueva = {"id":str(uuid.uuid4())[:8].upper(), "fecha":datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "nombre":nombre.strip().upper(), "titulo":titulo.strip().upper(), "universidad":universidad.strip().upper(), "pais":pais, "estado":"PENDIENTE", "diploma_path":str(diploma_path) if diploma_path else "", "notas":notas}
    df = pd.concat([df, pd.DataFrame([nueva])], ignore_index=True)
    df.to_csv(CSW_SOLICITUDES, index=False)
    return nueva["id"]

def actualizar_estado_solicitud(sol_id, nuevo_estado):
    df = leer_solicitudes()
    df.loc[df["id"] == sol_id, "estado"] = nuevo_estado
    df.to_csv(CSW_SOLICITUDES, index=False)

@st.cache_resource
def get_motor(): return ValidadorCSV()

with st.sidebar:
    st.markdown("## ValidaTitulos")
    st.caption("Sistema de uso interno")
    df_sol = leer_solicitudes()
    n_pend = len(df_sol[df_sol["estado"]=="PENDIENTE"]) if not df_sol.empty else 0
    if n_pend: st.markdown(f"<div class='btn-pendiente'>PENDIENTES BACK: {n_pend}</div>", unsafe_allow_html=True)
    pagina = st.radio("", ["Validar titulo","Ingresar diploma","Revision Back","Cargar datos","Historial","Dashboard"], label_visibility="collapsed")
    st.divider()
    if CSV_TITULOS.exists():
        dft = pd.read_csv(CSV_TITULO)
        ap = dft["aplica"].astype(str).str.lower().isin(["true","1","si","yes"]).sum() if "aplica" in dft.columns else 0
        st.metric("Registros totales", len(dft)); st.metric("Aplican", int(ap))
    consultas = 0
    if CSV_DECISIONES.exists():
        try: consultas = len(pd.read_csv(CSW_DECISIONES))
        except: pass
    st.metric("Consultas totales", consultas)
    st.divider()
    if st.button("Recargar base", use_container_width=True): get_motor.clear(); st.rerun()

if pagina == "Validar titulo":
    st.markdown("## Validar título académico")
    df_sol = leer_solicitudes()
    n_p = len(df_sol[df_sol["estado"]=="PENDIENTE"]) if not df_sol.empty else 0
    if n_p: st.warning(f"El Back tiene {n_p} solicitud(es) pendiente(s) por aprobar.")
    tab_con, tab_sol = st.tabs(["Consultar título", "Solicitar validacion al Back"])
    with tab_con:
        st.info("Ingresa el titulo para verificar si ya existe decision del Back.")
        c1, c2 = st.columns([3,2])
        ti = c1.text_input("Nombre del título *", placeholder="Ej: Tecnologo en Mercadotecnia")
        uu = c2.text_input("Universidad (opcional)", placeholder="Ej: SENA")
        if st.button("Consultar", use_container_width=True, type="primary"):
            if not ti.strip(): st.warning("Ingresa el nombre.")
            else:
                tu = ti.strip().upper(); uu2 = uu.strip().upper()
                r = get_motor().validar(tu, uu2, "Colombia")
                st.session_state.update({"prefill_titulo":tu,"prefill_univ":uu2})
                if r.requiere_revision: css,bc,ico,est,cb="res-rev","badge-rev","⚠️","REQUIERE REVISION BACK","#8a6a10"
                elif r.aplica: css,bc,ico,est,cb="res-ok","badge-ok","✅","APLICA","#1d7a40"
                else: css,bc,ico,est,cb="res-no","badge-no","❌","NO APLICA","#7a1a1a"
                st.markdown(f"<div class={css}><span class={bc}>{ico} {est}</span><p style='margin:.75rem 0 .25rem;font-size:15px'><b>Título:</b> {tu}<br><b>Nivel:</b> {r.nivel or 'No determinado'}</p><div class=barra-bg><div style='width:{r.confianza_pct}%;background:{cb};height:8px;border-radius:4px'></div></div><p style='font-size:12px;opacity:.75'>{r.confianza_pct}% - {r.metodo}</p><p style='font-size:13px;opacity:.85'>{r.razon}</p></div>", unsafe_allow_html=True)
                if r.requiere_revision: st.info("Ve a Ingresar diploma para enviar con documento adjunto.")
    with tab_sol:
        st.info("Envía el título al Back con el diploma adjunto.")
        ns = st.text_input("Nombre solicitante *", placeholder="Juan Pérez")
        c3, c4 = st.columns([3,2])
        ts = c3.text_input("Título *", value=st.session_state.get("prefill_titulo",""), placeholder="TECNOLOGO EN MERCADEO")
        us = c4.text_input("Universidad", value=st.session_state.get("prefill_univ",""), placeholder="SENA")
        ps = st.selectbox("País", ["Colombia","México","Argentina","Chile","Perú","Ecuador","Venezuela","España","Otro"], key="ps_sol")
        ds = st.file_uploader("Diploma o acta (PDF,JPG,PNG) *", type=["pdf","png","jpg","jpeg"], key="du_sol")
        nts = st.text_area("Notas", height=70, key="nt_sol")
        if st.button("Enviar al Back", use_container_width=True, type="primary", key="btn_sol"):
            if not ns.strip() or not ts.strip(): st.error("Nombre y título obligatorios.")
            elif ds is None: st.error("Adjunta el diploma.")
            else:
                ext=Path(ds.name).suffix; fn=f"{str(uuid.uuid4())[:8]}{ext}"
                (DIPLOMAS_DIR/fn).write_bytes(ds.read())
                sid=guardar_solicitud(ns,ts,us,ps,fn,nts)
                st.success(f"✅ Solicitud #{sid} enviada.")
                st.session_state.pop("prefill_titulo",None); st.session_state.pop("prefill_univ",None)

elif pagina == "Ingresar diploma":
    st.markdown("## Ingresar diploma")
    st.info("Registra un diploma y adjunta el archivo para revisión del Back.")
    nd = st.text_input("Nombre solicitante *", placeholder="María López")
    c1d,c2d = st.columns([3,2])
    td = c1d.text_input("Título *", placeholder="TECNOLOGA EN CONTABILIDAD")
    ud = c2d.text_input("Universidad", placeholder="SENA")
    pd2 = st.selectbox("País", ["Colombia","México","Argentina","Chile","Perú","Ecuador","Venezuela","España","Otro"], key="pd2")
    dd = st.file_uploader("Diploma/Acta (PDF,JPG,PNG) *", type=["pdf","png","jpg","jpeg"], key="dd_up")
    notasd = st.text_area("Notas", height=70, key="notasd")
    if dd:
        st.markdown("**Vista previa:**")
        if dd.type.startswith("image"): st.image(dd, use_container_width=True)
        else: st.info(f"PDF: {dd.name} ({dd.size:,} bytes)")
    if st.button("Ingresar y enviar al Back", use_container_width=True, type="primary", key="btn_dip"):
        if not nd.strip() or not td.strip(): st.error("Nombre y título obligatorios.")
        elif dd is None: st.error("Adjunta el diploma.")
        else:
            dd.seek(0); ext=Path(dd.name).suffix; fn=f"{str(uuid.uuid4())[:8]}{ext}"
            (DIPLOMAS_DIR/fn).write_bytes(dd.read())
            sid=guardar_solicitud(nd,td,ud,pd2,fn,notasd)
            st.success(f"✅ Diploma ingresado. Solicitud #{sid}.")

elif pagina == "Revision Back":
    st.markdown("## Revisión Back")
    st.caption("Solicitudes pendientes de aprobación manual.")
    df_sol = leer_solicitudes()
    pend = df_sol[df_sol["estado"]=="PENDIENTE"] if not df_sol.empty else pd.DataFrame()
    if pend.empty: st.success("No hay solicitudes pendientes.")
    else:
        st.info(f"**{len(pend)} solicitud(es)** esperando decisión.")
        for _, row in pend.iterrows():
            with st.expander(f"#{row['id']} - {row['titulo']} - {row['nombre']}"):
                cd, cf = st.columns([1,1])
                with cd:
                    st.markdown("**Documento adjunto**")
                    dp = DIPLOMAS_DIR / row["diploma_path"] if row["diploma_path"] else None
                    if dp and dp.exists():
                        ext = dp.suffix.lower()
                        if ext in [".jpg",".jpeg",".png",".webp"]: st.image(str(dp), use_container_width=True)
                        elif ext==".pdf":
                            st.download_button(f"Descargar PDF - {rou['diploma_path']}", data=open(dp,"rb").read(), file_name=row["diploma_path"], mime="application/pdf", use_container_width=True)
                    else: st.warning("Sin documento adjunto.")
                    st.markdown("---"); st.markdown(f"**Solicitante:** {row['nombre']}"); st.markdown(f"**País:** {row['pais']}")
                    if row.get("notas"): st.markdown(f"**Notas:** {row['notas']}")
                with cf:
                    st.markdown("**Registrar decisión**")
                    with st.form(f"form_back_{row['id']}"):
                        bt=st.text_input("Título revisado",value=row["titulo"])
                        bu=st.text_input("Universidad",value=row["universidad"])
                        PB=["Colombia","México","Argentina","Chile","Perú","Ecuador","Venezuela","España","Otro"]
                        bp=st.selectbox("País",PB,index=PB.index(row["pais"]) if row["pais"] in PB else 0)
                        ba=st.radio("¿Aplica?",["Sí","No"],horizontal=True)
                        bn=st.selectbox("Nivel",["universitario","maestria","especializacion","doctorado","tecnologo","tecnico","bachillerato"])
                        br=st.text_input("Revisor",placeholder="Nombre analista")
                        bm=st.text_area("Motivo",height=80)
                        bi=st.checkbox("Incorporar a la base",value=True)
                        bs=st.form_submit_button("Guardar decisión",use_container_width=True,type="primary")
                    if bs and bt.strip():
                        get_motor().guardar_decision(titulo=bt.strip().upper(),universidad=bu.strip().upper(),pais=bp,aplica=(ba=="Sí"),nivel=bn,revisor=br,semestre=None,motivo=bm,incorporar=bi)
                        actualizar_estado_solicitud(row["id"],"APROBADA" if ba=="Sí" else "RECHAZADA")
                        if bi: get_motor.clear()
                        st.success(f"✅ Decisión guardada."); st.rerun()
    st.divider()
    st.markdown("### Historial decisiones Back")
    if CSV_DECISIONES.exists():
        dfd=pd.read_csv(CSW_DECISIONES)
        if not dfd.empty: st.dataframe(dfd,use_container_width=True,hide_index=True)
        else: st.info("Sin decisiones.")
    else: st.info("Sin decisiones.")

elif pagina == "Cargar datos":
    st.markdown("## Cargar datos")
    st.info("Importa CSV con títulos de referencia.")
    st.download_button("Descargar plantilla", pd.DataFrame([{"nombre_titulo":"ADMINISTRACION DE EMPRESAS","universidad":"UNIVERSIDAD NACIONAL","pais":"Colombia","aplica":"true","nivel":"universitario"}]).to_csv(index=False).encode("utf-8"),"plantilla.csv","text/csv")
    archivo = st.file_uploader("CSV", type=["csv"])
    if archivo:
        try: dfn=pd.read_csv(archivo,dtype=str).fillna("")
        except Exception as e: st.error(f"Error: {e}"); st.stop()
        st.dataframe(dfn.head(10),use_container_width=True,hide_index=True)
        falt={"nombre_titulo","aplica","nivel"}-set(dfn.columns)
        if falt: st.error(f"Faltan: {falt}")
        elif st.button("Importar",use_container_width=True,type="primary"):
            dfn["nombre_titulo"]=dfn["nombre_titulo"].str.upper().str.strip()
            if "universidad" in dfn.columns: dfn["universidad"]=dfn["universidad"].str.upper().str.strip()
            sub=["nombre_titulo","universidad"] if "universidad" in dfn.columns else ["nombre_titulo"]
            dfn=dfn.drop_duplicates(subset=sub)
            if CSV_TITULOS.exists():
                dfb=pd.read_csv(CSV_TITULOS,dtype=str).fillna(""); dfb["nombre_titulo"]=dfb["nombre_titulo"].str.upper().str.strip()
                dfc=pd.concat([dfb,dfn],ignore_index=True).drop_duplicates(subset=sub,keep="last")
            else: dfc=dfn
            dfc.to_csv(CSV_TITULOS,index=False); get_motor.clear()
            st.success(f"✅ {len(dfn)} registros. Base: {len(dfc)} títulos.")

elif pagina == "Historial":
    st.markdown("## Historial de solicitudes")
    dfs=leer_solicitudes()
    if dfs.empty: st.info("Sin solicitudes.")
    else:
        b=st.text_input("Buscar",placeholder="SENA")
        if b.strip(): dfs=dfs[(dfs["nombre"].str.upper().str.contains(b.upper(),na=False))|(dfs["titulo"].str.upper().str.contains(b.upper(),na=False))]
        ef=st.columns(3)[0].selectbox("Estado",["Todos","PENDIENTE","APROBADA","RECHAZADA"])
        if ef!="Todos": dfs=dfs[dfs["estado"]==ef]
        st.dataframe(dfs[["id","fecha","nombre","titulo","universidad","estado"]],use_container_width=True,hide_index=True)
        st.caption(f"{len(dfs)} registros")

elif pagina == "Dashboard":
    st.markdown("### Dashboard")
    cols=st.columns(4); dfs=leer_solicitudes()
    if CSV_TITULOS.exists():
        dft=pd.read_csv(CSV_TITULOS)
        ap=dft["aplica"].astype(str).str.lower().isin(["true","1","si","yes"]).sum() if "aplica" in dft.columns else 0
        cols[0].metric("Títulos", len(dft)); cols[1].metric("Aplican", int(ap)); cols[2].metric("No aplican", len(dft)-int(ap))
    if not dfs.empty:
        cols[3].metric("Solicitudes", len(dfs)); st.divider(); sc=st.columns(3)
        sc[0].metric("Pendientes",len(dfs[dfs["estado"]=="PENDIENTE"]))
        sc[1].metric("Aprobadas",len(dfs[dfs["estado"]=="APROBADA"]))
        sc[2].metric("Rechazadas",len(dfs[dfs["estado"]=="RECHAZADA"]))
    if CSV_DECISIONES.exists():
        dfd=pd.read_csv(CSV_DECISIONES); st.divider(); st.markdown("#### Decisiones del equipo Back")
        if not dfd.empty and "nivel_confirmado" in dfd.columns:
            c=dfd["nivel_confirmado"].value_counts().reset_index(); c.columns=["Nivel","Cantidad"]; st.dataframe(c,use_container_width=True,hide_index=True)
    else: st.info("Sin datos de decisiones Back aún.")

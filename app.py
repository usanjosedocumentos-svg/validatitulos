"""
app.py - Validador de Titulos Academicos
Ejecutar: streamlit run app.py
"""
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import streamlit as st
from validador import ValidadorCSV, SEMESTRE_POR_NIVEL, CSV_DECISIONES, CSV_TITULOS

st.set_page_config(page_title="ValidaTitulos", page_icon="🎓", layout="wide", initial_sidebar_state="expanded")

@st.cache_resource
def get_motor():
    return ValidadorCSV()

motor = get_motor()


def existe_duplicado(nombre: str, nivel: str) -> bool:
    """Retorna True si ya existe ese nombre+nivel en la base (sin importar universidad/pais)."""
    n = nombre.strip().lower()
    nv = nivel.strip().lower()
    if CSV_TITULOS.exists():
        df = pd.read_csv(CSV_TITULOS)
        if not df.empty:
            mask = (
                df["nombre_titulo"].astype(str).str.lower().str.strip() == n
            ) & (
                df["nivel"].astype(str).str.lower().str.strip() == nv
            )
            if mask.any():
                return True
    if CSV_DECISIONES.exists():
        df2 = pd.read_csv(CSV_DECISIONES)
        if not df2.empty and "nivel_confirmado" in df2.columns:
            mask2 = (
                df2["nombre_titulo"].astype(str).str.lower().str.strip() == n
            ) & (
                df2["nivel_confirmado"].astype(str).str.lower().str.strip() == nv
            )
            if mask2.any():
                return True
    return False


with st.sidebar:
    st.markdown(
        "<div style='padding:0.5rem 0 1.2rem'>"
        "<div style='font-size:1.35rem;font-weight:700;color:#fff'>🎓 ValidaTitulos</div>"
        "<div style='font-size:0.72rem;color:#888'>Sistema de uso interno</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    pagina = st.radio(
        "Nav",
        ["📋 Validar titulo", "📋 Revision Back", "📂 Cargar datos", "📊 Historial"],
        label_visibility="collapsed",
    )
    stats = motor.stats()
    st.markdown(
        f"<div style='background:#1a1d2e;border-radius:8px;padding:0.6rem 0.9rem;"
        f"margin-bottom:5px;display:flex;justify-content:space-between'>"
        f"<span style='color:#aaa;font-size:0.78rem'>Total registros</span>"
        f"<span style='color:#fff;font-weight:700'>{stats['total']}</span></div>",
        unsafe_allow_html=True,
    )
    if st.button("🔄 Recargar base", use_container_width=True):
        get_motor.clear()
        st.cache_resource.clear()
        st.rerun()

PAISES  = ["Colombia","Mexico","Argentina","Chile","Peru","Ecuador","Venezuela","Bolivia","Espana","Estados Unidos","Otro"]
NIVELES = ["universitario","maestria","especializacion","doctorado","tecnologo","bachillerato"]


# ─── PAGINA 1: VALIDAR ──────────────────────────────────────────────────────
if pagina == "📋 Validar titulo":
    st.header("📋 Validar titulo academico")
    st.info("Ingresa el titulo del cliente. El Back siempre toma la decision final.")
    with st.form("form_validar", clear_on_submit=False):
        titulo      = st.text_input("Nombre del titulo *", placeholder="Ej: Administracion de Empresas")
        col1, col2  = st.columns(2)
        universidad = col1.text_input("Universidad", placeholder="Ej: Universidad Nacional")
        pais        = col2.selectbox("Pais", PAISES)
        st.file_uploader("Documento soporte (opcional)", type=["pdf","png","jpg","jpeg"])
        submitted   = st.form_submit_button("📋 Validar titulo", use_container_width=True)
    if submitted:
        if not titulo.strip():
            st.error("Por favor ingresa el nombre del titulo.")
        else:
            with st.spinner("Consultando base historica..."):
                r = motor.validar(titulo.strip(), universidad.strip(), pais)
            nivel_txt = (r.nivel or "").capitalize()
            sem_txt   = str(r.semestre) + "°" if r.semestre else "—"
            if r.requiere_revision:
                st.warning(f"⚠️ Requiere revision Back | Confianza: {r.confianza_pct}% | {r.razon}")
                st.session_state["back_titulo"] = titulo.strip()
                st.session_state["back_pre"]    = True
            elif r.aplica:
                st.success(f"✅ Aplica | Nivel: {nivel_txt} | Semestre: {sem_txt} | Confianza: {r.confianza_pct}%")
            else:
                st.error(f"❌ No aplica | Nivel: {nivel_txt} | Confianza: {r.confianza_pct}%")
            st.caption(f"Metodo: {r.metodo} | {r.razon}")
            st.session_state["ultimo_resultado"] = {
                "titulo": titulo.strip(), "universidad": universidad.strip(),
                "pais": pais, "resultado": r,
            }


# ─── PAGINA 2: BACK ──────────────────────────────────────────────────────
elif pagina == "📋 Revision Back":
    st.header("📋 Revision manual — equipo Back")
    st.warning("Solo para el equipo Back. Cada decision guardada mejora el sistema automaticamente.")
    prefill  = st.session_state.get("back_titulo", "")
    ult      = st.session_state.get("ultimo_resultado", {})
    PAISES_B = ["Colombia","Mexico","Argentina","Chile","Peru","Ecuador","Venezuela","Espana","Otro"]

    with st.form("form_back", clear_on_submit=True):
        b_titulo  = st.text_input("Titulo revisado *", value=prefill, placeholder="Nombre exacto del titulo")
        bc1, bc2  = st.columns(2)
        b_univ    = bc1.text_input("Universidad", value=ult.get("universidad", ""))
        idx_pais  = PAISES_B.index(ult.get("pais","Colombia")) if ult.get("pais","Colombia") in PAISES_B else 0
        b_pais    = bc2.selectbox("Pais", PAISES_B, index=idx_pais)
        bd1, bd2  = st.columns(2)
        b_aplica  = bd1.radio("Este titulo aplica?", ["✅ Si, aplica", "❌ No aplica"])
        b_nivel   = bd2.selectbox("Nivel academico confirmado", NIVELES)
        b_revisor = st.text_input("Nombre del revisor", placeholder="Ej: Ana Gomez / Area Back")
        b_motivo  = st.text_area("Observaciones", placeholder="Ej: Verificado con acreditacion CESU.", height=90)
        b_incorp  = st.checkbox(
            "✅ Incorporar a la base de conocimiento", value=True,
            help="Si esta marcado, el titulo se agrega a la base. No se permiten duplicados (mismo nombre + nivel).",
        )
        b_submit  = st.form_submit_button("💾 Guardar decision Back", use_container_width=True)

    if b_submit:
        if not b_titulo.strip():
            st.error("El campo Titulo es obligatorio.")
        elif b_incorp and existe_duplicado(b_titulo.strip(), b_nivel):
            # ── BLOQUEAR DUPLICADO MANUAL ────────────────────────────────
            st.error(
                f"⛔ El titulo **'{b_titulo.strip()}'** ya existe en la base "
                f"con nivel **{b_nivel}**. "
                f"No se permite duplicar (mismo nombre + nivel). "
                f"Si la decision es diferente, desmarca 'Incorporar a la base'."
            )
        else:
            aplica_bool = "Si" in b_aplica
            motor.guardar_decision(
                titulo=b_titulo.strip(), universidad=b_univ.strip(), pais=b_pais,
                aplica=aplica_bool, nivel=b_nivel,
                revisor=b_revisor.strip(), motivo=b_motivo.strip(), incorporar=b_incorp,
            )
            get_motor.clear()
            for k in ("back_titulo","back_pre","ultimo_resultado"):
                st.session_state.pop(k, None)
            decision_txt = "Aplica" if aplica_bool else "No aplica"
            st.success(f"✅ Guardado: '{b_titulo.strip()}' → {decision_txt} · Nivel: {b_nivel}")


# ─── PAGINA 3: CARGAR DATOS ───────────────────────────────────────────────────
elif pagina == "📂 Cargar datos":
    st.header("📂 Cargar base historica de titulos")
    st.info(
        "Sube un CSV con titulos. El sistema detecta duplicados por "
        "**nombre del titulo + nivel** — sin importar universidad ni pais."
    )

    archivo = st.file_uploader("Selecciona tu archivo CSV", type=["csv"], key="csv_uploader")

    if archivo:
        try:
            df_nuevo = pd.read_csv(archivo)
            st.markdown(f"**Vista previa** — {len(df_nuevo)} filas detectadas:")
            st.dataframe(df_nuevo.head(8), use_container_width=True, hide_index=True)

            cols_req  = {"nombre_titulo","aplica","nivel"}
            cols_falt = cols_req - set(df_nuevo.columns)
            if cols_falt:
                st.error(f"Faltan columnas obligatorias: **{', '.join(cols_falt)}**")
            else:
                df_nuevo["_key"] = (
                    df_nuevo["nombre_titulo"].astype(str).str.lower().str.strip()
                    + "||"
                    + df_nuevo["nivel"].astype(str).str.lower().str.strip()
                )

                # Duplicados dentro del archivo nuevo
                dupes_int = df_nuevo[df_nuevo.duplicated(subset=["_key"], keep=False)][
                    ["nombre_titulo","nivel"]].drop_duplicates()

                # Duplicados contra la base existente
                dupes_ext = pd.DataFrame()
                if CSV_TITULOS.exists():
                    df_base = pd.read_csv(CSV_TITULOS)
                    df_base["_key"] = (
                        df_base["nombre_titulo"].astype(str).str.lower().str.strip()
                        + "||"
                        + df_base["nivel"].astype(str).str.lower().str.strip()
                    )
                    dupes_ext = df_nuevo[df_nuevo["_key"].isin(df_base["_key"])][
                        ["nombre_titulo","nivel"]].drop_duplicates()

                hay_dupes = len(dupes_int) > 0 or len(dupes_ext) > 0

                if hay_dupes:
                    st.warning(
                        f"⚠️ Se detectaron titulos duplicados (mismo nombre + nivel). "
                        f"Elige como manejarlos antes de importar."
                    )
                    col_a, col_b = st.columns(2)
                    if len(dupes_int) > 0:
                        col_a.markdown(f"**Duplicados dentro del archivo ({len(dupes_int)}):**")
                        col_a.dataframe(dupes_int.reset_index(drop=True),
                                        use_container_width=True, hide_index=True)
                    if len(dupes_ext) > 0:
                        col_b.markdown(f"**Ya existen en la base ({len(dupes_ext)}):**")
                        col_b.dataframe(dupes_ext.reset_index(drop=True),
                                        use_container_width=True, hide_index=True)

                    opcion = st.radio(
                        "¿Que hacer con los duplicados?",
                        [
                            "✅ Omitir duplicados (conservar los existentes)",
                            "🔄 Reemplazar duplicados (actualizar con los nuevos)",
                            "❌ Cancelar importacion",
                        ],
                        index=0,
                    )
                else:
                    st.success(f"✅ Sin duplicados — {len(df_nuevo)} titulos listos para importar.")
                    opcion = "✅ Omitir duplicados (conservar los existentes)"

                cancelar = "Cancelar" in opcion
                if st.button("✅ Confirmar carga e importar titulos",
                             use_container_width=True, disabled=cancelar):
                    for col in ["universidad","pais","semestre"]:
                        if col not in df_nuevo.columns:
                            df_nuevo[col] = "" if col != "semestre" else 5
                    df_listo = df_nuevo.drop(columns=["_key"], errors="ignore")

                    if CSV_TITULOS.exists():
                        df_base2 = pd.read_csv(CSV_TITULOS)
                        df_merged = pd.concat([df_base2, df_listo], ignore_index=True)
                        keep = "first" if "Omitir" in opcion else "last"
                        df_merged.drop_duplicates(subset=["nombre_titulo","nivel"],
                                                  keep=keep, inplace=True)
                    else:
                        df_merged = df_listo
                        df_merged.drop_duplicates(subset=["nombre_titulo","nivel"],
                                                  keep="last", inplace=True)

                    df_merged.to_csv(CSV_TITULOS, index=False)
                    get_motor.clear()
                    total_d = len(dupes_int) + len(dupes_ext)
                    st.success(
                        f"✅ Importacion completada. "
                        f"Duplicados manejados: {total_d}. "
                        f"Base actualizada: {len(df_merged)} registros unicos."
                    )
                    st.balloons()

        except Exception as e:
            st.error(f"No se pudo leer el archivo: {e}")

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
        "⬇ Descargar plantilla CSV",
        data=plantilla.to_csv(index=False).encode("utf-8"),
        file_name="plantilla_titulos.csv", mime="text/csv", use_container_width=True,
    )


# ─── PAGINA 4: HISTORIAL ──────────────────────────────────────────────────────
elif pagina == "📊 Historial":
    st.header("📊 Historial de decisiones Back")
    if not CSW_DECISIONES.exists():
        st.info("Aun no hay decisiones registradas por el equipo Back.")
    else:
        df      = pd.read_csv(CSW_DECISIONES)
        total   = len(df)
        aplican = (df["decision_aplica"].astype(str).str.lower()
                   .isin(["true","si","1"])).sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total revisiones", total)
        c2.metric("Aprobadas", aplican)
        c3.metric("Rechazadas", total - aplican)
        buscar  = st.text_input("🔎 Buscar por titulo", placeholder="Filtrar...")
        df_show = df.copy()
        if buscar:
            df_show = df_show[df_show["nombre_titulo"].str.contains(buscar, case=False, na=False)]
        st.dataframe(df_show, use_container_width=True, hide_index=True, height=380)
        st.download_button(
            "⬇ Descargar CSV decisiones",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="decisiones_back.csv", mime="text/csv", use_container_width=True,
        )

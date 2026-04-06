"""
validador.py - Motor de validacion con busqueda inteligente
"""
from __future__ import annotations
import re, unicodedata, json, base64, time, io
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from difflib import SequenceMatcher
import pandas as pd
import urllib.request

CSV_DECISIONES = Path(__file__).parent / "decisiones_back.csv"
CSV_TITULOS    = Path(__file__).parent / "titulos.csv"

# ── Normalización ────────────────────────────────────────────────────────────
def normalizar(texto):
    if not isinstance(texto, str): return ""
    texto = unicodedata.normalize('NFD', texto)
    texto = texto.encode('ascii', 'ignore').decode('utf-8')
    texto = texto.lower()
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    return " ".join(texto.split())

def similitud(a, b):
    return SequenceMatcher(None, a, b).ratio()

def _norm(texto: str) -> str:
    return normalizar(texto)

# ── Niveles ──────────────────────────────────────────────────────────────────
SEMESTRE_POR_NIVEL = {
    "doctorado":8,"maestria":7,"especializacion":6,"universitario":5,
    "tecnologo":3,"tecnico":2,"bachillerato":1,
}

# ── Resultado ────────────────────────────────────────────────────────────────
@dataclass
class Resultado:
    aplica: bool
    nivel: Optional[str]
    semestre: Optional[int]
    confianza: float
    requiere_revision: bool
    metodo: str
    match: Optional[str] = None
    razon: str = ""
    revisor: str = ""
    @property
    def confianza_pct(self) -> int: return round(self.confianza * 100)

# ── GitHub ───────────────────────────────────────────────────────────────────
def github_read(token, repo, filename):
    if token and repo:
        try:
            url = f"https://raw.githubusercontent.com/{repo}/main/{filename}"
            req = urllib.request.Request(url, headers={"Authorization": f"token {token}"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return pd.read_csv(io.StringIO(r.read().decode("utf-8","replace")))
        except Exception: pass
    local = Path(__file__).parent / filename
    if local.exists():
        try: return pd.read_csv(local)
        except Exception: pass
    return pd.DataFrame()

def github_write(token, repo, filename, df):
    if not (token and repo):
        (Path(__file__).parent / filename).write_text(df.to_csv(index=False), encoding="utf-8")
        return
    buf = io.StringIO(); df.to_csv(buf, index=False); content = buf.getvalue()
    url = f"https://api.github.com/repos/{repo}/contents/{filename}"
    headers = {"Authorization": f"token {token}", "Content-Type": "application/json"}
    try:
        sha = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=10).read())["sha"]
    except Exception: sha = None
    body = {"message": f"Actualizacion {filename}", "content": base64.b64encode(content.encode()).decode()}
    if sha: body["sha"] = sha
    urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(body).encode(), method="PUT", headers=headers), timeout=15)
    time.sleep(1.0)

# ── Motor ────────────────────────────────────────────────────────────────────
class ValidadorCSV:

    def __init__(self, token="", repo=""):
        self.token = token; self.repo = repo; self._df = pd.DataFrame()
        self.recargar()

    def recargar(self):
        df = github_read(self.token, self.repo, "decisiones_back.csv")
        if df.empty: self._df = pd.DataFrame(); return
        df["_norm"] = df["nombre_titulo"].astype(str).apply(normalizar)
        df["aplica"] = df["decision_aplica"].astype(str).str.lower().isin(["true","1","si","yes"])
        self._df = df

    def buscar_titulo_inteligente(self, titulo_usuario, umbral=0.65):
        """Busca por similitud incluso con errores ortograficos o sin tildes."""
        titulo_norm = normalizar(titulo_usuario)
        mejor = None; mejor_score = 0.0
        for _, row in self._df.iterrows():
            score = similitud(titulo_norm, normalizar(str(row.get("nombre_titulo",""))))
            if score > mejor_score:
                mejor = row; mejor_score = score
        return (mejor, mejor_score) if mejor_score >= umbral else (None, mejor_score)

    def validar(self, titulo: str) -> Resultado:
        tn = normalizar(titulo)
        if self._df.empty:
            return Resultado(False,None,None,0,True,"vacio",razon="Base vacia")

        # 1. Exacto
        fila = self._df[self._df["_norm"] == tn]
        if not fila.empty:
            row = fila.iloc[-1]
            nivel   = str(row.get("nivel_confirmado","")).strip()
            motivo  = str(row.get("motivo","")).strip()
            revisor = str(row.get("revisor","")).strip()
            razon   = motivo if motivo and motivo.lower() not in ["nan","none",""] else "Decision del Back"
            return Resultado(aplica=bool(row["aplica"]),nivel=nivel or None,
                semestre=SEMESTRE_POR_NIVEL.get(nivel),confianza=0.99,
                requiere_revision=False,metodo="back_exacto",
                match=str(row.get("nombre_titulo","")),razon=razon,revisor=revisor)

        # 2. Similitud inteligente
        row_sim, score = self.buscar_titulo_inteligente(titulo, umbral=0.65)
        if row_sim is not None:
            nivel   = str(row_sim.get("nivel_confirmado","")).strip()
            motivo  = str(row_sim.get("motivo","")).strip()
            revisor = str(row_sim.get("revisor","")).strip()
            titulo_encontrado = str(row_sim.get("nombre_titulo",""))
            razon = f"Titulo similar ({round(score*100)}%): {titulo_encontrado}"
            if motivo and motivo.lower() not in ["nan","none",""]:
                razon += f". Obs: {motivo}"
            return Resultado(aplica=bool(row_sim["aplica"]),nivel=nivel or None,
                semestre=SEMESTRE_POR_NIVEL.get(nivel),confianza=round(score,2),
                requiere_revision=False,metodo="similitud",
                match=titulo_encontrado,razon=razon,revisor=revisor)

        # 3. No encontrado
        return Resultado(False,None,None,0.0,True,"no_encontrado",
            razon="No existe registro exacto ni similar en la base del Back")

    def guardar_decision(self, titulo, universidad, pais, aplica,
                         nivel, revisor="", motivo="", incorporar=True):
        df = github_read(self.token, self.repo, "decisiones_back.csv")
        nueva = {"fecha":datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "nombre_titulo":str(titulo).strip().upper(),
            "universidad":str(universidad).strip().upper() if universidad else "",
            "pais":pais,"decision_aplica":str(aplica).lower(),
            "nivel_confirmado":nivel,"semestre":SEMESTRE_POR_NIVEL.get(nivel,""),
            "revisor":str(revisor).strip(),"motivo":str(motivo).strip()}
        if not df.empty and "nombre_titulo" in df.columns:
            df = df[df["nombre_titulo"].astype(str).str.strip().str.upper() != nueva["nombre_titulo"]]
        df = pd.concat([df, pd.DataFrame([nueva])], ignore_index=True)
        CSV_DECISIONES.write_text(df.to_csv(index=False), encoding="utf-8")
        github_write(self.token, self.repo, "decisiones_back.csv", df)
        self.recargar()

    def eliminar_decision(self, nombre_titulo: str) -> bool:
        df = github_read(self.token, self.repo, "decisiones_back.csv")
        if df.empty: return False
        nombre_up = str(nombre_titulo).strip().upper()
        df_nuevo = df[df["nombre_titulo"].astype(str).str.strip().str.upper() != nombre_up].reset_index(drop=True)
        if len(df_nuevo) == len(df): return False
        CSV_DECISIONES.write_text(df_nuevo.to_csv(index=False), encoding="utf-8")
        github_write(self.token, self.repo, "decisiones_back.csv", df_nuevo)
        self.recargar()
        return True

    def editar_decision(self, titulo_original: str, nuevos_datos: dict) -> bool:
        df = github_read(self.token, self.repo, "decisiones_back.csv")
        if df.empty: return False
        mascara = df["nombre_titulo"].astype(str).str.strip().str.upper() == str(titulo_original).strip().upper()
        if not mascara.any(): return False
        ix = df[mascara].index[0]
        for campo, valor in nuevos_datos.items():
            if campo in df.columns: df.at[ix, campo] = valor
        CSV_DECISIONES.write_text(df.to_csv(index=False), encoding="utf-8")
        github_write(self.token, self.repo, "decisiones_back.csv", df)
        self.recargar()
        return True

    def stats(self): return {"total": len(self._df)}
